"""Command context and shared utilities."""

import functools
import logging
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

import click

if TYPE_CHECKING:
    from iris import UI

    from osiris.config import Config
    from osiris.restic import Restic


@dataclass
class CommandContext:
    """
    Common context for all commands.

    Consolidates the repeated pattern of extracting ui/config/logger/restic
    from Click's context object.
    """

    ui: "UI"
    config: "Config"
    logger: logging.Logger
    restic: "Restic"


def get_context(ctx: click.Context) -> CommandContext:
    """
    Extract CommandContext from Click context.

    Usage:
        @click.command()
        @click.pass_context
        def mycommand(ctx):
            c = get_context(ctx)
            c.ui.header("Hello")
            c.logger.info("Doing work")
    """
    from osiris.restic import Restic

    config = ctx.obj["config"]
    return CommandContext(
        ui=ctx.obj["ui"],
        config=config,
        logger=ctx.obj["logger"],
        restic=Restic(config.repository, config.password_file),
    )


def require_force(f):
    """
    Decorator: require --force flag in non-interactive mode.

    Use on commands that are destructive or have side effects.
    The decorated function must have a `force` parameter.

    Usage:
        @click.command()
        @click.option("--force", is_flag=True)
        @click.pass_context
        @require_force
        def backup(ctx, force):
            ...
    """

    @functools.wraps(f)
    def wrapper(ctx, *args, **kwargs):
        ui = ctx.obj["ui"]
        force = kwargs.get("force", False)
        if not ui.interactive and not force:
            ui.error("Non-interactive mode requires --force flag")
            raise SystemExit(1)
        return f(ctx, *args, **kwargs)

    return wrapper


def restic_error_exit(
    ui: "UI",
    logger: logging.Logger,
    e: subprocess.CalledProcessError,
    operation: str,
) -> NoReturn:
    """
    Handle restic CalledProcessError with consistent formatting.

    Usage:
        try:
            result = restic.forget(...)
        except subprocess.CalledProcessError as e:
            restic_error_exit(c.ui, c.logger, e, "Prune")
    """
    stderr = e.stderr.decode() if e.stderr else "unknown error"
    ui.error(f"{operation} failed: {stderr}")
    logger.error(f"{operation} failed: {e}")
    raise SystemExit(1)
