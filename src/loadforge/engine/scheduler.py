"""Concurrency scheduler that converts LoadPattern output into scale commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from loadforge.patterns.base import LoadPattern


class ScaleDirection(Enum):
    """Direction of a concurrency scale event."""

    UP = auto()
    DOWN = auto()
    HOLD = auto()


@dataclass(frozen=True)
class ScaleCommand:
    """A command to adjust the number of active virtual users.

    Attributes:
        elapsed_seconds: Time offset from test start.
        target_concurrency: Desired number of active virtual users.
        direction: Whether this is scaling up, down, or holding steady.
        delta: Absolute change in virtual user count (always >= 0).
    """

    elapsed_seconds: float
    target_concurrency: int
    direction: ScaleDirection
    delta: int


class Scheduler:
    """Converts a LoadPattern's concurrency timeline into ScaleCommands.

    Reads from ``LoadPattern.iter_concurrency()`` and emits a
    ``ScaleCommand`` for each tick, indicating the target concurrency
    and how it changed from the previous tick.

    Args:
        pattern: The traffic pattern to follow.
        duration_seconds: Total test duration in seconds.
        tick_interval: Seconds between concurrency adjustments.
    """

    def __init__(
        self,
        pattern: LoadPattern,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> None:
        """Initialize the scheduler.

        Args:
            pattern: LoadPattern instance defining the concurrency curve.
            duration_seconds: Total duration of the test.
            tick_interval: Seconds between ticks. Defaults to 1.0.
        """
        self._pattern = pattern
        self._duration_seconds = duration_seconds
        self._tick_interval = tick_interval

    def iter_commands(self) -> Iterator[ScaleCommand]:
        """Yield ScaleCommands for each tick of the pattern.

        Tracks the previous concurrency level and computes deltas.

        Yields:
            A ScaleCommand for each tick in the pattern's timeline.
        """
        prev_concurrency = 0
        for elapsed, target in self._pattern.iter_concurrency(
            self._duration_seconds, self._tick_interval
        ):
            delta = target - prev_concurrency
            if delta > 0:
                direction = ScaleDirection.UP
            elif delta < 0:
                direction = ScaleDirection.DOWN
            else:
                direction = ScaleDirection.HOLD

            yield ScaleCommand(
                elapsed_seconds=elapsed,
                target_concurrency=target,
                direction=direction,
                delta=abs(delta),
            )
            prev_concurrency = target

    @property
    def total_ticks(self) -> int:
        """Return the expected number of ticks for this schedule."""
        return int(self._duration_seconds / self._tick_interval) + 1
