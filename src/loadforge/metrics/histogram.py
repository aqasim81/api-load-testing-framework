"""HDR histogram wrapper for accurate percentile computation.

Provides a thin wrapper around ``hdrh.histogram.HdrHistogram`` that
works in milliseconds. Internally converts to integer microseconds
for the HDR histogram's integer-only API.
"""

from __future__ import annotations

from hdrh.histogram import HdrHistogram  # type: ignore[import-untyped]

from loadforge._internal.logging import get_logger

logger = get_logger("metrics.histogram")

# Range: 1 microsecond to 60 seconds (in microseconds)
_LOWEST_TRACKABLE_US = 1
_HIGHEST_TRACKABLE_US = 60_000_000
_SIGNIFICANT_DIGITS = 3


class HdrHistogramWrapper:
    """Wrapper around HDR histogram for latency percentile computation.

    All public methods accept and return values in **milliseconds**.
    Internally, values are stored as integer microseconds in the
    underlying HDR histogram.

    Attributes:
        lowest_us: Lowest trackable value in microseconds.
        highest_us: Highest trackable value in microseconds.
    """

    def __init__(
        self,
        lowest_us: int = _LOWEST_TRACKABLE_US,
        highest_us: int = _HIGHEST_TRACKABLE_US,
        significant_digits: int = _SIGNIFICANT_DIGITS,
    ) -> None:
        """Initialize the histogram.

        Args:
            lowest_us: Lowest trackable value in microseconds.
            highest_us: Highest trackable value in microseconds.
            significant_digits: Number of significant value digits to maintain.
        """
        self.lowest_us = lowest_us
        self.highest_us = highest_us
        self._histogram: HdrHistogram = HdrHistogram(  # type: ignore[no-any-unimported]
            lowest_us, highest_us, significant_digits
        )

    def record_latency_ms(self, latency_ms: float) -> bool:
        """Record a latency value in milliseconds.

        Values are clamped to the trackable range [lowest_us, highest_us]
        when converted to microseconds.

        Args:
            latency_ms: Latency in milliseconds.

        Returns:
            True if the value was successfully recorded, False otherwise.
        """
        value_us = int(latency_ms * 1000)
        value_us = max(self.lowest_us, min(value_us, self.highest_us))
        return bool(self._histogram.record_value(value_us))

    def get_percentile(self, percentile: float) -> float:
        """Get the value at a given percentile.

        Args:
            percentile: Percentile to compute (0.0 to 100.0).

        Returns:
            Latency value in milliseconds at the given percentile.
            Returns 0.0 if the histogram is empty.
        """
        if self._histogram.total_count == 0:
            return 0.0
        value_us = self._histogram.get_value_at_percentile(percentile)
        return float(value_us) / 1000.0

    def get_min(self) -> float:
        """Get the minimum recorded value in milliseconds.

        Returns:
            Minimum latency in milliseconds, or 0.0 if empty.
        """
        if self._histogram.total_count == 0:
            return 0.0
        return float(self._histogram.get_min_value()) / 1000.0

    def get_max(self) -> float:
        """Get the maximum recorded value in milliseconds.

        Returns:
            Maximum latency in milliseconds, or 0.0 if empty.
        """
        if self._histogram.total_count == 0:
            return 0.0
        return float(self._histogram.get_max_value()) / 1000.0

    def get_mean(self) -> float:
        """Get the mean of all recorded values in milliseconds.

        Returns:
            Mean latency in milliseconds, or 0.0 if empty.
        """
        if self._histogram.total_count == 0:
            return 0.0
        return float(self._histogram.get_mean_value()) / 1000.0

    def get_total_count(self) -> int:
        """Get the total number of recorded values.

        Returns:
            Number of values recorded.
        """
        return int(self._histogram.total_count)

    def reset(self) -> None:
        """Reset the histogram, clearing all recorded values."""
        self._histogram.reset()

    def add(self, other: HdrHistogramWrapper) -> None:
        """Merge another histogram into this one.

        Args:
            other: Histogram to merge from.
        """
        self._histogram.add(other._histogram)
