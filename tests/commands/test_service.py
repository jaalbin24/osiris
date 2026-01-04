"""Tests for service command."""

from unittest.mock import patch

from click.testing import CliRunner

from osiris.cli import cli


class TestServiceCommand:
    """Tests for service (systemd management) command."""

    def test_service_install_creates_unit_files(self, tmp_config, mock_subprocess):
        """Test that service install creates systemd unit files."""
        with patch("osiris.commands.service.systemd") as mock_systemd:
            mock_systemd.is_systemd_available.return_value = True
            mock_systemd.is_installed.return_value = False
            mock_systemd.SERVICE_NAME = "osiris-backup.service"
            mock_systemd.TIMER_NAME = "osiris-backup.timer"

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--config", str(tmp_config), "service", "install"],
            )

            assert result.exit_code == 0
            mock_systemd.install_service.assert_called_once()
            assert "installed" in result.output.lower()

    def test_service_install_fails_without_systemd(self, tmp_config, mock_subprocess):
        """Test that service install fails when systemd is not available."""
        with patch("osiris.commands.service.systemd") as mock_systemd:
            mock_systemd.is_systemd_available.return_value = False

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--config", str(tmp_config), "service", "install"],
            )

            assert result.exit_code == 1
            assert "not available" in result.output.lower()

    def test_service_enable_starts_timer(self, tmp_config, mock_subprocess):
        """Test that service enable activates the timer."""
        with patch("osiris.commands.service.systemd") as mock_systemd:
            mock_systemd.is_installed.return_value = True
            mock_systemd.is_active.return_value = False
            mock_systemd.get_timer_status.return_value = {"next_run": "2026-01-05 02:00:00"}

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--config", str(tmp_config), "service", "enable"],
            )

            assert result.exit_code == 0
            mock_systemd.enable_timer.assert_called_once()
            assert "enabled" in result.output.lower()

    def test_service_disable_stops_timer(self, tmp_config, mock_subprocess):
        """Test that service disable deactivates the timer."""
        with patch("osiris.commands.service.systemd") as mock_systemd:
            mock_systemd.is_active.return_value = True
            mock_systemd.is_enabled.return_value = True

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--config", str(tmp_config), "service", "disable"],
            )

            assert result.exit_code == 0
            mock_systemd.disable_timer.assert_called_once()

    def test_service_status_shows_timer_state(self, tmp_config, mock_subprocess):
        """Test that service status shows timer state."""
        with patch("osiris.commands.service.systemd") as mock_systemd:
            mock_systemd.is_systemd_available.return_value = True
            mock_systemd.is_installed.return_value = True
            mock_systemd.SERVICE_NAME = "osiris-backup.service"
            mock_systemd.get_timer_status.return_value = {
                "enabled": True,
                "active": True,
                "next_run": "2026-01-05 02:00:00",
                "last_run": "2026-01-04 02:00:00",
            }

            # Mock journalctl call in service_status
            mock_subprocess.add_response(
                cmd_contains=["journalctl"],
                stdout=b"Jan 04 02:00:00 backup completed",
            )

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["--config", str(tmp_config), "service", "status"],
            )

            assert result.exit_code == 0
            assert "installed" in result.output.lower()
