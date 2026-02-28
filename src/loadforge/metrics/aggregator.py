"""Cross-worker metric aggregation via background thread.

The ``MetricAggregator`` runs a daemon thread that drains per-worker
metric queues at regular intervals, feeds latencies into HDR histograms,
and emits ``MetricSnapshot`` objects to a ``MetricStore``.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from loadforge._internal.logging import get_logger
from loadforge.metrics.histogram import HdrHistogramWrapper
from loadforge.metrics.models import EndpointMetrics, MetricSnapshot

if TYPE_CHECKING:
    from collections.abc import Callable
    from multiprocessing import Queue as MpQueue

    from loadforge.dsl.http_client import RequestMetric
    from loadforge.metrics.store import MetricStore

logger = get_logger("metrics.aggregator")

_OVERALL_PERCENTILES = (50.0, 75.0, 90.0, 95.0, 99.0, 99.9)
_ENDPOINT_PERCENTILES = (50.0, 75.0, 90.0, 95.0, 99.0)


class MetricAggregator:
    """Aggregates metrics from multiple worker processes.

    Runs a daemon thread that reads ``RequestMetric`` batches from
    per-worker ``multiprocessing.Queue`` objects, updates HDR histograms,
    and emits ``MetricSnapshot`` objects each tick.

    Two histogram sets are maintained:
    - **Per-tick**: reset after each snapshot, captures interval statistics.
    - **Cumulative**: never reset, used for the final summary.

    Attributes:
        tick_interval: Seconds between aggregation ticks.
    """

    def __init__(
        self,
        metric_queues: list[MpQueue[list[RequestMetric]]],
        store: MetricStore,
        *,
        on_snapshot: Callable[[MetricSnapshot], None] | None = None,
        tick_interval: float = 1.0,
    ) -> None:
        """Initialize the aggregator.

        Args:
            metric_queues: Per-worker queues to drain metrics from.
            store: Store to append snapshots to.
            on_snapshot: Optional callback invoked with each new snapshot.
            tick_interval: Seconds between aggregation ticks.
        """
        self._metric_queues = metric_queues
        self._store = store
        self._on_snapshot = on_snapshot
        self.tick_interval = tick_interval

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0
        self._active_users: int = 0

        # Per-tick histograms (reset each tick)
        self._tick_overall = HdrHistogramWrapper()
        self._tick_endpoints: dict[str, HdrHistogramWrapper] = {}

        # Cumulative histograms (never reset)
        self._cumulative_overall = HdrHistogramWrapper()
        self._cumulative_endpoints: dict[str, HdrHistogramWrapper] = {}

        # Per-tick counters (reset each tick)
        self._tick_request_count = 0
        self._tick_error_count = 0
        self._tick_errors_by_status: dict[int, int] = defaultdict(int)
        self._tick_errors_by_type: dict[str, int] = defaultdict(int)
        self._tick_endpoint_counts: dict[str, int] = defaultdict(int)
        self._tick_endpoint_errors: dict[str, int] = defaultdict(int)

        # Cumulative counters
        self._total_request_count = 0
        self._total_error_count = 0
        self._total_errors_by_status: dict[int, int] = defaultdict(int)
        self._total_errors_by_type: dict[str, int] = defaultdict(int)
        self._total_endpoint_counts: dict[str, int] = defaultdict(int)
        self._total_endpoint_errors: dict[str, int] = defaultdict(int)

    def set_active_users(self, count: int) -> None:
        """Update the active user count for snapshots.

        Args:
            count: Current number of active virtual users across all workers.
        """
        self._active_users = count

    def start(self) -> None:
        """Start the aggregator background thread."""
        self._start_time = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="loadforge-aggregator",
            daemon=True,
        )
        self._thread.start()
        logger.debug("Aggregator thread started")

    def stop(self) -> None:
        """Stop the aggregator thread and wait for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.debug("Aggregator thread stopped")

    def get_final_snapshot(self, elapsed_seconds: float) -> MetricSnapshot:
        """Build a cumulative snapshot from all recorded data.

        Args:
            elapsed_seconds: Total test duration in seconds.

        Returns:
            Cumulative MetricSnapshot summarizing the entire test.
        """
        return self._build_snapshot(
            overall_hist=self._cumulative_overall,
            endpoint_hists=self._cumulative_endpoints,
            request_count=self._total_request_count,
            error_count=self._total_error_count,
            errors_by_status=dict(self._total_errors_by_status),
            errors_by_type=dict(self._total_errors_by_type),
            endpoint_counts=dict(self._total_endpoint_counts),
            endpoint_errors=dict(self._total_endpoint_errors),
            elapsed_seconds=elapsed_seconds,
            interval=max(elapsed_seconds, 0.001),
        )

    def _run_loop(self) -> None:
        """Main aggregator loop running in background thread."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.tick_interval)
            if self._stop_event.is_set():
                break

            self._drain_queues()
            elapsed = time.monotonic() - self._start_time
            snapshot = self._build_tick_snapshot(elapsed)
            self._store.append(snapshot)

            if self._on_snapshot is not None:
                self._on_snapshot(snapshot)

            self._reset_tick_state()

        # Final drain to catch any remaining metrics
        self._drain_queues()

    def _drain_queues(self) -> None:
        """Drain all worker metric queues and process the metrics."""
        for q in self._metric_queues:
            while True:
                try:
                    batch: list[RequestMetric] = q.get_nowait()
                except (queue.Empty, EOFError, ValueError, OSError):
                    # ValueError/OSError: queue was closed during shutdown
                    break
                self._process_batch(batch)

    def _process_batch(self, batch: list[RequestMetric]) -> None:
        """Process a batch of RequestMetric objects from a worker.

        Args:
            batch: List of metrics to aggregate.
        """
        for metric in batch:
            # Record latency in histograms
            self._tick_overall.record_latency_ms(metric.latency_ms)
            self._cumulative_overall.record_latency_ms(metric.latency_ms)

            # Per-endpoint histograms
            name = metric.name
            if name not in self._tick_endpoints:
                self._tick_endpoints[name] = HdrHistogramWrapper()
            self._tick_endpoints[name].record_latency_ms(metric.latency_ms)

            if name not in self._cumulative_endpoints:
                self._cumulative_endpoints[name] = HdrHistogramWrapper()
            self._cumulative_endpoints[name].record_latency_ms(metric.latency_ms)

            # Request counts
            self._tick_request_count += 1
            self._total_request_count += 1
            self._tick_endpoint_counts[name] += 1
            self._total_endpoint_counts[name] += 1

            # Error tracking
            is_error = metric.error is not None or metric.status_code >= 400
            if is_error:
                self._tick_error_count += 1
                self._total_error_count += 1
                self._tick_endpoint_errors[name] += 1
                self._total_endpoint_errors[name] += 1

                if metric.status_code >= 400:
                    self._tick_errors_by_status[metric.status_code] += 1
                    self._total_errors_by_status[metric.status_code] += 1
                if metric.error is not None:
                    error_type = metric.error.split(":")[0].strip()
                    self._tick_errors_by_type[error_type] += 1
                    self._total_errors_by_type[error_type] += 1

    def _build_tick_snapshot(self, elapsed_seconds: float) -> MetricSnapshot:
        """Build a snapshot from per-tick state.

        Args:
            elapsed_seconds: Seconds since test start.

        Returns:
            MetricSnapshot for the current tick interval.
        """
        return self._build_snapshot(
            overall_hist=self._tick_overall,
            endpoint_hists=self._tick_endpoints,
            request_count=self._tick_request_count,
            error_count=self._tick_error_count,
            errors_by_status=dict(self._tick_errors_by_status),
            errors_by_type=dict(self._tick_errors_by_type),
            endpoint_counts=dict(self._tick_endpoint_counts),
            endpoint_errors=dict(self._tick_endpoint_errors),
            elapsed_seconds=elapsed_seconds,
            interval=self.tick_interval,
        )

    def _build_snapshot(
        self,
        overall_hist: HdrHistogramWrapper,
        endpoint_hists: dict[str, HdrHistogramWrapper],
        request_count: int,
        error_count: int,
        errors_by_status: dict[int, int],
        errors_by_type: dict[str, int],
        endpoint_counts: dict[str, int],
        endpoint_errors: dict[str, int],
        elapsed_seconds: float,
        interval: float,
    ) -> MetricSnapshot:
        """Build a MetricSnapshot from histogram and counter state.

        Args:
            overall_hist: Overall latency histogram.
            endpoint_hists: Per-endpoint latency histograms.
            request_count: Total requests in the period.
            error_count: Total errors in the period.
            errors_by_status: Error counts by HTTP status code.
            errors_by_type: Error counts by error type string.
            endpoint_counts: Request counts per endpoint.
            endpoint_errors: Error counts per endpoint.
            elapsed_seconds: Elapsed seconds for the snapshot.
            interval: Time interval for RPS computation.

        Returns:
            Aggregated MetricSnapshot.
        """
        # Overall percentiles from histogram
        error_rate = error_count / request_count if request_count > 0 else 0.0

        # Per-endpoint metrics
        endpoints: dict[str, EndpointMetrics] = {}
        for name, hist in endpoint_hists.items():
            ep_count = endpoint_counts.get(name, 0)
            ep_errors = endpoint_errors.get(name, 0)
            ep_error_rate = ep_errors / ep_count if ep_count > 0 else 0.0

            endpoints[name] = EndpointMetrics(
                name=name,
                request_count=ep_count,
                error_count=ep_errors,
                error_rate=ep_error_rate,
                requests_per_second=ep_count / interval,
                latency_min=hist.get_min(),
                latency_max=hist.get_max(),
                latency_avg=hist.get_mean(),
                latency_p50=hist.get_percentile(50.0),
                latency_p75=hist.get_percentile(75.0),
                latency_p90=hist.get_percentile(90.0),
                latency_p95=hist.get_percentile(95.0),
                latency_p99=hist.get_percentile(99.0),
            )

        return MetricSnapshot(
            timestamp=time.monotonic(),
            elapsed_seconds=elapsed_seconds,
            active_users=self._active_users,
            total_requests=request_count,
            requests_per_second=request_count / interval,
            latency_min=overall_hist.get_min(),
            latency_max=overall_hist.get_max(),
            latency_avg=overall_hist.get_mean(),
            latency_p50=overall_hist.get_percentile(50.0),
            latency_p75=overall_hist.get_percentile(75.0),
            latency_p90=overall_hist.get_percentile(90.0),
            latency_p95=overall_hist.get_percentile(95.0),
            latency_p99=overall_hist.get_percentile(99.0),
            latency_p999=overall_hist.get_percentile(99.9),
            total_errors=error_count,
            error_rate=error_rate,
            errors_by_status=errors_by_status,
            errors_by_type=errors_by_type,
            endpoints=endpoints,
        )

    def _reset_tick_state(self) -> None:
        """Reset per-tick histograms and counters."""
        self._tick_overall.reset()
        self._tick_endpoints.clear()
        self._tick_request_count = 0
        self._tick_error_count = 0
        self._tick_errors_by_status.clear()
        self._tick_errors_by_type.clear()
        self._tick_endpoint_counts.clear()
        self._tick_endpoint_errors.clear()
