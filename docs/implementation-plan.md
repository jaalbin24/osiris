# Osiris Implementation Plan

## Overview

Osiris is a CLI backup management tool that wraps restic to provide a simplified, opinionated interface for backing up PostgreSQL databases and MinIO object stores.

**Repository**: `~/workspace/Osiris`
**Dependency**: Iris (git+https://git.kriib.com/Kriib/iris.git@v1.0.0)

---

## Architecture

```
osiris/
├── pyproject.toml
├── README.md
├── src/osiris/
│   ├── __init__.py
│   ├── cli.py              # Click CLI entry point
│   ├── config.py           # Configuration loading/validation
│   ├── context.py          # CommandContext and shared decorators
│   ├── logging.py          # Logging setup (file + journal)
│   ├── results.py          # BackupItemResult, BackupBatchResult dataclasses
│   ├── restic.py           # Restic wrapper (subprocess calls)
│   ├── ssh.py              # SSHManager with ControlMaster support
│   ├── batch.py            # Batch ID resolution and grouping
│   ├── utils.py            # Shared formatting utilities
│   ├── targets/
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract base target
│   │   ├── postgres.py     # PostgreSQL backup target (multi-database)
│   │   └── rsync.py        # Rsync-based backup target (MinIO)
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── backup.py       # osiris backup
│   │   ├── restore.py      # osiris restore
│   │   ├── list.py         # osiris list
│   │   ├── show.py         # osiris show
│   │   ├── status.py       # osiris status
│   │   ├── verify.py       # osiris verify
│   │   ├── prune.py        # osiris prune
│   │   ├── chpass.py       # osiris chpass
│   │   ├── init.py         # osiris init
│   │   ├── unlock.py       # osiris unlock
│   │   └── validate.py     # osiris validate
│   └── systemd.py          # Systemd service/timer installation
└── tests/
    ├── __init__.py
    ├── conftest.py         # Pytest fixtures
    ├── test_config.py
    ├── test_restic.py
    ├── test_targets.py
    └── test_commands/
        └── ...
```

---

## Design Decisions (Resolved)

| Decision | Resolution |
|----------|------------|
| Error handling | Continue after partial failure, exit non-zero if any failed |
| Restore safety | Prompt for interactive, `--force` required for non-interactive |
| Config location | `/etc/osiris/config.yaml` only (system service) |
| Logging | Configurable: file + journal by default, logrotate config installed by `osiris init` |
| PostgreSQL restore | Always DROP and recreate database before restore |
| MinIO backup | Two-step: rsync to staging, then restic backup |

## Technical Fixes (from code review)

| Issue | Fix |
|-------|-----|
| Partial failure tracking | Added `BackupItemResult` and `BackupBatchResult` dataclasses in `results.py` |
| Subprocess coordination | Fixed pg_dump \| restic piping with proper `Popen` + `communicate()` |
| PostgreSQL active connections | Added `pg_terminate_backend()` before DROP DATABASE |
| PostgreSQL snapshot query | Fixed: query all snapshots, filter by ID (not by invalid tag format) |
| Restic restore path nesting | Fixed `_find_restored_data()` logic to correctly walk single-child dir chains |
| PostgreSQL owner/encoding loss | Use `pg_dump --create --clean --if-exists` to preserve database metadata |
| SQL injection risk | Use psql `-v` variable binding (`:'varname'`) instead of string interpolation |
| Restic JSON assumptions | Documented actual JSON output format, use `.get()` for optional fields |
| `backup_stdin()` implementation | Full implementation shown with error handling and JSON parsing |
| SSH connection overhead | Added `SSHManager` with ControlMaster for connection multiplexing |
| SSH authentication | Added global `ssh` config section with user, key_file, and per-target overrides |
| SSH ControlMaster robustness | Added `_is_master_alive()`, `ensure_master()`, control path expansion, cleanup on error |
| pg_dump stderr capture | Fixed piping to capture pg_dump errors, added SSH process cleanup on failure |
| `_resolve_databases()` SSH | Fixed to use `SSHManager` instead of raw `["ssh", self.host, ...]` |
| Restic JSON field consistency | Fixed RsyncTarget to use `snapshot.get("snapshot_id")` consistently |
| PostgreSQL restore race | Added retry loop (3 attempts) for "is being accessed" errors |
| Iris debug parameter | Added `--debug` flag to CLI, passed to `UI(debug=debug)` |
| Backup `--force` flag | Added `--force` flag required in non-interactive mode (matches systemd service) |
| Batch ID resolution | Added `batch.py` module with `group_snapshots_by_batch()`, `resolve_batch()`, edge case handling |
| Test mocking strategy | Added `SubprocessRouter` fixture, `mock_restic_responses`, example test cases |
| `_find_restored_data` symlinks | Added symlink loop detection, max depth limit, permission error handling |
| Config validation | Full `load_config()` implementation with type checking, required field validation, helpful errors |
| Password file creation | Full `init` command with atomic file creation (chmod 400), `--generate-password` option |
| Interrupted backup handling | Added `is_locked()`, `ensure_unlocked()` methods; auto-unlock before backup/restore |
| `backup_path()` implementation | Full implementation with path validation, JSON parsing, error handling |
| Pipe buffer handling | Added diagram and documentation for kernel-managed pipe flow; added timeout handling |
| SSH key validation timing | Moved from config load to validate command (allows config syntax testing on incomplete deployments) |
| Password file newline | Added trailing `\n` to password file (restic reads until newline or EOF) |
| Config/target class naming | Renamed config dataclasses to `PostgresTargetConfig`/`RsyncTargetConfig` to avoid conflict |
| Signal handling | Added `register_cleanup()`/`unregister_cleanup()` for SIGINT/SIGTERM SSH cleanup |
| Restic version requirements | Documented minimum restic 0.16.0+ for JSON format; added version check to validate command |
| Incomplete Restic methods | Added full implementations for `snapshots()`, `dump()`, `restore()`, `forget()`, `check()`, `key_list()`, `key_add()`, `key_remove()`, `stats()` |
| Restore command | Added full implementation with batch resolution, dry-run support, confirmation prompts, error handling, and summary output |
| Logrotate config | Added `_install_logrotate_config()` to init command; uses actual log path from config; skips gracefully if logrotate not installed |
| Stub commands | Fleshed out `list`, `show`, `status`, `verify`, `prune`, `chpass`, `unlock` with full implementations |
| Systemd integration | Added full `systemd.py` module with `install_service()`, `uninstall_service()`, `enable_timer()`, `disable_timer()`, `get_timer_status()`; fleshed out CLI subcommands including `service status` |
| DRY consolidation | Added `context.py` with `CommandContext`, `get_context()`, `require_force` decorator, `restic_error_exit()`; added `ssh_session()` context manager; added `utils.py` with `parse_timestamp()`, `format_age()`, `format_size()`, `format_duration()`; added `create_target()` factory methods to config dataclasses |

---

## Phase 1: Project Setup & Core Infrastructure

### 1.1 Create Project Structure
- Initialize Poetry project at `~/workspace/Osiris`
- Add dependencies: iris, click, pyyaml
- Create directory structure

### 1.2 Configuration Module (`src/osiris/config.py`)

**Config file location**: `/etc/osiris/config.yaml`

**Full config with comments**:
```yaml
# /etc/osiris/config.yaml
# Osiris Backup Configuration
# ============================================================================

# Repository settings
# ----------------------------------------------------------------------------
# Path to the restic repository where backups are stored.
repository: /backup/repo

# Path to file containing the repository password.
# This file should be readable only by root (chmod 400).
password_file: /etc/osiris/repo-password

# Logging settings
# ----------------------------------------------------------------------------
logging:
  # Log level: debug, info, warn, error
  level: info

  # Log to file (in addition to systemd journal)
  # Set to null to disable file logging
  file: /var/log/osiris/osiris.log

  # Log to systemd journal (stdout/stderr captured by systemd)
  # Disable if running outside systemd
  journal: true

# SSH settings (global defaults)
# ----------------------------------------------------------------------------
# These settings apply to all targets unless overridden per-target.
ssh:
  # Default user for SSH connections to targets
  user: osiris

  # Path to SSH private key (should be readable only by root)
  key_file: /etc/osiris/ssh/id_ed25519

  # Use ControlMaster for connection multiplexing
  # Reduces overhead when backing up multiple databases
  control_master: true
  control_path: /run/osiris/ssh-%r@%h:%p
  control_persist: 300  # seconds to keep connection alive after last use

# Backup targets
# ----------------------------------------------------------------------------
# Each target defines a data source to back up. Supported types:
#   - pg_dump: PostgreSQL databases via SSH + pg_dump
#   - rsync: Remote directories via SSH + rsync
#
# SSH settings can be overridden per-target with ssh_user and ssh_key_file.
targets:
  # PostgreSQL databases
  # Connects via SSH to the host and runs pg_dump for each database.
  # Uses pg_dump with --create --clean --if-exists to preserve DB metadata.
  postgres:
    type: pg_dump
    host: postgres-01

    # PostgreSQL user for pg_dump (uses peer auth on remote host)
    pg_user: postgres
    port: 5432  # optional, defaults to 5432

    # Databases to back up. Options:
    #   - Explicit list: ["kriib", "analytics"]
    #   - All databases: ["*"]
    databases:
      - kriib
      - analytics

    # Databases to exclude when using ["*"]. Ignored for explicit lists.
    # System databases are excluded by default.
    exclude:
      - template0
      - template1
      - postgres

    # Optional: override global SSH settings for this target
    # ssh_user: backup
    # ssh_key_file: /etc/osiris/ssh/postgres_key

  # MinIO / Object storage
  # Syncs the data directory via rsync, then backs up with restic.
  # This backs up all buckets in the MinIO instance.
  minio:
    type: rsync
    host: minio-01
    path: /var/lib/minio/data

    # Local staging directory for rsync. Cleaned after backup.
    # Must have enough space for a full copy of the remote data.
    staging_dir: /var/cache/osiris/minio  # optional, defaults to /var/cache/osiris/{target_name}

# Retention policy
# ----------------------------------------------------------------------------
# Controls how long backups are kept. Uses restic's forget command.
# At least one snapshot matching each policy is kept.
retention:
  keep_daily: 7      # Keep last 7 daily backups
  keep_weekly: 4     # Keep last 4 weekly backups (one per week)
  keep_monthly: 6    # Keep last 6 monthly backups (one per month)
```

**Log format**:
```
2026-01-03 02:00:15 [INFO] Starting backup batch 20260103-020000
2026-01-03 02:00:15 [INFO] [postgres] Backing up database: kriib
2026-01-03 02:00:45 [INFO] [postgres] Completed: kriib (1.2 GB in 30s)
2026-01-03 02:00:45 [INFO] [postgres] Backing up database: analytics
2026-01-03 02:01:10 [ERROR] [postgres] Failed: analytics - connection refused
2026-01-03 02:01:10 [INFO] [minio] Starting rsync from minio-01:/var/lib/minio/data
2026-01-03 02:02:30 [INFO] [minio] Completed: minio (1.1 GB in 80s)
2026-01-03 02:02:31 [WARN] Backup completed with errors (1 failed, 2 succeeded)
```

**Implementation (dataclasses)**:
```python
@dataclass
class LoggingConfig:
    level: Literal["debug", "info", "warn", "error"] = "info"
    file: str | None = "/var/log/osiris/osiris.log"
    journal: bool = True

@dataclass
class SSHConfig:
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
    exclude: list[str] = field(default_factory=lambda: ["template0", "template1", "postgres"])
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

# Note: These config dataclasses are distinct from the target classes in targets/*.py
# Config classes: Hold configuration data loaded from YAML
# Target classes: Implement backup/restore logic using the config

@dataclass
class Retention:
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 6

@dataclass
class Config:
    repository: str
    password_file: str
    logging: LoggingConfig
    ssh: SSHConfig
    targets: dict[str, PostgresTargetConfig | RsyncTargetConfig]
    retention: Retention

class ConfigError(Exception):
    """Configuration validation error."""
    pass

def load_config(path: str = "/etc/osiris/config.yaml") -> Config:
    """
    Load and validate configuration.

    Raises:
        FileNotFoundError: If config file doesn't exist
        ConfigError: If config is invalid (missing fields, wrong types, etc.)
    """
    import yaml
    from pathlib import Path

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
    for field in required:
        if field not in raw:
            raise ConfigError(f"Missing required field: {field}")

    # Validate repository
    repository = raw["repository"]
    if not isinstance(repository, str):
        raise ConfigError(f"repository must be a string, got {type(repository).__name__}")

    # Validate password_file exists
    password_file = raw["password_file"]
    if not isinstance(password_file, str):
        raise ConfigError(f"password_file must be a string, got {type(password_file).__name__}")
    if not Path(password_file).exists():
        raise ConfigError(f"password_file not found: {password_file}")

    # Parse logging (with defaults)
    logging_raw = raw.get("logging", {})
    logging = LoggingConfig(
        level=logging_raw.get("level", "info"),
        file=logging_raw.get("file", "/var/log/osiris/osiris.log"),
        journal=logging_raw.get("journal", True),
    )
    if logging.level not in ("debug", "info", "warn", "error"):
        raise ConfigError(f"Invalid logging.level: {logging.level}")

    # Parse SSH (with defaults)
    ssh_raw = raw.get("ssh", {})
    ssh = SSHConfig(
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
    if not targets_raw:
        raise ConfigError("At least one target must be defined")

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
                exclude=target_raw.get("exclude", ["template0", "template1", "postgres"]),
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
        logging=logging,
        ssh=ssh,
        targets=targets,
        retention=retention,
    )
```

### 1.3 Logging Module (`src/osiris/logging.py`)

```python
import logging
import sys
from pathlib import Path

def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Configure logging based on config.

    - File handler: writes to config.file if set
    - Stream handler: writes to stdout/stderr (captured by journald)
    """
    logger = logging.getLogger("osiris")
    logger.setLevel(getattr(logging, config.level.upper()))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if config.file:
        Path(config.file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if config.journal:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
```

### 1.4 Command Context (`src/osiris/context.py`)

Shared utilities to reduce boilerplate across commands:

```python
import functools
import logging
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from typing import NoReturn, TYPE_CHECKING

import click

if TYPE_CHECKING:
    from iris import UI
    from osiris.config import Config
    from osiris.restic import Restic


@dataclass
class CommandContext:
    """
    Common context for all commands.

    Consolidates the repeated pattern of extracting ui/config/logger/restic
    from Click's context object.
    """
    ui: "UI"
    config: "Config"
    logger: logging.Logger
    restic: "Restic"


def get_context(ctx: click.Context) -> CommandContext:
    """
    Extract CommandContext from Click context.

    Usage:
        @click.command()
        @click.pass_context
        def mycommand(ctx):
            c = get_context(ctx)
            c.ui.header("Hello")
            c.logger.info("Doing work")
    """
    from osiris.restic import Restic

    config = ctx.obj["config"]
    return CommandContext(
        ui=ctx.obj["ui"],
        config=config,
        logger=ctx.obj["logger"],
        restic=Restic(config.repository, config.password_file),
    )


def require_force(f):
    """
    Decorator: require --force flag in non-interactive mode.

    Use on commands that are destructive or have side effects.
    The decorated function must have a `force` parameter.

    Usage:
        @click.command()
        @click.option("--force", is_flag=True)
        @click.pass_context
        @require_force
        def backup(ctx, force):
            ...
    """
    @functools.wraps(f)
    def wrapper(ctx, *args, **kwargs):
        ui = ctx.obj["ui"]
        force = kwargs.get("force", False)
        if not ui.interactive and not force:
            ui.error("Non-interactive mode requires --force flag")
            raise SystemExit(1)
        return f(ctx, *args, **kwargs)
    return wrapper


def restic_error_exit(
    ui: "UI",
    logger: logging.Logger,
    e: subprocess.CalledProcessError,
    operation: str,
) -> NoReturn:
    """
    Handle restic CalledProcessError with consistent formatting.

    Usage:
        try:
            result = restic.forget(...)
        except subprocess.CalledProcessError as e:
            restic_error_exit(c.ui, c.logger, e, "Prune")
    """
    stderr = e.stderr.decode() if e.stderr else "unknown error"
    ui.error(f"{operation} failed: {stderr}")
    logger.error(f"{operation} failed: {e}")
    raise SystemExit(1)
```

### 1.5 SSH Manager (`src/osiris/ssh.py`)

Manages SSH connections with ControlMaster for connection multiplexing:

```python
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("osiris.ssh")

@dataclass
class SSHConnection:
    """SSH connection parameters for a target."""
    host: str
    user: str
    key_file: str
    control_path: str  # Expanded path (no %r/%h/%p placeholders)

class SSHManager:
    """
    Manages SSH ControlMaster connections for efficient multi-command sessions.

    ControlMaster allows multiple SSH commands to share a single TCP connection,
    reducing overhead when running many commands against the same host
    (e.g., backing up 10 databases).
    """

    def __init__(self, config: "SSHConfig"):
        self.config = config
        self._active_masters: dict[str, SSHConnection] = {}

    def _expand_control_path(self, user: str, host: str, port: int = 22) -> str:
        """
        Expand SSH control path placeholders.

        %r -> remote user
        %h -> remote host
        %p -> port
        """
        path = self.config.control_path
        path = path.replace("%r", user)
        path = path.replace("%h", host)
        path = path.replace("%p", str(port))
        return path

    def get_connection(
        self,
        host: str,
        ssh_user: str | None = None,
        ssh_key_file: str | None = None,
    ) -> SSHConnection:
        """Get SSH connection params, using target overrides or global defaults."""
        user = ssh_user or self.config.user
        return SSHConnection(
            host=host,
            user=user,
            key_file=ssh_key_file or self.config.key_file,
            control_path=self._expand_control_path(user, host),
        )

    def _is_master_alive(self, conn: SSHConnection) -> bool:
        """Check if ControlMaster socket exists and is responsive."""
        result = subprocess.run([
            "ssh",
            "-o", f"ControlPath={conn.control_path}",
            "-O", "check",
            f"{conn.user}@{conn.host}"
        ], capture_output=True)
        return result.returncode == 0

    def start_master(self, conn: SSHConnection) -> None:
        """
        Start a ControlMaster connection for a host.

        Call this before running multiple SSH commands to the same host.
        If master already exists and is alive, does nothing.
        """
        if not self.config.control_master:
            return

        # Check if master already running (e.g., from previous backup)
        if conn.host in self._active_masters:
            if self._is_master_alive(conn):
                return
            # Master died, remove stale entry
            logger.warning(f"ControlMaster for {conn.host} died, restarting")
            del self._active_masters[conn.host]

        # Ensure control socket directory exists
        control_dir = Path(conn.control_path).parent
        control_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ssh",
            "-o", "ControlMaster=yes",
            "-o", f"ControlPath={conn.control_path}",
            "-o", f"ControlPersist={self.config.control_persist}",
            "-o", "BatchMode=yes",  # Fail instead of prompting
            "-i", conn.key_file,
            "-f", "-N",  # Background, no command
            f"{conn.user}@{conn.host}"
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start SSH ControlMaster for {conn.host}: "
                f"{result.stderr.decode().strip()}"
            )
        self._active_masters[conn.host] = conn

    def ensure_master(self, conn: SSHConnection) -> None:
        """
        Ensure ControlMaster is running, restarting if necessary.

        Call this before critical operations to handle master death mid-session.
        """
        if not self.config.control_master:
            return

        if conn.host not in self._active_masters or not self._is_master_alive(conn):
            # Remove stale entry if exists
            self._active_masters.pop(conn.host, None)
            self.start_master(conn)

    def get_ssh_cmd(self, conn: SSHConnection, remote_cmd: str) -> list[str]:
        """
        Build SSH command that uses ControlMaster if available.

        Args:
            conn: SSH connection parameters
            remote_cmd: Command to run on remote host

        Returns:
            Full SSH command as list of args
        """
        cmd = ["ssh"]

        if self.config.control_master:
            cmd.extend([
                "-o", f"ControlPath={conn.control_path}",
                "-o", "ControlMaster=auto",  # Use existing or create new
            ])

        cmd.extend([
            "-o", "BatchMode=yes",
            "-i", conn.key_file,
            f"{conn.user}@{conn.host}",
            remote_cmd
        ])

        return cmd

    def close_master(self, host: str) -> None:
        """Close ControlMaster connection for a specific host."""
        if host not in self._active_masters:
            return

        conn = self._active_masters[host]
        result = subprocess.run([
            "ssh",
            "-o", f"ControlPath={conn.control_path}",
            "-O", "exit",
            f"{conn.user}@{conn.host}"
        ], capture_output=True)

        if result.returncode != 0:
            logger.warning(
                f"Failed to cleanly close ControlMaster for {host}: "
                f"{result.stderr.decode().strip()}"
            )
            # Try to remove stale socket file
            socket_path = Path(conn.control_path)
            if socket_path.exists():
                try:
                    socket_path.unlink()
                except OSError:
                    pass

        del self._active_masters[host]

    def close_all(self) -> None:
        """Close all active ControlMaster connections."""
        for host in list(self._active_masters.keys()):
            self.close_master(host)

    def __enter__(self) -> "SSHManager":
        return self

    def __exit__(self, *args) -> None:
        self.close_all()


@contextmanager
def ssh_session(config: "Config", targets: list["PostgresTargetConfig | RsyncTargetConfig"]):
    """
    Context manager for SSH session with automatic cleanup registration.

    Consolidates the repeated pattern of:
    1. Creating SSHManager
    2. Registering signal cleanup handlers
    3. Starting ControlMaster for each target host
    4. Unregistering cleanup on exit

    Usage:
        with ssh_session(config, list(config.targets.values())) as ssh:
            for target in targets:
                target.backup(restic, batch_id, ssh)

    Args:
        config: Full Osiris config (uses config.ssh for SSH settings)
        targets: List of target configs to establish SSH connections for
    """
    with SSHManager(config.ssh) as ssh:
        register_cleanup(ssh)
        try:
            # Start SSH masters for all unique target hosts
            seen_hosts = set()
            for target in targets:
                if target.host in seen_hosts:
                    continue
                seen_hosts.add(target.host)

                conn = ssh.get_connection(
                    target.host,
                    getattr(target, 'ssh_user', None),
                    getattr(target, 'ssh_key_file', None),
                )
                ssh.start_master(conn)

            yield ssh
        finally:
            unregister_cleanup()
```

**Usage in backup command** (simplified with `ssh_session`):
```python
def backup(ctx):
    c = get_context(ctx)

    # ssh_session handles: SSHManager creation, cleanup registration,
    # starting ControlMaster for each host, and cleanup on exit
    with ssh_session(c.config, list(c.config.targets.values())) as ssh:
        for target in c.config.targets.values():
            target.backup(c.restic, batch_id, ssh)
```

### 1.6 Restic Wrapper (`src/osiris/restic.py`)

Low-level wrapper for restic commands:

```python
import json
import subprocess
from typing import IO

class Restic:
    def __init__(self, repository: str, password_file: str):
        self.repository = repository
        self.password_file = password_file

    def _base_args(self) -> list[str]:
        """Common args for all restic commands."""
        return [
            "restic",
            "--repo", self.repository,
            "--password-file", self.password_file,
            "--json",  # JSON output where supported
        ]

    def _run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        """Run restic with common arguments."""
        cmd = self._base_args() + args
        return subprocess.run(cmd, check=True, capture_output=True, **kwargs)

    def init(self) -> None:
        """Initialize repository."""
        self._run(["init"], check=True)

    def is_initialized(self) -> bool:
        """Check if repository is initialized."""
        try:
            self._run(["snapshots", "--json"])
            return True
        except subprocess.CalledProcessError:
            return False

    def is_locked(self) -> bool:
        """
        Check if repository has stale locks.

        Restic creates locks to prevent concurrent operations.
        If a backup was interrupted, locks may be left behind.
        """
        try:
            # Try a read-only operation
            result = self._run(["snapshots", "--json"])
            return False
        except subprocess.CalledProcessError as e:
            # Check if error is due to lock
            stderr = e.stderr.decode() if e.stderr else ""
            return "repository is already locked" in stderr.lower()

    def unlock(self, remove_all: bool = False) -> None:
        """
        Remove stale locks.

        Args:
            remove_all: If True, remove all locks (including active ones).
                       Use with caution - only when sure no other process is running.
        """
        args = ["unlock"]
        if remove_all:
            args.append("--remove-all")
        self._run(args)

    def ensure_unlocked(self, ui: "UI", logger: "logging.Logger") -> None:
        """
        Check for stale locks and offer to remove them.

        Called automatically before backup/restore operations.
        """
        if not self.is_locked():
            return

        logger.warning("Repository has stale lock (previous operation may have been interrupted)")

        if ui.interactive:
            if ui.confirm("Remove stale lock and continue?", default=True):
                self.unlock()
                ui.success("Lock removed")
            else:
                raise RuntimeError("Repository is locked. Run 'osiris unlock' to remove stale locks.")
        else:
            # In non-interactive mode, just try to unlock
            logger.info("Attempting to remove stale lock (non-interactive mode)")
            try:
                self.unlock()
                logger.info("Lock removed successfully")
            except subprocess.CalledProcessError:
                raise RuntimeError("Repository is locked and could not be unlocked automatically")

    def backup_stdin(self, filename: str, tags: list[str], stdin: IO[bytes]) -> dict:
        """
        Backup from stdin stream, return snapshot info.

        This method handles the complexity of piping external data into restic:
        1. Spawns restic backup process with stdin connected to provided stream
        2. Waits for completion
        3. Parses JSON output for snapshot info
        4. Raises on non-zero exit

        Args:
            filename: Virtual filename for the stdin content (e.g., "kriib.sql")
            tags: List of tags to apply to snapshot
            stdin: File-like object to read from (e.g., ssh_proc.stdout)

        Returns:
            Dict with snapshot info. Key fields:
              - snapshot_id: Short ID of created snapshot
              - total_bytes_processed: Size of backed up data

        Raises:
            subprocess.CalledProcessError: If restic exits non-zero
            json.JSONDecodeError: If output parsing fails
        """
        cmd = self._base_args() + [
            "backup", "--stdin", "--stdin-filename", filename
        ]
        for tag in tags:
            cmd.extend(["--tag", tag])

        # Run restic with stdin connected to the provided stream
        result = subprocess.run(
            cmd,
            stdin=stdin,
            capture_output=True,
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        # Parse JSON output (restic outputs multiple JSON objects, one per line)
        # The last "summary" line contains the snapshot info
        for line in result.stdout.decode().strip().split("\n"):
            if not line:
                continue
            data = json.loads(line)
            if data.get("message_type") == "summary":
                return data

        # Fallback: return empty dict if no summary found
        return {}

    def backup_path(self, path: str, tags: list[str]) -> dict:
        """
        Backup local path, return snapshot info.

        Args:
            path: Local path to backup (file or directory)
            tags: List of tags to apply to snapshot

        Returns:
            Dict with snapshot info. Key fields:
              - snapshot_id: Short ID of created snapshot
              - total_bytes_processed: Size of backed up data

        Raises:
            FileNotFoundError: If path doesn't exist
            subprocess.CalledProcessError: If restic exits non-zero
        """
        from pathlib import Path as PathLib

        if not PathLib(path).exists():
            raise FileNotFoundError(f"Path not found: {path}")

        cmd = self._base_args() + ["backup", path]
        for tag in tags:
            cmd.extend(["--tag", tag])

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        # Parse JSON output - restic outputs multiple JSON lines
        # The last "summary" line contains the snapshot info
        for line in result.stdout.decode().strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("message_type") == "summary":
                    return data
            except json.JSONDecodeError:
                continue

        # Fallback: return empty dict if no summary found
        return {}

    def snapshots(self, tags: list[str] | None = None) -> list[dict]:
        """
        List snapshots as JSON.

        Args:
            tags: Optional list of tags to filter by

        Returns:
            List of dicts with fields:
              - id: Full snapshot ID
              - short_id: Short snapshot ID (8 chars)
              - time: ISO timestamp
              - hostname: Host where backup was created
              - tags: List of tags
              - paths: List of backed up paths
        """
        args = ["snapshots"]
        if tags:
            for tag in tags:
                args.extend(["--tag", tag])

        result = self._run(args)
        return json.loads(result.stdout.decode())

    def dump(self, snapshot_id: str, path: str) -> bytes:
        """
        Dump file content from snapshot to stdout.

        This is used to extract a specific file (e.g., a database dump)
        from a snapshot without restoring the entire snapshot.

        Args:
            snapshot_id: Snapshot ID (short or full)
            path: Path within the snapshot (e.g., "/kriib.sql")

        Returns:
            Raw bytes of the file content

        Raises:
            subprocess.CalledProcessError: If snapshot or path not found
        """
        # Note: restic dump doesn't support --json, outputs raw file content
        cmd = [
            "restic",
            "--repo", self.repository,
            "--password-file", self.password_file,
            "dump", snapshot_id, path
        ]
        result = subprocess.run(cmd, capture_output=True, check=True)
        return result.stdout

    def restore(self, snapshot_id: str, target: str) -> None:
        """
        Restore snapshot to target path.

        Restores the full snapshot contents to the target directory.
        The original path structure is preserved within the target.

        Example:
            If snapshot contains /var/cache/osiris/minio/data/...
            and target is /tmp/restore, files are restored to
            /tmp/restore/var/cache/osiris/minio/data/...

        Args:
            snapshot_id: Snapshot ID (short or full)
            target: Local directory to restore to

        Raises:
            subprocess.CalledProcessError: If restore fails
        """
        from pathlib import Path

        # Ensure target directory exists
        Path(target).mkdir(parents=True, exist_ok=True)

        # Note: restore doesn't support --json for progress, uses --target
        cmd = [
            "restic",
            "--repo", self.repository,
            "--password-file", self.password_file,
            "restore", snapshot_id,
            "--target", target
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def forget(
        self,
        keep_daily: int,
        keep_weekly: int,
        keep_monthly: int,
        prune: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """
        Forget old snapshots per retention policy.

        Applies the keep-* policies to all snapshots, marking old ones
        for removal. If prune=True, also removes unreferenced data.

        Args:
            keep_daily: Keep last N daily snapshots
            keep_weekly: Keep last N weekly snapshots
            keep_monthly: Keep last N monthly snapshots
            prune: If True, also prune unreferenced data
            dry_run: If True, show what would be removed without doing it

        Returns:
            Dict with forget summary:
              - removed: List of removed snapshot IDs
              - kept: Number of snapshots kept
        """
        args = [
            "forget",
            "--keep-daily", str(keep_daily),
            "--keep-weekly", str(keep_weekly),
            "--keep-monthly", str(keep_monthly),
        ]

        if prune:
            args.append("--prune")
        if dry_run:
            args.append("--dry-run")

        result = self._run(args)

        # Parse JSON output
        # restic forget --json outputs multiple lines, one per snapshot group
        output = result.stdout.decode().strip()
        if not output:
            return {"removed": [], "kept": 0}

        # Collect all removed snapshots
        removed = []
        kept = 0
        for line in output.split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                # Each line is a group with "keep" and "remove" arrays
                if "remove" in data:
                    removed.extend(s.get("short_id", s.get("id", "")) for s in data["remove"])
                if "keep" in data:
                    kept += len(data["keep"])
            except json.JSONDecodeError:
                continue

        return {"removed": removed, "kept": kept}

    def check(self, read_data: bool = False) -> tuple[bool, str]:
        """
        Verify repository integrity.

        Runs restic check to verify:
        - Pack files are complete and valid
        - Index is consistent
        - Snapshots are valid
        - (if read_data) All data can be read

        Args:
            read_data: If True, also read and verify all data blobs.
                      This is slow but thorough.

        Returns:
            Tuple of (success: bool, message: str)
        """
        args = ["check"]
        if read_data:
            args.append("--read-data")

        try:
            result = subprocess.run(
                [
                    "restic",
                    "--repo", self.repository,
                    "--password-file", self.password_file,
                ] + args,
                capture_output=True,
                check=True,
            )
            return True, result.stdout.decode().strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.decode().strip()

    def key_list(self) -> list[dict]:
        """
        List repository keys.

        Returns:
            List of dicts with fields:
              - id: Key ID
              - user: Username that created the key
              - host: Hostname where key was created
              - created: ISO timestamp
              - current: True if this is the active key
        """
        result = self._run(["key", "list"])
        return json.loads(result.stdout.decode())

    def key_add(self, new_password: str) -> str:
        """
        Add new key to repository.

        The new password is provided via stdin to avoid command-line exposure.

        Args:
            new_password: The new password for the additional key

        Returns:
            Key ID of the newly added key

        Raises:
            subprocess.CalledProcessError: If key creation fails
        """
        # restic key add reads new password from stdin
        cmd = [
            "restic",
            "--repo", self.repository,
            "--password-file", self.password_file,
            "key", "add", "--new-password-file", "/dev/stdin"
        ]
        result = subprocess.run(
            cmd,
            input=(new_password + "\n").encode(),
            capture_output=True,
            check=True,
        )

        # Parse output to extract key ID
        # Output format: "saved new key as <key_id>"
        output = result.stdout.decode().strip()
        if "saved new key as" in output:
            return output.split()[-1]

        return ""

    def key_remove(self, key_id: str) -> None:
        """
        Remove key from repository.

        Warning: Cannot remove the currently active key.

        Args:
            key_id: Key ID to remove

        Raises:
            subprocess.CalledProcessError: If removal fails
            ValueError: If trying to remove the active key
        """
        # Verify we're not removing the active key
        keys = self.key_list()
        for key in keys:
            if key.get("id", "").startswith(key_id) and key.get("current"):
                raise ValueError("Cannot remove the currently active key")

        cmd = [
            "restic",
            "--repo", self.repository,
            "--password-file", self.password_file,
            "key", "remove", key_id
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    def stats(self, mode: str = "restore-size") -> dict:
        """
        Get repository statistics.

        Args:
            mode: Stats mode, one of:
              - "restore-size": Size if all data was restored (default)
              - "files-by-contents": File count grouped by contents
              - "blobs-per-file": Blob usage per file
              - "raw-data": Raw data size in repository

        Returns:
            Dict with stats, format depends on mode. For restore-size:
              - total_size: Total bytes
              - total_file_count: Number of files
        """
        args = ["stats", "--mode", mode]
        result = self._run(args)
        return json.loads(result.stdout.decode())
```

**Restic JSON Output Reference**:

`restic backup --json` outputs newline-delimited JSON. The final line is a summary:
```json
{"message_type":"summary","files_new":1,"files_changed":0,"files_unmodified":0,
 "dirs_new":1,"dirs_changed":0,"dirs_unmodified":0,"data_blobs":1,"tree_blobs":2,
 "data_added":1234567,"total_files_processed":1,"total_bytes_processed":1234567,
 "total_duration":1.234,"snapshot_id":"abc12345"}
```

`restic snapshots --json` outputs an array:
```json
[{"time":"2026-01-03T02:00:00Z","hostname":"backup-01","tags":["osiris:20260103-020000"],
  "paths":["/stdin"],"id":"abc12345...","short_id":"abc12345"}]
```

### 1.7 Utils Module (`src/osiris/utils.py`)

Shared formatting utilities:

```python
from datetime import datetime, timezone

def parse_timestamp(iso_string: str) -> datetime:
    """
    Parse ISO timestamp from restic, handling Z suffix.

    Restic outputs timestamps like "2026-01-03T02:00:00.123456789Z".
    This function handles the Z suffix and returns a timezone-aware datetime.

    Usage:
        created_dt = parse_timestamp(snapshot["time"])
        age = datetime.now(timezone.utc) - created_dt
    """
    # Handle Z suffix (UTC indicator)
    if iso_string.endswith("Z"):
        iso_string = iso_string[:-1] + "+00:00"

    # Handle nanosecond precision (Python only supports microseconds)
    # Truncate to microseconds if needed
    if "." in iso_string:
        base, frac_and_tz = iso_string.split(".", 1)
        # Find where timezone starts (+ or - after the decimal)
        for i, c in enumerate(frac_and_tz):
            if c in "+-":
                frac = frac_and_tz[:i]
                tz = frac_and_tz[i:]
                break
        else:
            frac = frac_and_tz
            tz = ""

        # Truncate to 6 digits (microseconds)
        frac = frac[:6].ljust(6, "0")
        iso_string = f"{base}.{frac}{tz}"

    return datetime.fromisoformat(iso_string)


def format_age(dt: datetime) -> str:
    """
    Format a datetime as a human-readable age string.

    Examples:
        "just now", "5 minutes ago", "2 hours ago", "3 days ago"
    """
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def format_size(bytes: int) -> str:
    """
    Format bytes as human-readable size.

    Examples:
        format_size(1024) -> "1.0 KB"
        format_size(1536000) -> "1.5 MB"
        format_size(2147483648) -> "2.0 GB"
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(bytes) < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """
    Format seconds as human-readable duration.

    Examples:
        format_duration(45) -> "45s"
        format_duration(125) -> "2m 5s"
        format_duration(3725) -> "1h 2m 5s"
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"
```

### 1.8 CLI Entry Point (`src/osiris/cli.py`)

```python
import atexit
import signal
import sys
import click
from iris import UI

# Global reference for cleanup on signals
_active_ssh_manager: SSHManager | None = None

def _cleanup_handler(signum, frame):
    """Clean up SSH ControlMasters on SIGINT/SIGTERM."""
    if _active_ssh_manager is not None:
        _active_ssh_manager.close_all()
    sys.exit(128 + signum)

def register_cleanup(ssh_manager: SSHManager) -> None:
    """Register SSH manager for cleanup on interrupt."""
    global _active_ssh_manager
    _active_ssh_manager = ssh_manager
    signal.signal(signal.SIGINT, _cleanup_handler)
    signal.signal(signal.SIGTERM, _cleanup_handler)
    atexit.register(ssh_manager.close_all)

def unregister_cleanup() -> None:
    """Unregister cleanup handlers after normal completion."""
    global _active_ssh_manager
    _active_ssh_manager = None
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

@click.group()
@click.option("--config", "-c", default="/etc/osiris/config.yaml")
@click.option("--non-interactive", is_flag=True)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--debug", "-d", is_flag=True, help="Enable debug output")
@click.pass_context
def cli(ctx, config, non_interactive, verbose, debug):
    """Osiris - Backup management for Kriib infrastructure."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)
    ctx.obj["ui"] = UI(interactive=not non_interactive, verbose=verbose, debug=debug)
    ctx.obj["logger"] = setup_logging(ctx.obj["config"].logging)

# Register subcommands
cli.add_command(backup)
cli.add_command(restore)
cli.add_command(list_cmd)
cli.add_command(show)
cli.add_command(status)
cli.add_command(verify)
cli.add_command(prune)
cli.add_command(chpass)
cli.add_command(init)
cli.add_command(unlock)
cli.add_command(validate)
```

---

## Phase 2: Target Abstraction

### 2.1 Result Types (`src/osiris/results.py`)

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class BackupItemResult:
    """Result of backing up a single item (database, path, etc.)."""
    target: str           # Target name (e.g., "postgres")
    item: str             # Item name (e.g., "kriib" or "/var/lib/minio/data")
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
        return all(r.success for r in self.results)

    @property
    def any_succeeded(self) -> bool:
        return any(r.success for r in self.results)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)
