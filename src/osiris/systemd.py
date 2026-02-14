"""Systemd service and timer management."""

import subprocess
from pathlib import Path

SYSTEMD_DIR = Path("/etc/systemd/system")
SERVICE_NAME = "osiris-backup.service"
TIMER_NAME = "osiris-backup.timer"

SERVICE_CONTENT = """\
[Unit]
Description=Osiris Backup Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/osiris backup --non-interactive --force
User=root

# Logging to journal
StandardOutput=journal
StandardError=journal
SyslogIdentifier=osiris

# Security hardening
ProtectSystem=strict
ReadWritePaths=/backup /var/log/osiris /var/cache/osiris /run/osiris
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""

TIMER_CONTENT = """\
[Unit]
Description=Daily Osiris Backup Timer

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""


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


def install_service() -> None:
    """
    Install systemd service and timer files.

    Raises:
        PermissionError: If not running as root
        RuntimeError: If systemd is not available
    """
    if not is_systemd_available():
        raise RuntimeError("systemd is not available on this system")

    service_path = SYSTEMD_DIR / SERVICE_NAME
    timer_path = SYSTEMD_DIR / TIMER_NAME

    # Write service file
    service_path.write_text(SERVICE_CONTENT)

    # Write timer file
    timer_path.write_text(TIMER_CONTENT)

    # Reload systemd daemon
    subprocess.run(["systemctl", "daemon-reload"], check=True)


def uninstall_service() -> None:
    """
    Remove systemd service and timer files.

    Stops and disables the service first if active.
    """
    if is_active():
        subprocess.run(["systemctl", "stop", TIMER_NAME], check=False)

    if is_enabled():
        subprocess.run(["systemctl", "disable", TIMER_NAME], check=False)

    service_path = SYSTEMD_DIR / SERVICE_NAME
    timer_path = SYSTEMD_DIR / TIMER_NAME

    service_path.unlink(missing_ok=True)
    timer_path.unlink(missing_ok=True)

    subprocess.run(["systemctl", "daemon-reload"], check=True)


def enable_timer() -> None:
    """Enable and start the backup timer."""
    subprocess.run(["systemctl", "enable", TIMER_NAME], check=True)
    subprocess.run(["systemctl", "start", TIMER_NAME], check=True)


def disable_timer() -> None:
    """Stop and disable the backup timer."""
    subprocess.run(["systemctl", "stop", TIMER_NAME], check=True)
    subprocess.run(["systemctl", "disable", TIMER_NAME], check=True)


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
