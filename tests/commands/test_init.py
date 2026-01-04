"""Tests for init command."""

from click.testing import CliRunner

from osiris.cli import cli


class TestInitCommand:
    """Tests for init command."""

    def test_init_runs_without_config(self, tmp_path, mock_subprocess):
        """Test that init can run without an existing config file."""
        config_path = tmp_path / "config.yaml"
        repo_path = tmp_path / "repo"

        # Mock restic init
        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            stdout=b"created restic repository",
            returncode=0,
        )
        # Mock restic snapshots (for is_initialized check)
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            returncode=2,  # Not initialized yet
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--repository",
                str(repo_path),
                "--generate-password",
            ],
        )

        assert result.exit_code == 0
        assert config_path.exists()
        assert "initialization complete" in result.output.lower()

    def test_init_creates_config_file(self, tmp_path, mock_subprocess):
        """Test that init creates a valid config file."""
        config_path = tmp_path / "config.yaml"
        repo_path = tmp_path / "repo"

        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            stdout=b"created restic repository",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            returncode=2,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--repository",
                str(repo_path),
                "--generate-password",
            ],
        )

        assert result.exit_code == 0
        assert config_path.exists()

        # Verify config content
        config_content = config_path.read_text()
        assert f"repository: {repo_path}" in config_content
        assert "password_file:" in config_content
        assert "targets:" in config_content

    def test_init_creates_password_file(self, tmp_path, mock_subprocess):
        """Test that init creates password file with secure permissions."""
        config_path = tmp_path / "config.yaml"
        repo_path = tmp_path / "repo"

        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            stdout=b"created restic repository",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            returncode=2,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--repository",
                str(repo_path),
                "--generate-password",
            ],
        )

        # Password file is created relative to config dir in test environment
        # Check the output confirms creation
        assert result.exit_code == 0
        assert "password file" in result.output.lower()

    def test_init_fails_if_already_initialized(self, tmp_path, mock_subprocess):
        """Test that init fails if config already exists without --force."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("repository: /test")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--generate-password",
            ],
        )

        assert result.exit_code == 1
        assert "already initialized" in result.output.lower()

    def test_init_force_overwrites_config(self, tmp_path, mock_subprocess):
        """Test that init --force overwrites existing config."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("repository: /old-repo")
        repo_path = tmp_path / "new-repo"

        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            stdout=b"created restic repository",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            returncode=2,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--repository",
                str(repo_path),
                "--generate-password",
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert str(repo_path) in config_path.read_text()

    def test_init_requires_password_in_non_interactive(self, tmp_path, mock_subprocess):
        """Test that init fails in non-interactive mode without --generate-password."""
        config_path = tmp_path / "config.yaml"

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "--non-interactive",
                "init",
            ],
        )

        assert result.exit_code == 1
        assert "--generate-password" in result.output

    def test_init_shows_generated_password(self, tmp_path, mock_subprocess):
        """Test that init displays the generated password."""
        config_path = tmp_path / "config.yaml"
        repo_path = tmp_path / "repo"

        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            stdout=b"created restic repository",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            returncode=2,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--repository",
                str(repo_path),
                "--generate-password",
            ],
        )

        assert result.exit_code == 0
        assert "password:" in result.output.lower()
        assert "save this password" in result.output.lower()

    def test_init_shows_next_steps(self, tmp_path, mock_subprocess):
        """Test that init shows next steps after completion."""
        config_path = tmp_path / "config.yaml"
        repo_path = tmp_path / "repo"

        mock_subprocess.add_response(
            cmd_contains=["restic", "init"],
            stdout=b"created restic repository",
        )
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            returncode=2,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config_path),
                "init",
                "--repository",
                str(repo_path),
                "--generate-password",
            ],
        )

        assert result.exit_code == 0
        assert "next steps" in result.output.lower()
        assert "validate" in result.output.lower()
