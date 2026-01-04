"""Tests for prune command."""

import pytest
from click.testing import CliRunner

from osiris.cli import cli


class TestPruneCommand:
    """Tests for prune command."""

    @pytest.mark.skip(reason="TODO: Implement prune tests")
    def test_prune_applies_retention_policy(self, tmp_config, mock_subprocess):
        """Test that prune applies the configured retention policy."""
        pass

    @pytest.mark.skip(reason="TODO: Implement prune tests")
    def test_prune_dry_run(self, tmp_config, mock_subprocess):
        """Test that prune --dry-run shows what would be removed."""
        pass

    @pytest.mark.skip(reason="TODO: Implement prune tests")
    def test_prune_requires_force_non_interactive(self, tmp_config, mock_subprocess):
        """Test that prune requires --force in non-interactive mode."""
        pass
