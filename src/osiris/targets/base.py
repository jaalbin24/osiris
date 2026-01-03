"""Abstract base class for backup targets."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from osiris.restic import Restic
    from osiris.results import BackupItemResult
    from osiris.ssh import SSHManager


class BackupTarget(ABC):
    """Abstract base class for backup targets."""

    name: str

    @abstractmethod
    def backup(
        self, restic: "Restic", batch_id: str, ssh: "SSHManager"
    ) -> list["BackupItemResult"]:
        """
        Perform backup, return list of results (one per item).

        Each result indicates success/failure with optional snapshot info.
        """

    @abstractmethod
    def restore(self, restic: "Restic", snapshot_id: str, ssh: "SSHManager") -> None:
        """Restore from snapshot."""

    @abstractmethod
    def check_connectivity(self, ssh: "SSHManager") -> bool:
        """Verify target is reachable."""

    @abstractmethod
    def get_snapshot_items(self) -> list[str]:
        """Return list of items this target backs up (database names, paths, etc.)."""
