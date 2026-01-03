"""Status command."""

import subprocess
from datetime import UTC, datetime

import click

from osiris.batch import group_snapshots_by_batch
from osiris.context import get_context
from osiris.utils import format_age, format_size, parse_timestamp


@click.command()
@click.pass_context
def status(ctx):
    """
    Show overall backup system status.

    Displays:
    - Last successful backup time and age
    - Repository health (locked, size)
    - Target connectivity
    - Next scheduled backup (if timer enabled)
    """
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    restic = c.restic

    ui.header("Osiris Backup Status")

    issues = []

    # 1. Repository status
    ui.info("Repository:")
    try:
        if not restic.is_initialized():
            ui.error("  Not initialized")
            issues.append("Repository not initialized")
        elif restic.is_locked():
            ui.warning("  Initialized (LOCKED - stale lock detected)")
            issues.append("Repository has stale locks")
        else:
            ui.success("  Initialized and accessible")

            # Get repo stats
            try:
                stats = restic.stats()
                total_size = stats.get("total_size", 0)
                ui.info(f"  Size: {format_size(total_size)}")
            except Exception:
                pass  # Stats are optional

    except Exception as e:
        ui.error(f"  Error accessing repository: {e}")
        issues.append(f"Repository error: {e}")

    # 2. Last backup status
    print()
    ui.info("Last Backup:")
    try:
        all_snapshots = restic.snapshots()
        batches = group_snapshots_by_batch(all_snapshots)

        if not batches:
            ui.warning("  No backups found")
            issues.append("No backups exist")
        else:
            # Find most recent batch
            sorted_batches = sorted(
                batches.items(),
                key=lambda x: x[1].created,
                reverse=True,
            )
            latest_id, latest_batch = sorted_batches[0]

            # Parse timestamp
            try:
                created_dt = parse_timestamp(latest_batch.created)
                age = datetime.now(UTC) - created_dt
                age_hours = age.total_seconds() / 3600

                ui.info(f"  Batch: {latest_id}")
                ui.info(
                    f"  Time: {created_dt.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"({format_age(created_dt)})"
                )

                # Check if backup is stale (>25 hours for daily backups)
                if age_hours > 25:
                    ui.warning(f"  Last backup is {int(age_hours)} hours old")
                    issues.append(f"Last backup is {int(age_hours)} hours old")
                else:
                    ui.success("  Recent backup exists")

                # Check completeness
                expected = set(config.targets.keys())
                actual = set(latest_batch.targets.keys())
                if actual >= expected:
                    ui.success("  All targets backed up")
                else:
                    missing = expected - actual
                    ui.warning(f"  Missing targets: {', '.join(missing)}")
                    issues.append(f"Last backup missing: {', '.join(missing)}")

            except (ValueError, AttributeError):
                ui.info(f"  Batch: {latest_id} (could not parse timestamp)")

    except Exception as e:
        ui.error(f"  Error checking backups: {e}")
        issues.append(f"Backup check error: {e}")

    # 3. Systemd timer status
    print()
    ui.info("Scheduled Backups:")
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "osiris-backup.timer"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            ui.success("  Timer: active")

            # Get next run time
            result = subprocess.run(
                [
                    "systemctl",
                    "show",
                    "osiris-backup.timer",
                    "--property=NextElapseUSecRealtime",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                # Parse "NextElapseUSecRealtime=Sat 2026-01-04 02:00:00 UTC"
                line = result.stdout.strip()
                if "=" in line:
                    next_time = line.split("=", 1)[1]
                    if next_time and next_time != "n/a":
                        ui.info(f"  Next run: {next_time}")
        else:
            ui.warning("  Timer: not active")
            ui.hint("  Run 'osiris service enable' to enable scheduled backups")
    except FileNotFoundError:
        ui.info("  Timer: systemd not available")

    # 4. Summary
    print()
    if issues:
        ui.warning(f"Issues detected ({len(issues)}):")
        for issue in issues:
            ui.error(f"  - {issue}")
        raise SystemExit(1)
    else:
        ui.success("All systems operational")
