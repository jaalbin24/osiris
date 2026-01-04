"""Tests for service command."""

import pytest
from click.testing import CliRunner

from osiris.cli import cli


class TestServiceCommand:
    """Tests for service (systemd management) command."""

    @pytest.mark.skip(reason="TODO: Implement service tests")
    def test_service_install(self, tmp_config, mock_subprocess):
        """Test that service install creates systemd unit files."""
        pass

    @pytest.mark.skip(reason="TODO: Implement service tests")
    def test_service_uninstall(self, tmp_config, mock_subprocess):
        """Test that service uninstall removes systemd unit files."""
        pass

    @pytest.mark.skip(reason="TODO: Implement service tests")
    def test_service_enable(self, tmp_config, mock_subprocess):
        """Test that service enable activates the timer."""
        pass

    @pytest.mark.skip(reason="TODO: Implement service tests")
    def test_service_disable(self, tmp_config, mock_subprocess):
        """Test that service disable deactivates the timer."""
        pass

    @pytest.mark.skip(reason="TODO: Implement service tests")
    def test_service_status(self, tmp_config, mock_subprocess):
        """Test that service status shows timer state."""
        pass
