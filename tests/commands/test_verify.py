"""Tests for verify command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestVerifyCommand:
    """Tests for verify command."""

    def test_verify_success(self, tmp_config, mock_subprocess):
        """Test successful repository verification."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "check"],
            stdout=b"no errors were found",
            returncode=0,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "verify"],
        )
        assert result.exit_code == 0
        assert "passed" in result.output.lower()

    def test_verify_failure(self, tmp_config, mock_subprocess):
        """Test failed repository verification."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "check"],
            stderr=b"pack abc123 is damaged",
            returncode=1,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "verify"],
        )
        assert result.exit_code == 1
        assert "failed" in result.output.lower()
