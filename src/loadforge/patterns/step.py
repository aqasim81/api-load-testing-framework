"""Step traffic pattern — staircase concurrency increments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loadforge.patterns.base import LoadPattern, _validate_positive

if TYPE_CHECKING:
    from collections.abc import Iterator


class StepPattern(LoadPattern):
    """Increase concurrency in discrete staircase steps.

    Starting at *start_users*, the pattern adds *step_size* users every
    *step_duration* seconds for *steps* increments.  After all steps complete,
    concurrency holds at the final level.

    Args:
        start_users: Initial number of virtual users.  Must be >= 1.
        step_size: Users added at each step.  Must be >= 1.
        step_duration: Seconds between each step increase.  Must be > 0.
        steps: Number of step increments.  Must be >= 1.

    Raises:
        ConfigError: If any argument is out of range.

    Example::

        pattern = StepPattern(start_users=10, step_size=10, step_duration=30.0, steps=5)
        # t=0: 10, t=30: 20, t=60: 30, t=90: 40, t=120: 50
    """

    def __init__(
        self,
        start_users: int,
        step_size: int,
        step_duration: float,
        steps: int,
    ) -> None:
        _validate_positive(start_users, "start_users")
        _validate_positive(step_size, "step_size")
        _validate_positive(step_duration, "step_duration")
        _validate_positive(steps, "steps")
        self._start_users = start_users
        self._step_size = step_size
        self._step_duration = step_duration
        self._steps = steps

    def iter_concurrency(
        self,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed, target_concurrency)`` with staircase increments.

        Args:
            duration_seconds: Total duration to generate ticks for.
            tick_interval: Seconds between ticks.

        Yields:
            ``(elapsed_seconds, target_concurrency)`` tuples.  The concurrency
            increases by *step_size* at each step boundary.
        """
        _validate_positive(duration_seconds, "duration_seconds")
        _validate_positive(tick_interval, "tick_interval")
        final_users = self._start_users + self._step_size * self._steps
        elapsed = 0.0
        while elapsed <= duration_seconds:
            completed_steps = min(
                int(elapsed / self._step_duration),
                self._steps,
            )
            users = self._start_users + self._step_size * completed_steps
            users = min(users, final_users)
            yield (elapsed, users)
            elapsed += tick_interval

    def describe(self) -> str:
        """Return a human-readable description.

        Returns:
            Description string.
        """
        final = self._start_users + self._step_size * self._steps
        return (
            f"Step: {self._start_users} -> {final} users "
            f"(+{self._step_size} every {self._step_duration}s, "
            f"{self._steps} steps)"
        )
