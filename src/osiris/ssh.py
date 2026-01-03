"""SSH connection management with ControlMaster support."""

import logging
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from osiris.config import Config, PostgresTargetConfig, RsyncTargetConfig, SSHConfig

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
        result = subprocess.run(
            [
                "ssh",
                "-o",
                f"ControlPath={conn.control_path}",
                "-O",
                "check",
                f"{conn.user}@{conn.host}",
            ],
            capture_output=True,
        )
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
            "-o",
            "ControlMaster=yes",
            "-o",
            f"ControlPath={conn.control_path}",
            "-o",
            f"ControlPersist={self.config.control_persist}",
            "-o",
            "BatchMode=yes",  # Fail instead of prompting
            "-i",
            conn.key_file,
            "-f",
            "-N",  # Background, no command
            f"{conn.user}@{conn.host}",
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
            cmd.extend(
                [
                    "-o",
                    f"ControlPath={conn.control_path}",
                    "-o",
                    "ControlMaster=auto",  # Use existing or create new
                ]
            )

        cmd.extend(
            [
                "-o",
                "BatchMode=yes",
                "-i",
                conn.key_file,
                f"{conn.user}@{conn.host}",
                remote_cmd,
            ]
        )

        return cmd

    def close_master(self, host: str) -> None:
        """Close ControlMaster connection for a specific host."""
        if host not in self._active_masters:
            return

        conn = self._active_masters[host]
        result = subprocess.run(
            [
                "ssh",
                "-o",
                f"ControlPath={conn.control_path}",
                "-O",
                "exit",
                f"{conn.user}@{conn.host}",
            ],
            capture_output=True,
        )

        if result.returncode != 0:
            logger.warning(
                f"Failed to cleanly close ControlMaster for {host}: "
                f"{result.stderr.decode().strip()}"
            )
            # Try to remove stale socket file
            socket_path = Path(conn.control_path)
            if socket_path.exists():
                with suppress(OSError):
                    socket_path.unlink()

        del self._active_masters[host]

    def close_all(self) -> None:
        """Close all active ControlMaster connections."""
        for host in list(self._active_masters.keys()):
            self.close_master(host)

    def __enter__(self) -> "SSHManager":
        return self

    def __exit__(self, *args) -> None:
        self.close_all()


# Global reference for cleanup on signals
_active_ssh_manager: SSHManager | None = None


def _cleanup_handler(signum, frame):
    """Clean up SSH ControlMasters on SIGINT/SIGTERM."""
    import sys

    if _active_ssh_manager is not None:
        _active_ssh_manager.close_all()
    sys.exit(128 + signum)


def register_cleanup(ssh_manager: SSHManager) -> None:
    """Register SSH manager for cleanup on interrupt."""
    import atexit
    import signal

    global _active_ssh_manager
    _active_ssh_manager = ssh_manager
    signal.signal(signal.SIGINT, _cleanup_handler)
    signal.signal(signal.SIGTERM, _cleanup_handler)
    atexit.register(ssh_manager.close_all)


def unregister_cleanup() -> None:
    """Unregister cleanup handlers after normal completion."""
    import signal

    global _active_ssh_manager
    _active_ssh_manager = None
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


@contextmanager
def ssh_session(
    config: "Config",
    targets: list["PostgresTargetConfig | RsyncTargetConfig"],
) -> Iterator[SSHManager]:
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
            seen_hosts: set[str] = set()
            for target in targets:
                if target.host in seen_hosts:
                    continue
                seen_hosts.add(target.host)

                conn = ssh.get_connection(
                    target.host,
                    getattr(target, "ssh_user", None),
                    getattr(target, "ssh_key_file", None),
                )
                ssh.start_master(conn)

            yield ssh
        finally:
            unregister_cleanup()
