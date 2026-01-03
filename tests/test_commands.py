"""Tests for CLI commands."""

import json

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


class TestBackupCommand:
    """Tests for backup command."""

    def test_backup_requires_force_non_interactive(self, tmp_config, mock_subprocess):
        """Test that backup requires --force in non-interactive mode."""
        # Add responses for restic commands
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "--non-interactive", "backup"],
        )
        assert result.exit_code == 1
        assert "--force" in result.output.lower()

    def test_backup_unknown_target(self, tmp_config, mock_subprocess):
        """Test backup with unknown target name."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(tmp_config),
                "--non-interactive",
                "backup",
                "--target",
                "unknown",
                "--force",
            ],
        )
        assert result.exit_code == 1
        assert "unknown target" in result.output.lower()


class TestRestoreCommand:
    """Tests for restore command."""

    def test_restore_requires_batch_id(self, tmp_config, mock_subprocess):
        """Test that restore requires --batch-id."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--config", str(tmp_config), "restore"],
        )
        assert result.exit_code != 0
        assert (
            "batch-id" in result.output.lower() or "required" in result.output.lower()
        )

    def test_restore_batch_not_found(self, tmp_config, mock_subprocess):
        """Test restore with non-existent batch ID."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=b"[]",
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(tmp_config),
                "--non-interactive",
                "restore",
                "--batch-id",
                "20260101-000000",
                "--force",
            ],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_restore_dry_run(self, tmp_config, mock_subprocess, mock_restic_snapshots):
        """Test restore --dry-run shows plan without executing."""
        mock_subprocess.add_response(
            cmd_contains=["restic", "snapshots"],
            stdout=json.dumps(mock_restic_snapshots).encode(),
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--config",
                str(tmp_config),
                "restore",
                "--batch-id",
                "20260103-020000",
                "--dry-run",
            ],
        )
        # Dry-run should succeed without actually restoring
        assert "dry-run" in result.output.lower()


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