```

### 2.2 Base Target (`src/osiris/targets/base.py`)

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from osiris.results import BackupItemResult

if TYPE_CHECKING:
    from osiris.restic import Restic

class BackupTarget(ABC):
    name: str

    @abstractmethod
    def backup(self, restic: "Restic", batch_id: str, ssh: "SSHManager") -> list[BackupItemResult]:
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
```

### 2.3 PostgreSQL Target (`src/osiris/targets/postgres.py`)

**Multi-database support with tagging**:

```python
import time
import shlex
from osiris.results import BackupItemResult

class PostgresTarget(BackupTarget):
    def __init__(
        self,
        name: str,
        host: str,
        user: str,
        databases: list[str],
        exclude: list[str] | None = None,
        port: int = 5432,
        ssh_user: str | None = None,
        ssh_key_file: str | None = None,
    ):
        self.name = name
        self.host = host
        self.user = user  # PostgreSQL user (not SSH user)
        self.databases = databases
        self.exclude = exclude or ["template0", "template1", "postgres"]
        self.port = port
        self.ssh_user = ssh_user
        self.ssh_key_file = ssh_key_file

    def backup(self, restic: Restic, batch_id: str, ssh: "SSHManager") -> list[BackupItemResult]:
        """
        Backup each database, return list of results.

        For each database:
          1. SSH to host, run pg_dump --create --clean --if-exists
          2. Pipe stdout to restic backup --stdin
          3. Tag with: osiris:{batch_id}, target:{name}, database:{db}

        Using --create preserves database owner, encoding, tablespace, etc.
        Using --clean --if-exists allows restore to drop/recreate automatically.
        """
        results = []
        databases = self._resolve_databases(ssh)

        # Get SSH connection for this target (uses target overrides or global defaults)
        conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)

        for db in databases:
            start_time = time.time()
            ssh_proc = None
            try:
                # Ensure SSH master is alive before each database backup
                ssh.ensure_master(conn)

                # pg_dump with --create includes CREATE DATABASE with full options
                # --clean adds DROP statements, --if-exists prevents errors on fresh restore
                pg_dump_cmd = f"pg_dump -U {self.user} -p {self.port} --create --clean --if-exists {shlex.quote(db)}"
                ssh_cmd = ssh.get_ssh_cmd(conn, pg_dump_cmd)
                ssh_proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                # Pipe flow for large databases:
                # ┌─────────┐    pipe    ┌────────┐
                # │ pg_dump │ ────────── │ restic │
                # └─────────┘  (kernel   └────────┘
                #              managed)
                #
                # Both processes run concurrently. The kernel manages pipe buffering
                # (typically 64KB on Linux). If pg_dump writes faster than restic reads,
                # pg_dump blocks (backpressure). This is safe and handles databases of
                # any size without memory issues in Python.
                #
                # Error scenarios:
                # - restic fails early: pg_dump gets SIGPIPE when writing to closed pipe
                # - pg_dump fails: restic gets EOF and completes (we check ssh_proc.returncode)
                snapshot = restic.backup_stdin(
                    filename=f"{db}.sql",
                    tags=[f"osiris:{batch_id}", f"target:{self.name}", f"database:{db}"],
                    stdin=ssh_proc.stdout,
                )

                # After restic completes (read until EOF), pg_dump should have finished.
                # Use short timeout since pg_dump should already be done; if not, it's stuck.
                try:
                    _, stderr = ssh_proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    ssh_proc.kill()
                    ssh_proc.wait()
                    raise RuntimeError("pg_dump hung after restic completed (killed)")

                if ssh_proc.returncode != 0:
                    # Include pg_dump stderr in the error
                    pg_dump_error = stderr.decode().strip() if stderr else "unknown error"
                    raise RuntimeError(f"pg_dump failed: {pg_dump_error}")

                results.append(BackupItemResult(
                    target=self.name,
                    item=db,
                    success=True,
                    snapshot_id=snapshot.get("snapshot_id"),
                    size_bytes=snapshot.get("total_bytes_processed"),
                    duration_seconds=time.time() - start_time,
                ))

            except Exception as e:
                # Ensure SSH process is cleaned up on error
                if ssh_proc is not None:
                    ssh_proc.kill()
                    ssh_proc.wait()

                results.append(BackupItemResult(
                    target=self.name,
                    item=db,
                    success=False,
                    error=str(e),
                    duration_seconds=time.time() - start_time,
                ))

        return results

    def restore(self, restic: Restic, snapshot_id: str, ssh: "SSHManager") -> None:
        """
        Restore database from snapshot.

        Since backup uses pg_dump --create --clean --if-exists, the dump contains:
          - DROP DATABASE IF EXISTS
          - CREATE DATABASE with owner/encoding/tablespace
          - \connect to database
          - DROP/CREATE for all objects

        We restore by piping to psql connected to 'postgres' (maintenance db).
        The dump handles database creation itself.
        """
        import time as time_module

        # Query snapshot by ID
        all_snapshots = restic.snapshots()
        snapshot = next(
            s for s in all_snapshots
            if s.get("short_id") == snapshot_id or s.get("id", "").startswith(snapshot_id)
        )

        # Extract database name from tags (for terminating connections)
        db_tag = next(t for t in snapshot.get("tags", []) if t.startswith("database:"))
        db_name = db_tag.split(":", 1)[1]

        # Get SSH connection for this target
        conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)

        # Terminate connections and restore with retry
        # Race condition: new connections may be established between termination and restore.
        # We retry a few times to handle this case.
        #
        # Using psql -v variable binding to safely pass db_name (prevents SQL injection)
        # How this works:
        # 1. shlex.quote(db_name) escapes for the remote shell (e.g., "my-db" -> "'my-db'")
        # 2. Remote shell parses and passes unquoted value to psql's -v option
        # 3. psql stores variable "dbname" with value "my-db"
        # 4. In SQL, :'dbname' substitutes as a properly-quoted string literal
        terminate_sql = """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = :'dbname' AND pid <> pg_backend_pid();
        """
        terminate_cmd = f"psql -U {self.user} -d postgres -v dbname={shlex.quote(db_name)} -c {shlex.quote(terminate_sql)}"

        # Get dump data once (may be large, don't re-fetch on retry)
        dump_data = restic.dump(snapshot_id, f"/{db_name}.sql")
        restore_cmd = f"psql -U {self.user} -d postgres"

        max_retries = 3
        for attempt in range(max_retries):
            # Terminate active connections
            subprocess.run(
                ssh.get_ssh_cmd(conn, terminate_cmd),
                check=False,  # OK if no connections to terminate
                capture_output=True
            )

            # Attempt restore immediately after termination
            result = subprocess.run(
                ssh.get_ssh_cmd(conn, restore_cmd),
                input=dump_data,
                capture_output=True
            )

            if result.returncode == 0:
                return  # Success

            stderr = result.stderr.decode()
            # Check if failure is due to active connections (race condition)
            if "is being accessed by other users" in stderr and attempt < max_retries - 1:
                time_module.sleep(0.5)  # Brief pause before retry
                continue

            # Non-recoverable error or max retries exceeded
            raise RuntimeError(f"psql restore failed: {stderr}")

    def _resolve_databases(self, ssh: "SSHManager") -> list[str]:
        """Resolve database list, expanding ["*"] to actual databases."""
        if self.databases == ["*"]:
            conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
            psql_cmd = f'psql -U {self.user} -t -c "SELECT datname FROM pg_database WHERE datistemplate = false"'
            cmd = ssh.get_ssh_cmd(conn, psql_cmd)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            all_dbs = [db.strip() for db in result.stdout.strip().split("\n") if db.strip()]
            return [db for db in all_dbs if db not in self.exclude]
        return self.databases

    def check_connectivity(self, ssh: "SSHManager") -> bool:
        """Verify SSH and pg_dump availability."""
        try:
            conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
            subprocess.run(
                ssh.get_ssh_cmd(conn, "which pg_dump"),
                capture_output=True, check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_snapshot_items(self) -> list[str]:
        """
        Return configured database list.

        Note: Returns ["*"] if configured for all databases.
        Use _resolve_databases(ssh) during backup to get actual list.
        """
        return self.databases
```

