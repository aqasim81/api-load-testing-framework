"""Composite traffic pattern — chain multiple patterns sequentially."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError
from loadforge.patterns.base import LoadPattern, _validate_positive

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


class CompositePattern(LoadPattern):
    """Chain multiple patterns sequentially into a single pattern.

    Each entry in *phases* is a ``(pattern, duration)`` tuple.  The composite
    pattern runs each sub-pattern for its specified duration, then transitions
    to the next.  Elapsed time is continuous across phases.

    Args:
        phases: Sequence of ``(LoadPattern, duration_seconds)`` tuples.
            Must contain at least one phase.  All durations must be > 0.

    Raises:
        ConfigError: If *phases* is empty or any duration is not positive.

    Example::

        pattern = CompositePattern(
            [
                (RampPattern(start_users=0, end_users=100, ramp_duration=60.0), 60.0),
                (ConstantPattern(users=100), 300.0),
                (RampPattern(start_users=100, end_users=0, ramp_duration=60.0), 60.0),
            ]
        )
        # Ramp up over 60s, hold 100 for 300s, ramp down over 60s
    """

    def __init__(self, phases: Sequence[tuple[LoadPattern, float]]) -> None:
        if not phases:
            msg = "phases must contain at least one (pattern, duration) entry"
            raise ConfigError(msg)
        validated: list[tuple[LoadPattern, float]] = []
        for i, (pattern, duration) in enumerate(phases):
            _validate_positive(duration, f"phases[{i}] duration")
            validated.append((pattern, duration))
        self._phases = validated

    def iter_concurrency(
        self,
        duration_seconds: float,  # noqa: ARG002
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed, target_concurrency)`` across all chained phases.

        The *duration_seconds* parameter is ignored in favour of the sum of
        individual phase durations.  Each sub-pattern's
        :meth:`iter_concurrency` is called with that phase's duration.

        Args:
            duration_seconds: Ignored — total duration is the sum of phase
                durations.  Kept for interface compatibility.
            tick_interval: Seconds between ticks, passed to each sub-pattern.

        Yields:
            ``(elapsed_seconds, target_concurrency)`` tuples with elapsed time
            offset so it is continuous across all phases.
        """
        _validate_positive(tick_interval, "tick_interval")
        global_offset = 0.0
        for pattern, phase_duration in self._phases:
            for local_elapsed, users in pattern.iter_concurrency(
                duration_seconds=phase_duration,
                tick_interval=tick_interval,
            ):
                yield (global_offset + local_elapsed, users)
            global_offset += phase_duration

    def describe(self) -> str:
        """Return a human-readable description.

        Returns:
            Description listing each phase's pattern and duration.
        """
        total = sum(d for _, d in self._phases)
        phase_descs = [
            f"  {i + 1}. {p.describe()} ({d}s)" for i, (p, d) in enumerate(self._phases)
        ]
        header = f"Composite: {len(self._phases)} phases, {total}s total"
        return "\n".join([header, *phase_descs])
