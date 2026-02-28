"""Thread-safe in-memory time-series storage for metric snapshots."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loadforge.metrics.models import MetricSnapshot


class MetricStore:
    """Thread-safe storage for a time-series of ``MetricSnapshot`` objects.

    The aggregator thread appends snapshots, and the main thread reads
    them for building the final ``TestResult``. A ``threading.Lock``
    protects concurrent access.
    """

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._snapshots: list[MetricSnapshot] = []
        self._lock = threading.Lock()

    def append(self, snapshot: MetricSnapshot) -> None:
        """Append a snapshot to the time-series.

        Args:
            snapshot: The metric snapshot to store.
        """
        with self._lock:
            self._snapshots.append(snapshot)

    def get_all(self) -> list[MetricSnapshot]:
        """Return a copy of all stored snapshots.

        Returns:
            List of all snapshots in chronological order.
        """
        with self._lock:
            return list(self._snapshots)

    def get_latest(self) -> MetricSnapshot | None:
        """Return the most recently appended snapshot.

        Returns:
            The latest snapshot, or None if the store is empty.
        """
        with self._lock:
            if not self._snapshots:
                return None
            return self._snapshots[-1]

    def __len__(self) -> int:
        """Return the number of stored snapshots."""
        with self._lock:
            return len(self._snapshots)
