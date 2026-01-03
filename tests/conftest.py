"""Shared test fixtures."""

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_config(tmp_path):
    """Create a sample config file with all sections."""
    config_path = tmp_path / "config.yaml"
    password_path = tmp_path / "password"
    password_path.write_text("test-password\n")
    # Set secure permissions
    password_path.chmod(0o400)

    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    staging_path = tmp_path / "staging"
    staging_path.mkdir()

    config_path.write_text(f"""
repository: {repo_path}
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
    staging_dir: {staging_path}

retention:
  keep_daily: 7
  keep_weekly: 4
  keep_monthly: 6
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
            self.responses.append(
                {
                    "patterns": cmd_contains,
                    "stdout": stdout,
                    "stderr": stderr,
                    "returncode": returncode,
                }
            )

        def _find_response(self, cmd: list[str]) -> dict:
            cmd_str = " ".join(str(c) for c in cmd)
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
            if kwargs.get("check") and resp["returncode"] != 0:
                import subprocess

                raise subprocess.CalledProcessError(
                    resp["returncode"], cmd, resp["stdout"], resp["stderr"]
                )
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
def mock_restic_snapshots():
    """Sample restic snapshots response."""
    return [
        {
            "id": "abc123def456abc123def456abc123def456abc123def456abc123def456abcd",
            "short_id": "abc123de",
            "time": "2026-01-03T02:00:00.123456789Z",
            "hostname": "backup-01",
            "tags": [
                "osiris:20260103-020000",
                "target:postgres",
                "database:testdb",
            ],
            "paths": ["/stdin"],
        },
        {
            "id": "def456abc123def456abc123def456abc123def456abc123def456abc123efgh",
            "short_id": "def456ab",
            "time": "2026-01-03T02:01:00.123456789Z",
            "hostname": "backup-01",
            "tags": [
                "osiris:20260103-020000",
                "target:minio",
            ],
            "paths": ["/var/cache/osiris/minio/data"],
        },
    ]


@pytest.fixture
def mock_restic_responses(mock_subprocess, mock_restic_snapshots):
    """Pre-configure common restic responses."""
    # Snapshots response
    mock_subprocess.add_response(
        cmd_contains=["restic", "snapshots"],
        stdout=json.dumps(mock_restic_snapshots).encode(),
    )

    # Backup response
    mock_subprocess.add_response(
        cmd_contains=["restic", "backup"],
        stdout=json.dumps(
            {
                "message_type": "summary",
                "snapshot_id": "abc123de",
                "total_bytes_processed": 1234567,
            }
        ).encode(),
    )

    # Stats response
    mock_subprocess.add_response(
        cmd_contains=["restic", "stats"],
        stdout=json.dumps(
            {
                "total_size": 15200000000,
                "total_file_count": 1234,
            }
        ).encode(),
    )

    # Check response
    mock_subprocess.add_response(
        cmd_contains=["restic", "check"],
        stdout=b"no errors were found",
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


@pytest.fixture
def mock_ui(mocker):
    """Create a mock UI that captures all output."""

    class MockUI:
        def __init__(self):
            self.interactive = True
            self.verbose = False
            self._debug = False
            self.messages = []
            self._confirm_response = True
            self._prompt_response = ""

        def header(self, msg):
            self.messages.append(("header", msg))

        def success(self, msg):
            self.messages.append(("success", msg))

        def error(self, msg):
            self.messages.append(("error", msg))

        def warning(self, msg):
            self.messages.append(("warning", msg))

        def info(self, msg):
            self.messages.append(("info", msg))

        def hint(self, msg):
            self.messages.append(("hint", msg))

        def step(self, current, total, msg):
            self.messages.append(("step", f"[{current}/{total}] {msg}"))

        def confirm(self, msg, default=False):
            self.messages.append(("confirm", msg))
            return self._confirm_response

        def prompt(self, msg, mask=False, default=""):
            self.messages.append(("prompt", msg))
            return self._prompt_response or default

        def table(self, columns):
            return MockTable(columns, self)

        def set_confirm_response(self, value: bool):
            self._confirm_response = value

        def set_prompt_response(self, value: str):
            self._prompt_response = value

    class MockTable:
        def __init__(self, columns, ui):
            self.columns = columns
            self.rows = []
            self.ui = ui

        def add_row(self, *values):
            self.rows.append(values)

        def render(self):
            self.ui.messages.append(
                ("table", {"columns": self.columns, "rows": self.rows})
            )

    return MockUI()
