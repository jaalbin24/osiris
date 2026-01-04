"""Tests for prune command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestPruneCommand:
    """Tests for prune command."""

    def test_prune_requires_force_in_non_interactive(self, tmp_config, mock_subprocess):
        """Test that prune requires --force in non-interactive mode."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "--non-interactive", "prune"],
        )

        assert result.exit_code == 1
        assert "--force" in result.output

    def test_prune_dry_run_shows_snapshots(self, tmp_config, mock_subprocess):
        """Test that prune --dry-run shows what would be removed."""
        # Mock restic forget with dry-run
        # Each line is a JSON object with keep/remove arrays
        mock_subprocess.add_response(
            cmd_contains=["restic", "forget"],
            stdout=b'{"keep":[],"remove":[{"id":"abc123full","short_id":"abc123"}]}',
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "--non-interactive", "prune", "--dry-run"],
        )

        assert result.exit_code == 0
        assert "would remove" in result.output.lower()

    def test_prune_applies_retention_policy(self, tmp_config, mock_subprocess):
        """Test that prune applies the configured retention policy."""
        # Mock restic forget
        mock_subprocess.add_response(
            cmd_contains=["restic", "forget"],
            stdout=b'{"keep":[{"id":"kept1"}],"remove":[{"id":"removed1full","short_id":"removed1"}]}',
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "--non-interactive", "prune", "--force"],
        )

        assert result.exit_code == 0
        assert "removed" in result.output.lower()
