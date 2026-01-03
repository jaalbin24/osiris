"""Systemd service management commands."""

import subprocess

import click

from osiris import systemd


@click.group()
def service():
    """Manage systemd service and timer."""
    pass


@service.command()
@click.pass_context
def install(ctx):
    """Install systemd service and timer files."""
    ui = ctx.obj["ui"]

    ui.header("Install Systemd Service")

    if not systemd.is_systemd_available():
        ui.error("systemd is not available on this system")
        raise SystemExit(1)

    if systemd.is_installed():
        ui.warning("Service files already exist")
        if ui.interactive:
            if not ui.confirm("Overwrite existing files?"):
                ui.info("Installation cancelled")
                return
        else:
            ui.info("Overwriting existing files (non-interactive mode)")

    try:
        systemd.install_service()
        ui.success(f"Installed {systemd.SERVICE_NAME}")
        ui.success(f"Installed {systemd.TIMER_NAME}")
        print()
        ui.hint("Run 'osiris service enable' to enable scheduled backups")
    except PermissionError:
        ui.error("Permission denied. Run as root.")
        raise SystemExit(1)
    except Exception as e:
        ui.error(f"Installation failed: {e}")
        raise SystemExit(1)


@service.command()
@click.pass_context
def uninstall(ctx):
    """Remove systemd service and timer files."""
    ui = ctx.obj["ui"]

    ui.header("Uninstall Systemd Service")

    if not systemd.is_installed():
        ui.info("Service files not installed")
        return

    if ui.interactive:
        if not ui.confirm("Remove Osiris systemd service and timer?"):
            ui.info("Uninstall cancelled")
            return

    try:
        systemd.uninstall_service()
        ui.success("Removed service and timer files")
    except PermissionError:
        ui.error("Permission denied. Run as root.")
        raise SystemExit(1)
    except Exception as e:
        ui.error(f"Uninstall failed: {e}")
        raise SystemExit(1)


@service.command()
@click.pass_context
def enable(ctx):
    """Enable and start the backup timer."""
    ui = ctx.obj["ui"]

    if not systemd.is_installed():
        ui.error("Service not installed. Run 'osiris service install' first.")
        raise SystemExit(1)

    if systemd.is_active():
        ui.info("Timer is already enabled and active")
        return

    try:
        systemd.enable_timer()
        ui.success("Backup timer enabled and started")

        # Show next run time
        status = systemd.get_timer_status()
        if status["next_run"]:
            ui.info(f"Next backup: {status['next_run']}")
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to enable timer: {e}")
        raise SystemExit(1)


@service.command()
@click.pass_context
def disable(ctx):
    """Stop and disable the backup timer."""
    ui = ctx.obj["ui"]

    if not systemd.is_active() and not systemd.is_enabled():
        ui.info("Timer is already disabled")
        return

    try:
        systemd.disable_timer()
        ui.success("Backup timer stopped and disabled")
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to disable timer: {e}")
        raise SystemExit(1)


@service.command("status")
@click.pass_context
def service_status(ctx):
    """Show systemd service status."""
    ui = ctx.obj["ui"]

    ui.header("Systemd Service Status")

    if not systemd.is_systemd_available():
        ui.warning("systemd is not available on this system")
        return

    if not systemd.is_installed():
        ui.warning("Service not installed")
        ui.hint("Run 'osiris service install' to install")
        return

    status = systemd.get_timer_status()

    # Installation status
    ui.success("Installed: yes")

    # Enabled status
    if status["enabled"]:
        ui.success("Enabled: yes")
    else:
        ui.warning("Enabled: no")

    # Active status
    if status["active"]:
        ui.success("Active: yes")
    else:
        ui.warning("Active: no")

    # Schedule info
    if status["next_run"]:
        ui.info(f"Next run: {status['next_run']}")
    if status["last_run"]:
        ui.info(f"Last run: {status['last_run']}")

    # Show recent logs
    print()
    ui.info("Recent logs:")
    result = subprocess.run(
        ["journalctl", "-u", systemd.SERVICE_NAME, "-n", "5", "--no-pager"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
    else:
        ui.info("  No recent logs")
