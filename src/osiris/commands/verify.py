"""Verify command."""

import click

from osiris.context import get_context


@click.command()
@click.option(
    "--thorough",
    is_flag=True,
    help="Read and verify all data (slow but complete)",
)
@click.pass_context
def verify(ctx, thorough):
    """
    Verify backup repository integrity.

    Runs restic check to verify:
    - Pack files are complete and valid
    - Index is consistent
    - Snapshots reference valid data

    Use --thorough to also read and verify all data blobs.
    This is slow but provides complete verification.
    """
    c = get_context(ctx)
    ui = c.ui
    logger = c.logger
    restic = c.restic

    if thorough:
        ui.header("Verifying Repository (Thorough)")
        ui.warning("This will read ALL data and may take a long time...")
        logger.info("Starting thorough repository verification")
    else:
        ui.header("Verifying Repository")
        logger.info("Starting repository verification")

    # Check for locks first
    if restic.is_locked():
        ui.warning("Repository is locked - verification may fail")
        ui.hint("Run 'osiris unlock' to remove stale locks")

    # Run verification
    ui.info("Running restic check...")
    success, message = restic.check(read_data=thorough)

    if success:
        ui.success("Repository verification passed")
        logger.info("Repository verification passed")
        if message:
            # Show summary stats from restic
            for line in message.split("\n"):
                if line.strip():
                    ui.info(f"  {line.strip()}")
    else:
        ui.error("Repository verification FAILED")
        logger.error(f"Repository verification failed: {message}")
        if message:
            for line in message.split("\n"):
                if line.strip():
                    ui.error(f"  {line.strip()}")
        ui.hint(
            "Repository may be corrupted. Check restic documentation for recovery options."
        )
        raise SystemExit(1)
