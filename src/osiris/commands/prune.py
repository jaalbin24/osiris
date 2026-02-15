"""Prune command."""

import subprocess

import click

from osiris.context import get_context, require_force


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be removed without doing it",
)
@click.option("--force", is_flag=True, help="Required for non-interactive mode")
@click.pass_context
@require_force
def prune(ctx, dry_run, force):
    """
    Remove old backups per retention policy.

    Applies the retention policy from config.yaml:
    - keep_daily: Keep last N daily backups
    - keep_weekly: Keep last N weekly backups
    - keep_monthly: Keep last N monthly backups

    Snapshots outside the retention window are removed and
    unreferenced data is cleaned up.
    """
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    logger = c.logger
    restic = c.restic

    retention = config.retention

    ui.header("Prune Old Backups")

    # Show retention policy
    ui.info("Retention policy:")
    ui.info(f"  Keep daily:   {retention.keep_daily}")
    ui.info(f"  Keep weekly:  {retention.keep_weekly}")
    ui.info(f"  Keep monthly: {retention.keep_monthly}")
    print()

    # Confirm unless dry-run or --force
    if not dry_run and not force and ui.interactive:
        if not ui.confirm(
            "Apply retention policy and remove old snapshots?", default=False
        ):
            ui.info("Prune cancelled")
            return

    # Run forget with prune
    action = "Simulating" if dry_run else "Applying"
    ui.info(f"{action} retention policy...")
    logger.info(f"Running prune (dry_run={dry_run})")

    try:
        result = restic.forget(
            keep_daily=retention.keep_daily,
            keep_weekly=retention.keep_weekly,
            keep_monthly=retention.keep_monthly,
            prune=not dry_run,  # Only prune data if not dry-run
            dry_run=dry_run,
        )

        removed = result.get("removed", [])
        kept = result.get("kept", 0)

        if dry_run:
            ui.info(f"Would remove {len(removed)} snapshots, keep {kept}")
            if removed:
                ui.info("Snapshots to remove:")
                for snap_id in removed[:10]:  # Show first 10
                    ui.info(f"  {snap_id}")
                if len(removed) > 10:
                    ui.info(f"  ... and {len(removed) - 10} more")
        else:
            if removed:
                ui.success(f"Removed {len(removed)} snapshots, kept {kept}")
                logger.info(f"Pruned {len(removed)} snapshots")
            else:
                ui.info("No snapshots to remove")
                logger.info("Prune complete, no snapshots removed")

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "unknown error"
        ui.error(f"Prune failed: {stderr}")
        logger.error(f"Prune failed: {e}")
        raise SystemExit(1)