### 2.4 Rsync Target (`src/osiris/targets/rsync.py`)

**Two-step rsync + restic backup**:

```python
import time
from pathlib import Path
from osiris.results import BackupItemResult

class RsyncTarget(BackupTarget):
    def __init__(
        self,
        name: str,
        host: str,
        path: str,
        staging_dir: str | None = None,
        ssh_user: str | None = None,
        ssh_key_file: str | None = None,
    ):
        self.name = name
        self.host = host
        self.path = path
        self.staging_dir = staging_dir or f"/var/cache/osiris/{name}"
        self.ssh_user = ssh_user
        self.ssh_key_file = ssh_key_file

    def _get_rsync_ssh_opts(self, ssh: "SSHManager") -> list[str]:
        """Build rsync -e option for SSH with ControlMaster."""
        conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
        ssh_opts = f"ssh -i {conn.key_file}"
        if ssh.config.control_master:
            ssh_opts += f" -o ControlPath={conn.control_path} -o ControlMaster=auto"
        return ["-e", ssh_opts]

    def _get_rsync_remote(self, ssh: "SSHManager") -> str:
        """Build rsync remote string (user@host:path)."""
        conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
        return f"{conn.user}@{conn.host}"

    def backup(self, restic: Restic, batch_id: str, ssh: "SSHManager") -> list[BackupItemResult]:
        """
        Two-step backup:
          1. rsync from remote to staging (data subdir)
          2. restic backup staging/data directory
          3. Leave staging for faster incremental rsync next time
        """
        start_time = time.time()
        # Use a 'data' subdir so restore path handling is clean
        data_dir = f"{self.staging_dir}/data"

        try:
            Path(data_dir).mkdir(parents=True, exist_ok=True)

            # Step 1: rsync from remote to staging/data
            remote = self._get_rsync_remote(ssh)
            rsync_cmd = [
                "rsync", "-az", "--delete",
                *self._get_rsync_ssh_opts(ssh),
                f"{remote}:{self.path}/",
                f"{data_dir}/"
            ]
            subprocess.run(rsync_cmd, check=True)

            # Step 2: restic backup the data directory
            # Using cwd approach so paths in snapshot are relative
            snapshot = restic.backup_path(
                path=data_dir,
                tags=[f"osiris:{batch_id}", f"target:{self.name}"],
            )

            return [BackupItemResult(
                target=self.name,
                item=self.path,
                success=True,
                snapshot_id=snapshot.get("snapshot_id"),  # restic JSON field name
                size_bytes=snapshot.get("total_bytes_processed"),
                duration_seconds=time.time() - start_time,
            )]
        except Exception as e:
            return [BackupItemResult(
                target=self.name,
                item=self.path,
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
            )]

    def restore(self, restic: Restic, snapshot_id: str, ssh: "SSHManager") -> None:
        """
        Restore to remote via rsync:
          1. restic restore to temp directory
          2. Find the actual data (handles nested path issue)
          3. rsync to remote

        Note: restic restore preserves the original backup path structure.
        If we backed up /var/cache/osiris/minio/data, restoring to /tmp/restore
        creates /tmp/restore/var/cache/osiris/minio/data/...

        We handle this by finding the deepest directory that contains our data.
        """
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as restore_root:
            # Restore snapshot to temp directory
            restic.restore(snapshot_id, restore_root)

            # Find the actual data directory (restic preserves full path)
            # Walk down to find where our files are
            restored_data = self._find_restored_data(restore_root)

            # Rsync restored data to remote
            remote = self._get_rsync_remote(ssh)
            rsync_cmd = [
                "rsync", "-az", "--delete",
                *self._get_rsync_ssh_opts(ssh),
                f"{restored_data}/",
                f"{remote}:{self.path}/"
            ]
            subprocess.run(rsync_cmd, check=True)

    def _find_restored_data(self, restore_root: str) -> str:
        """
        Find the actual data directory within the restored tree.

        Restic preserves the full path, so if we backed up
        /var/cache/osiris/minio/data, restoring to /tmp/restore creates:
        /tmp/restore/var/cache/osiris/minio/data/...

        We need to return the path to where the actual data files are.

        Edge cases handled:
        - Symlinks: followed but with loop detection
        - Empty directories: treated as data (might be intentional)
        - Max depth: prevents infinite loops in malformed restores
        """
        # The staging data dir we backed up
        expected_suffix = f"{self.staging_dir}/data"

        # Check if it exists at the expected nested path
        nested_path = Path(f"{restore_root}{expected_suffix}")
        if nested_path.exists():
            # Resolve symlinks to get real path
            return str(nested_path.resolve())

        # Fallback: walk down single-child directory chains
        # e.g., /tmp/restore/var/cache/osiris/minio/data
        # where each level has only one subdirectory
        current = Path(restore_root).resolve()
        visited: set[str] = set()  # Loop detection for symlinks
        max_depth = 50  # Prevent infinite loops in pathological cases

        for _ in range(max_depth):
            # Check for symlink loops
            current_str = str(current)
            if current_str in visited:
                break
            visited.add(current_str)

            if not current.is_dir():
                break

            try:
                children = list(current.iterdir())
            except PermissionError:
                break

            # Separate files, dirs, and symlinks (resolving symlinks to check type)
            files = []
            subdirs = []
            for c in children:
                try:
                    if c.is_symlink():
                        # Follow symlink to determine actual type
                        resolved = c.resolve()
                        if resolved.is_file():
                            files.append(c)
                        elif resolved.is_dir():
                            subdirs.append(c)
                    elif c.is_file():
                        files.append(c)
                    elif c.is_dir():
                        subdirs.append(c)
                except (OSError, PermissionError):
                    continue  # Skip inaccessible entries

            # If there are files here, or multiple/zero subdirs, we've found our data
            if files or len(subdirs) != 1:
                break

            # Otherwise, descend into the single subdirectory
            current = subdirs[0].resolve() if subdirs[0].is_symlink() else subdirs[0]

        return str(current)

    def check_connectivity(self, ssh: "SSHManager") -> bool:
        """Verify SSH and remote path exists."""
        try:
            conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
            subprocess.run(
                ssh.get_ssh_cmd(conn, f"test -d {self.path}"),
                capture_output=True, check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_snapshot_items(self) -> list[str]:
        """Return the remote path."""
        return [self.path]
```

