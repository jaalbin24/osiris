"""Validate command."""

import subprocess
from pathlib import Path

import click

from osiris.config import PostgresTargetConfig, RsyncTargetConfig
from osiris.context import get_context
from osiris.ssh import SSHManager
from osiris.targets.postgres import PostgresTarget
from osiris.targets.rsync import RsyncTarget


@click.command()
@click.pass_context
def validate(ctx):
    """Validate configuration and connectivity."""
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    restic = c.restic

    errors = []
    warnings = []

    ui.header("Validating Osiris Configuration")

    # 1. Check SSH key file exists
    ui.info("Checking SSH key...")
    ssh_key_path = Path(config.ssh.key_file)
    if not ssh_key_path.exists():
        errors.append(f"SSH key file not found: {config.ssh.key_file}")
        ui.error(f"  SSH key not found: {config.ssh.key_file}")
    else:
        # Check permissions (should be 600 or 400)
        mode = ssh_key_path.stat().st_mode & 0o777
        if mode not in (0o600, 0o400):
            warnings.append(
                f"SSH key has insecure permissions: {oct(mode)} (should be 0600 or 0400)"
            )
            ui.warning(f"  Insecure permissions: {oct(mode)}")
        else:
            ui.success("  SSH key OK")

    # 2. Check password file exists and is readable
    ui.info("Checking password file...")
    password_path = Path(config.password_file)
    if not password_path.exists():
        errors.append(f"Password file not found: {config.password_file}")
        ui.error(f"  Password file not found: {config.password_file}")
    else:
        # Check permissions
        mode = password_path.stat().st_mode & 0o777
        if mode not in (0o600, 0o400):
            warnings.append(
                f"Password file has insecure permissions: {oct(mode)} (should be 0600 or 0400)"
            )
            ui.warning(f"  Insecure permissions: {oct(mode)}")
        else:
            ui.success("  Password file OK")

    # 3. Check repository is accessible
    ui.info("Checking repository...")
    try:
        if not restic.is_initialized():
            errors.append(f"Repository not initialized: {config.repository}")
            ui.error("  Repository not initialized")
        elif restic.is_locked():
            warnings.append("Repository has stale locks")
            ui.warning("  Repository is locked (stale lock detected)")
        else:
            ui.success("  Repository OK")
    except Exception as e:
        errors.append(f"Repository error: {e}")
        ui.error(f"  Repository error: {e}")

    # 4. Check each target is reachable
    ui.info("Checking targets...")
    with SSHManager(config.ssh) as ssh:
        for name, target_config in config.targets.items():
            ui.info(f"  [{name}] Checking connectivity...")

            # Create target instance
            if isinstance(target_config, PostgresTargetConfig):
                target = PostgresTarget(
                    name=name,
                    host=target_config.host,
                    user=target_config.pg_user,
                    databases=target_config.databases,
                    port=target_config.port,
                    ssh_user=target_config.ssh_user,
                    ssh_key_file=target_config.ssh_key_file,
                )
            elif isinstance(target_config, RsyncTargetConfig):
                target = RsyncTarget(
                    name=name,
                    host=target_config.host,
                    path=target_config.path,
                    staging_dir=target_config.staging_dir,
                    ssh_user=target_config.ssh_user,
                    ssh_key_file=target_config.ssh_key_file,
                )
            else:
                ui.warning(f"  [{name}] Unknown target type, skipping")
                continue

            if target.check_connectivity(ssh):
                ui.success(f"  [{name}] OK")
            else:
                errors.append(f"Target '{name}' unreachable: {target_config.host}")
                ui.error(f"  [{name}] Unreachable")

    # 5. Check required tools
    ui.info("Checking required tools...")
    for tool in ["restic", "rsync"]:
        result = subprocess.run(["which", tool], capture_output=True)
        if result.returncode != 0:
            errors.append(f"Required tool not found: {tool}")
            ui.error(f"  {tool}: not found")
        else:
            ui.success(f"  {tool}: OK")

    # Print summary
    print()
    if warnings:
        ui.warning(f"Warnings ({len(warnings)}):")
        for warning in warnings:
            ui.warning(f"  - {warning}")

    print()
    if errors:
        ui.error(f"Errors ({len(errors)}):")
        for error in errors:
            ui.error(f"  - {error}")
        raise SystemExit(1)
    else:
        ui.success("All checks passed")
