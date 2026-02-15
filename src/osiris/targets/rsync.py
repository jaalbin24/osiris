"""Rsync-based backup target (for MinIO and similar)."""

import subprocess
import time
from pathlib import Path

from osiris.restic import Restic
from osiris.results import BackupItemResult
from osiris.ssh import SSHManager
from osiris.targets.base import BackupTarget


class RsyncTarget(BackupTarget):
    """
    Rsync-based backup target.

    Two-step backup: rsync to local staging, then restic backup.
    Used for backing up MinIO data directories and similar.
    """

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

    def _get_rsync_ssh_opts(self, ssh: SSHManager) -> list[str]:
        """Build rsync -e option for SSH with ControlMaster."""
        conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
        ssh_opts = f"ssh -i {conn.key_file}"
        if ssh.config.control_master:
            ssh_opts += f" -o ControlPath={conn.control_path} -o ControlMaster=auto"
        return ["-e", ssh_opts]

    def _get_rsync_remote(self, ssh: SSHManager) -> str:
        """Build rsync remote string (user@host:path)."""
        conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
        return f"{conn.user}@{conn.host}"

    def backup(
        self, restic: Restic, batch_id: str, ssh: SSHManager
    ) -> list[BackupItemResult]:
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
                "rsync",
                "-az",
                "--delete",
                *self._get_rsync_ssh_opts(ssh),
                f"{remote}:{self.path}/",
                f"{data_dir}/",
            ]
            subprocess.run(rsync_cmd, check=True, capture_output=True)

            # Step 2: restic backup the data directory
            snapshot = restic.backup_path(
                path=data_dir,
                tags=[f"osiris:{batch_id}", f"target:{self.name}"],
            )

            return [
                BackupItemResult(
                    target=self.name,
                    item=self.path,
                    success=True,
                    snapshot_id=snapshot.get("snapshot_id"),
                    size_bytes=snapshot.get("total_bytes_processed"),
                    duration_seconds=time.time() - start_time,
                )
            ]
        except Exception as e:
            return [
                BackupItemResult(
                    target=self.name,
                    item=self.path,
                    success=False,
                    error=str(e),
                    duration_seconds=time.time() - start_time,
                )
            ]

    def restore(self, restic: Restic, snapshot_id: str, ssh: SSHManager) -> None:
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

        with tempfile.TemporaryDirectory() as restore_root:
            # Restore snapshot to temp directory
            restic.restore(snapshot_id, restore_root)

            # Find the actual data directory (restic preserves full path)
            # Walk down to find where our files are
            restored_data = self._find_restored_data(restore_root)

            # Rsync restored data to remote
            remote = self._get_rsync_remote(ssh)
            rsync_cmd = [
                "rsync",
                "-az",
                "--delete",
                *self._get_rsync_ssh_opts(ssh),
                f"{restored_data}/",
                f"{remote}:{self.path}/",
            ]
            result = subprocess.run(rsync_cmd, capture_output=True)
            # Exit 23 = partial transfer (e.g. service metadata files locked
            # by a running process). Data files are restored; treat as success.
            if result.returncode not in (0, 23):
                raise subprocess.CalledProcessError(
                    result.returncode, rsync_cmd, result.stdout, result.stderr
                )

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

    def check_connectivity(self, ssh: SSHManager) -> bool:
        """Verify SSH and remote path exists."""
        try:
            conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
            subprocess.run(
                ssh.get_ssh_cmd(conn, f"test -d {self.path}"),
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_snapshot_items(self) -> list[str]:
        """Return the remote path."""
        return [self.path]
