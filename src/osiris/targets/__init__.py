"""Osiris backup targets."""

from osiris.targets.base import BackupTarget
from osiris.targets.postgres import PostgresTarget
from osiris.targets.rsync import RsyncTarget

__all__ = ["BackupTarget", "PostgresTarget", "RsyncTarget"]
