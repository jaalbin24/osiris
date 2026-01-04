"""Configuration loading and validation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from osiris.targets.postgres import PostgresTarget
    from osiris.targets.rsync import RsyncTarget


class ConfigError(Exception):
    """Configuration validation error."""

    pass


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: Literal["debug", "info", "warn", "error"] = "info"
    file: str | None = "/var/log/osiris/osiris.log"
    journal: bool = True


@dataclass
class SSHConfig:
    """SSH connection configuration."""

    user: str = "osiris"
    key_file: str = "/etc/osiris/ssh/id_ed25519"
    control_master: bool = True
    control_path: str = "/run/osiris/ssh-%r@%h:%p"
    control_persist: int = 300


@dataclass
class PostgresTargetConfig:
    """Configuration for a PostgreSQL backup target (from config.yaml)."""

    name: str
    type: Literal["pg_dump"]
    host: str
    pg_user: str  # PostgreSQL user (not SSH user)
    databases: list[str]  # ["kriib", "analytics"] or ["*"]
    exclude: list[str] = field(
        default_factory=lambda: ["template0", "template1", "postgres"]
    )
    port: int = 5432
    # SSH overrides (None = use global ssh config)
    ssh_user: str | None = None
    ssh_key_file: str | None = None

    def create_target(self, databases: list[str] | None = None) -> "PostgresTarget":
        """
        Create a PostgresTarget instance from this config.

        Args:
            databases: Optional override for databases to backup/restore.
                       If None, uses self.databases.

        Returns:
            Configured PostgresTarget instance
        """
        from osiris.targets.postgres import PostgresTarget

        return PostgresTarget(
            name=self.name,
            host=self.host,
            user=self.pg_user,
            databases=databases or self.databases,
            exclude=self.exclude,
            port=self.port,
            ssh_user=self.ssh_user,
            ssh_key_file=self.ssh_key_file,
        )


@dataclass
class RsyncTargetConfig:
    """Configuration for an rsync backup target (from config.yaml)."""

    name: str
    type: Literal["rsync"]
    host: str
    path: str
    staging_dir: str | None = None  # Defaults to /var/cache/osiris/{name}
    # SSH overrides (None = use global ssh config)
    ssh_user: str | None = None
    ssh_key_file: str | None = None

    def create_target(self) -> "RsyncTarget":
        """
        Create an RsyncTarget instance from this config.

        Returns:
            Configured RsyncTarget instance
        """
        from osiris.targets.rsync import RsyncTarget

        return RsyncTarget(
            name=self.name,
            host=self.host,
            path=self.path,
            staging_dir=self.staging_dir,
            ssh_user=self.ssh_user,
            ssh_key_file=self.ssh_key_file,
        )


@dataclass
class Retention:
    """Backup retention policy."""

    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 6


@dataclass
class Config:
    """Main configuration."""

    repository: str
    password_file: str
    logging: LoggingConfig
    ssh: SSHConfig
    targets: dict[str, PostgresTargetConfig | RsyncTargetConfig]
    retention: Retention


def load_config(path: str = "/etc/osiris/config.yaml") -> Config:
    """
    Load and validate configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist
        ConfigError: If config is invalid (missing fields, wrong types, etc.)
    """
    import yaml

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}")

    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    # Validate required top-level fields
    required = ["repository", "password_file", "targets"]
    for field_name in required:
        if field_name not in raw:
            raise ConfigError(f"Missing required field: {field_name}")

    # Validate repository
    repository = raw["repository"]
    if not isinstance(repository, str):
        raise ConfigError(
            f"repository must be a string, got {type(repository).__name__}"
        )

    # Validate password_file path
    password_file = raw["password_file"]
    if not isinstance(password_file, str):
        raise ConfigError(
            f"password_file must be a string, got {type(password_file).__name__}"
        )
    # Note: password_file existence is NOT checked here.
    # The file is created by 'osiris init'. If missing when running
    # other commands, restic will fail with a clear error.

    # Parse logging (with defaults)
    logging_raw = raw.get("logging", {})
    logging_config = LoggingConfig(
        level=logging_raw.get("level", "info"),
        file=logging_raw.get("file", "/var/log/osiris/osiris.log"),
        journal=logging_raw.get("journal", True),
    )
    if logging_config.level not in ("debug", "info", "warn", "error"):
        raise ConfigError(f"Invalid logging.level: {logging_config.level}")

    # Parse SSH (with defaults)
    ssh_raw = raw.get("ssh", {})
    ssh_config = SSHConfig(
        user=ssh_raw.get("user", "osiris"),
        key_file=ssh_raw.get("key_file", "/etc/osiris/ssh/id_ed25519"),
        control_master=ssh_raw.get("control_master", True),
        control_path=ssh_raw.get("control_path", "/run/osiris/ssh-%r@%h:%p"),
        control_persist=ssh_raw.get("control_persist", 300),
    )
    # Note: SSH key file existence is NOT checked here.
    # Config validation should work even on incomplete deployments (e.g., testing config syntax).
    # Use 'osiris validate' to check for SSH key and other runtime dependencies.

    # Parse targets
    targets_raw = raw.get("targets", {})
    if not isinstance(targets_raw, dict):
        raise ConfigError("targets must be a mapping")
    # Note: Empty targets is allowed after 'osiris init'.
    # The 'backup' command will warn if no targets are configured.

    targets: dict[str, PostgresTargetConfig | RsyncTargetConfig] = {}
    for name, target_raw in targets_raw.items():
        if not isinstance(target_raw, dict):
            raise ConfigError(f"Target '{name}' must be a mapping")

        target_type = target_raw.get("type")
        if target_type not in ("pg_dump", "rsync"):
            raise ConfigError(f"Target '{name}' has invalid type: {target_type}")

        if "host" not in target_raw:
            raise ConfigError(f"Target '{name}' missing required field: host")

        if target_type == "pg_dump":
            if "pg_user" not in target_raw:
                raise ConfigError(f"Target '{name}' missing required field: pg_user")
            if "databases" not in target_raw:
                raise ConfigError(f"Target '{name}' missing required field: databases")

            targets[name] = PostgresTargetConfig(
                name=name,
                type="pg_dump",
                host=target_raw["host"],
                pg_user=target_raw["pg_user"],
                databases=target_raw["databases"],
                exclude=target_raw.get(
                    "exclude", ["template0", "template1", "postgres"]
                ),
                port=target_raw.get("port", 5432),
                ssh_user=target_raw.get("ssh_user"),
                ssh_key_file=target_raw.get("ssh_key_file"),
            )

        elif target_type == "rsync":
            if "path" not in target_raw:
                raise ConfigError(f"Target '{name}' missing required field: path")

            targets[name] = RsyncTargetConfig(
                name=name,
                type="rsync",
                host=target_raw["host"],
                path=target_raw["path"],
                staging_dir=target_raw.get("staging_dir"),
                ssh_user=target_raw.get("ssh_user"),
                ssh_key_file=target_raw.get("ssh_key_file"),
            )

    # Parse retention (with defaults)
    retention_raw = raw.get("retention", {})
    retention = Retention(
        keep_daily=retention_raw.get("keep_daily", 7),
        keep_weekly=retention_raw.get("keep_weekly", 4),
        keep_monthly=retention_raw.get("keep_monthly", 6),
    )

    return Config(
        repository=repository,
        password_file=password_file,
        logging=logging_config,
        ssh=ssh_config,
        targets=targets,
        retention=retention,
    )
