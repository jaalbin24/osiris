"""Systemd service and timer status queries."""

import subprocess
from pathlib import Path

SYSTEMD_DIR = Path("/lib/systemd/system")
SERVICE_NAME = "osiris-backup.service"
TIMER_NAME = "osiris-backup.timer"


def is_systemd_available() -> bool:
    """Check if systemd is available on this system."""
    return SYSTEMD_DIR.exists() and Path("/run/systemd/system").exists()


def is_installed() -> bool:
    """Check if Osiris service files are installed."""
    return (SYSTEMD_DIR / SERVICE_NAME).exists() and (SYSTEMD_DIR / TIMER_NAME).exists()


def is_enabled() -> bool:
    """Check if the timer is enabled."""
    result = subprocess.run(
        ["systemctl", "is-enabled", TIMER_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def is_active() -> bool:
    """Check if the timer is active."""
    result = subprocess.run(
        ["systemctl", "is-active", TIMER_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def get_timer_status() -> dict:
    """
    Get detailed timer status.

    Returns:
        Dict with keys: enabled, active, next_run, last_run
    """
    status = {
        "enabled": is_enabled(),
        "active": is_active(),
        "next_run": None,
        "last_run": None,
    }

    # Get next run time
    result = subprocess.run(
        ["systemctl", "show", TIMER_NAME, "--property=NextElapseUSecRealtime"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        line = result.stdout.strip()
        if "=" in line:
            value = line.split("=", 1)[1]
            if value and value != "n/a":
                status["next_run"] = value

    # Get last run time
    result = subprocess.run(
        ["systemctl", "show", TIMER_NAME, "--property=LastTriggerUSec"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        line = result.stdout.strip()
        if "=" in line:
            value = line.split("=", 1)[1]
            if value and value != "n/a":
                status["last_run"] = value

    return status
