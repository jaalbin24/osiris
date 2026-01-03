"""Tests for backup targets."""

from unittest.mock import MagicMock

import pytest

from osiris.config import SSHConfig
from osiris.ssh import SSHManager
from osiris.targets.postgres import PostgresTarget
from osiris.targets.rsync import RsyncTarget


class TestPostgresTarget:
    """Tests for PostgresTarget."""

    @pytest.fixture
    def postgres_target(self):
        """Create a PostgresTarget instance for testing."""
        return PostgresTarget(
            name="postgres",
            host="db.example.com",
            user="backup",
            databases=["testdb"],
            port=5432,
        )

    @pytest.fixture
    def mock_ssh_manager(self):
        """Create a mock SSHManager."""
        ssh = MagicMock(spec=SSHManager)
        ssh.config = SSHConfig()

        mock_conn = MagicMock()
        mock_conn.host = "db.example.com"
        mock_conn.user = "backup"
        mock_conn.key_file = "/etc/osiris/ssh/id_ed25519"
        mock_conn.control_path = "/tmp/ssh-backup@db.example.com:22"

        ssh.get_connection.return_value = mock_conn
        ssh.get_ssh_cmd.return_value = [
            "ssh",
            "-i",
            "/etc/osiris/ssh/id_ed25519",
            "backup@db.example.com",
            "pg_dump -U backup -p 5432 --create --clean --if-exists testdb",
        ]

        return ssh

    def test_target_initialization(self, postgres_target):
        """Test PostgresTarget initialization."""
        assert postgres_target.name == "postgres"
        assert postgres_target.host == "db.example.com"
        assert postgres_target.user == "backup"
        assert postgres_target.databases == ["testdb"]
        assert postgres_target.port == 5432

    def test_default_exclude_databases(self, postgres_target):
        """Test default excluded databases."""
        assert "template0" in postgres_target.exclude
        assert "template1" in postgres_target.exclude
        assert "postgres" in postgres_target.exclude

    def test_get_snapshot_items(self, postgres_target):
        """Test get_snapshot_items returns configured databases."""
        items = postgres_target.get_snapshot_items()
        assert items == ["testdb"]

    def test_get_snapshot_items_wildcard(self):
        """Test get_snapshot_items with wildcard."""
        target = PostgresTarget(
            name="postgres",
            host="localhost",
            user="postgres",
            databases=["*"],
        )
        items = target.get_snapshot_items()
        assert items == ["*"]

    def test_check_connectivity_success(self, postgres_target, mock_subprocess):
        """Test connectivity check when pg_dump is available."""
        mock_subprocess.add_response(
            cmd_contains=["ssh", "which", "pg_dump"],
            returncode=0,
        )

        ssh = MagicMock(spec=SSHManager)
        ssh.config = SSHConfig()
        mock_conn = MagicMock()
        ssh.get_connection.return_value = mock_conn
        ssh.get_ssh_cmd.return_value = ["ssh", "user@host", "which pg_dump"]

        result = postgres_target.check_connectivity(ssh)
        assert result is True

    def test_check_connectivity_failure(self, postgres_target, mock_subprocess):
        """Test connectivity check when pg_dump is not available."""
        mock_subprocess.add_response(
            cmd_contains=["ssh"],
            returncode=1,
        )

        ssh = MagicMock(spec=SSHManager)
        ssh.config = SSHConfig()
        mock_conn = MagicMock()
        ssh.get_connection.return_value = mock_conn
        ssh.get_ssh_cmd.return_value = ["ssh", "user@host", "which pg_dump"]

        result = postgres_target.check_connectivity(ssh)
        assert result is False


class TestRsyncTarget:
    """Tests for RsyncTarget."""

    @pytest.fixture
    def rsync_target(self, tmp_path):
        """Create an RsyncTarget instance for testing."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        return RsyncTarget(
            name="minio",
            host="storage.example.com",
            path="/var/lib/minio/data",
            staging_dir=str(staging_dir),
        )

    def test_target_initialization(self, rsync_target):
        """Test RsyncTarget initialization."""
        assert rsync_target.name == "minio"
        assert rsync_target.host == "storage.example.com"
        assert rsync_target.path == "/var/lib/minio/data"

    def test_default_staging_dir(self):
        """Test default staging directory."""
        target = RsyncTarget(
            name="minio",
            host="localhost",
            path="/data",
        )
        assert target.staging_dir == "/var/cache/osiris/minio"

    def test_get_snapshot_items(self, rsync_target):
        """Test get_snapshot_items returns the path."""
        items = rsync_target.get_snapshot_items()
        assert items == ["/var/lib/minio/data"]

    def test_check_connectivity_success(self, rsync_target, mock_subprocess):
        """Test connectivity check when path exists."""
        mock_subprocess.add_response(
            cmd_contains=["ssh", "test -d"],
            returncode=0,
        )

        ssh = MagicMock(spec=SSHManager)
        ssh.config = SSHConfig()
        mock_conn = MagicMock()
        ssh.get_connection.return_value = mock_conn
        ssh.get_ssh_cmd.return_value = [
            "ssh",
            "user@host",
            "test -d /var/lib/minio/data",
        ]

        result = rsync_target.check_connectivity(ssh)
        assert result is True

    def test_check_connectivity_failure(self, rsync_target, mock_subprocess):
        """Test connectivity check when path doesn't exist."""
        mock_subprocess.add_response(
            cmd_contains=["ssh"],
            returncode=1,
        )

        ssh = MagicMock(spec=SSHManager)
        ssh.config = SSHConfig()
        mock_conn = MagicMock()
        ssh.get_connection.return_value = mock_conn
        ssh.get_ssh_cmd.return_value = [
            "ssh",
            "user@host",
            "test -d /var/lib/minio/data",
        ]

        result = rsync_target.check_connectivity(ssh)
        assert result is False

    def test_find_restored_data_direct_path(self, rsync_target, tmp_path):
        """Test finding restored data at expected nested path."""
        # Create the expected nested structure
        nested_path = tmp_path / rsync_target.staging_dir.lstrip("/") / "data"
        nested_path.mkdir(parents=True)
        (nested_path / "file.txt").write_text("test")

        result = rsync_target._find_restored_data(str(tmp_path))
        assert "data" in result

    def test_find_restored_data_single_child_descent(self, rsync_target, tmp_path):
        """Test descending through single-child directories."""
        # Create a separate root to avoid the staging dir created by fixture
        test_root = tmp_path / "restore_test"
        test_root.mkdir()

        # Create a/b/c/file.txt structure
        deep_path = test_root / "a" / "b" / "c"
        deep_path.mkdir(parents=True)
        (deep_path / "file.txt").write_text("test")

        result = rsync_target._find_restored_data(str(test_root))
        # Should descend to 'c' where the file is
        assert result.endswith("c")

    def test_find_restored_data_stops_at_multiple_children(
        self, rsync_target, tmp_path
    ):
        """Test stopping descent when multiple children exist."""
        # Create a separate root to avoid the staging dir created by fixture
        test_root = tmp_path / "restore_test"
        test_root.mkdir()

        # Create structure with multiple children
        (test_root / "dir1").mkdir()
        (test_root / "dir2").mkdir()

        result = rsync_target._find_restored_data(str(test_root))
        # Should stop at test_root since it has multiple children
        assert result == str(test_root)
