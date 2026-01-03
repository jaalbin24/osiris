"""Change password command."""

import os
import subprocess
from pathlib import Path

import click

from osiris.context import get_context


@click.command()
@click.option("--update-file", is_flag=True, help="Also update the password file")
@click.pass_context
def chpass(ctx, update_file):
    """
    Change repository password.

    This adds a new password to the repository. The old password
    remains valid until explicitly removed.

    Use --update-file to also update /etc/osiris/repo-password
    with the new password.

    After changing the password, you may want to remove the old key
    using 'restic key remove <key-id>' (list keys with 'restic key list').
    """
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    logger = c.logger
    restic = c.restic

    if not ui.interactive:
        ui.error("Password change requires interactive mode")
        raise SystemExit(1)

    ui.header("Change Repository Password")

    # Get new password
    new_password = ui.prompt("Enter new password", mask=True)
    confirm = ui.prompt("Confirm new password", mask=True)

    if new_password != confirm:
        ui.error("Passwords do not match")
        raise SystemExit(1)

    if len(new_password) < 8:
        ui.warning("Password is very short (< 8 characters)")
        if not ui.confirm("Continue anyway?"):
            raise SystemExit(1)

    # Show current keys
    ui.info("Current repository keys:")
    try:
        keys = restic.key_list()
        for key in keys:
            current = " (current)" if key.get("current") else ""
            ui.info(f"  {key.get('id', 'unknown')[:8]}{current}")
    except Exception as e:
        ui.warning(f"Could not list keys: {e}")

    # Add new key
    print()
    ui.info("Adding new key...")
    try:
        key_id = restic.key_add(new_password)
        ui.success(f"Added new key: {key_id}")
        logger.info(f"Added new repository key: {key_id}")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "unknown error"
        ui.error(f"Failed to add key: {stderr}")
        raise SystemExit(1)

    # Update password file if requested
    if update_file:
        password_path = Path(config.password_file)
        try:
            # Write atomically by writing to temp file first
            temp_path = password_path.with_suffix(".new")
            fd = os.open(
                temp_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                mode=0o400,
            )
            with os.fdopen(fd, "w") as f:
                f.write(new_password + "\n")
            temp_path.rename(password_path)
            ui.success(f"Updated password file: {password_path}")
            logger.info(f"Updated password file: {password_path}")
        except Exception as e:
            ui.error(f"Failed to update password file: {e}")
            ui.warning("New key was added but password file not updated")
            ui.hint(f"Manually update {password_path} with the new password")

    # Remind about old key
    print()
    ui.hint("The old password still works. To remove it:")
    ui.hint("  1. Run 'restic -r <repo> key list' to find the old key ID")
    ui.hint("  2. Run 'restic -r <repo> key remove <old-key-id>'")
