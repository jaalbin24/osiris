"""Batch ID resolution and grouping utilities."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from osiris.restic import Restic


@dataclass
class BatchInfo:
    """Information about a backup batch."""

    batch_id: str
    snapshots: list[dict]  # Raw restic snapshot dicts
    targets: dict[str, list[str]]  # target_name -> [items]
    created: str  # ISO timestamp of earliest snapshot
    total_size: int  # Sum of all snapshot sizes
    _is_complete: bool = field(default=False, repr=False)

    @property
    def is_complete(self) -> bool:
        """Check if batch has all expected targets (based on config)."""
        return self._is_complete


def parse_batch_id(snapshot: dict) -> str | None:
    """Extract batch ID from snapshot tags, or None if not an Osiris snapshot."""
    for tag in snapshot.get("tags", []):
        if tag.startswith("osiris:"):
            return tag.split(":", 1)[1]
    return None


def parse_target_info(snapshot: dict) -> tuple[str | None, str | None]:
    """Extract (target_name, item) from snapshot tags."""
    target = None
    item = None
    for tag in snapshot.get("tags", []):
        if tag.startswith("target:"):
            target = tag.split(":", 1)[1]
        elif tag.startswith("database:"):
            item = tag.split(":", 1)[1]
    return target, item


def group_snapshots_by_batch(snapshots: list[dict]) -> dict[str, BatchInfo]:
    """
    Group snapshots by batch ID.

    Handles edge cases:
    - Snapshots without osiris: tag are ignored
    - Snapshots with missing target: tag are logged and skipped
    - Partial batches (some targets failed) are included with partial data
    """
    batches: dict[str, list[dict]] = {}

    for snap in snapshots:
        batch_id = parse_batch_id(snap)
        if batch_id is None:
            continue  # Not an Osiris snapshot

        if batch_id not in batches:
            batches[batch_id] = []
        batches[batch_id].append(snap)

    # Build BatchInfo for each batch
    result = {}
    for batch_id, snaps in batches.items():
        targets: dict[str, list[str]] = {}
        earliest = None
        total_size = 0

        for snap in snaps:
            target, item = parse_target_info(snap)
            if target is None:
                continue  # Malformed snapshot, skip

            if target not in targets:
                targets[target] = []
            if item:
                targets[target].append(item)

            # Track earliest timestamp
            snap_time = snap.get("time", "")
            if earliest is None or snap_time < earliest:
                earliest = snap_time

            # Accumulate size (if available)
            # Note: restic snapshots --json doesn't include size; need stats call
            # For now, leave as 0 - can be populated separately

        result[batch_id] = BatchInfo(
            batch_id=batch_id,
            snapshots=snaps,
            targets=targets,
            created=earliest or "",
            total_size=total_size,
        )

    return result


def resolve_batch(
    restic: "Restic",
    batch_id: str,
    target_filter: str | None = None,
    database_filter: str | None = None,
) -> list[dict]:
    """
    Resolve a batch ID to specific snapshots.

    Args:
        restic: Restic wrapper instance
        batch_id: The batch ID to resolve (e.g., "20260103-020000")
        target_filter: Optional target name to filter (e.g., "postgres")
        database_filter: Optional database name to filter (e.g., "kriib")

    Returns:
        List of matching snapshot dicts

    Raises:
        ValueError: If batch_id not found or filters match nothing
    """
    all_snapshots = restic.snapshots()
    batches = group_snapshots_by_batch(all_snapshots)

    if batch_id not in batches:
        raise ValueError(f"Batch '{batch_id}' not found")

    batch = batches[batch_id]
    result = []

    for snap in batch.snapshots:
        target, item = parse_target_info(snap)

        # Apply filters
        if target_filter and target != target_filter:
            continue
        if database_filter and item != database_filter:
            continue

        result.append(snap)

    if not result:
        filters = []
        if target_filter:
            filters.append(f"target={target_filter}")
        if database_filter:
            filters.append(f"database={database_filter}")
        raise ValueError(
            f"No snapshots in batch '{batch_id}' match filters: {', '.join(filters)}"
        )

    return result
