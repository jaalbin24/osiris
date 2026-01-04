"""Tests for chpass command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestChpassCommand:
    """Tests for chpass (change password) command."""

    def test_chpass_requires_interactive_mode(self, tmp_config, mock_subprocess):
        """Test that chpass fails in non-interactive mode."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "--non-interactive", "chpass"],
        )

        assert result.exit_code == 1
        assert "interactive mode" in result.output.lower()

    def test_chpass_requires_matching_passwords(self, tmp_config, mock_subprocess):
        """Test that chpass fails when passwords don't match."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "chpass"],
            input="newpassword123\ndifferentpassword\n",
        )

        assert result.exit_code == 1
        assert "do not match" in result.output.lower()

    def test_chpass_adds_new_key(self, tmp_config, mock_subprocess):
        """Test that chpass successfully adds a new key."""
        # Mock restic key list
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "list"],
            stdout=b'[{"id":"abc123","current":true}]',
        )
        # Mock restic key add
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "add"],
            stdout=b"saved new key as def456",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "chpass"],
            input="newpassword123\nnewpassword123\n",
        )

        assert result.exit_code == 0
        assert "added new key" in result.output.lower()
