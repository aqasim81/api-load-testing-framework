"""Configuration loading for LoadForge."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError

if TYPE_CHECKING:
    from loadforge._internal.types import Headers, ThinkTime


@dataclass(frozen=True)
class LoadForgeConfig:
    """Global LoadForge configuration.

    Attributes:
        default_base_url: Default base URL when none specified in scenario.
        default_headers: Default HTTP headers for all requests.
        default_think_time: Default think time range (min, max) in seconds.
        connection_pool_size: Maximum connections per worker.
        request_timeout: Default request timeout in seconds.
    """

    default_base_url: str = ""
    default_headers: Headers = field(default_factory=dict)
    default_think_time: ThinkTime = (0.5, 1.5)
    connection_pool_size: int = 100
    request_timeout: float = 30.0


def load_config() -> LoadForgeConfig:
    """Load configuration from environment variables with defaults.

    Environment variables:
        LOADFORGE_BASE_URL: Default base URL.
        LOADFORGE_POOL_SIZE: Connection pool size (default: 100).
        LOADFORGE_TIMEOUT: Request timeout in seconds (default: 30.0).

    Returns:
        Populated LoadForgeConfig instance.

    Raises:
        ConfigError: If an environment variable has an invalid value.
    """
    pool_size_str = os.environ.get("LOADFORGE_POOL_SIZE", "100")
    timeout_str = os.environ.get("LOADFORGE_TIMEOUT", "30.0")

    try:
        pool_size = int(pool_size_str)
    except ValueError:
        msg = f"LOADFORGE_POOL_SIZE must be an integer, got: {pool_size_str!r}"
        raise ConfigError(msg) from None

    if pool_size < 1:
        msg = f"LOADFORGE_POOL_SIZE must be >= 1, got: {pool_size}"
        raise ConfigError(msg)

    try:
        timeout = float(timeout_str)
    except ValueError:
        msg = f"LOADFORGE_TIMEOUT must be a number, got: {timeout_str!r}"
        raise ConfigError(msg) from None

    if timeout <= 0:
        msg = f"LOADFORGE_TIMEOUT must be positive, got: {timeout}"
        raise ConfigError(msg)

    return LoadForgeConfig(
        default_base_url=os.environ.get("LOADFORGE_BASE_URL", ""),
        connection_pool_size=pool_size,
        request_timeout=timeout,
    )
