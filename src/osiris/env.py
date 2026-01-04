"""
Environment detection for Osiris.

This module provides a centralized way to determine the current runtime
environment (production, development, or test). This affects behavior like
file paths, logging verbosity, and other environment-specific settings.

Environment is controlled via the OSIRIS_ENV environment variable:
    - "production" (default): System paths like /etc/osiris/, /var/log/osiris/
    - "development": Paths relative to config file location
    - "test": Paths relative to config file location, optimized for testing

Usage:
    from osiris.env import get_environment, is_production, is_test

    if is_production():
        # Use system paths
        ...
    else:
        # Use local/relative paths
        ...

See docs/environment.md for full documentation.
"""

import os
from typing import Literal

# Valid environment names
Environment = Literal["production", "development", "test"]

# Environment variable name
ENV_VAR = "OSIRIS_ENV"

# Default environment when not specified
DEFAULT_ENV: Environment = "production"

# Valid environment values
VALID_ENVIRONMENTS: set[Environment] = {"production", "development", "test"}


def get_environment() -> Environment:
    """
    Get the current Osiris environment.

    Returns the value of OSIRIS_ENV environment variable, defaulting to
    "production" if not set. Invalid values are treated as "production"
    with a warning.

    Returns:
        One of: "production", "development", "test"
    """
    env = os.environ.get(ENV_VAR, DEFAULT_ENV).lower()

    if env not in VALID_ENVIRONMENTS:
        # Invalid environment - fall back to production for safety
        import warnings

        warnings.warn(
            f"Invalid {ENV_VAR}={env!r}, expected one of {VALID_ENVIRONMENTS}. "
            f"Defaulting to '{DEFAULT_ENV}'.",
            UserWarning,
            stacklevel=2,
        )
        return DEFAULT_ENV

    return env  # type: ignore[return-value]


def is_production() -> bool:
    """Check if running in production environment."""
    return get_environment() == "production"


def is_development() -> bool:
    """Check if running in development environment."""
    return get_environment() == "development"


def is_test() -> bool:
    """Check if running in test environment."""
    return get_environment() == "test"


def is_local() -> bool:
    """
    Check if running in a local (non-production) environment.

    Returns True for both "development" and "test" environments.
    Useful when you want the same behavior for dev and test.
    """
    return get_environment() in ("development", "test")