---

## Phase 3: Core Commands

### 3.1 Backup Command (`src/osiris/commands/backup.py`)

```python
@click.command()
@click.option("--target", "-t", help="Backup specific target only")
@click.option("--force", is_flag=True, help="Proceed without confirmation (required in non-interactive mode)")
@click.pass_context
def backup(ctx, target, force):
    """Create a new backup of all configured targets."""
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    restic = Restic(config.repository, config.password_file)

    # In non-interactive mode, --force is required to proceed
    if not ui.interactive and not force:
        ui.error("Non-interactive mode requires --force flag")
        raise SystemExit(1)

    # Check for stale locks from interrupted backups
    restic.ensure_unlocked(ui, logger)
```

**Flow**:
0. Check for stale locks (auto-unlock if interrupted backup)
1. Generate batch ID: `YYYYMMDD-HHMMSS`
2. For each target (or specified target):
   - For PostgreSQL: iterate over databases
   - For Rsync: single backup operation
   - Tag all snapshots with `osiris:{batch_id}`
3. Continue on failure, track partial success
4. Print summary table
5. Exit non-zero if any failures

**Output Example (multi-database)**:
```
═══════════════════════════════════════════════════════════════════
Creating Backup
═══════════════════════════════════════════════════════════════════

[1/2] Backing up postgres...
  [1/2] Backing up database: kriib
  [>] Running: ssh postgres-01 "pg_dump -U postgres kriib" | restic backup --stdin
  [✓] kriib complete (1.2 GB)
  [2/2] Backing up database: analytics
  [>] Running: ssh postgres-01 "pg_dump -U postgres analytics" | restic backup --stdin
  [✓] analytics complete (800 MB)
[✓] postgres complete

[2/2] Backing up minio...
  [>] Running: rsync -az minio-01:/var/lib/minio/data/ /var/cache/osiris/minio/
  [>] Running: restic backup /var/cache/osiris/minio
  [✓] minio complete (1.1 GB)

[✓] Backup 20260103-020000 created successfully

Target    Item        Size     Duration   Status
───────────────────────────────────────────────────
postgres  kriib       1.2 GB   30s        OK
postgres  analytics   800 MB   25s        OK
minio     (all)       1.1 GB   80s        OK

Total                 3.1 GB   2m 15s
```

