"""Ramp traffic pattern — linear interpolation between two concurrency levels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError
from loadforge.patterns.base import LoadPattern, _validate_non_negative, _validate_positive

if TYPE_CHECKING:
    from collections.abc import Iterator


class RampPattern(LoadPattern):
    """Linearly ramp concurrency from *start_users* to *end_users*.

    During the ramp phase (``0`` to ``ramp_duration``), concurrency increases
    (or decreases) linearly.  After the ramp completes, concurrency holds at
    *end_users* for the remainder of *duration_seconds*.

    Args:
        start_users: Initial number of virtual users.  Must be >= 0.
        end_users: Final number of virtual users.  Must be >= 0.
        ramp_duration: Seconds over which the ramp occurs.  Must be > 0.

    Raises:
        ConfigError: If any argument is out of range.

    Example::

        pattern = RampPattern(start_users=0, end_users=100, ramp_duration=60.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=120.0))
        assert ticks[0][1] == 0  # start
        assert ticks[60][1] == 100  # end of ramp
        assert ticks[90][1] == 100  # holds after ramp
    """

    def __init__(
        self,
        start_users: int,
        end_users: int,
        ramp_duration: float,
    ) -> None:
        _validate_non_negative(start_users, "start_users")
        _validate_non_negative(end_users, "end_users")
        _validate_positive(ramp_duration, "ramp_duration")
        if start_users == end_users:
            msg = (
                "start_users and end_users must differ; use ConstantPattern for fixed concurrency"
            )
            raise ConfigError(msg)
        self._start_users = start_users
        self._end_users = end_users
        self._ramp_duration = ramp_duration

    def iter_concurrency(
        self,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed, target_concurrency)`` with linear interpolation.

        Args:
            duration_seconds: Total duration to generate ticks for.
            tick_interval: Seconds between ticks.

        Yields:
            ``(elapsed_seconds, target_concurrency)`` tuples.  During the ramp
            phase the value changes linearly; after that it holds at
            *end_users*.
        """
        _validate_positive(duration_seconds, "duration_seconds")
        _validate_positive(tick_interval, "tick_interval")
        elapsed = 0.0
        while elapsed <= duration_seconds:
            if elapsed >= self._ramp_duration:
                users = self._end_users
            else:
                fraction = elapsed / self._ramp_duration
                users = round(self._start_users + (self._end_users - self._start_users) * fraction)
            yield (elapsed, max(users, 0))
            elapsed += tick_interval

    def describe(self) -> str:
        """Return a human-readable description.

        Returns:
            Description string.
        """
        return f"Ramp: {self._start_users} -> {self._end_users} users over {self._ramp_duration}s"
