"""Logging configuration."""

import logging
import sys
from pathlib import Path

from osiris.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Configure logging based on config.

    - File handler: writes to config.file if set
    - Stream handler: writes to stdout/stderr (captured by journald)
    """
    logger = logging.getLogger("osiris")
    logger.setLevel(getattr(logging, config.level.upper()))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    if config.file:
        Path(config.file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if config.journal:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
