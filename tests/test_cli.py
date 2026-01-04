"""Tests for basic CLI functionality."""

from click.testing import CliRunner

from osiris.cli import cli


class TestCliBasics:
    """Tests for basic CLI functionality."""

    def test_cli_help(self):
        """Test that --help works."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Osiris" in result.output

    def test_cli_config_not_found(self, tmp_path):
        """Test error when config file doesn't exist."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_path / "nonexistent.yaml"), "status"],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()
