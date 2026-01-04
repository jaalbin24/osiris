"""Osiris CLI entry point."""

import click
from iris import UI

from osiris.config import ConfigError, load_config
from osiris.logging import setup_logging


# Commands that can run without a config file
BOOTSTRAP_COMMANDS = {"init"}


@click.group()
@click.option(
    "--config", "-c", default="/etc/osiris/config.yaml", help="Config file path"
)
@click.option("--non-interactive", is_flag=True, help="Disable interactive prompts")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--debug", "-d", is_flag=True, help="Enable debug output")
@click.pass_context
def cli(ctx, config, non_interactive, verbose, debug):
    """Osiris - Backup management for Kriib infrastructure."""
    ctx.ensure_object(dict)

    # Store config path for use by init command
    ctx.obj["config_path"] = config

    # Initialize UI (always needed)
    ctx.obj["ui"] = UI(interactive=not non_interactive, verbose=verbose, debug=debug)

    # Skip config loading for bootstrap commands
    if ctx.invoked_subcommand in BOOTSTRAP_COMMANDS:
        ctx.obj["config"] = None
        ctx.obj["logger"] = None
        return

    # Load configuration for all other commands
    try:
        ctx.obj["config"] = load_config(config)
    except FileNotFoundError as e:
        ctx.obj["ui"].error(str(e))
        ctx.obj["ui"].hint("Run 'osiris init' to initialize the system")
        raise SystemExit(1) from None
    except ConfigError as e:
        ctx.obj["ui"].error(f"Configuration error: {e}")
        raise SystemExit(1) from None

    # Setup logging
    ctx.obj["logger"] = setup_logging(ctx.obj["config"].logging)


# Import and register commands
from osiris.commands.backup import backup
from osiris.commands.chpass import chpass
from osiris.commands.init import init
from osiris.commands.list import list_cmd
from osiris.commands.prune import prune
from osiris.commands.restore import restore
from osiris.commands.service import service
from osiris.commands.show import show
from osiris.commands.status import status
from osiris.commands.unlock import unlock
from osiris.commands.validate import validate
from osiris.commands.verify import verify

cli.add_command(backup)
cli.add_command(restore)
cli.add_command(list_cmd)
cli.add_command(show)
cli.add_command(status)
cli.add_command(verify)
cli.add_command(prune)
cli.add_command(chpass)
cli.add_command(init)
cli.add_command(unlock)
cli.add_command(validate)
cli.add_command(service)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
