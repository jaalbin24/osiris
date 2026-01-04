"""Tests for unlock command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestUnlockCommand:
    """Tests for unlock command."""

    def test_unlock_not_locked(self, tmp_config, mock_subprocess):
        """Test unlock when repository is not locked."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
            returncode=0,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "unlock"],
        )
        assert result.exit_code == 0
        assert "not locked" in result.output.lower()
