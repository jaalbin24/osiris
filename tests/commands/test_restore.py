"""Tests for restore command."""

import json

from click.testing import CliRunner

from osiris.cli import cli


class TestRestoreCommand:
    """Tests for restore command."""

    def test_restore_requires_batch_id(self, tmp_config, mock_subprocess):
        """Test that restore requires --batch-id."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "restore"],
        )
        assert result.exit_code != 0
        assert (
            "batch-id" in result.output.lower() or "required" in result.output.lower()
        )

    def test_restore_batch_not_found(self, tmp_config, mock_subprocess):
        """Test restore with non-existent batch ID."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(tmp_config),
                "--non-interactive",
                "restore",
                "--batch-id",
                "20260101-000000",
                "--force",
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_restore_dry_run(self, tmp_config, mock_subprocess, mock_restic_snapshots):
        """Test restore --dry-run shows plan without executing."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(tmp_config),
                "restore",
                "--batch-id",
                "20260103-020000",
                "--dry-run",
            ],
        )
        # Dry-run should succeed without actually restoring
        assert "dry-run" in result.output.lower()
