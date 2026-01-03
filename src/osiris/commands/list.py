"""List command."""

import subprocess

import click

from osiris.batch import group_snapshots_by_batch
from osiris.context import get_context
from osiris.utils import format_age, parse_timestamp


@click.command("list")
@click.option("--target", "-t", help="Filter by target")
@click.option(
    "--limit", "-n", default=20, help="Number of batches to show (default: 20)"
)
@click.pass_context
def list_cmd(ctx, target, limit):
    """List all backups."""
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    restic = c.restic

    # Get all snapshots
    try:
        all_snapshots = restic.snapshots()
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "unknown error"
        ui.error(f"Failed to list snapshots: {stderr}")
        raise SystemExit(1)

    if not all_snapshots:
        ui.info("No backups found")
        return

    # Group by batch
    batches = group_snapshots_by_batch(all_snapshots)

    if not batches:
        ui.info("No Osiris backups found (snapshots exist but lack osiris: tags)")
        return

    # Build expected targets from config for status comparison
    expected_targets = set(config.targets.keys())

    # Build table data
    table_data = []
    for batch_id, batch_info in batches.items():
        # Filter by target if specified
        if target and target not in batch_info.targets:
            continue

        # Determine status
        actual_targets = set(batch_info.targets.keys())
        if actual_targets >= expected_targets:
            status = "OK"
        elif actual_targets & expected_targets:
            status = "PARTIAL"
        else:
            status = "UNKNOWN"

        # Format targets column: "postgres(2), minio"
        target_parts = []
        for t_name, items in sorted(batch_info.targets.items()):
            if len(items) > 1:
                target_parts.append(f"{t_name}({len(items)})")
            elif len(items) == 1:
                target_parts.append(t_name)
            else:
                target_parts.append(t_name)
        targets_str = ", ".join(target_parts)

        # Parse created timestamp
        try:
            created_dt = parse_timestamp(batch_info.created)
            created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
            age_str = format_age(created_dt)
        except (ValueError, AttributeError):
            created_str = batch_info.created[:19] if batch_info.created else "unknown"
            age_str = "unknown"

        table_data.append(
            {
                "batch_id": batch_id,
                "created": created_str,
                "created_dt": batch_info.created,  # For sorting
                "age": age_str,
                "targets": targets_str,
                "status": status,
            }
        )

    if not table_data:
        if target:
            ui.info(f"No backups found for target '{target}'")
        else:
            ui.info("No backups found")
        return

    # Sort by created timestamp (newest first)
    table_data.sort(key=lambda x: x["created_dt"], reverse=True)

    # Apply limit
    total = len(table_data)
    table_data = table_data[:limit]

    # Render table
    table = ui.table(["Batch-ID", "Created", "Age", "Targets", "Status"])
    for row in table_data:
        table.add_row(
            row["batch_id"],
            row["created"],
            row["age"],
            row["targets"],
            row["status"],
        )
    table.render()

    # Show count if limited
    if len(table_data) < total:
        print()
        ui.info(
            f"Showing {len(table_data)} of {total} batches (use --limit to show more)"
        )