### 3.2 Restore Command (`src/osiris/commands/restore.py`)

```python
from osiris.batch import resolve_batch, parse_target_info

@click.command()
@click.option("--batch-id", "-b", required=True, help="Batch ID to restore (e.g., 20260103-020000)")
@click.option("--target", "-t", help="Restore specific target only")
@click.option("--database", "-d", help="Restore specific database (postgres only)")
@click.option("--force", is_flag=True, help="Required for non-interactive mode")
@click.option("--dry-run", is_flag=True, help="Show what would be restored without doing it")
@click.pass_context
def restore(ctx, batch_id, target, database, force, dry_run):
    """
    Restore from a backup.

    WARNING: This is a destructive operation!
    - PostgreSQL: Drops and recreates databases
    - Rsync: Overwrites remote files with backup contents
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    restic = Restic(config.repository, config.password_file)

    # In non-interactive mode, --force is required
    if not ui.interactive and not force:
        ui.error("Non-interactive mode requires --force flag for restore")
        raise SystemExit(1)

    # Check for stale locks
    restic.ensure_unlocked(ui, logger)

    # Resolve batch ID to snapshots
    try:
        snapshots = resolve_batch(restic, batch_id, target, database)
    except ValueError as e:
        ui.error(str(e))
        raise SystemExit(1)

    if not snapshots:
        ui.error(f"No snapshots found for batch {batch_id}")
        raise SystemExit(1)

    # Build list of what will be restored
    ui.header("Restore Plan")
    restore_items = []

    for snap in snapshots:
        target_name, item = parse_target_info(snap)
        if target_name is None:
            continue

        target_config = config.targets.get(target_name)
        if target_config is None:
            ui.warning(f"Target '{target_name}' not in current config, skipping")
            continue

        restore_items.append({
            "snapshot": snap,
            "target_name": target_name,
            "target_config": target_config,
            "item": item,
        })

    if not restore_items:
        ui.error("No restorable items found")
        raise SystemExit(1)

    # Show what will be restored
    table = ui.table(["Target", "Item", "Snapshot", "Action"])
    for item in restore_items:
        if item["target_config"].type == "pg_dump":
            action = f"DROP + CREATE database '{item['item']}'"
        else:
            action = f"Overwrite {item['target_config'].path}"

        table.add_row(
            item["target_name"],
            item["item"] or "(all)",
            item["snapshot"].get("short_id", "unknown"),
            action,
        )
    table.render()

    # Dry-run stops here
    if dry_run:
        ui.info("Dry-run complete. No changes made.")
        return

    # Confirm destructive operation
    ui.warning("\nWARNING: This is a destructive operation!")
    if any(i["target_config"].type == "pg_dump" for i in restore_items):
        ui.warning("PostgreSQL databases will be DROPPED and recreated.")
    if any(i["target_config"].type == "rsync" for i in restore_items):
        ui.warning("Remote files will be OVERWRITTEN with backup contents.")

    if ui.interactive:
        if not ui.confirm("\nProceed with restore?", default=False):
            ui.info("Restore cancelled")
            raise SystemExit(0)
    # Non-interactive already checked for --force above

    # Perform restore
    logger.info(f"Starting restore from batch {batch_id}")
    ui.header("Restoring")

    with SSHManager(config.ssh) as ssh:
        register_cleanup(ssh)

        try:
            # Start SSH masters for all target hosts
            for item in restore_items:
                tc = item["target_config"]
                conn = ssh.get_connection(tc.host, tc.ssh_user, tc.ssh_key_file)
                ssh.start_master(conn)

            # Perform restores
            failed = []
            succeeded = []

            for i, item in enumerate(restore_items, 1):
                target_name = item["target_name"]
                target_config = item["target_config"]
                snapshot = item["snapshot"]
                item_name = item["item"] or target_config.path

                ui.step(i, len(restore_items), f"Restoring {target_name}: {item_name}")
                logger.info(f"Restoring {target_name}: {item_name} from {snapshot.get('short_id')}")

                try:
                    # Create target instance
                    if target_config.type == "pg_dump":
                        target_instance = PostgresTarget(
                            name=target_name,
                            host=target_config.host,
                            user=target_config.pg_user,
                            databases=[item["item"]],
                            port=target_config.port,
                            ssh_user=target_config.ssh_user,
                            ssh_key_file=target_config.ssh_key_file,
                        )
                    else:
                        target_instance = RsyncTarget(
                            name=target_name,
                            host=target_config.host,
                            path=target_config.path,
                            staging_dir=target_config.staging_dir,
                            ssh_user=target_config.ssh_user,
                            ssh_key_file=target_config.ssh_key_file,
                        )

                    target_instance.restore(restic, snapshot.get("short_id"), ssh)
                    ui.success(f"{item_name} restored")
                    logger.info(f"Restored {target_name}: {item_name}")
                    succeeded.append(item_name)

                except Exception as e:
                    ui.error(f"{item_name} failed: {e}")
                    logger.error(f"Failed to restore {target_name}: {item_name}: {e}")
                    failed.append((item_name, str(e)))

        finally:
            unregister_cleanup()

    # Summary
    ui.header("Restore Summary")
    if succeeded:
        ui.success(f"Restored: {', '.join(succeeded)}")
    if failed:
        ui.error(f"Failed ({len(failed)}):")
        for name, error in failed:
            ui.error(f"  {name}: {error}")

    if failed:
        raise SystemExit(1)
    else:
        logger.info(f"Restore from batch {batch_id} completed successfully")
        ui.success("Restore completed successfully")
```

**Flow**:
1. Resolve batch ID to snapshot IDs using `resolve_batch()` helper
2. Build restore plan showing what will happen
3. Show warning: "This will DROP and recreate the following databases: ..."
4. If dry-run: show plan and exit
5. Require confirmation (interactive) or `--force` (non-interactive)
6. For each target/database:
   - Create target instance from config
   - Call `target.restore()`
   - Track success/failure
7. Print summary, exit non-zero if any failures

### 3.3 Init Command (`src/osiris/commands/init.py`)

```python
import os
import secrets
import string
from pathlib import Path

@click.command()
@click.option("--generate-password", is_flag=True, help="Generate a random password instead of prompting")
@click.pass_context
def init(ctx):
    """Initialize the restic repository and create password file."""
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    restic = ctx.obj["restic"]

    # Check if repository already exists
    if restic.is_initialized():
        ui.error("Repository already initialized")
        raise SystemExit(1)

    password_path = Path(config.password_file)

    # Check if password file already exists
    if password_path.exists():
        ui.error(f"Password file already exists: {password_path}")
        ui.hint("Remove it first if you want to reinitialize")
        raise SystemExit(1)

    # Get or generate password
    if ctx.params.get("generate_password"):
        # Generate 32-character random password
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        password = "".join(secrets.choice(alphabet) for _ in range(32))
        ui.info("Generated random password")
    else:
        if not ui.interactive:
            ui.error("Cannot prompt for password in non-interactive mode")
            ui.hint("Use --generate-password to auto-generate")
            raise SystemExit(1)

        password = ui.prompt("Enter repository password", mask=True)
        confirm = ui.prompt("Confirm password", mask=True)

        if password != confirm:
            ui.error("Passwords do not match")
            raise SystemExit(1)

        if len(password) < 8:
            ui.warning("Password is very short (< 8 characters)")
            if not ui.confirm("Continue anyway?"):
                raise SystemExit(1)

    # Create password file with restricted permissions
    try:
        # Ensure parent directory exists
        password_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file with restricted permissions (before writing)
        # This prevents a race condition where the file is briefly world-readable
        fd = os.open(
            password_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode=0o400,  # Owner read-only
        )
        with os.fdopen(fd, "w") as f:
            # Add trailing newline - restic reads until newline or EOF
            # Having a newline is more standard and avoids potential issues
            f.write(password + "\n")

        ui.success(f"Created password file: {password_path}")

    except PermissionError:
        ui.error(f"Permission denied creating: {password_path}")
        ui.hint("Run as root or check directory permissions")
        raise SystemExit(1)
    except FileExistsError:
        ui.error(f"Password file already exists: {password_path}")
        raise SystemExit(1)

    # Initialize restic repository
    try:
        restic.init()
        ui.success(f"Initialized repository: {config.repository}")
    except Exception as e:
        # Clean up password file on failure
        password_path.unlink(missing_ok=True)
        ui.error(f"Failed to initialize repository: {e}")
        raise SystemExit(1)

    # Show generated password if applicable
    if ctx.params.get("generate_password"):
        ui.warning("IMPORTANT: Save this password securely!")
        ui.info(f"Password: {password}")
        ui.hint("This is the only time the password will be displayed")

    # Install logrotate config
    _install_logrotate_config(ui, config)


LOGROTATE_CONFIG = """\
/var/log/osiris/osiris.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
"""

def _install_logrotate_config(ui: "UI", config: "Config") -> None:
    """
    Install logrotate configuration for Osiris logs.

    Only installs if:
    - File logging is enabled in config
    - /etc/logrotate.d/ exists (logrotate is installed)
    - Config file doesn't already exist
    """
    logrotate_path = Path("/etc/logrotate.d/osiris")
    logrotate_dir = logrotate_path.parent

    # Skip if file logging is disabled
    if config.logging.file is None:
        ui.info("File logging disabled, skipping logrotate config")
        return

    # Skip if logrotate not installed
    if not logrotate_dir.exists():
        ui.warning("logrotate not installed (/etc/logrotate.d/ not found), skipping")
        return

    # Skip if already exists
    if logrotate_path.exists():
        ui.info("Logrotate config already exists, skipping")
        return

    # Generate config with actual log path from config
    log_path = config.logging.file
    logrotate_content = f"""\
{log_path} {{
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}}
"""

    try:
        logrotate_path.write_text(logrotate_content)
        ui.success(f"Created logrotate config: {logrotate_path}")
    except PermissionError:
        ui.warning(f"Could not create logrotate config (permission denied): {logrotate_path}")
        ui.hint("Run as root or manually create the logrotate config")
```

**Flow**:
1. Check if repository already exists
2. Prompt for password (or generate with `--generate-password`)
3. Create password file with chmod 400 (using atomic file creation)
4. Run `restic init`
5. Clean up password file if init fails
6. Display generated password if applicable
7. Install logrotate config (if logging to file and logrotate is available)

---

## Phase 4: Status & Listing Commands

### 4.1 Batch Resolution Helper (`src/osiris/batch.py`)

Helper functions for resolving batch IDs to snapshots with edge case handling:

