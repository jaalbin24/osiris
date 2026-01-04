"""Tests for chpass command."""

import pytest
from click.testing import CliRunner

from osiris.cli import cli


class TestChpassCommand:
    """Tests for chpass (change password) command."""

    @pytest.mark.skip(reason="TODO: Implement chpass tests")
    def test_chpass_requires_confirmation(self, tmp_config, mock_subprocess):
        """Test that chpass requires password confirmation."""
        pass

    @pytest.mark.skip(reason="TODO: Implement chpass tests")
    def test_chpass_updates_password_file(self, tmp_config, mock_subprocess):
        """Test that chpass updates the password file."""
        pass

    @pytest.mark.skip(reason="TODO: Implement chpass tests")
    def test_chpass_updates_restic_key(self, tmp_config, mock_subprocess):
        """Test that chpass adds new key and removes old key in restic."""
        pass
