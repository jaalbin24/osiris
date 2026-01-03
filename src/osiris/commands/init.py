"""Init command."""

import os
import secrets
import string
from pathlib import Path

import click

from osiris.context import get_context


@click.command()
@click.option(
    "--generate-password",
    is_flag=True,
    help="Generate a random password instead of prompting",
)
@click.pass_context
def init(ctx, generate_password):
    """Initialize the restic repository and create password file."""
    c = get_context(ctx)
    ui = c.ui
    config = c.config
    logger = c.logger
    restic = c.restic

    # Check if repository already exists
    if restic.is_initialized():
        ui.error("Repository already initialized")
        raise SystemExit(1)

    password_path = Path(config.password_file)

    # Check if password file already exists
    if password_path.exists():
        ui.error(f"Password file already exists: {password_path}")
        ui.hint("Remove it first if you want to reinitialize")
        raise SystemExit(1)

    # Get or generate password
    if generate_password:
        # Generate 32-character random password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(32))
        ui.info("Generated random password")
    else:
        if not ui.interactive:
            ui.error("Cannot prompt for password in non-interactive mode")
            ui.hint("Use --generate-password to auto-generate")
            raise SystemExit(1)

        password = ui.prompt("Enter repository password", mask=True)
        confirm = ui.prompt("Confirm password", mask=True)

        if password != confirm:
            ui.error("Passwords do not match")
            raise SystemExit(1)

        if len(password) < 8:
            ui.warning("Password is very short (< 8 characters)")
            if not ui.confirm("Continue anyway?"):
                raise SystemExit(1)

    # Create password file with restricted permissions
    try:
        # Ensure parent directory exists
        password_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file with restricted permissions (before writing)
        # This prevents a race condition where the file is briefly world-readable
        fd = os.open(
            password_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode=0o400,  # Owner read-only
        )
        with os.fdopen(fd, "w") as f:
            # Add trailing newline - restic reads until newline or EOF
            # Having a newline is more standard and avoids potential issues
            f.write(password + "\n")

        ui.success(f"Created password file: {password_path}")
        logger.info(f"Created password file: {password_path}")

    except PermissionError:
        ui.error(f"Permission denied creating: {password_path}")
        ui.hint("Run as root or check directory permissions")
        raise SystemExit(1)
    except FileExistsError:
        ui.error(f"Password file already exists: {password_path}")
        raise SystemExit(1)

    # Initialize restic repository
    try:
        ui.info(f"Initializing repository: {config.repository}")
        restic.init()
        ui.success(f"Initialized repository: {config.repository}")
        logger.info(f"Initialized repository: {config.repository}")
    except Exception as e:
        # Clean up password file on failure
        password_path.unlink(missing_ok=True)
        ui.error(f"Failed to initialize repository: {e}")
        raise SystemExit(1)

    # Show generated password if applicable
    if generate_password:
        print()
        ui.warning("IMPORTANT: Save this password securely!")
        ui.info(f"Password: {password}")
        ui.hint("This is the only time the password will be displayed")

    # Install logrotate config
    _install_logrotate_config(ui, config, logger)

    print()
    ui.success("Initialization complete!")


def _install_logrotate_config(ui, config, logger) -> None:
    """
    Install logrotate configuration for Osiris logs.

    Only installs if:
    - File logging is enabled in config
    - /etc/logrotate.d/ exists (logrotate is installed)
    - Config file doesn't already exist
    """
    logrotate_path = Path("/etc/logrotate.d/osiris")
    logrotate_dir = logrotate_path.parent

    # Skip if file logging is disabled
    if config.logging.file is None:
        ui.info("File logging disabled, skipping logrotate config")
        return

    # Skip if logrotate not installed
    if not logrotate_dir.exists():
        ui.warning("logrotate not installed (/etc/logrotate.d/ not found), skipping")
        return

    # Skip if already exists
    if logrotate_path.exists():
        ui.info("Logrotate config already exists, skipping")
        return

    # Generate config with actual log path from config
    log_path = config.logging.file
    logrotate_content = f"""\
{log_path} {{
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}}
"""

    try:
        logrotate_path.write_text(logrotate_content)
        ui.success(f"Created logrotate config: {logrotate_path}")
        logger.info(f"Created logrotate config: {logrotate_path}")
    except PermissionError:
        ui.warning(
            f"Could not create logrotate config (permission denied): {logrotate_path}"
        )
        ui.hint("Run as root or manually create the logrotate config")
