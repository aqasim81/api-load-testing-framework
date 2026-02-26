"""Diurnal traffic pattern — sine-wave day/night cycle."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError
from loadforge.patterns.base import LoadPattern, _validate_positive

if TYPE_CHECKING:
    from collections.abc import Iterator


class DiurnalPattern(LoadPattern):
    """Simulate day/night traffic with a sine-wave curve.

    Concurrency oscillates between *min_users* and *max_users* following a
    sine wave with the given *period*.  The wave is phase-shifted so that it
    starts at *min_users* (trough) and reaches *max_users* (peak) at
    ``period / 2``.

    A 24-hour period can be compressed to any duration for testing purposes
    (e.g. ``period=600`` for a 10-minute cycle).

    Args:
        min_users: Minimum concurrency (trough of the wave).  Must be >= 0.
        max_users: Maximum concurrency (peak of the wave).  Must be > *min_users*.
        period: Full cycle duration in seconds.  Must be > 0.

    Raises:
        ConfigError: If arguments are out of range or *max_users* <= *min_users*.

    Example::

        pattern = DiurnalPattern(min_users=50, max_users=500, period=600.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=600.0))
        assert ticks[0][1] == 50  # starts at trough
        assert ticks[300][1] == 500  # peak at half-period
    """

    def __init__(
        self,
        min_users: int,
        max_users: int,
        period: float,
    ) -> None:
        if min_users < 0:
            msg = f"min_users must be >= 0, got {min_users}"
            raise ConfigError(msg)
        if max_users <= min_users:
            msg = (
                f"max_users must be greater than min_users, "
                f"got max_users={max_users}, min_users={min_users}"
            )
            raise ConfigError(msg)
        _validate_positive(period, "period")
        self._min_users = min_users
        self._max_users = max_users
        self._period = period

    def iter_concurrency(
        self,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed, target_concurrency)`` following a sine wave.

        The formula is::

            users = min + (max - min) * (sin(2 * pi * t / period - pi / 2) + 1) / 2

        This shifts the sine wave so that ``t=0`` gives ``min_users`` and
        ``t=period/2`` gives ``max_users``.

        Args:
            duration_seconds: Total duration to generate ticks for.
            tick_interval: Seconds between ticks.

        Yields:
            ``(elapsed_seconds, target_concurrency)`` tuples.
        """
        _validate_positive(duration_seconds, "duration_seconds")
        _validate_positive(tick_interval, "tick_interval")
        amplitude = self._max_users - self._min_users
        two_pi_over_period = 2.0 * math.pi / self._period
        elapsed = 0.0
        while elapsed <= duration_seconds:
            sine_value = math.sin(two_pi_over_period * elapsed - math.pi / 2.0)
            users = round(self._min_users + amplitude * (sine_value + 1.0) / 2.0)
            yield (elapsed, users)
            elapsed += tick_interval

    def describe(self) -> str:
        """Return a human-readable description.

        Returns:
            Description string.
        """
        return f"Diurnal: {self._min_users} - {self._max_users} users, period {self._period}s"