```python
from dataclasses import dataclass
from typing import Iterator

@dataclass
class BatchInfo:
    """Information about a backup batch."""
    batch_id: str
    snapshots: list[dict]  # Raw restic snapshot dicts
    targets: dict[str, list[str]]  # target_name -> [items] (e.g., {"postgres": ["kriib", "analytics"]})
    created: str  # ISO timestamp of earliest snapshot
    total_size: int  # Sum of all snapshot sizes

    @property
    def is_complete(self) -> bool:
        """Check if batch has all expected targets (based on config)."""
        # This is set by the caller based on config comparison
        return self._is_complete

def parse_batch_id(snapshot: dict) -> str | None:
    """Extract batch ID from snapshot tags, or None if not an Osiris snapshot."""
    for tag in snapshot.get("tags", []):
        if tag.startswith("osiris:"):
            return tag.split(":", 1)[1]
    return None

def parse_target_info(snapshot: dict) -> tuple[str, str | None]:
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
        raise ValueError(f"No snapshots in batch '{batch_id}' match filters: {', '.join(filters)}")

    return result
```

### 4.2 List Command (`src/osiris/commands/list.py`)

```python
from datetime import datetime
from osiris.batch import group_snapshots_by_batch, parse_target_info
from osiris.utils import format_age, format_size

@click.command("list")
@click.option("--target", "-t", help="Filter by target")
@click.option("--limit", "-n", default=20, help="Number of batches to show (default: 20)")
@click.pass_context
def list_cmd(ctx, target, limit):
    """List all backups."""
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    restic = Restic(config.repository, config.password_file)

    # Get all snapshots
    try:
        all_snapshots = restic.snapshots()
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to list snapshots: {e.stderr.decode()}")
        raise SystemExit(1)

    if not all_snapshots:
        ui.info("No backups found")
        return

    # Group by batch
    batches = group_snapshots_by_batch(all_snapshots)

    if not batches:
        ui.info("No Osiris backups found (snapshots exist but lack osiris: tags)")
        return

    # Build expected targets from config for status comparison
    expected_targets = set(config.targets.keys())

    # Build table data
    table_data = []
    for batch_id, batch_info in batches.items():
        # Filter by target if specified
        if target and target not in batch_info.targets:
            continue

        # Determine status
        actual_targets = set(batch_info.targets.keys())
        if actual_targets >= expected_targets:
            status = "OK"
        elif actual_targets & expected_targets:
            status = "PARTIAL"
        else:
            status = "UNKNOWN"

        # Format targets column: "postgres(2), minio"
        target_parts = []
        for t_name, items in sorted(batch_info.targets.items()):
            if len(items) > 1:
                target_parts.append(f"{t_name}({len(items)})")
            else:
                target_parts.append(t_name)
        targets_str = ", ".join(target_parts)

        # Parse created timestamp
        try:
            created_dt = datetime.fromisoformat(batch_info.created.replace("Z", "+00:00"))
            created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
            age_str = format_age(created_dt)
        except (ValueError, AttributeError):
            created_str = batch_info.created[:19] if batch_info.created else "unknown"
            age_str = "unknown"

        table_data.append({
            "batch_id": batch_id,
            "created": created_str,
            "created_dt": batch_info.created,  # For sorting
            "age": age_str,
            "targets": targets_str,
            "status": status,
        })

    # Sort by created timestamp (newest first)
    table_data.sort(key=lambda x: x["created_dt"], reverse=True)

    # Apply limit
    table_data = table_data[:limit]

    # Render table
    table = ui.table(["Batch-ID", "Created", "Age", "Targets", "Status"])
    for row in table_data:
        table.add_row(
            row["batch_id"],
            row["created"],
            row["age"],
            row["targets"],
            row["status"],
        )
    table.render()

    # Show count if limited
    total = len(batches)
    if len(table_data) < total:
        ui.info(f"Showing {len(table_data)} of {total} batches (use --limit to show more)")
```

**Output**:
```
Batch-ID         Created               Age          Targets                    Status
─────────────────────────────────────────────────────────────────────────────────────────────
20260103-020000  2026-01-03 02:00:00   4 hours ago  postgres(2), minio         OK
20260102-020000  2026-01-02 02:00:00   1 day ago    postgres(2), minio         OK
20260101-020000  2026-01-01 02:00:00   2 days ago   postgres(1), minio         PARTIAL
```

### 4.3 Show Command (`src/osiris/commands/show.py`)

```python
from datetime import datetime
from osiris.batch import group_snapshots_by_batch, parse_target_info
from osiris.utils import format_age, format_size

@click.command()
@click.argument("batch_id")
@click.pass_context
def show(ctx, batch_id):
    """
    Show details of a specific backup batch.

    BATCH_ID is the batch identifier (e.g., 20260103-020000)
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    restic = Restic(config.repository, config.password_file)

    # Get all snapshots and find the batch
    try:
        all_snapshots = restic.snapshots()
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to list snapshots: {e.stderr.decode()}")
        raise SystemExit(1)

    batches = group_snapshots_by_batch(all_snapshots)

    if batch_id not in batches:
        ui.error(f"Batch '{batch_id}' not found")
        ui.hint("Use 'osiris list' to see available batches")
        raise SystemExit(1)

    batch = batches[batch_id]

    # Header
    ui.header(f"Backup: {batch_id}")

    # Summary info
    try:
        created_dt = datetime.fromisoformat(batch.created.replace("Z", "+00:00"))
        ui.info(f"Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S')} ({format_age(created_dt)})")
    except (ValueError, AttributeError):
        ui.info(f"Created: {batch.created}")

    # Determine overall status
    expected_targets = set(config.targets.keys())
    actual_targets = set(batch.targets.keys())
    if actual_targets >= expected_targets:
        ui.success("Status: Complete")
    else:
        missing = expected_targets - actual_targets
        ui.warning(f"Status: Partial (missing: {', '.join(missing)})")

    # Snapshot details table
    print()  # Blank line
    table = ui.table(["Target", "Item", "Snapshot", "Time", "Path"])

    for snap in batch.snapshots:
        target_name, item = parse_target_info(snap)
        if target_name is None:
            continue

        snap_time = snap.get("time", "")[:19].replace("T", " ")
        paths = ", ".join(snap.get("paths", []))

        table.add_row(
            target_name,
            item or "(all)",
            snap.get("short_id", snap.get("id", "")[:8]),
            snap_time,
            paths[:40] + "..." if len(paths) > 40 else paths,
        )

    table.render()

    # Show all tags for reference
    print()
    ui.info("Tags:")
    all_tags = set()
    for snap in batch.snapshots:
        all_tags.update(snap.get("tags", []))
    for tag in sorted(all_tags):
        print(f"  {tag}")
```

**Output**:
```
═══════════════════════════════════════════════════════════════════
Backup: 20260103-020000
═══════════════════════════════════════════════════════════════════

[i] Created: 2026-01-03 02:00:00 (4 hours ago)
[✓] Status: Complete

Target    Item       Snapshot  Time                 Path
─────────────────────────────────────────────────────────────────────
postgres  kriib      abc123de  2026-01-03 02:00:15  /stdin
postgres  analytics  def456gh  2026-01-03 02:00:45  /stdin
minio     (all)      hij789kl  2026-01-03 02:01:30  /var/cache/osiris/minio/data

[i] Tags:
  database:analytics
  database:kriib
  osiris:20260103-020000
  target:minio
  target:postgres
```

### 4.4 Status Command (`src/osiris/commands/status.py`)

```python
from datetime import datetime, timezone
from osiris.batch import group_snapshots_by_batch

@click.command()
@click.pass_context
def status(ctx):
    """
    Show overall backup system status.

    Displays:
    - Last successful backup time and age
    - Repository health (locked, size)
    - Target connectivity
    - Next scheduled backup (if timer enabled)
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    restic = Restic(config.repository, config.password_file)

    ui.header("Osiris Backup Status")

    issues = []

    # 1. Repository status
    ui.info("Repository:")
    try:
        if not restic.is_initialized():
            ui.error("  Not initialized")
            issues.append("Repository not initialized")
        elif restic.is_locked():
            ui.warning("  Initialized (LOCKED - stale lock detected)")
            issues.append("Repository has stale locks")
        else:
            ui.success("  Initialized and accessible")

            # Get repo stats
            try:
                stats = restic.stats()
                total_size = stats.get("total_size", 0)
                ui.info(f"  Size: {format_size(total_size)}")
            except Exception:
                pass  # Stats are optional

    except Exception as e:
        ui.error(f"  Error accessing repository: {e}")
        issues.append(f"Repository error: {e}")

    # 2. Last backup status
    print()
    ui.info("Last Backup:")
    try:
        all_snapshots = restic.snapshots()
        batches = group_snapshots_by_batch(all_snapshots)

        if not batches:
            ui.warning("  No backups found")
            issues.append("No backups exist")
        else:
            # Find most recent batch
            sorted_batches = sorted(
                batches.items(),
                key=lambda x: x[1].created,
                reverse=True
            )
            latest_id, latest_batch = sorted_batches[0]

            # Parse timestamp
            try:
                created_dt = datetime.fromisoformat(latest_batch.created.replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - created_dt
                age_hours = age.total_seconds() / 3600

                ui.info(f"  Batch: {latest_id}")
                ui.info(f"  Time: {created_dt.strftime('%Y-%m-%d %H:%M:%S')} ({format_age(created_dt)})")

                # Check if backup is stale (>25 hours for daily backups)
                if age_hours > 25:
                    ui.warning(f"  ⚠ Last backup is {int(age_hours)} hours old")
                    issues.append(f"Last backup is {int(age_hours)} hours old")
                else:
                    ui.success("  Recent backup exists")

                # Check completeness
                expected = set(config.targets.keys())
                actual = set(latest_batch.targets.keys())
                if actual >= expected:
                    ui.success("  All targets backed up")
                else:
                    missing = expected - actual
                    ui.warning(f"  Missing targets: {', '.join(missing)}")
                    issues.append(f"Last backup missing: {', '.join(missing)}")

            except (ValueError, AttributeError) as e:
                ui.info(f"  Batch: {latest_id} (could not parse timestamp)")

    except Exception as e:
        ui.error(f"  Error checking backups: {e}")
        issues.append(f"Backup check error: {e}")

    # 3. Systemd timer status
    print()
    ui.info("Scheduled Backups:")
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "osiris-backup.timer"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            ui.success("  Timer: active")

            # Get next run time
            result = subprocess.run(
                ["systemctl", "show", "osiris-backup.timer", "--property=NextElapseUSecRealtime"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                # Parse "NextElapseUSecRealtime=Sat 2026-01-04 02:00:00 UTC"
                line = result.stdout.strip()
                if "=" in line:
                    next_time = line.split("=", 1)[1]
                    if next_time and next_time != "n/a":
                        ui.info(f"  Next run: {next_time}")
        else:
            ui.warning("  Timer: not active")
            ui.hint("  Run 'osiris service enable' to enable scheduled backups")
    except FileNotFoundError:
        ui.info("  Timer: systemd not available")

    # 4. Summary
    print()
    if issues:
        ui.warning(f"Issues detected ({len(issues)}):")
        for issue in issues:
            ui.error(f"  • {issue}")
        raise SystemExit(1)
    else:
        ui.success("All systems operational")
```

**Output**:
```
═══════════════════════════════════════════════════════════════════
Osiris Backup Status
═══════════════════════════════════════════════════════════════════

[i] Repository:
[✓]   Initialized and accessible
[i]   Size: 15.2 GB

[i] Last Backup:
[i]   Batch: 20260103-020000
[i]   Time: 2026-01-03 02:00:00 (4 hours ago)
[✓]   Recent backup exists
[✓]   All targets backed up

[i] Scheduled Backups:
[✓]   Timer: active
[i]   Next run: Sat 2026-01-04 02:00:00 UTC

[✓] All systems operational
```

---

## Phase 5: Maintenance Commands

### 5.1 Verify Command (`src/osiris/commands/verify.py`)

```python
@click.command()
@click.option("--thorough", is_flag=True, help="Read and verify all data (slow but complete)")
@click.pass_context
def verify(ctx, thorough):
    """
    Verify backup repository integrity.

    Runs restic check to verify:
    - Pack files are complete and valid
    - Index is consistent
    - Snapshots reference valid data

    Use --thorough to also read and verify all data blobs.
    This is slow but provides complete verification.
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    restic = Restic(config.repository, config.password_file)

    if thorough:
        ui.header("Verifying Repository (Thorough)")
        ui.warning("This will read ALL data and may take a long time...")
        logger.info("Starting thorough repository verification")
    else:
        ui.header("Verifying Repository")
        logger.info("Starting repository verification")

    # Check for locks first
    if restic.is_locked():
        ui.warning("Repository is locked - verification may fail")
        ui.hint("Run 'osiris unlock' to remove stale locks")

    # Run verification
    ui.info("Running restic check...")
    success, message = restic.check(read_data=thorough)

    if success:
        ui.success("Repository verification passed")
        logger.info("Repository verification passed")
        if message:
            # Show summary stats from restic
            for line in message.split("\n"):
                if line.strip():
                    ui.info(f"  {line.strip()}")
    else:
        ui.error("Repository verification FAILED")
        logger.error(f"Repository verification failed: {message}")
        if message:
            for line in message.split("\n"):
                if line.strip():
                    ui.error(f"  {line.strip()}")
        ui.hint("Repository may be corrupted. Check restic documentation for recovery options.")
        raise SystemExit(1)
```

### 5.2 Prune Command (`src/osiris/commands/prune.py`)

