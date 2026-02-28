"""Tests for MetricAggregator."""

from __future__ import annotations

import multiprocessing
import time

from loadforge.dsl.http_client import RequestMetric
from loadforge.metrics.aggregator import MetricAggregator
from loadforge.metrics.store import MetricStore


def _make_metric(
    name: str = "Test",
    latency_ms: float = 10.0,
    status_code: int = 200,
    error: str | None = None,
    worker_id: int = 0,
) -> RequestMetric:
    return RequestMetric(
        timestamp=time.monotonic(),
        name=name,
        method="GET",
        url=f"http://localhost/{name.lower()}",
        status_code=status_code,
        latency_ms=latency_ms,
        content_length=100,
        error=error,
        worker_id=worker_id,
    )


class TestMetricAggregator:
    def test_drains_queues_and_produces_snapshots(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        # Put a batch of metrics
        batch = [_make_metric(latency_ms=float(i)) for i in range(1, 11)]
        q.put(batch)

        aggregator = MetricAggregator([q], store, tick_interval=0.2)
        aggregator.set_active_users(5)
        aggregator.start()

        # Wait for at least one tick
        time.sleep(0.5)
        aggregator.stop()

        assert len(store) >= 1
        snapshot = store.get_all()[0]
        assert snapshot.total_requests == 10
        assert snapshot.active_users == 5
        assert snapshot.requests_per_second > 0
        assert snapshot.latency_p50 > 0

    def test_multiple_worker_queues(self):
        ctx = multiprocessing.get_context("spawn")
        q1: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        q2: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        # Worker 1 sends fast requests
        q1.put([_make_metric(latency_ms=5.0, worker_id=0) for _ in range(5)])
        # Worker 2 sends slow requests
        q2.put([_make_metric(latency_ms=50.0, worker_id=1) for _ in range(5)])

        aggregator = MetricAggregator([q1, q2], store, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.5)
        aggregator.stop()

        assert len(store) >= 1
        snapshot = store.get_all()[0]
        assert snapshot.total_requests == 10
        # p50 should be between fast and slow
        assert snapshot.latency_p50 > 0

    def test_per_endpoint_metrics(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        batch = [
            _make_metric(name="List Items", latency_ms=10.0),
            _make_metric(name="List Items", latency_ms=20.0),
            _make_metric(name="Create Item", latency_ms=50.0),
        ]
        q.put(batch)

        aggregator = MetricAggregator([q], store, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.5)
        aggregator.stop()

        snapshot = store.get_all()[0]
        assert "List Items" in snapshot.endpoints
        assert "Create Item" in snapshot.endpoints
        assert snapshot.endpoints["List Items"].request_count == 2
        assert snapshot.endpoints["Create Item"].request_count == 1

    def test_error_tracking(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        batch = [
            _make_metric(status_code=200),
            _make_metric(status_code=500),
            _make_metric(status_code=200, error="ConnectionError: timeout"),
        ]
        q.put(batch)

        aggregator = MetricAggregator([q], store, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.5)
        aggregator.stop()

        snapshot = store.get_all()[0]
        assert snapshot.total_errors == 2
        assert snapshot.error_rate > 0
        assert 500 in snapshot.errors_by_status
        assert "ConnectionError" in snapshot.errors_by_type

    def test_empty_queues_produce_zero_snapshots(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        aggregator = MetricAggregator([q], store, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.5)
        aggregator.stop()

        assert len(store) >= 1
        snapshot = store.get_all()[0]
        assert snapshot.total_requests == 0
        assert snapshot.latency_p50 == 0.0
        assert snapshot.latency_p99 == 0.0

    def test_get_final_snapshot_cumulative(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        # Put two batches across ticks
        q.put([_make_metric(latency_ms=10.0) for _ in range(5)])

        aggregator = MetricAggregator([q], store, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.4)

        # Add more metrics in second tick
        q.put([_make_metric(latency_ms=20.0) for _ in range(5)])
        time.sleep(0.4)
        aggregator.stop()

        # Final snapshot should contain all 10 requests
        final = aggregator.get_final_snapshot(elapsed_seconds=1.0)
        assert final.total_requests == 10

    def test_on_snapshot_callback(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()
        callbacks: list[object] = []

        q.put([_make_metric()])

        aggregator = MetricAggregator([q], store, on_snapshot=callbacks.append, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.5)
        aggregator.stop()

        assert len(callbacks) >= 1

    def test_start_and_stop_idempotent(self):
        ctx = multiprocessing.get_context("spawn")
        q: multiprocessing.Queue[list[RequestMetric]] = ctx.Queue()
        store = MetricStore()

        aggregator = MetricAggregator([q], store, tick_interval=0.2)
        aggregator.start()
        time.sleep(0.3)
        aggregator.stop()
        # Stopping again should not raise
        aggregator.stop()
