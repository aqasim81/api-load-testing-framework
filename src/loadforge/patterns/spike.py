"""Spike traffic pattern — sudden burst then decay back to base."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError
from loadforge.patterns.base import LoadPattern, _validate_non_negative, _validate_positive

if TYPE_CHECKING:
    from collections.abc import Iterator


class SpikePattern(LoadPattern):
    """Simulate a traffic spike: instant burst to peak, then decay to base.

    The pattern starts at *base_users*, instantly jumps to *spike_users* at
    ``t=0``, and exponentially decays back to *base_users* over
    *spike_duration* seconds.  After the spike window, concurrency holds at
    *base_users*.

    The decay uses an exponential curve so that the spike feels sharp and
    realistic, reaching approximately 95% decay at *spike_duration*.

    Args:
        base_users: Sustained concurrency before and after the spike.  Must be >= 0.
        spike_users: Peak concurrency during the spike.  Must be > *base_users*.
        spike_duration: Seconds for the spike to decay back to base.  Must be > 0.

    Raises:
        ConfigError: If arguments are out of range or *spike_users* <= *base_users*.

    Example::

        pattern = SpikePattern(base_users=100, spike_users=1000, spike_duration=30.0)
        ticks = list(pattern.iter_concurrency(duration_seconds=60.0))
        assert ticks[0][1] == 1000  # peak at t=0
        assert ticks[30][1] == 100  # decayed back
    """

    def __init__(
        self,
        base_users: int,
        spike_users: int,
        spike_duration: float,
    ) -> None:
        _validate_non_negative(base_users, "base_users")
        _validate_positive(spike_duration, "spike_duration")
        if spike_users <= base_users:
            msg = (
                f"spike_users must be greater than base_users, "
                f"got spike_users={spike_users}, base_users={base_users}"
            )
            raise ConfigError(msg)
        self._base_users = base_users
        self._spike_users = spike_users
        self._spike_duration = spike_duration
        # Decay constant: exp(-3) ≈ 0.05, so ~95% decay at spike_duration
        self._decay_rate = 3.0 / spike_duration

    def iter_concurrency(
        self,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed, target_concurrency)`` with spike and decay.

        Args:
            duration_seconds: Total duration to generate ticks for.
            tick_interval: Seconds between ticks.

        Yields:
            ``(elapsed_seconds, target_concurrency)`` tuples.  At ``t=0`` the
            value jumps to *spike_users* and decays exponentially toward
            *base_users*.  After *spike_duration*, holds at *base_users*.
        """
        _validate_positive(duration_seconds, "duration_seconds")
        _validate_positive(tick_interval, "tick_interval")
        spike_delta = self._spike_users - self._base_users
        elapsed = 0.0
        while elapsed <= duration_seconds:
            if elapsed >= self._spike_duration:
                users = self._base_users
            else:
                decay = math.exp(-self._decay_rate * elapsed)
                users = round(self._base_users + spike_delta * decay)
            yield (elapsed, users)
            elapsed += tick_interval

    def describe(self) -> str:
        """Return a human-readable description.

        Returns:
            Description string.
        """
        return (
            f"Spike: {self._base_users} -> {self._spike_users} users, "
            f"decay over {self._spike_duration}s"
        )
