"""Tests for status command."""

import pytest
from click.testing import CliRunner

from osiris.cli import cli


class TestStatusCommand:
    """Tests for status command."""

    @pytest.mark.skip(reason="TODO: Implement status tests")
    def test_status_shows_repository_info(self, tmp_config, mock_subprocess):
        """Test that status shows repository information."""
        pass

    @pytest.mark.skip(reason="TODO: Implement status tests")
    def test_status_shows_last_backup(self, tmp_config, mock_subprocess):
        """Test that status shows last backup time."""
        pass

    @pytest.mark.skip(reason="TODO: Implement status tests")
    def test_status_shows_timer_status(self, tmp_config, mock_subprocess):
        """Test that status shows systemd timer status."""
        pass

    @pytest.mark.skip(reason="TODO: Implement status tests")
    def test_status_no_backups(self, tmp_config, mock_subprocess):
        """Test status output when no backups exist."""
        pass
