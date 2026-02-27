"""In-memory metric collection for a single worker."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING

import numpy as np

from loadforge._internal.logging import get_logger

if TYPE_CHECKING:
    from loadforge.dsl.http_client import RequestMetric

from loadforge.metrics.models import EndpointMetrics, MetricSnapshot

logger = get_logger("metrics.collector")


def _compute_percentiles(
    latencies: list[float],
) -> tuple[float, float, float, float, float, float, float, float, float]:
    """Compute latency percentiles from a list of latency values.

    Args:
        latencies: List of latency values in milliseconds.

    Returns:
        Tuple of (min, max, avg, p50, p75, p90, p95, p99, p999).
    """
    if not latencies:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    arr = np.array(latencies, dtype=np.float64)
    percentiles = np.percentile(arr, [50.0, 75.0, 90.0, 95.0, 99.0, 99.9])

    return (
        float(np.min(arr)),
        float(np.max(arr)),
        float(np.mean(arr)),
        float(percentiles[0]),
        float(percentiles[1]),
        float(percentiles[2]),
        float(percentiles[3]),
        float(percentiles[4]),
        float(percentiles[5]),
    )


def _compute_endpoint_percentiles(
    latencies: list[float],
) -> tuple[float, float, float, float, float, float, float, float]:
    """Compute endpoint-level latency percentiles (no p999).

    Args:
        latencies: List of latency values in milliseconds.

    Returns:
        Tuple of (min, max, avg, p50, p75, p90, p95, p99).
    """
    if not latencies:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    arr = np.array(latencies, dtype=np.float64)
    percentiles = np.percentile(arr, [50.0, 75.0, 90.0, 95.0, 99.0])

    return (
        float(np.min(arr)),
        float(np.max(arr)),
        float(np.mean(arr)),
        float(percentiles[0]),
        float(percentiles[1]),
        float(percentiles[2]),
        float(percentiles[3]),
        float(percentiles[4]),
    )


class MetricCollector:
    """Collects RequestMetric objects in a thread-safe deque.

    The ``record`` method is designed to be passed as the
    ``HttpClient.metric_callback`` parameter. It appends metrics to an
    internal deque. The ``flush`` method drains the deque and computes
    a ``MetricSnapshot`` for the interval.

    This is the Phase 3 single-worker implementation. Phase 4 replaces it
    with shared-memory ring buffers.

    Attributes:
        worker_id: Worker process identifier for metric tagging.
    """

    def __init__(self, worker_id: int = 0) -> None:
        """Initialize the collector.

        Args:
            worker_id: Worker process identifier.
        """
        self.worker_id = worker_id
        self._buffer: deque[RequestMetric] = deque()
        self._all_metrics: list[RequestMetric] = []
        self._last_flush_time: float = time.monotonic()

    @property
    def pending_count(self) -> int:
        """Return the number of unprocessed metrics in the buffer."""
        return len(self._buffer)

    def record(self, metric: RequestMetric) -> None:
        """Append a metric to the collection buffer.

        This method is designed to be used as ``HttpClient.metric_callback``.
        It is safe to call from async code (appending to a deque is atomic
        in CPython).

        Args:
            metric: The request metric to record.
        """
        self._buffer.append(metric)

    def flush(
        self,
        elapsed_seconds: float,
        active_users: int,
    ) -> MetricSnapshot:
        """Drain the buffer and compute an aggregated snapshot.

        Removes all pending metrics from the deque, computes per-endpoint
        and overall aggregate statistics, and returns a ``MetricSnapshot``.

        Args:
            elapsed_seconds: Seconds elapsed since the test started.
            active_users: Current number of active virtual user coroutines.

        Returns:
            A MetricSnapshot summarizing all metrics flushed in this call.
        """
        # Drain buffer
        drained: list[RequestMetric] = []
        while self._buffer:
            drained.append(self._buffer.popleft())

        # Track cumulative state
        self._all_metrics.extend(drained)

        # Compute interval duration for RPS
        now = time.monotonic()
        interval = max(now - self._last_flush_time, 0.001)
        self._last_flush_time = now

        return self._build_snapshot(
            metrics=drained,
            elapsed_seconds=elapsed_seconds,
            active_users=active_users,
            interval=interval,
        )

    def get_cumulative_snapshot(
        self,
        elapsed_seconds: float,
        active_users: int,
    ) -> MetricSnapshot:
        """Return a snapshot summarizing ALL metrics collected since init.

        Unlike ``flush()``, this does not drain the buffer. It uses the
        cumulative internal state.

        Args:
            elapsed_seconds: Total elapsed seconds.
            active_users: Current active virtual user count.

        Returns:
            A cumulative MetricSnapshot.
        """
        return self._build_snapshot(
            metrics=self._all_metrics,
            elapsed_seconds=elapsed_seconds,
            active_users=active_users,
            interval=max(elapsed_seconds, 0.001),
        )

    def reset(self) -> None:
        """Clear all internal state. Primarily for testing."""
        self._buffer.clear()
        self._all_metrics.clear()
        self._last_flush_time = time.monotonic()

    def _build_snapshot(
        self,
        metrics: list[RequestMetric],
        elapsed_seconds: float,
        active_users: int,
        interval: float,
    ) -> MetricSnapshot:
        """Build a MetricSnapshot from a list of metrics.

        Args:
            metrics: List of RequestMetric objects to aggregate.
            elapsed_seconds: Elapsed seconds value for the snapshot.
            active_users: Active user count for the snapshot.
            interval: Time interval for computing RPS.

        Returns:
            Aggregated MetricSnapshot.
        """
        if not metrics:
            return MetricSnapshot(
                timestamp=time.monotonic(),
                elapsed_seconds=elapsed_seconds,
                active_users=active_users,
            )

        # Group by endpoint
        by_endpoint: dict[str, list[RequestMetric]] = defaultdict(list)
        all_latencies: list[float] = []
        errors_by_status: dict[int, int] = defaultdict(int)
        errors_by_type: dict[str, int] = defaultdict(int)
        total_errors = 0

        for metric in metrics:
            by_endpoint[metric.name].append(metric)
            all_latencies.append(metric.latency_ms)

            is_error = metric.error is not None or metric.status_code >= 400
            if is_error:
                total_errors += 1
                if metric.status_code >= 400:
                    errors_by_status[metric.status_code] += 1
                if metric.error is not None:
                    # Extract error type (e.g., "ConnectionError" from "ConnectionError: ...")
                    error_type = metric.error.split(":")[0].strip()
                    errors_by_type[error_type] += 1

        # Overall percentiles
        (
            lat_min,
            lat_max,
            lat_avg,
            lat_p50,
            lat_p75,
            lat_p90,
            lat_p95,
            lat_p99,
            lat_p999,
        ) = _compute_percentiles(all_latencies)

        total_requests = len(metrics)
        error_rate = total_errors / total_requests if total_requests > 0 else 0.0

        # Per-endpoint metrics
        endpoints: dict[str, EndpointMetrics] = {}
        for name, ep_metrics in by_endpoint.items():
            ep_latencies = [m.latency_ms for m in ep_metrics]
            ep_errors = sum(1 for m in ep_metrics if m.error is not None or m.status_code >= 400)
            ep_count = len(ep_metrics)

            (
                ep_min,
                ep_max,
                ep_avg,
                ep_p50,
                ep_p75,
                ep_p90,
                ep_p95,
                ep_p99,
            ) = _compute_endpoint_percentiles(ep_latencies)

            endpoints[name] = EndpointMetrics(
                name=name,
                request_count=ep_count,
                error_count=ep_errors,
                error_rate=ep_errors / ep_count if ep_count > 0 else 0.0,
                requests_per_second=ep_count / interval,
                latency_min=ep_min,
                latency_max=ep_max,
                latency_avg=ep_avg,
                latency_p50=ep_p50,
                latency_p75=ep_p75,
                latency_p90=ep_p90,
                latency_p95=ep_p95,
                latency_p99=ep_p99,
            )

        return MetricSnapshot(
            timestamp=time.monotonic(),
            elapsed_seconds=elapsed_seconds,
            active_users=active_users,
            total_requests=total_requests,
            requests_per_second=total_requests / interval,
            latency_min=lat_min,
            latency_max=lat_max,
            latency_avg=lat_avg,
            latency_p50=lat_p50,
            latency_p75=lat_p75,
            latency_p90=lat_p90,
            latency_p95=lat_p95,
            latency_p99=lat_p99,
            latency_p999=lat_p999,
            total_errors=total_errors,
            error_rate=error_rate,
            errors_by_status=dict(errors_by_status),
            errors_by_type=dict(errors_by_type),
            endpoints=endpoints,
        )
