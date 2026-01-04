"""Tests for show command."""

import json

from click.testing import CliRunner

from osiris.cli import cli


class TestShowCommand:
    """Tests for show command."""

    def test_show_batch_not_found(self, tmp_config, mock_subprocess):
        """Test show with non-existent batch ID."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "show", "20260101-000000"],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_show_batch_details(
        self, tmp_config, mock_subprocess, mock_restic_snapshots
    ):
        """Test show displays batch details."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "show", "20260103-020000"],
        )
        assert result.exit_code == 0
        assert "20260103-020000" in result.output
        assert "postgres" in result.output.lower()
