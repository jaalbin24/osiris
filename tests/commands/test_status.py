"""Tests for status command."""

import json

from click.testing import CliRunner

from osiris.cli import cli


class TestStatusCommand:
    """Tests for status command."""

    def test_status_shows_repository_info(self, tmp_config, mock_subprocess, mock_restic_snapshots):
        """Test that status shows repository information."""
        # Mock restic snapshots (for is_initialized check and snapshots list)
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )
        # Mock restic stats
        mock_subprocess.add_response(
            cmd_contains=["restic", "stats"],
            stdout=b'{"total_size": 1000000}',
        )
        # Mock systemctl is-active
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "is-active"],
            returncode=0,
            stdout=b"active",
        )
        # Mock systemctl show for next run time
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "show"],
            stdout=b"NextElapseUSecRealtime=2026-01-05 02:00:00",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "status"],
        )

        assert "repository" in result.output.lower()
        assert "initialized" in result.output.lower()

    def test_status_shows_last_backup(self, tmp_config, mock_subprocess, mock_restic_snapshots):
        """Test that status shows last backup time."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "stats"],
            stdout=b'{"total_size": 1000000}',
        )
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "is-active"],
            returncode=0,
            stdout=b"active",
        )
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "show"],
            stdout=b"NextElapseUSecRealtime=2026-01-05 02:00:00",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "status"],
        )

        assert "last backup" in result.output.lower()

    def test_status_shows_timer_status(self, tmp_config, mock_subprocess, mock_restic_snapshots):
        """Test that status shows systemd timer status."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "stats"],
            stdout=b'{"total_size": 1000000}',
        )
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "is-active"],
            returncode=0,
            stdout=b"active",
        )
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "show"],
            stdout=b"NextElapseUSecRealtime=2026-01-05 02:00:00",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "status"],
        )

        assert "scheduled" in result.output.lower() or "timer" in result.output.lower()

    def test_status_warns_when_no_backups(self, tmp_config, mock_subprocess):
        """Test status output when no backups exist."""
        # Return empty snapshots array
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "stats"],
            stdout=b'{"total_size": 0}',
        )
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "is-active"],
            returncode=0,
            stdout=b"active",
        )
        mock_subprocess.add_response(
            cmd_contains=["systemctl", "show"],
            stdout=b"NextElapseUSecRealtime=2026-01-05 02:00:00",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "status"],
        )

        assert result.exit_code == 1  # Should exit with error when issues exist
        assert "no backups" in result.output.lower()
