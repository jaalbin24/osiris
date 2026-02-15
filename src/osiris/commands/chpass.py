"""Change password command."""

import os
import subprocess
from pathlib import Path

import click

from osiris.context import get_context


@click.command()
@click.pass_context
def chpass(ctx):
    """
    Change repository password.

    This adds a new password to the repository, updates the password file,
    and removes the old key(s).
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

    # Show current keys and record old key IDs for later removal
    old_key_ids = []
    ui.info("Current repository keys:")
    try:
        keys = restic.key_list()
        for key in keys:
            current = " (current)" if key.get("current") else ""
            key_id = key.get("id", "unknown")
            ui.info(f"  {key_id[:8]}{current}")
            old_key_ids.append(key_id)
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

    # Update password file
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
        return

    # Remove old key(s)
    for old_id in old_key_ids:
        try:
            restic.key_remove(old_id)
            ui.success(f"Removed old key: {old_id[:8]}")
            logger.info(f"Removed old repository key: {old_id}")
        except Exception as e:
            ui.warning(f"Could not remove old key {old_id[:8]}: {e}")
            ui.hint("You may want to remove it manually with 'restic key remove'")
