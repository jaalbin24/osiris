"""Tests for configuration loading and validation."""

import pytest

from osiris.config import (
    Config,
    ConfigError,
    LoggingConfig,
    PostgresTargetConfig,
    Retention,
    RsyncTargetConfig,
    SSHConfig,
    load_config,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_config):
        """Test loading a valid configuration file."""
        config = load_config(str(tmp_config))

        assert isinstance(config, Config)
        assert "repo" in config.repository
        assert config.logging.level == "info"
        assert config.ssh.user == "testuser"
        assert "postgres" in config.targets
        assert "minio" in config.targets

    def test_config_not_found(self, tmp_path):
        """Test error when config file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_config(str(tmp_path / "nonexistent.yaml"))

    def test_invalid_yaml(self, tmp_path):
        """Test error on invalid YAML syntax."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: syntax:")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(str(config_path))

    def test_missing_repository(self, tmp_path):
        """Test error when repository field is missing."""
        password_path = tmp_path / "password"
        password_path.write_text("test")

        config_path = tmp_path / "config.yaml"
        config_path.write_text(f"""
password_file: {password_path}
targets:
  test:
    type: pg_dump
    host: localhost
    pg_user: postgres
    databases: [testdb]
""")

        with pytest.raises(ConfigError, match="Missing required field: repository"):
            load_config(str(config_path))

    def test_empty_targets_allowed(self, tmp_path):
        """Test that empty targets section is allowed (for post-init config)."""
        password_path = tmp_path / "password"
        password_path.write_text("test")

        config_path = tmp_path / "config.yaml"
        config_path.write_text(f"""
repository: /backup
password_file: {password_path}
targets: {{}}
""")

        # Empty targets should be allowed - user will add them after init
        config = load_config(str(config_path))
        assert config.targets == {}

    def test_invalid_target_type(self, tmp_path):
        """Test error on invalid target type."""
        password_path = tmp_path / "password"
        password_path.write_text("test")

        config_path = tmp_path / "config.yaml"
        config_path.write_text(f"""
repository: /backup
password_file: {password_path}
targets:
  test:
    type: invalid_type
    host: localhost
""")

        with pytest.raises(ConfigError, match="invalid type"):
            load_config(str(config_path))

    def test_postgres_target_missing_fields(self, tmp_path):
        """Test error when postgres target is missing required fields."""
        password_path = tmp_path / "password"
        password_path.write_text("test")

        config_path = tmp_path / "config.yaml"
        config_path.write_text(f"""
repository: /backup
password_file: {password_path}
targets:
  postgres:
    type: pg_dump
    host: localhost
    # missing pg_user and databases
""")

        with pytest.raises(ConfigError, match="missing required field"):
            load_config(str(config_path))

    def test_rsync_target_missing_path(self, tmp_path):
        """Test error when rsync target is missing path."""
        password_path = tmp_path / "password"
        password_path.write_text("test")

        config_path = tmp_path / "config.yaml"
        config_path.write_text(f"""
repository: /backup
password_file: {password_path}
targets:
  minio:
    type: rsync
    host: localhost
    # missing path
""")

        with pytest.raises(ConfigError, match="missing required field: path"):
            load_config(str(config_path))


class TestLoggingConfig:
    """Tests for LoggingConfig defaults."""

    def test_defaults(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        assert config.level == "info"
        assert config.file == "/var/log/osiris/osiris.log"
        assert config.journal is True


class TestSSHConfig:
    """Tests for SSHConfig defaults."""

    def test_defaults(self):
        """Test default SSH configuration."""
        config = SSHConfig()
        assert config.user == "osiris"
        assert config.control_master is True
        assert config.control_persist == 300


class TestRetention:
    """Tests for Retention defaults."""

    def test_defaults(self):
        """Test default retention policy."""
        retention = Retention()
        assert retention.keep_daily == 7
        assert retention.keep_weekly == 4
        assert retention.keep_monthly == 6


class TestPostgresTargetConfig:
    """Tests for PostgresTargetConfig."""

    def test_create_target(self):
        """Test creating a PostgresTarget from config."""
        config = PostgresTargetConfig(
            name="test",
            type="pg_dump",
            host="db.example.com",
            pg_user="backup",
            databases=["app", "analytics"],
            port=5433,
        )

        target = config.create_target()

        assert target.name == "test"
        assert target.host == "db.example.com"
        assert target.user == "backup"
        assert target.databases == ["app", "analytics"]
        assert target.port == 5433

    def test_create_target_with_override(self):
        """Test creating target with database override."""
        config = PostgresTargetConfig(
            name="test",
            type="pg_dump",
            host="localhost",
            pg_user="postgres",
            databases=["db1", "db2"],
        )

        target = config.create_target(databases=["only_this"])

        assert target.databases == ["only_this"]

    def test_default_exclude(self):
        """Test default excluded databases."""
        config = PostgresTargetConfig(
            name="test",
            type="pg_dump",
            host="localhost",
            pg_user="postgres",
            databases=["*"],
        )

        assert "template0" in config.exclude
        assert "template1" in config.exclude
        assert "postgres" in config.exclude


class TestRsyncTargetConfig:
    """Tests for RsyncTargetConfig."""

    def test_create_target(self):
        """Test creating an RsyncTarget from config."""
        config = RsyncTargetConfig(
            name="minio",
            type="rsync",
            host="storage.example.com",
            path="/var/lib/minio/data",
            staging_dir="/var/cache/backup/minio",
        )

        target = config.create_target()

        assert target.name == "minio"
        assert target.host == "storage.example.com"
        assert target.path == "/var/lib/minio/data"
        assert target.staging_dir == "/var/cache/backup/minio"

    def test_default_staging_dir(self):
        """Test default staging directory."""
        config = RsyncTargetConfig(
            name="minio",
            type="rsync",
            host="localhost",
            path="/data",
        )

        assert config.staging_dir is None
        target = config.create_target()
        assert target.staging_dir == "/var/cache/osiris/minio"
