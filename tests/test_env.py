"""Tests for environment detection."""

import pytest

from osiris.env import (
    ENV_VAR,
    get_environment,
    is_development,
    is_local,
    is_production,
    is_test,
)


class TestGetEnvironment:
    """Tests for get_environment function."""

    def test_default_is_production(self, monkeypatch):
        """Test that default environment is production."""
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert get_environment() == "production"

    def test_production_environment(self, monkeypatch):
        """Test explicit production environment."""
        monkeypatch.setenv(ENV_VAR, "production")
        assert get_environment() == "production"

    def test_development_environment(self, monkeypatch):
        """Test development environment."""
        monkeypatch.setenv(ENV_VAR, "development")
        assert get_environment() == "development"

    def test_test_environment(self, monkeypatch):
        """Test test environment."""
        monkeypatch.setenv(ENV_VAR, "test")
        assert get_environment() == "test"

    def test_case_insensitive(self, monkeypatch):
        """Test that environment values are case-insensitive."""
        monkeypatch.setenv(ENV_VAR, "PRODUCTION")
        assert get_environment() == "production"

        monkeypatch.setenv(ENV_VAR, "Development")
        assert get_environment() == "development"

        monkeypatch.setenv(ENV_VAR, "TEST")
        assert get_environment() == "test"

    def test_invalid_environment_warns(self, monkeypatch):
        """Test that invalid environment values trigger a warning."""
        monkeypatch.setenv(ENV_VAR, "invalid")

        with pytest.warns(UserWarning, match="Invalid OSIRIS_ENV"):
            env = get_environment()

        assert env == "production"  # Falls back to production


class TestEnvironmentChecks:
    """Tests for is_* helper functions."""

    def test_is_production(self, monkeypatch):
        """Test is_production helper."""
        monkeypatch.setenv(ENV_VAR, "production")
        assert is_production() is True
        assert is_development() is False
        assert is_test() is False

    def test_is_development(self, monkeypatch):
        """Test is_development helper."""
        monkeypatch.setenv(ENV_VAR, "development")
        assert is_production() is False
        assert is_development() is True
        assert is_test() is False

    def test_is_test(self, monkeypatch):
        """Test is_test helper."""
        monkeypatch.setenv(ENV_VAR, "test")
        assert is_production() is False
        assert is_development() is False
        assert is_test() is True

    def test_is_local_development(self, monkeypatch):
        """Test is_local returns True for development."""
        monkeypatch.setenv(ENV_VAR, "development")
        assert is_local() is True

    def test_is_local_test(self, monkeypatch):
        """Test is_local returns True for test."""
        monkeypatch.setenv(ENV_VAR, "test")
        assert is_local() is True

    def test_is_local_production(self, monkeypatch):
        """Test is_local returns False for production."""
        monkeypatch.setenv(ENV_VAR, "production")
        assert is_local() is False