```python
@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be removed without doing it")
@click.option("--force", is_flag=True, help="Required for non-interactive mode")
@click.pass_context
def prune(ctx, dry_run, force):
    """
    Remove old backups per retention policy.

    Applies the retention policy from config.yaml:
    - keep_daily: Keep last N daily backups
    - keep_weekly: Keep last N weekly backups
    - keep_monthly: Keep last N monthly backups

    Snapshots outside the retention window are removed and
    unreferenced data is cleaned up.
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    restic = Restic(config.repository, config.password_file)

    retention = config.retention

    ui.header("Prune Old Backups")

    # Show retention policy
    ui.info("Retention policy:")
    ui.info(f"  Keep daily:   {retention.keep_daily}")
    ui.info(f"  Keep weekly:  {retention.keep_weekly}")
    ui.info(f"  Keep monthly: {retention.keep_monthly}")
    print()

    # In non-interactive mode without dry-run, require --force
    if not ui.interactive and not dry_run and not force:
        ui.error("Non-interactive mode requires --force flag (or use --dry-run)")
        raise SystemExit(1)

    # Confirm unless dry-run
    if not dry_run and ui.interactive:
        if not ui.confirm("Apply retention policy and remove old snapshots?", default=False):
            ui.info("Prune cancelled")
            return

    # Run forget with prune
    action = "Simulating" if dry_run else "Applying"
    ui.info(f"{action} retention policy...")
    logger.info(f"Running prune (dry_run={dry_run})")

    try:
        result = restic.forget(
            keep_daily=retention.keep_daily,
            keep_weekly=retention.keep_weekly,
            keep_monthly=retention.keep_monthly,
            prune=not dry_run,  # Only prune data if not dry-run
            dry_run=dry_run,
        )

        removed = result.get("removed", [])
        kept = result.get("kept", 0)

        if dry_run:
            ui.info(f"Would remove {len(removed)} snapshots, keep {kept}")
            if removed:
                ui.info("Snapshots to remove:")
                for snap_id in removed[:10]:  # Show first 10
                    ui.info(f"  {snap_id}")
                if len(removed) > 10:
                    ui.info(f"  ... and {len(removed) - 10} more")
        else:
            if removed:
                ui.success(f"Removed {len(removed)} snapshots, kept {kept}")
                logger.info(f"Pruned {len(removed)} snapshots")
            else:
                ui.info("No snapshots to remove")
                logger.info("Prune complete, no snapshots removed")

    except subprocess.CalledProcessError as e:
        ui.error(f"Prune failed: {e.stderr.decode()}")
        logger.error(f"Prune failed: {e}")
        raise SystemExit(1)
```

### 5.3 Chpass Command (`src/osiris/commands/chpass.py`)

```python
@click.command()
@click.option("--update-file", is_flag=True, help="Also update the password file")
@click.pass_context
def chpass(ctx):
    """
    Change repository password.

    This adds a new password to the repository. The old password
    remains valid until explicitly removed.

    Use --update-file to also update /etc/osiris/repo-password
    with the new password.

    After changing the password, you may want to remove the old key
    using 'restic key remove <key-id>' (list keys with 'restic key list').
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    restic = Restic(config.repository, config.password_file)

    if not ui.interactive:
        ui.error("Password change requires interactive mode")
        raise SystemExit(1)

    ui.header("Change Repository Password")

    # Get new password
    new_password = ui.prompt("Enter new password", mask=True)
    confirm = ui.prompt("Confirm new password", mask=True)

    if new_password != confirm:
        ui.error("Passwords do not match")
        raise SystemExit(1)

    if len(new_password) < 8:
        ui.warning("Password is very short (< 8 characters)")
        if not ui.confirm("Continue anyway?"):
            raise SystemExit(1)

    # Show current keys
    ui.info("Current repository keys:")
    try:
        keys = restic.key_list()
        for key in keys:
            current = " (current)" if key.get("current") else ""
            ui.info(f"  {key.get('id', 'unknown')[:8]}{current}")
    except Exception as e:
        ui.warning(f"Could not list keys: {e}")

    # Add new key
    ui.info("Adding new key...")
    try:
        key_id = restic.key_add(new_password)
        ui.success(f"Added new key: {key_id}")
        logger.info(f"Added new repository key: {key_id}")
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to add key: {e.stderr.decode()}")
        raise SystemExit(1)

    # Update password file if requested
    if ctx.params.get("update_file"):
        password_path = Path(config.password_file)
        try:
            # Write atomically by writing to temp file first
            temp_path = password_path.with_suffix(".new")
            fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode=0o400)
            with os.fdopen(fd, "w") as f:
                f.write(new_password + "\n")
            temp_path.rename(password_path)
            ui.success(f"Updated password file: {password_path}")
            logger.info(f"Updated password file: {password_path}")
        except Exception as e:
            ui.error(f"Failed to update password file: {e}")
            ui.warning("New key was added but password file not updated")
            ui.hint(f"Manually update {password_path} with the new password")

    # Remind about old key
    ui.info("")
    ui.hint("The old password still works. To remove it:")
    ui.hint("  1. Run 'restic -r <repo> key list' to find the old key ID")
    ui.hint("  2. Run 'restic -r <repo> key remove <old-key-id>'")
```

### 5.4 Unlock Command (`src/osiris/commands/unlock.py`)

```python
@click.command()
@click.option("--force", is_flag=True, help="Remove all locks (use with caution)")
@click.pass_context
def unlock(ctx, force):
    """
    Remove stale repository locks.

    Restic creates locks to prevent concurrent operations. If a backup
    is interrupted (crash, kill, etc.), locks may be left behind.

    This command removes stale locks so new operations can proceed.

    Use --force to remove ALL locks, including potentially active ones.
    Only use this if you're sure no other osiris/restic process is running.
    """
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    restic = Restic(config.repository, config.password_file)

    ui.header("Remove Repository Locks")

    # Check current lock status
    if not restic.is_locked():
        ui.success("Repository is not locked")
        return

    ui.warning("Repository is currently locked")

    if force:
        ui.warning("--force specified: will remove ALL locks")
        if ui.interactive:
            if not ui.confirm("Are you sure? This may corrupt the repository if another process is running."):
                ui.info("Unlock cancelled")
                return
    else:
        ui.info("Removing stale locks...")

    # Remove locks
    try:
        restic.unlock(remove_all=force)
        ui.success("Locks removed successfully")
        logger.info(f"Removed repository locks (force={force})")
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to remove locks: {e.stderr.decode()}")
        logger.error(f"Failed to unlock repository: {e}")
        raise SystemExit(1)

    # Verify
    if restic.is_locked():
        ui.warning("Repository is still locked")
        ui.hint("Try 'osiris unlock --force' if you're sure no other process is running")
    else:
        ui.success("Repository is now unlocked")
```

### 5.5 Validate Command (`src/osiris/commands/validate.py`)

```python
from pathlib import Path

@click.command()
@click.pass_context
def validate(ctx):
    """Validate configuration and connectivity."""
    ui = ctx.obj["ui"]
    config = ctx.obj["config"]
    errors = []
    warnings = []

    ui.header("Validating Osiris Configuration")

    # 1. Check SSH key file exists
    with ui.progress(["SSH key", "Password file", "Repository", "Targets", "Tools"]) as p:
        p.start("SSH key")
        if not Path(config.ssh.key_file).exists():
            errors.append(f"SSH key file not found: {config.ssh.key_file}")
            p.fail("SSH key", "not found")
        else:
            # Check permissions (should be 600 or 400)
            mode = Path(config.ssh.key_file).stat().st_mode & 0o777
            if mode not in (0o600, 0o400):
                warnings.append(f"SSH key has insecure permissions: {oct(mode)} (should be 0600 or 0400)")
            p.complete("SSH key")

        # 2. Check password file exists and is readable
        p.start("Password file")
        if not Path(config.password_file).exists():
            errors.append(f"Password file not found: {config.password_file}")
            p.fail("Password file", "not found")
        else:
            # Check permissions
            mode = Path(config.password_file).stat().st_mode & 0o777
            if mode not in (0o600, 0o400):
                warnings.append(f"Password file has insecure permissions: {oct(mode)}")
            p.complete("Password file")

        # 3. Check repository is accessible
        p.start("Repository")
        restic = Restic(config.repository, config.password_file)
        if not restic.is_initialized():
            errors.append(f"Repository not initialized: {config.repository}")
            p.fail("Repository", "not initialized")
        elif restic.is_locked():
            warnings.append("Repository has stale locks")
            p.complete("Repository", "locked")
        else:
            p.complete("Repository")

        # 4. Check each target is reachable
        p.start("Targets")
        with SSHManager(config.ssh) as ssh:
            for name, target in config.targets.items():
                if not target.check_connectivity(ssh):
                    errors.append(f"Target '{name}' unreachable: {target.host}")
        if any("unreachable" in e for e in errors):
            p.fail("Targets", f"{len([e for e in errors if 'unreachable' in e])} failed")
        else:
            p.complete("Targets")

        # 5. Check required tools
        p.start("Tools")
        for tool in ["restic", "rsync"]:
            result = subprocess.run(["which", tool], capture_output=True)
            if result.returncode != 0:
                errors.append(f"Required tool not found: {tool}")
        if any("not found" in e for e in errors if "tool" in e.lower()):
            p.fail("Tools", "missing")
        else:
            p.complete("Tools")

    # Print summary
    for warning in warnings:
        ui.warning(warning)

    if errors:
        for error in errors:
            ui.error(error)
        raise SystemExit(1)
    else:
        ui.success("All checks passed")
```

**Checks**:
1. SSH key file exists and has secure permissions (0600 or 0400)
2. Password file exists and has secure permissions
3. Repository is initialized and accessible
4. Each target is reachable via SSH
5. Required tools available locally (restic, rsync)
6. Reports warnings for insecure permissions, stale locks

---

## Phase 6: Systemd Integration

### 6.1 Systemd Module (`src/osiris/systemd.py`)

```python
from pathlib import Path
import subprocess

SYSTEMD_DIR = Path("/etc/systemd/system")
SERVICE_NAME = "osiris-backup.service"
TIMER_NAME = "osiris-backup.timer"

SERVICE_CONTENT = """\
[Unit]
Description=Osiris Backup Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/osiris backup --non-interactive --force
User=root

# Logging to journal
StandardOutput=journal
StandardError=journal
SyslogIdentifier=osiris

# Security hardening
ProtectSystem=strict
ReadWritePaths=/backup /var/log/osiris /var/cache/osiris /run/osiris
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""

TIMER_CONTENT = """\
[Unit]
Description=Daily Osiris Backup Timer

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""


def is_systemd_available() -> bool:
    """Check if systemd is available on this system."""
    return SYSTEMD_DIR.exists() and Path("/run/systemd/system").exists()


def is_installed() -> bool:
    """Check if Osiris service files are installed."""
    return (SYSTEMD_DIR / SERVICE_NAME).exists() and (SYSTEMD_DIR / TIMER_NAME).exists()


def is_enabled() -> bool:
    """Check if the timer is enabled."""
    result = subprocess.run(
        ["systemctl", "is-enabled", TIMER_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def is_active() -> bool:
    """Check if the timer is active."""
    result = subprocess.run(
        ["systemctl", "is-active", TIMER_NAME],
        capture_output=True,
    )
    return result.returncode == 0


def install_service() -> None:
    """
    Install systemd service and timer files.

    Raises:
        PermissionError: If not running as root
        RuntimeError: If systemd is not available
    """
    if not is_systemd_available():
        raise RuntimeError("systemd is not available on this system")

    service_path = SYSTEMD_DIR / SERVICE_NAME
    timer_path = SYSTEMD_DIR / TIMER_NAME

    # Write service file
    service_path.write_text(SERVICE_CONTENT)

    # Write timer file
    timer_path.write_text(TIMER_CONTENT)

    # Reload systemd daemon
    subprocess.run(["systemctl", "daemon-reload"], check=True)


def uninstall_service() -> None:
    """
    Remove systemd service and timer files.

    Stops and disables the service first if active.
    """
    if is_active():
        subprocess.run(["systemctl", "stop", TIMER_NAME], check=False)

    if is_enabled():
        subprocess.run(["systemctl", "disable", TIMER_NAME], check=False)

    service_path = SYSTEMD_DIR / SERVICE_NAME
    timer_path = SYSTEMD_DIR / TIMER_NAME

    service_path.unlink(missing_ok=True)
    timer_path.unlink(missing_ok=True)

    subprocess.run(["systemctl", "daemon-reload"], check=True)


def enable_timer() -> None:
    """Enable and start the backup timer."""
    subprocess.run(["systemctl", "enable", TIMER_NAME], check=True)
    subprocess.run(["systemctl", "start", TIMER_NAME], check=True)


def disable_timer() -> None:
    """Stop and disable the backup timer."""
    subprocess.run(["systemctl", "stop", TIMER_NAME], check=True)
    subprocess.run(["systemctl", "disable", TIMER_NAME], check=True)


def get_timer_status() -> dict:
    """
    Get detailed timer status.

    Returns:
        Dict with keys: enabled, active, next_run, last_run
    """
    status = {
        "enabled": is_enabled(),
        "active": is_active(),
        "next_run": None,
        "last_run": None,
    }

    # Get next run time
    result = subprocess.run(
        ["systemctl", "show", TIMER_NAME, "--property=NextElapseUSecRealtime"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        line = result.stdout.strip()
        if "=" in line:
            value = line.split("=", 1)[1]
            if value and value != "n/a":
                status["next_run"] = value

    # Get last run time
    result = subprocess.run(
        ["systemctl", "show", TIMER_NAME, "--property=LastTriggerUSec"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        line = result.stdout.strip()
        if "=" in line:
            value = line.split("=", 1)[1]
            if value and value != "n/a":
                status["last_run"] = value

    return status
```

