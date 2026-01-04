"""Tests for backup command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestBackupCommand:
    """Tests for backup command."""

    def test_backup_requires_force_non_interactive(self, tmp_config, mock_subprocess):
        """Test that backup requires --force in non-interactive mode."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "--non-interactive", "backup"],
        )
        assert result.exit_code == 1
        assert "--force" in result.output.lower()

    def test_backup_unknown_target(self, tmp_config, mock_subprocess):
        """Test backup with unknown target name."""
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
                "backup",
                "--target",
                "unknown",
                "--force",
            ],
        )
        assert result.exit_code == 1
        assert "unknown target" in result.output.lower()
