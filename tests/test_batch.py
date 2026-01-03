"""Tests for batch resolution utilities."""

from osiris.batch import (
    BatchInfo,
    group_snapshots_by_batch,
    parse_batch_id,
    parse_target_info,
)


class TestParseBatchId:
    """Tests for parse_batch_id function."""

    def test_parse_valid_batch_id(self):
        """Test extracting batch ID from snapshot tags."""
        snapshot = {
            "tags": ["osiris:20260103-020000", "target:postgres"],
        }
        assert parse_batch_id(snapshot) == "20260103-020000"

    def test_parse_no_osiris_tag(self):
        """Test snapshot without osiris tag."""
        snapshot = {
            "tags": ["target:postgres", "other:tag"],
        }
        assert parse_batch_id(snapshot) is None

    def test_parse_empty_tags(self):
        """Test snapshot with empty tags."""
        snapshot = {"tags": []}
        assert parse_batch_id(snapshot) is None

    def test_parse_no_tags_key(self):
        """Test snapshot without tags key."""
        snapshot = {}
        assert parse_batch_id(snapshot) is None


class TestParseTargetInfo:
    """Tests for parse_target_info function."""

    def test_parse_postgres_target(self):
        """Test extracting target and database from postgres snapshot."""
        snapshot = {
            "tags": [
                "osiris:20260103-020000",
                "target:postgres",
                "database:testdb",
            ],
        }
        target, item = parse_target_info(snapshot)
        assert target == "postgres"
        assert item == "testdb"

    def test_parse_rsync_target(self):
        """Test extracting target from rsync snapshot (no database tag)."""
        snapshot = {
            "tags": [
                "osiris:20260103-020000",
                "target:minio",
            ],
        }
        target, item = parse_target_info(snapshot)
        assert target == "minio"
        assert item is None

    def test_parse_no_target_tag(self):
        """Test snapshot without target tag."""
        snapshot = {
            "tags": ["osiris:20260103-020000"],
        }
        target, item = parse_target_info(snapshot)
        assert target is None
        assert item is None


class TestGroupSnapshotsByBatch:
    """Tests for group_snapshots_by_batch function."""

    def test_group_single_batch(self, mock_restic_snapshots):
        """Test grouping snapshots from single batch."""
        batches = group_snapshots_by_batch(mock_restic_snapshots)

        assert len(batches) == 1
        assert "20260103-020000" in batches

        batch = batches["20260103-020000"]
        assert len(batch.snapshots) == 2
        assert "postgres" in batch.targets
        assert "minio" in batch.targets

    def test_group_multiple_batches(self):
        """Test grouping snapshots from multiple batches."""
        snapshots = [
            {
                "id": "snap1",
                "time": "2026-01-03T02:00:00Z",
                "tags": ["osiris:20260103-020000", "target:postgres"],
            },
            {
                "id": "snap2",
                "time": "2026-01-04T02:00:00Z",
                "tags": ["osiris:20260104-020000", "target:postgres"],
            },
        ]

        batches = group_snapshots_by_batch(snapshots)

        assert len(batches) == 2
        assert "20260103-020000" in batches
        assert "20260104-020000" in batches

    def test_group_ignores_non_osiris_snapshots(self):
        """Test that snapshots without osiris tag are ignored."""
        snapshots = [
            {
                "id": "snap1",
                "time": "2026-01-03T02:00:00Z",
                "tags": ["osiris:20260103-020000", "target:postgres"],
            },
            {
                "id": "snap2",
                "time": "2026-01-03T02:00:00Z",
                "tags": ["manual-backup", "target:postgres"],
            },
        ]

        batches = group_snapshots_by_batch(snapshots)

        assert len(batches) == 1
        batch = batches["20260103-020000"]
        assert len(batch.snapshots) == 1

    def test_group_handles_malformed_snapshots(self):
        """Test that snapshots without target tag are skipped in targets dict."""
        snapshots = [
            {
                "id": "snap1",
                "time": "2026-01-03T02:00:00Z",
                "tags": ["osiris:20260103-020000", "target:postgres"],
            },
            {
                "id": "snap2",
                "time": "2026-01-03T02:00:00Z",
                "tags": ["osiris:20260103-020000"],  # missing target tag
            },
        ]

        batches = group_snapshots_by_batch(snapshots)

        batch = batches["20260103-020000"]
        # Both snapshots are in the batch
        assert len(batch.snapshots) == 2
        # But only one has a valid target
        assert len(batch.targets) == 1
        assert "postgres" in batch.targets

    def test_group_tracks_earliest_timestamp(self):
        """Test that batch.created is the earliest snapshot time."""
        snapshots = [
            {
                "id": "snap1",
                "time": "2026-01-03T02:00:30Z",
                "tags": ["osiris:20260103-020000", "target:postgres"],
            },
            {
                "id": "snap2",
                "time": "2026-01-03T02:00:00Z",
                "tags": ["osiris:20260103-020000", "target:minio"],
            },
        ]

        batches = group_snapshots_by_batch(snapshots)
        batch = batches["20260103-020000"]

        assert batch.created == "2026-01-03T02:00:00Z"

    def test_group_postgres_multiple_databases(self):
        """Test grouping postgres snapshots with multiple databases."""
        snapshots = [
            {
                "id": "snap1",
                "time": "2026-01-03T02:00:00Z",
                "tags": [
                    "osiris:20260103-020000",
                    "target:postgres",
                    "database:db1",
                ],
            },
            {
                "id": "snap2",
                "time": "2026-01-03T02:00:15Z",
                "tags": [
                    "osiris:20260103-020000",
                    "target:postgres",
                    "database:db2",
                ],
            },
        ]

        batches = group_snapshots_by_batch(snapshots)
        batch = batches["20260103-020000"]

        assert len(batch.targets["postgres"]) == 2
        assert "db1" in batch.targets["postgres"]
        assert "db2" in batch.targets["postgres"]


class TestBatchInfo:
    """Tests for BatchInfo dataclass."""

    def test_batch_info_creation(self):
        """Test creating BatchInfo instance."""
        batch = BatchInfo(
            batch_id="20260103-020000",
            snapshots=[{"id": "snap1"}],
            targets={"postgres": ["db1"]},
            created="2026-01-03T02:00:00Z",
            total_size=1024000,
        )

        assert batch.batch_id == "20260103-020000"
        assert len(batch.snapshots) == 1
        assert batch.targets["postgres"] == ["db1"]
        assert batch.total_size == 1024000
