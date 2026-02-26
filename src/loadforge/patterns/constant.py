"""Constant traffic pattern — fixed number of concurrent users."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError
from loadforge.patterns.base import LoadPattern, _validate_positive

if TYPE_CHECKING:
    from collections.abc import Iterator


class ConstantPattern(LoadPattern):
    """Maintain a fixed number of virtual users for the entire duration.

    This is the simplest pattern: every tick yields the same concurrency value.

    Args:
        users: Number of concurrent virtual users.  Must be >= 1.

    Raises:
        ConfigError: If *users* < 1.

    Example::

        pattern = ConstantPattern(users=100)
        for t, n in pattern.iter_concurrency(duration_seconds=60.0):
            assert n == 100
    """

    def __init__(self, users: int) -> None:
        if users < 1:
            msg = f"users must be >= 1, got {users}"
            raise ConfigError(msg)
        self._users = users

    def iter_concurrency(
        self,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed, users)`` at every tick.

        Args:
            duration_seconds: Total duration to generate ticks for.
            tick_interval: Seconds between ticks.

        Yields:
            ``(elapsed_seconds, users)`` where *users* is always the
            configured constant value.
        """
        _validate_positive(duration_seconds, "duration_seconds")
        _validate_positive(tick_interval, "tick_interval")
        elapsed = 0.0
        while elapsed <= duration_seconds:
            yield (elapsed, self._users)
            elapsed += tick_interval

    def describe(self) -> str:
        """Return a human-readable description.

        Returns:
            Description string.
        """
        return f"Constant: {self._users} users"
