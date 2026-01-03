"""Low-level wrapper for restic commands."""

import json
import logging
import subprocess
from pathlib import Path
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from iris import UI


class Restic:
    """Wrapper for restic backup tool."""

    def __init__(self, repository: str, password_file: str):
        self.repository = repository
        self.password_file = password_file

    def _base_args(self) -> list[str]:
        """Common args for all restic commands."""
        return [
            "restic",
            "--repo",
            self.repository,
            "--password-file",
            self.password_file,
            "--json",  # JSON output where supported
        ]

    def _run(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        """Run restic with common arguments."""
        cmd = self._base_args() + args
        return subprocess.run(cmd, check=True, capture_output=True, **kwargs)

    def init(self) -> None:
        """Initialize repository."""
        cmd = self._base_args() + ["init"]
        subprocess.run(cmd, check=True, capture_output=True)

    def is_initialized(self) -> bool:
        """Check if repository is initialized."""
        try:
            self._run(["snapshots"])
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
            self._run(["snapshots"])
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

    def ensure_unlocked(self, ui: "UI", logger: logging.Logger) -> None:
        """
        Check for stale locks and offer to remove them.

        Called automatically before backup/restore operations.
        """
        if not self.is_locked():
            return

        logger.warning(
            "Repository has stale lock (previous operation may have been interrupted)"
        )

        if ui.interactive:
            if ui.confirm("Remove stale lock and continue?", default=True):
                self.unlock()
                ui.success("Lock removed")
            else:
                raise RuntimeError(
                    "Repository is locked. Run 'osiris unlock' to remove stale locks."
                )
        else:
            # In non-interactive mode, just try to unlock
            logger.info("Attempting to remove stale lock (non-interactive mode)")
            try:
                self.unlock()
                logger.info("Lock removed successfully")
            except subprocess.CalledProcessError:
                raise RuntimeError(
                    "Repository is locked and could not be unlocked automatically"
                )

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
        cmd = self._base_args() + ["backup", "--stdin", "--stdin-filename", filename]
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
        if not Path(path).exists():
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
            "--repo",
            self.repository,
            "--password-file",
            self.password_file,
            "dump",
            snapshot_id,
            path,
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
        # Ensure target directory exists
        Path(target).mkdir(parents=True, exist_ok=True)

        # Note: restore doesn't support --json for progress, uses --target
        cmd = [
            "restic",
            "--repo",
            self.repository,
            "--password-file",
            self.password_file,
            "restore",
            snapshot_id,
            "--target",
            target,
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
            "--keep-daily",
            str(keep_daily),
            "--keep-weekly",
            str(keep_weekly),
            "--keep-monthly",
            str(keep_monthly),
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
                    removed.extend(
                        s.get("short_id", s.get("id", "")) for s in data["remove"]
                    )
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
                    "--repo",
                    self.repository,
                    "--password-file",
                    self.password_file,
                ]
                + args,
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
            "--repo",
            self.repository,
            "--password-file",
            self.password_file,
            "key",
            "add",
            "--new-password-file",
            "/dev/stdin",
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
            "--repo",
            self.repository,
            "--password-file",
            self.password_file,
            "key",
            "remove",
            key_id,
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
