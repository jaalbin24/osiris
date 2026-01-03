"""Unlock command."""

import subprocess

import click

from osiris.context import get_context


@click.command()
@click.option("--force", is_flag=True, help="Remove all locks (use with caution)")
@click.pass_context
def unlock(ctx, force):
    """
    Remove stale repository locks.

    Restic creates locks to prevent concurrent operations. If a backup
    is interrupted (crash, kill, etc.), locks may be left behind.

    This command removes stale locks so new operations can proceed.

    Use --force to remove ALL locks, including potentially active ones.
    Only use this if you're sure no other osiris/restic process is running.
    """
    c = get_context(ctx)
    ui = c.ui
    logger = c.logger
    restic = c.restic

    ui.header("Remove Repository Locks")

    # Check current lock status
    if not restic.is_locked():
        ui.success("Repository is not locked")
        return

    ui.warning("Repository is currently locked")

    if force:
        ui.warning("--force specified: will remove ALL locks")
        if ui.interactive:
            if not ui.confirm(
                "Are you sure? This may corrupt the repository if another process is running."
            ):
                ui.info("Unlock cancelled")
                return
    else:
        ui.info("Removing stale locks...")

    # Remove locks
    try:
        restic.unlock(remove_all=force)
        ui.success("Locks removed successfully")
        logger.info(f"Removed repository locks (force={force})")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "unknown error"
        ui.error(f"Failed to remove locks: {stderr}")
        logger.error(f"Failed to unlock repository: {e}")
        raise SystemExit(1)

    # Verify
    if restic.is_locked():
        ui.warning("Repository is still locked")
        ui.hint(
            "Try 'osiris unlock --force' if you're sure no other process is running"
        )
    else:
        ui.success("Repository is now unlocked")
