"""Restore command."""

import click

from osiris.batch import parse_target_info, resolve_batch
from osiris.config import PostgresTargetConfig, RsyncTargetConfig
from osiris.context import get_context, require_force
from osiris.ssh import SSHManager, register_cleanup, unregister_cleanup
from osiris.targets.postgres import PostgresTarget
from osiris.targets.rsync import RsyncTarget


@click.command()
@click.option(
    "--batch-id",
    "-b",
    required=True,
    help="Batch ID to restore (e.g., 20260103-020000)",
)
@click.option("--target", "-t", help="Restore specific target only")
@click.option("--database", "-d", help="Restore specific database (postgres only)")
@click.option("--force", is_flag=True, help="Required for non-interactive mode")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be restored without doing it"
)
@click.pass_context
@require_force
def restore(ctx, batch_id, target, database, force, dry_run):
    """
    Restore from a backup.

    WARNING: This is a destructive operation!
    - PostgreSQL: Drops and recreates databases
    - Rsync: Overwrites remote files with backup contents
    """
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    logger = c.logger
    restic = c.restic

    # Check for stale locks
    restic.ensure_unlocked(ui, logger)

    # Resolve batch ID to snapshots
    try:
        snapshots = resolve_batch(restic, batch_id, target, database)
    except ValueError as e:
        ui.error(str(e))
        raise SystemExit(1)

    if not snapshots:
        ui.error(f"No snapshots found for batch {batch_id}")
        raise SystemExit(1)

    # Build list of what will be restored
    ui.header("Restore Plan")

    restore_items = []
    for snap in snapshots:
        target_name, item = parse_target_info(snap)
        if target_name is None:
            continue

        target_config = config.targets.get(target_name)
        if target_config is None:
            ui.warning(f"Target '{target_name}' not in current config, skipping")
            continue

        restore_items.append(
            {
                "snapshot": snap,
                "target_name": target_name,
                "target_config": target_config,
                "item": item,
            }
        )

    if not restore_items:
        ui.error("No restorable items found")
        raise SystemExit(1)

    # Show what will be restored
    table = ui.table(["Target", "Item", "Snapshot", "Action"])
    for item in restore_items:
        if item["target_config"].type == "pg_dump":
            action = f"DROP + CREATE database '{item['item']}'"
        else:
            action = f"Overwrite {item['target_config'].path}"

        table.add_row(
            item["target_name"],
            item["item"] or "(all)",
            item["snapshot"].get("short_id", "unknown"),
            action,
        )
    table.render()

    # Dry-run stops here
    if dry_run:
        print()
        ui.info("Dry-run complete. No changes made.")
        return

    # Confirm destructive operation
    print()
    ui.warning("WARNING: This is a destructive operation!")
    if any(i["target_config"].type == "pg_dump" for i in restore_items):
        ui.warning("PostgreSQL databases will be DROPPED and recreated.")
    if any(i["target_config"].type == "rsync" for i in restore_items):
        ui.warning("Remote files will be OVERWRITTEN with backup contents.")

    if not force and ui.interactive:
        print()
        if not ui.confirm("Proceed with restore?", default=False):
            ui.info("Restore cancelled")
            raise SystemExit(0)
    # Non-interactive already checked for --force above

    # Perform restore
    logger.info(f"Starting restore from batch {batch_id}")
    ui.header("Restoring")

    with SSHManager(config.ssh) as ssh:
        register_cleanup(ssh)

        try:
            # Start SSH masters for all target hosts
            for item in restore_items:
                tc = item["target_config"]
                conn = ssh.get_connection(
                    tc.host,
                    getattr(tc, "ssh_user", None),
                    getattr(tc, "ssh_key_file", None),
                )
                ssh.start_master(conn)

            # Perform restores
            failed = []
            succeeded = []

            for i, item in enumerate(restore_items, 1):
                target_name = item["target_name"]
                target_config = item["target_config"]
                snapshot = item["snapshot"]
                item_name = item["item"] or target_config.path

                ui.step(i, len(restore_items), f"Restoring {target_name}: {item_name}")
                logger.info(
                    f"Restoring {target_name}: {item_name} "
                    f"from {snapshot.get('short_id')}"
                )

                try:
                    # Create target instance
                    if isinstance(target_config, PostgresTargetConfig):
                        target_instance = PostgresTarget(
                            name=target_name,
                            host=target_config.host,
                            user=target_config.pg_user,
                            databases=[item["item"]],
                            port=target_config.port,
                            ssh_user=target_config.ssh_user,
                            ssh_key_file=target_config.ssh_key_file,
                        )
                    elif isinstance(target_config, RsyncTargetConfig):
                        target_instance = RsyncTarget(
                            name=target_name,
                            host=target_config.host,
                            path=target_config.path,
                            staging_dir=target_config.staging_dir,
                            ssh_user=target_config.ssh_user,
                            ssh_key_file=target_config.ssh_key_file,
                        )
                    else:
                        ui.warning("Unknown target type, skipping")
                        continue

                    target_instance.restore(restic, snapshot.get("short_id"), ssh)
                    ui.success(f"  {item_name} restored")
                    logger.info(f"Restored {target_name}: {item_name}")
                    succeeded.append(item_name)

                except Exception as e:
                    ui.error(f"  {item_name} failed: {e}")
                    logger.error(f"Failed to restore {target_name}: {item_name}: {e}")
                    failed.append((item_name, str(e)))

        finally:
            unregister_cleanup()

    # Summary
    print()
    ui.header("Restore Summary")
    if succeeded:
        ui.success(f"Restored: {', '.join(succeeded)}")
    if failed:
        ui.error(f"Failed ({len(failed)}):")
        for name, error in failed:
            ui.error(f"  {name}: {error}")

    if failed:
        raise SystemExit(1)
    else:
        logger.info(f"Restore from batch {batch_id} completed successfully")
        ui.success("Restore completed successfully")
