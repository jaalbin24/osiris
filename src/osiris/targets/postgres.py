"""PostgreSQL backup target."""

import shlex
import subprocess
import time

from osiris.restic import Restic
from osiris.results import BackupItemResult
from osiris.ssh import SSHManager
from osiris.targets.base import BackupTarget


class PostgresTarget(BackupTarget):
    """
    PostgreSQL backup target.

    Backs up databases via SSH + pg_dump, streaming directly to restic.
    """

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

    def backup(
        self, restic: Restic, batch_id: str, ssh: SSHManager
    ) -> list[BackupItemResult]:
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
                pg_dump_cmd = (
                    f"pg_dump -U {self.user} -p {self.port} "
                    f"--create --clean --if-exists {shlex.quote(db)}"
                )
                ssh_cmd = ssh.get_ssh_cmd(conn, pg_dump_cmd)
                ssh_proc = subprocess.Popen(
                    ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

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
                    tags=[
                        f"osiris:{batch_id}",
                        f"target:{self.name}",
                        f"database:{db}",
                    ],
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
                    pg_dump_error = (
                        stderr.decode().strip() if stderr else "unknown error"
                    )
                    raise RuntimeError(f"pg_dump failed: {pg_dump_error}")

                results.append(
                    BackupItemResult(
                        target=self.name,
                        item=db,
                        success=True,
                        snapshot_id=snapshot.get("snapshot_id"),
                        size_bytes=snapshot.get("total_bytes_processed"),
                        duration_seconds=time.time() - start_time,
                    )
                )

            except Exception as e:
                # Ensure SSH process is cleaned up on error
                if ssh_proc is not None:
                    ssh_proc.kill()
                    ssh_proc.wait()

                results.append(
                    BackupItemResult(
                        target=self.name,
                        item=db,
                        success=False,
                        error=str(e),
                        duration_seconds=time.time() - start_time,
                    )
                )

        return results

    def restore(self, restic: Restic, snapshot_id: str, ssh: SSHManager) -> None:
        """
        Restore database from snapshot.

        Since backup uses pg_dump --create --clean --if-exists, the dump contains:
          - DROP DATABASE IF EXISTS
          - CREATE DATABASE with owner/encoding/tablespace
          - \\connect to database
          - DROP/CREATE for all objects

        We restore by piping to psql connected to 'postgres' (maintenance db).
        The dump handles database creation itself.
        """
        # Query snapshot by ID
        all_snapshots = restic.snapshots()
        snapshot = next(
            s
            for s in all_snapshots
            if s.get("short_id") == snapshot_id
            or s.get("id", "").startswith(snapshot_id)
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
        terminate_cmd = (
            f"psql -U {self.user} -d postgres "
            f"-v dbname={shlex.quote(db_name)} -c {shlex.quote(terminate_sql)}"
        )

        # Get dump data once (may be large, don't re-fetch on retry)
        dump_data = restic.dump(snapshot_id, f"/{db_name}.sql")
        restore_cmd = f"psql -U {self.user} -d postgres"

        max_retries = 3
        for attempt in range(max_retries):
            # Terminate active connections
            subprocess.run(
                ssh.get_ssh_cmd(conn, terminate_cmd),
                check=False,  # OK if no connections to terminate
                capture_output=True,
            )

            # Attempt restore immediately after termination
            result = subprocess.run(
                ssh.get_ssh_cmd(conn, restore_cmd),
                input=dump_data,
                capture_output=True,
            )

            if result.returncode == 0:
                return  # Success

            stderr = result.stderr.decode()
            # Check if failure is due to active connections (race condition)
            if (
                "is being accessed by other users" in stderr
                and attempt < max_retries - 1
            ):
                time.sleep(0.5)  # Brief pause before retry
                continue

            # Non-recoverable error or max retries exceeded
            raise RuntimeError(f"psql restore failed: {stderr}")

    def _resolve_databases(self, ssh: SSHManager) -> list[str]:
        """Resolve database list, expanding ["*"] to actual databases."""
        if self.databases == ["*"]:
            conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
            psql_cmd = (
                f"psql -U {self.user} -t -c "
                f'"SELECT datname FROM pg_database WHERE datistemplate = false"'
            )
            cmd = ssh.get_ssh_cmd(conn, psql_cmd)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            all_dbs = [
                db.strip() for db in result.stdout.strip().split("\n") if db.strip()
            ]
            return [db for db in all_dbs if db not in self.exclude]
        return self.databases

    def check_connectivity(self, ssh: SSHManager) -> bool:
        """Verify SSH and pg_dump availability."""
        try:
            conn = ssh.get_connection(self.host, self.ssh_user, self.ssh_key_file)
            subprocess.run(
                ssh.get_ssh_cmd(conn, "which pg_dump"),
                capture_output=True,
                check=True,
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
