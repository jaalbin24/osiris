"""Backup command."""

from datetime import datetime

import click

from osiris.config import PostgresTargetConfig, RsyncTargetConfig
from osiris.context import get_context, require_force
from osiris.results import BackupBatchResult, BackupItemResult
from osiris.ssh import ssh_session
from osiris.utils import format_duration, format_size


@click.command()
@click.option("--target", "-t", help="Backup specific target only")
@click.option(
    "--force",
    is_flag=True,
    help="Proceed without confirmation (required in non-interactive mode)",
)
@click.pass_context
@require_force
def backup(ctx, target, force):
    """Create a new backup of all configured targets."""
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    logger = c.logger
    restic = c.restic

    # Check for stale locks from interrupted backups
    restic.ensure_unlocked(ui, logger)

    # Generate batch ID
    batch_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    ui.header("Creating Backup")
    ui.info(f"Batch ID: {batch_id}")
    logger.info(f"Starting backup batch {batch_id}")

    # Determine which targets to backup
    if target:
        if target not in config.targets:
            ui.error(f"Unknown target: {target}")
            ui.hint(f"Available targets: {', '.join(config.targets.keys())}")
            raise SystemExit(1)
        targets_to_backup = {target: config.targets[target]}
    else:
        targets_to_backup = config.targets

    all_results: list[BackupItemResult] = []

    # Use ssh_session for connection management
    with ssh_session(config, list(targets_to_backup.values())) as ssh:
        target_count = len(targets_to_backup)

        for idx, (target_name, target_config) in enumerate(
            targets_to_backup.items(), 1
        ):
            ui.step(idx, target_count, f"Backing up {target_name}...")
            logger.info(f"[{target_name}] Starting backup")

            # Create target instance from config
            if isinstance(target_config, PostgresTargetConfig | RsyncTargetConfig):
                target_instance = target_config.create_target()
            else:
                ui.warning(f"Unknown target type for {target_name}, skipping")
                continue

            # Perform backup
            try:
                results = target_instance.backup(restic, batch_id, ssh)
                all_results.extend(results)

                # Log individual results
                for result in results:
                    if result.success:
                        size_str = (
                            format_size(result.size_bytes)
                            if result.size_bytes
                            else "unknown size"
                        )
                        duration_str = (
                            format_duration(result.duration_seconds)
                            if result.duration_seconds
                            else ""
                        )
                        ui.success(f"  {result.item} complete ({size_str})")
                        logger.info(
                            f"[{target_name}] Completed: {result.item} "
                            f"({size_str} in {duration_str})"
                        )
                    else:
                        ui.error(f"  {result.item} failed: {result.error}")
                        logger.error(
                            f"[{target_name}] Failed: {result.item} - {result.error}"
                        )

            except Exception as e:
                ui.error(f"  Target backup failed: {e}")
                logger.error(f"[{target_name}] Target backup failed: {e}")
                all_results.append(
                    BackupItemResult(
                        target=target_name,
                        item="(all)",
                        success=False,
                        error=str(e),
                    )
                )

    # Build batch result
    batch_result = BackupBatchResult(batch_id=batch_id, results=all_results)

    # Print summary
    print()  # Blank line before summary
    _print_summary(ui, batch_result)

    # Log final status
    if batch_result.all_succeeded:
        logger.info(f"Backup {batch_id} completed successfully")
        ui.success(f"Backup {batch_id} created successfully")
    elif batch_result.any_succeeded:
        logger.warning(
            f"Backup {batch_id} completed with errors "
            f"({batch_result.failed_count} failed, {batch_result.success_count} succeeded)"
        )
        ui.warning(
            f"Backup completed with errors "
            f"({batch_result.failed_count} failed, {batch_result.success_count} succeeded)"
        )
    else:
        logger.error(f"Backup {batch_id} failed completely")
        ui.error("Backup failed completely")

    # Exit non-zero if any failures
    if not batch_result.all_succeeded:
        raise SystemExit(1)


def _print_summary(ui, batch_result: BackupBatchResult) -> None:
    """Print backup summary table."""
    table = ui.table(["Target", "Item", "Size", "Duration", "Status"])

    total_size = 0
    total_duration = 0.0

    for result in batch_result.results:
        size_str = format_size(result.size_bytes) if result.size_bytes else "-"
        duration_str = (
            format_duration(result.duration_seconds) if result.duration_seconds else "-"
        )
        status = "OK" if result.success else f"FAILED: {result.error}"

        if result.size_bytes:
            total_size += result.size_bytes
        if result.duration_seconds:
            total_duration += result.duration_seconds

        table.add_row(
            result.target,
            result.item,
            size_str,
            duration_str,
            status[:40] + "..." if len(status) > 40 else status,
        )

    table.render()

    # Print totals
    print()
    ui.info(f"Total: {format_size(total_size)} in {format_duration(total_duration)}")
