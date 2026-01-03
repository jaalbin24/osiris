"""Tests for Restic wrapper."""

import json

import pytest

from osiris.restic import Restic


class TestResticInit:
    """Tests for repository initialization."""

    def test_init_success(self, mock_subprocess, tmp_path):
        """Test successful repository initialization."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            returncode=0,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        restic.init()

        # Verify init was called
        assert any("init" in str(call) for call, _ in mock_subprocess.calls)

    def test_is_initialized_true(self, mock_subprocess, tmp_path):
        """Test checking initialized repository."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
            returncode=0,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        assert restic.is_initialized() is True

    def test_is_initialized_false(self, mock_subprocess, tmp_path):
        """Test checking uninitialized repository."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stderr=b"Fatal: unable to open config file",
            returncode=1,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        assert restic.is_initialized() is False


class TestResticLocking:
    """Tests for repository locking."""

    def test_is_locked_true(self, mock_subprocess, tmp_path):
        """Test detecting locked repository."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stderr=b"repository is already locked",
            returncode=1,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        assert restic.is_locked() is True

    def test_is_locked_false(self, mock_subprocess, tmp_path):
        """Test unlocked repository."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
            returncode=0,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        assert restic.is_locked() is False

    def test_unlock(self, mock_subprocess, tmp_path):
        """Test unlocking repository."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "unlock"],
            returncode=0,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        restic.unlock()

        assert any("unlock" in str(call) for call, _ in mock_subprocess.calls)


class TestResticSnapshots:
    """Tests for snapshot operations."""

    def test_snapshots_list(self, mock_subprocess, tmp_path, mock_restic_snapshots):
        """Test listing snapshots."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        snapshots = restic.snapshots()

        assert len(snapshots) == 2
        assert snapshots[0]["short_id"] == "abc123de"
        assert "osiris:20260103-020000" in snapshots[0]["tags"]

    def test_snapshots_with_tags(self, mock_subprocess, tmp_path):
        """Test listing snapshots with tag filter."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots", "--tag"],
            stdout=b"[]",
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        restic.snapshots(tags=["target:postgres"])

        # Verify --tag was included
        assert any(
            "--tag" in str(call) and "target:postgres" in str(call)
            for call, _ in mock_subprocess.calls
        )


class TestResticBackup:
    """Tests for backup operations."""

    def test_backup_path(self, mock_subprocess, tmp_path):
        """Test backing up a local path."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "backup"],
            stdout=json.dumps(
                {
                    "message_type": "summary",
                    "snapshot_id": "abc123de",
                    "total_bytes_processed": 1024000,
                }
            ).encode(),
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        result = restic.backup_path(
            str(data_dir),
            tags=["osiris:test", "target:test"],
        )

        assert result.get("snapshot_id") == "abc123de"
        assert result.get("total_bytes_processed") == 1024000

    def test_backup_path_not_found(self, mock_subprocess, tmp_path):
        """Test error when backup path doesn't exist."""
        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))

        with pytest.raises(FileNotFoundError):
            restic.backup_path("/nonexistent/path", tags=[])


class TestResticForget:
    """Tests for forget/prune operations."""

    def test_forget_with_retention(self, mock_subprocess, tmp_path):
        """Test forget with retention policy."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "forget"],
            stdout=json.dumps(
                {
                    "keep": [{"id": "keep1"}, {"id": "keep2"}],
                    "remove": [{"short_id": "rm1"}, {"short_id": "rm2"}],
                }
            ).encode(),
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        result = restic.forget(
            keep_daily=7,
            keep_weekly=4,
            keep_monthly=6,
        )

        assert len(result["removed"]) == 2
        assert result["kept"] == 2

    def test_forget_dry_run(self, mock_subprocess, tmp_path):
        """Test forget with dry-run."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "forget", "--dry-run"],
            stdout=b"{}",
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        restic.forget(
            keep_daily=7,
            keep_weekly=4,
            keep_monthly=6,
            dry_run=True,
        )

        # Verify --dry-run was included
        assert any("--dry-run" in str(call) for call, _ in mock_subprocess.calls)


class TestResticCheck:
    """Tests for repository verification."""

    def test_check_success(self, mock_subprocess, tmp_path):
        """Test successful repository check."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "check"],
            stdout=b"no errors were found",
            returncode=0,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        success, message = restic.check()

        assert success is True
        assert "no errors" in message

    def test_check_failure(self, mock_subprocess, tmp_path):
        """Test failed repository check."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "check"],
            stderr=b"pack abc123 is damaged",
            returncode=1,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        success, message = restic.check()

        assert success is False
        assert "damaged" in message

    def test_check_thorough(self, mock_subprocess, tmp_path):
        """Test thorough repository check."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "check", "--read-data"],
            stdout=b"no errors",
            returncode=0,
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        restic.check(read_data=True)

        # Verify --read-data was included
        assert any("--read-data" in str(call) for call, _ in mock_subprocess.calls)


class TestResticStats:
    """Tests for repository statistics."""

    def test_stats(self, mock_subprocess, tmp_path):
        """Test getting repository stats."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "stats"],
            stdout=json.dumps(
                {
                    "total_size": 1073741824,
                    "total_file_count": 500,
                }
            ).encode(),
        )

        password_file = tmp_path / "password"
        password_file.write_text("test")

        restic = Restic(str(tmp_path / "repo"), str(password_file))
        stats = restic.stats()

        assert stats["total_size"] == 1073741824
        assert stats["total_file_count"] == 500
