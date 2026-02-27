"""Tests for the MetricCollector."""

from __future__ import annotations

import time

from loadforge.dsl.http_client import RequestMetric
from loadforge.metrics.collector import MetricCollector


def _make_metric(
    name: str = "Test",
    latency_ms: float = 10.0,
    status_code: int = 200,
    error: str | None = None,
) -> RequestMetric:
    """Create a RequestMetric with sensible defaults."""
    return RequestMetric(
        timestamp=time.monotonic(),
        name=name,
        method="GET",
        url="http://localhost/test",
        status_code=status_code,
        latency_ms=latency_ms,
        content_length=0,
        error=error,
        worker_id=0,
    )


class TestMetricCollectorRecord:
    """Tests for the record method."""

    def test_record_appends_to_buffer(self) -> None:
        collector = MetricCollector()
        metric = _make_metric()
        collector.record(metric)
        assert collector.pending_count == 1

    def test_record_multiple_appends(self) -> None:
        collector = MetricCollector()
        for _ in range(5):
            collector.record(_make_metric())
        assert collector.pending_count == 5

    def test_pending_count_starts_at_zero(self) -> None:
        collector = MetricCollector()
        assert collector.pending_count == 0


class TestMetricCollectorFlush:
    """Tests for the flush method."""

    def test_flush_drains_buffer(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric())
        collector.record(_make_metric())
        collector.flush(elapsed_seconds=1.0, active_users=1)
        assert collector.pending_count == 0

    def test_flush_returns_snapshot_with_correct_request_count(self) -> None:
        collector = MetricCollector()
        for _ in range(3):
            collector.record(_make_metric())
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=2)
        assert snapshot.total_requests == 3
        assert snapshot.active_users == 2

    def test_flush_computes_latency_percentiles(self) -> None:
        collector = MetricCollector()
        # Add metrics with known latencies
        for lat in [10.0, 20.0, 30.0, 40.0, 50.0]:
            collector.record(_make_metric(latency_ms=lat))
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        assert snapshot.latency_min == 10.0
        assert snapshot.latency_max == 50.0
        assert snapshot.latency_avg == 30.0
        assert snapshot.latency_p50 > 0

    def test_flush_groups_by_endpoint(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric(name="Endpoint A", latency_ms=10.0))
        collector.record(_make_metric(name="Endpoint A", latency_ms=20.0))
        collector.record(_make_metric(name="Endpoint B", latency_ms=30.0))
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        assert "Endpoint A" in snapshot.endpoints
        assert "Endpoint B" in snapshot.endpoints
        assert snapshot.endpoints["Endpoint A"].request_count == 2
        assert snapshot.endpoints["Endpoint B"].request_count == 1

    def test_flush_computes_error_rate(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric(status_code=200))
        collector.record(_make_metric(status_code=500))
        collector.record(_make_metric(status_code=200))
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        assert snapshot.total_errors == 1
        assert abs(snapshot.error_rate - 1 / 3) < 0.01

    def test_flush_tracks_errors_by_status(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric(status_code=500))
        collector.record(_make_metric(status_code=500))
        collector.record(_make_metric(status_code=503))
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        assert snapshot.errors_by_status[500] == 2
        assert snapshot.errors_by_status[503] == 1

    def test_flush_tracks_errors_by_type(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric(status_code=0, error="ConnectionError: refused"))
        collector.record(_make_metric(status_code=0, error="TimeoutError: timed out"))
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        assert snapshot.errors_by_type["ConnectionError"] == 1
        assert snapshot.errors_by_type["TimeoutError"] == 1

    def test_flush_computes_rps(self) -> None:
        collector = MetricCollector()
        for _ in range(10):
            collector.record(_make_metric())
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        # RPS should be positive (exact value depends on timing)
        assert snapshot.requests_per_second > 0

    def test_empty_flush_returns_zero_snapshot(self) -> None:
        collector = MetricCollector()
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=0)
        assert snapshot.total_requests == 0
        assert snapshot.requests_per_second == 0.0
        assert snapshot.latency_min == 0.0
        assert snapshot.total_errors == 0
        assert snapshot.active_users == 0

    def test_flush_endpoint_error_rate(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric(name="EP", status_code=200))
        collector.record(_make_metric(name="EP", status_code=500))
        snapshot = collector.flush(elapsed_seconds=1.0, active_users=1)
        ep = snapshot.endpoints["EP"]
        assert ep.error_count == 1
        assert abs(ep.error_rate - 0.5) < 0.01


class TestMetricCollectorCumulative:
    """Tests for get_cumulative_snapshot."""

    def test_cumulative_includes_all_flushed_metrics(self) -> None:
        collector = MetricCollector()
        for _ in range(3):
            collector.record(_make_metric())
        collector.flush(elapsed_seconds=1.0, active_users=1)

        for _ in range(2):
            collector.record(_make_metric())
        collector.flush(elapsed_seconds=2.0, active_users=1)

        cumulative = collector.get_cumulative_snapshot(elapsed_seconds=2.0, active_users=0)
        assert cumulative.total_requests == 5

    def test_cumulative_does_not_drain_buffer(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric())
        # get_cumulative_snapshot doesn't touch the buffer
        collector.get_cumulative_snapshot(elapsed_seconds=1.0, active_users=1)
        assert collector.pending_count == 1


class TestMetricCollectorReset:
    """Tests for the reset method."""

    def test_reset_clears_buffer(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric())
        collector.reset()
        assert collector.pending_count == 0

    def test_reset_clears_cumulative_state(self) -> None:
        collector = MetricCollector()
        collector.record(_make_metric())
        collector.flush(elapsed_seconds=1.0, active_users=1)
        collector.reset()
        cumulative = collector.get_cumulative_snapshot(elapsed_seconds=0.0, active_users=0)
        assert cumulative.total_requests == 0
