"""Abstract base class for all traffic patterns."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from loadforge._internal.errors import ConfigError

if TYPE_CHECKING:
    from collections.abc import Iterator


class LoadPattern(ABC):
    """Abstract base for all traffic patterns.

    A traffic pattern defines how the target concurrency (number of virtual
    users) changes over time.  Concrete subclasses implement
    :meth:`iter_concurrency` to yield ``(elapsed_seconds, target_concurrency)``
    tuples at a configurable tick interval.

    Example::

        pattern = RampPattern(start_users=0, end_users=100, ramp_duration=60.0)
        for elapsed, users in pattern.iter_concurrency(duration_seconds=60.0):
            print(f"t={elapsed:.1f}s -> {users} users")
    """

    @abstractmethod
    def iter_concurrency(
        self,
        duration_seconds: float,
        tick_interval: float = 1.0,
    ) -> Iterator[tuple[float, int]]:
        """Yield ``(elapsed_seconds, target_concurrency)`` at each tick.

        Args:
            duration_seconds: Total duration to generate ticks for.
            tick_interval: Seconds between each yielded tick.  Defaults to 1.0.

        Yields:
            A tuple of ``(elapsed_seconds, target_concurrency)`` where
            *elapsed_seconds* is the time offset from the start and
            *target_concurrency* is the number of virtual users that should be
            active at that moment.
        """

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of this pattern.

        Returns:
            A short string summarising the pattern configuration, suitable for
            logs and report headers.
        """


def _validate_positive(value: float, name: str) -> None:
    """Raise :class:`ConfigError` if *value* is not strictly positive.

    Args:
        value: The numeric value to validate.
        name: Parameter name used in the error message.

    Raises:
        ConfigError: If *value* is not > 0.
    """
    if value <= 0:
        msg = f"{name} must be positive, got {value}"
        raise ConfigError(msg)


def _validate_non_negative(value: float, name: str) -> None:
    """Raise :class:`ConfigError` if *value* is negative.

    Args:
        value: The numeric value to validate.
        name: Parameter name used in the error message.

    Raises:
        ConfigError: If *value* is < 0.
    """
    if value < 0:
        msg = f"{name} must be non-negative, got {value}"
        raise ConfigError(msg)