### 6.2 CLI Integration

```python
from osiris import systemd

@cli.group()
def service():
    """Manage systemd service and timer."""
    pass


@service.command()
@click.pass_context
def install(ctx):
    """Install systemd service and timer files."""
    ui = ctx.obj["ui"]

    ui.header("Install Systemd Service")

    if not systemd.is_systemd_available():
        ui.error("systemd is not available on this system")
        raise SystemExit(1)

    if systemd.is_installed():
        ui.warning("Service files already exist")
        if not ui.confirm("Overwrite existing files?"):
            ui.info("Installation cancelled")
            return

    try:
        systemd.install_service()
        ui.success(f"Installed {systemd.SERVICE_NAME}")
        ui.success(f"Installed {systemd.TIMER_NAME}")
        ui.info("")
        ui.hint("Run 'osiris service enable' to enable scheduled backups")
    except PermissionError:
        ui.error("Permission denied. Run as root.")
        raise SystemExit(1)
    except Exception as e:
        ui.error(f"Installation failed: {e}")
        raise SystemExit(1)


@service.command()
@click.pass_context
def uninstall(ctx):
    """Remove systemd service and timer files."""
    ui = ctx.obj["ui"]

    ui.header("Uninstall Systemd Service")

    if not systemd.is_installed():
        ui.info("Service files not installed")
        return

    if ui.interactive:
        if not ui.confirm("Remove Osiris systemd service and timer?"):
            ui.info("Uninstall cancelled")
            return

    try:
        systemd.uninstall_service()
        ui.success("Removed service and timer files")
    except PermissionError:
        ui.error("Permission denied. Run as root.")
        raise SystemExit(1)
    except Exception as e:
        ui.error(f"Uninstall failed: {e}")
        raise SystemExit(1)


@service.command()
@click.pass_context
def enable(ctx):
    """Enable and start the backup timer."""
    ui = ctx.obj["ui"]

    if not systemd.is_installed():
        ui.error("Service not installed. Run 'osiris service install' first.")
        raise SystemExit(1)

    if systemd.is_active():
        ui.info("Timer is already enabled and active")
        return

    try:
        systemd.enable_timer()
        ui.success("Backup timer enabled and started")

        # Show next run time
        status = systemd.get_timer_status()
        if status["next_run"]:
            ui.info(f"Next backup: {status['next_run']}")
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to enable timer: {e}")
        raise SystemExit(1)


@service.command()
@click.pass_context
def disable(ctx):
    """Stop and disable the backup timer."""
    ui = ctx.obj["ui"]

    if not systemd.is_active() and not systemd.is_enabled():
        ui.info("Timer is already disabled")
        return

    try:
        systemd.disable_timer()
        ui.success("Backup timer stopped and disabled")
    except subprocess.CalledProcessError as e:
        ui.error(f"Failed to disable timer: {e}")
        raise SystemExit(1)


@service.command("status")
@click.pass_context
def service_status(ctx):
    """Show systemd service status."""
    ui = ctx.obj["ui"]

    ui.header("Systemd Service Status")

    if not systemd.is_systemd_available():
        ui.warning("systemd is not available on this system")
        return

    if not systemd.is_installed():
        ui.warning("Service not installed")
        ui.hint("Run 'osiris service install' to install")
        return

    status = systemd.get_timer_status()

    # Installation status
    ui.success("Installed: yes")

    # Enabled status
    if status["enabled"]:
        ui.success("Enabled: yes")
    else:
        ui.warning("Enabled: no")

    # Active status
    if status["active"]:
        ui.success("Active: yes")
    else:
        ui.warning("Active: no")

    # Schedule info
    if status["next_run"]:
        ui.info(f"Next run: {status['next_run']}")
    if status["last_run"]:
        ui.info(f"Last run: {status['last_run']}")

    # Show recent logs
    print()
    ui.info("Recent logs:")
    result = subprocess.run(
        ["journalctl", "-u", systemd.SERVICE_NAME, "-n", "5", "--no-pager"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
    else:
        ui.info("  No recent logs")
```

---

## Phase 7: Testing

### 7.1 Test Strategy

- **Unit tests**: Config parsing, restic command building, target logic
- **Integration tests**: Full backup/restore cycle with mock restic/ssh
- **Fixtures**: Sample configs, mock subprocess responses

### 7.2 Test Files

```
tests/
├── conftest.py           # Shared fixtures
├── test_config.py        # Config loading/validation
├── test_restic.py        # Restic wrapper
├── test_logging.py       # Logging setup
├── test_ssh.py           # SSHManager and ControlMaster
├── test_targets/
│   ├── test_postgres.py
│   └── test_rsync.py
└── test_commands/
    ├── test_backup.py
    ├── test_restore.py
    ├── test_list.py
    └── ...
```

### 7.3 Key Fixtures

```python
import json
from unittest.mock import MagicMock, patch
import pytest

@pytest.fixture
def sample_config(tmp_path):
    """Create a sample config file with all sections."""
    config_path = tmp_path / "config.yaml"
    password_path = tmp_path / "password"
    password_path.write_text("test-password")

    config_path.write_text(f"""
repository: {tmp_path}/repo
password_file: {password_path}

logging:
  level: info
  file: null
  journal: false

ssh:
  user: testuser
  key_file: /tmp/test_key
  control_master: false

targets:
  postgres:
    type: pg_dump
    host: localhost
    pg_user: postgres
    databases:
      - testdb

  minio:
    type: rsync
    host: localhost
    path: /tmp/minio
    staging_dir: {tmp_path}/staging
""")
    return config_path


@pytest.fixture
def mock_subprocess(mocker):
    """
    Central subprocess mock that routes based on command.

    Usage:
        def test_backup(mock_subprocess):
            mock_subprocess.add_response(
                cmd_contains="pg_dump",
                stdout=b"-- PostgreSQL dump\\n",
                returncode=0
            )
    """
    class SubprocessRouter:
        def __init__(self):
            self.responses = []
            self.calls = []

        def add_response(
            self,
            cmd_contains: str | list[str],
            stdout: bytes = b"",
            stderr: bytes = b"",
            returncode: int = 0,
        ):
            """Add a response for commands matching pattern."""
            if isinstance(cmd_contains, str):
                cmd_contains = [cmd_contains]
            self.responses.append({
                "patterns": cmd_contains,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": returncode,
            })

        def _find_response(self, cmd: list[str]) -> dict:
            cmd_str = " ".join(cmd)
            for resp in self.responses:
                if all(p in cmd_str for p in resp["patterns"]):
                    return resp
            # Default: success with empty output
            return {"stdout": b"", "stderr": b"", "returncode": 0}

        def run(self, cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            resp = self._find_response(cmd)
            result = MagicMock()
            result.stdout = resp["stdout"]
            result.stderr = resp["stderr"]
            result.returncode = resp["returncode"]
            return result

        def Popen(self, cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            resp = self._find_response(cmd)
            proc = MagicMock()
            proc.stdout = MagicMock()
            proc.stdout.read.return_value = resp["stdout"]
            proc.stderr = MagicMock()
            proc.stderr.read.return_value = resp["stderr"]
            proc.returncode = resp["returncode"]
            proc.communicate.return_value = (resp["stdout"], resp["stderr"])
            proc.wait.return_value = resp["returncode"]
            return proc

    router = SubprocessRouter()
    mocker.patch("subprocess.run", side_effect=router.run)
    mocker.patch("subprocess.Popen", side_effect=router.Popen)
    return router


@pytest.fixture
def mock_restic_responses(mock_subprocess):
    """Pre-configure common restic responses."""
    # Snapshots response
    mock_subprocess.add_response(
        cmd_contains=["restic", "snapshots"],
        stdout=json.dumps([
            {
                "id": "abc123def456",
                "short_id": "abc123de",
                "time": "2026-01-03T02:00:00Z",
                "hostname": "backup-01",
                "tags": ["osiris:20260103-020000", "target:postgres", "database:kriib"],
                "paths": ["/stdin"],
            }
        ]).encode(),
    )

    # Backup response
    mock_subprocess.add_response(
        cmd_contains=["restic", "backup"],
        stdout=json.dumps({
            "message_type": "summary",
            "snapshot_id": "abc123de",
            "total_bytes_processed": 1234567,
        }).encode(),
    )

    return mock_subprocess


@pytest.fixture
def mock_ssh_success(mock_subprocess):
    """Configure SSH commands to succeed."""
    mock_subprocess.add_response(
        cmd_contains="ssh",
        returncode=0,
    )
    return mock_subprocess
```

### 7.4 Example Test Cases

```python
class TestPostgresBackup:
    """Test PostgreSQL target backup."""

    def test_backup_single_database(self, sample_config, mock_restic_responses):
        """Test backing up a single database."""
        mock_restic_responses.add_response(
            cmd_contains=["ssh", "pg_dump"],
            stdout=b"-- PostgreSQL dump\\nCREATE DATABASE...",
        )

        config = load_config(sample_config)
        restic = Restic(config.repository, config.password_file)
        target = PostgresTarget(
            name="postgres",
            host="localhost",
            user="postgres",
            databases=["testdb"],
        )

        with SSHManager(config.ssh) as ssh:
            results = target.backup(restic, "20260103-020000", ssh)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].item == "testdb"

    def test_backup_handles_pg_dump_failure(self, sample_config, mock_subprocess):
        """Test that pg_dump failure is captured and reported."""
        mock_subprocess.add_response(
            cmd_contains=["ssh", "pg_dump"],
            stderr=b"pg_dump: error: connection refused",
            returncode=1,
        )

        # ... test that BackupItemResult.success is False
        # ... and error contains "connection refused"


class TestBatchResolution:
    """Test batch ID resolution edge cases."""

    def test_partial_batch(self, mock_restic_responses):
        """Test handling of partial batch (some targets missing)."""
        # Configure snapshots response with only postgres, not minio
        mock_restic_responses.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps([
                {"id": "abc", "tags": ["osiris:20260103-020000", "target:postgres"]},
                # minio snapshot missing
            ]).encode(),
        )

        # ... test that batch status shows PARTIAL

    def test_malformed_snapshot_tags(self, mock_restic_responses):
        """Test that snapshots with missing tags are handled gracefully."""
        mock_restic_responses.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps([
                {"id": "abc", "tags": ["osiris:20260103-020000"]},  # missing target:
            ]).encode(),
        )

        # ... test that snapshot is skipped without error
```

---

## Phase 8: Documentation & Packaging

### 8.1 README.md

- Installation instructions
- Configuration reference
- Command reference
- Example workflows
- Troubleshooting

### 8.2 pyproject.toml Entry Point

```toml
[tool.poetry.scripts]
osiris = "osiris.cli:cli"
```

---

## Implementation Order

| Phase | Description | Est. Files |
|-------|-------------|------------|
| 1 | Project setup, config, logging, ssh, results, restic wrapper, CLI skeleton | 8 |
| 2 | Target abstraction (base, postgres, rsync) | 4 |
| 3 | Core commands (backup, restore, init) | 3 |
| 4 | Status & listing (batch.py, list, show, status) | 4 |
| 5 | Maintenance (verify, prune, chpass, unlock, validate) | 5 |
| 6 | Systemd integration | 1 |
| 7 | Tests (including test_ssh.py, test_batch.py) | 12+ |
| 8 | Documentation | 1 |

**Total**: ~38 files

---

## Dependencies

### Python Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"
click = "^8.1"
pyyaml = "^6.0"
iris = { git = "https://git.kriib.com/Kriib/iris.git", tag = "v1.0.0" }

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-mock = "^3.12"
ruff = "^0.8"
```

### System Dependencies

| Tool | Min Version | Notes |
|------|-------------|-------|
| restic | 0.16.0+ | Required for `--json` output format with `message_type` in backup summary |
| rsync | 3.0+ | Required for `-az --delete` options |
| ssh | OpenSSH 6.7+ | Required for ControlMaster/ControlPersist |
| pg_dump | 14+ | Required on remote PostgreSQL hosts |

**Restic JSON Output Compatibility:**

The plan relies on restic's JSON output format, specifically:
- `restic backup --json` producing `{"message_type": "summary", "snapshot_id": "...", ...}`
- `restic snapshots --json` producing `[{"id": "...", "short_id": "...", "tags": [...], ...}]`

This format has been stable since restic 0.16.0 (2023). Earlier versions may have different field names.

**Version Check in Validate Command:**

The validate command should verify restic version:
```python
result = subprocess.run(["restic", "version"], capture_output=True, text=True)
# Output: "restic 0.16.4 compiled with go1.21.5 on linux/amd64"
version_str = result.stdout.split()[1]  # "0.16.4"
major, minor, patch = map(int, version_str.split("."))
if (major, minor) < (0, 16):
    warnings.append(f"restic {version_str} may have incompatible JSON format (0.16.0+ recommended)")
```

---

## Tagging Scheme

Each restic snapshot gets multiple tags for flexible querying:

| Tag | Purpose | Example |
|-----|---------|---------|
| `osiris:{batch_id}` | Group all snapshots in one backup run | `osiris:20260103-020000` |
| `target:{name}` | Identify which target config | `target:postgres` |
| `database:{name}` | PostgreSQL database name (if applicable) | `database:kriib` |

**Query examples**:
- All snapshots for a batch: `--tag osiris:20260103-020000`
- All postgres snapshots: `--tag target:postgres`
- Specific database: `--tag target:postgres --tag database:kriib`
