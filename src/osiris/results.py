"""Backup result types."""

from dataclasses import dataclass


@dataclass
class BackupItemResult:
    """Result of backing up a single item (database, path, etc.)."""

    target: str  # Target name (e.g., "postgres")
    item: str  # Item name (e.g., "kriib" or "/var/lib/minio/data")
    success: bool
    snapshot_id: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None
    error: str | None = None


@dataclass
class BackupBatchResult:
    """Result of a complete backup batch."""

    batch_id: str
    results: list[BackupItemResult]

    @property
    def all_succeeded(self) -> bool:
        """Check if all items succeeded."""
        return all(r.success for r in self.results)

    @property
    def any_succeeded(self) -> bool:
        """Check if any items succeeded."""
        return any(r.success for r in self.results)

    @property
    def failed_count(self) -> int:
        """Count of failed items."""
        return sum(1 for r in self.results if not r.success)

    @property
    def success_count(self) -> int:
        """Count of successful items."""
        return sum(1 for r in self.results if r.success)
