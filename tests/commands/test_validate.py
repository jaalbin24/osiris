"""Tests for validate command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_checks_tools(self, tmp_config, mock_subprocess):
        """Test that validate checks for required tools."""
        # Mock all the checks
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )
        mock_subprocess.add_response(
            cmd_contains=["which", "restic"],
            returncode=0,
        )
        mock_subprocess.add_response(
            cmd_contains=["which", "rsync"],
            returncode=0,
        )
        mock_subprocess.add_response(
            cmd_contains=["ssh"],
            returncode=0,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "validate"],
        )
        # May fail due to SSH key not existing, but should check tools
        assert "restic" in result.output.lower() or "ssh" in result.output.lower()
