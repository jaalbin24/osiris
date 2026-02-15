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

    def test_chpass_adds_new_key(self, tmp_config, tmp_path, mock_subprocess):
        """Test that chpass adds a new key, updates password file, and removes old key."""
        # Mock restic key list — old key is not current (simulates state after
        # password file is updated to new password, which is what key_remove's
        # internal key_list call will see)
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "list"],
            stdout=b'[{"id":"abc12345","current":false}]',
        )
        # Mock restic key add
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "add"],
            stdout=b"saved new key as def456",
        )
        # Mock restic key remove
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "remove"],
            stdout=b"",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "chpass"],
            input="newpassword123\nnewpassword123\n",
        )

        assert result.exit_code == 0
        assert "added new key" in result.output.lower()

        # Verify password file was updated
        password_path = tmp_path / "password"
        assert password_path.read_text() == "newpassword123\n"

        # Verify key remove was called with old key ID
        remove_calls = [
            cmd for cmd, _ in mock_subprocess.calls if "key" in str(cmd) and "remove" in str(cmd)
        ]
        assert len(remove_calls) == 1
        assert "abc12345" in str(remove_calls[0])

        assert "removed old key" in result.output.lower()

    def test_chpass_key_remove_failure_still_succeeds(self, tmp_config, tmp_path, mock_subprocess):
        """Test that chpass succeeds with a warning when key_remove fails."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "list"],
            stdout=b'[{"id":"abc12345","current":false}]',
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "add"],
            stdout=b"saved new key as def456",
        )
        # Mock restic key remove to fail
        mock_subprocess.add_response(
            cmd_contains=["restic", "key", "remove"],
            returncode=1,
            stderr=b"remove failed",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "chpass"],
            input="newpassword123\nnewpassword123\n",
        )

        # Command should still succeed (exit 0)
        assert result.exit_code == 0
        assert "added new key" in result.output.lower()

        # Password file should still be updated
        password_path = tmp_path / "password"
        assert password_path.read_text() == "newpassword123\n"

        # Should show a warning about failed key removal
        assert "could not remove old key" in result.output.lower()
