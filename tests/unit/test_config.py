"""Tests for configuration loading."""

from __future__ import annotations

import pytest

from loadforge._internal.config import LoadForgeConfig, load_config
from loadforge._internal.errors import ConfigError


class TestLoadForgeConfig:
    """Tests for the LoadForgeConfig dataclass."""

    def test_defaults(self):
        """LoadForgeConfig has sensible defaults."""
        config = LoadForgeConfig()
        assert config.default_base_url == ""
        assert config.default_headers == {}
        assert config.default_think_time == (0.5, 1.5)
        assert config.connection_pool_size == 100
        assert config.request_timeout == 30.0

    def test_frozen(self):
        """LoadForgeConfig is immutable."""
        config = LoadForgeConfig()
        with pytest.raises(AttributeError):
            config.default_base_url = "http://changed"  # type: ignore[misc]


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_defaults_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """load_config returns defaults when no env vars are set."""
        monkeypatch.delenv("LOADFORGE_BASE_URL", raising=False)
        monkeypatch.delenv("LOADFORGE_POOL_SIZE", raising=False)
        monkeypatch.delenv("LOADFORGE_TIMEOUT", raising=False)

        config = load_config()
        assert config.default_base_url == ""
        assert config.connection_pool_size == 100
        assert config.request_timeout == 30.0

    def test_base_url_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """LOADFORGE_BASE_URL is read from the environment."""
        monkeypatch.setenv("LOADFORGE_BASE_URL", "http://api.example.com")
        config = load_config()
        assert config.default_base_url == "http://api.example.com"

    def test_pool_size_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """LOADFORGE_POOL_SIZE is read from the environment."""
        monkeypatch.setenv("LOADFORGE_POOL_SIZE", "50")
        config = load_config()
        assert config.connection_pool_size == 50

    def test_timeout_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """LOADFORGE_TIMEOUT is read from the environment."""
        monkeypatch.setenv("LOADFORGE_TIMEOUT", "10.5")
        config = load_config()
        assert config.request_timeout == 10.5

    def test_invalid_pool_size_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        """Non-integer LOADFORGE_POOL_SIZE raises ConfigError."""
        monkeypatch.setenv("LOADFORGE_POOL_SIZE", "not_a_number")
        with pytest.raises(ConfigError, match="must be an integer"):
            load_config()

    def test_zero_pool_size_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        """LOADFORGE_POOL_SIZE of 0 raises ConfigError."""
        monkeypatch.setenv("LOADFORGE_POOL_SIZE", "0")
        with pytest.raises(ConfigError, match="must be >= 1"):
            load_config()

    def test_invalid_timeout_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        """Non-numeric LOADFORGE_TIMEOUT raises ConfigError."""
        monkeypatch.setenv("LOADFORGE_TIMEOUT", "abc")
        with pytest.raises(ConfigError, match="must be a number"):
            load_config()

    def test_zero_timeout_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        """LOADFORGE_TIMEOUT of 0 raises ConfigError."""
        monkeypatch.setenv("LOADFORGE_TIMEOUT", "0")
        with pytest.raises(ConfigError, match="must be positive"):
            load_config()

    def test_negative_timeout_raises_error(self, monkeypatch: pytest.MonkeyPatch):
        """LOADFORGE_TIMEOUT of negative value raises ConfigError."""
        monkeypatch.setenv("LOADFORGE_TIMEOUT", "-5.0")
        with pytest.raises(ConfigError, match="must be positive"):
            load_config()
