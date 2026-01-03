"""Show command."""

import subprocess

import click

from osiris.batch import group_snapshots_by_batch, parse_target_info
from osiris.context import get_context
from osiris.utils import format_age, parse_timestamp


@click.command()
@click.argument("batch_id")
@click.pass_context
def show(ctx, batch_id):
    """
    Show details of a specific backup batch.

    BATCH_ID is the batch identifier (e.g., 20260103-020000)
    """
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    restic = c.restic

    # Get all snapshots and find the batch
    try:
        all_snapshots = restic.snapshots()
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "unknown error"
        ui.error(f"Failed to list snapshots: {stderr}")
        raise SystemExit(1)

    batches = group_snapshots_by_batch(all_snapshots)

    if batch_id not in batches:
        ui.error(f"Batch '{batch_id}' not found")
        ui.hint("Use 'osiris list' to see available batches")
        raise SystemExit(1)

    batch = batches[batch_id]

    # Header
    ui.header(f"Backup: {batch_id}")

    # Summary info
    try:
        created_dt = parse_timestamp(batch.created)
        ui.info(
            f"Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S')} "
            f"({format_age(created_dt)})"
        )
    except (ValueError, AttributeError):
        ui.info(f"Created: {batch.created}")

    # Determine overall status
    expected_targets = set(config.targets.keys())
    actual_targets = set(batch.targets.keys())
    if actual_targets >= expected_targets:
        ui.success("Status: Complete")
    else:
        missing = expected_targets - actual_targets
        ui.warning(f"Status: Partial (missing: {', '.join(missing)})")

    # Snapshot details table
    print()  # Blank line
    table = ui.table(["Target", "Item", "Snapshot", "Time", "Path"])

    for snap in batch.snapshots:
        target_name, item = parse_target_info(snap)
        if target_name is None:
            continue

        snap_time = snap.get("time", "")[:19].replace("T", " ")
        paths = ", ".join(snap.get("paths", []))

        table.add_row(
            target_name,
            item or "(all)",
            snap.get("short_id", snap.get("id", "")[:8]),
            snap_time,
            paths[:40] + "..." if len(paths) > 40 else paths,
        )

    table.render()

    # Show all tags for reference
    print()
    ui.info("Tags:")
    all_tags = set()
    for snap in batch.snapshots:
        all_tags.update(snap.get("tags", []))
    for tag in sorted(all_tags):
        print(f"  {tag}")
