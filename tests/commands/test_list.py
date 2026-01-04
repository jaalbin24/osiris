"""Tests for list command."""

import json

from click.testing import CliRunner

from osiris.cli import cli


class TestListCommand:
    """Tests for list command."""

    def test_list_no_backups(self, tmp_config, mock_subprocess):
        """Test list when no backups exist."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "list"],
        )
        assert result.exit_code == 0
        assert "no backups" in result.output.lower()

    def test_list_with_backups(
        self, tmp_config, mock_subprocess, mock_restic_snapshots
    ):
        """Test list shows existing backups."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "list"],
        )
        assert result.exit_code == 0
        assert "20260103-020000" in result.output
