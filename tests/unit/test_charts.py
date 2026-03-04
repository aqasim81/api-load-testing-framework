"""Unit tests for loadforge.reports.charts."""

from __future__ import annotations

import json
import time

from loadforge.metrics.models import EndpointMetrics, MetricSnapshot
from loadforge.reports.charts import (
    concurrency_chart,
    error_breakdown_chart,
    error_pie_chart,
    figure_to_json,
    latency_bands_chart,
    latency_by_endpoint_chart,
    latency_histogram_chart,
    throughput_chart,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    elapsed: float,
    *,
    rps: float = 100.0,
    active: int = 10,
    errors: int = 2,
) -> MetricSnapshot:
    return MetricSnapshot(
        timestamp=time.monotonic(),
        elapsed_seconds=elapsed,
        active_users=active,
        total_requests=int(rps),
        requests_per_second=rps,
        latency_p50=50.0,
        latency_p75=75.0,
        latency_p90=90.0,
        latency_p95=95.0,
        latency_p99=99.0,
        latency_p999=150.0,
        latency_min=5.0,
        latency_max=200.0,
        latency_avg=55.0,
        total_errors=errors,
        error_rate=errors / max(int(rps), 1),
        errors_by_status={500: errors} if errors > 0 else {},
        errors_by_type={"ServerError": errors} if errors > 0 else {},
        endpoints={
            "List Items": EndpointMetrics(
                name="List Items",
                request_count=80,
                error_count=1,
                error_rate=0.0125,
                requests_per_second=80.0,
                latency_p50=45.0,
                latency_p95=90.0,
                latency_p99=120.0,
                latency_min=5.0,
                latency_max=150.0,
                latency_avg=48.0,
                latency_p75=65.0,
                latency_p90=85.0,
            ),
            "Create Item": EndpointMetrics(
                name="Create Item",
                request_count=20,
                error_count=1,
                error_rate=0.05,
                requests_per_second=20.0,
                latency_p50=80.0,
                latency_p95=150.0,
                latency_p99=180.0,
                latency_min=20.0,
                latency_max=200.0,
                latency_avg=85.0,
                latency_p75=110.0,
                latency_p90=140.0,
            ),
        },
    )


def _make_snapshots(count: int = 10) -> list[MetricSnapshot]:
    return [_make_snapshot(float(i)) for i in range(count)]


def _make_endpoints() -> dict[str, EndpointMetrics]:
    snap = _make_snapshot(0.0)
    return snap.endpoints


# ---------------------------------------------------------------------------
# Throughput chart
# ---------------------------------------------------------------------------


class TestThroughputChart:
    def test_returns_figure(self):
        fig = throughput_chart(_make_snapshots())
        assert fig is not None
        assert len(fig.data) == 1

    def test_empty_snapshots(self):
        fig = throughput_chart([])
        assert fig is not None
        assert len(fig.data) == 0

    def test_x_values_match_elapsed(self):
        snapshots = _make_snapshots(5)
        fig = throughput_chart(snapshots)
        x_vals = list(fig.data[0].x)
        expected = [s.elapsed_seconds for s in snapshots]
        assert x_vals == expected

    def test_y_values_match_rps(self):
        snapshots = _make_snapshots(5)
        fig = throughput_chart(snapshots)
        y_vals = list(fig.data[0].y)
        expected = [s.requests_per_second for s in snapshots]
        assert y_vals == expected


# ---------------------------------------------------------------------------
# Latency bands chart
# ---------------------------------------------------------------------------


class TestLatencyBandsChart:
    def test_returns_figure(self):
        fig = latency_bands_chart(_make_snapshots())
        assert fig is not None

    def test_three_traces(self):
        fig = latency_bands_chart(_make_snapshots())
        assert len(fig.data) == 3

    def test_trace_names(self):
        fig = latency_bands_chart(_make_snapshots())
        names = {t.name for t in fig.data}
        assert names == {"p99", "p95", "p50"}

    def test_empty_snapshots(self):
        fig = latency_bands_chart([])
        assert len(fig.data) == 0


# ---------------------------------------------------------------------------
# Latency histogram
# ---------------------------------------------------------------------------


class TestLatencyHistogramChart:
    def test_returns_figure(self):
        fig = latency_histogram_chart(_make_snapshots())
        assert fig is not None
        assert len(fig.data) == 1

    def test_empty_snapshots(self):
        fig = latency_histogram_chart([])
        assert len(fig.data) == 0

    def test_zero_request_snapshots_returns_empty(self):
        snapshots = [_make_snapshot(float(i), rps=0.0) for i in range(5)]
        for s in snapshots:
            s.total_requests = 0
        fig = latency_histogram_chart(snapshots)
        assert len(fig.data) == 0


# ---------------------------------------------------------------------------
# Latency by endpoint
# ---------------------------------------------------------------------------


class TestLatencyByEndpointChart:
    def test_returns_figure_with_endpoints(self):
        fig = latency_by_endpoint_chart(_make_endpoints())
        assert fig is not None
        assert len(fig.data) == 3  # p50, p95, p99

    def test_empty_endpoints(self):
        fig = latency_by_endpoint_chart({})
        assert len(fig.data) == 0

    def test_bar_names(self):
        fig = latency_by_endpoint_chart(_make_endpoints())
        names = [t.name for t in fig.data]
        assert names == ["p50", "p95", "p99"]


# ---------------------------------------------------------------------------
# Error breakdown chart
# ---------------------------------------------------------------------------


class TestErrorBreakdownChart:
    def test_returns_figure(self):
        fig = error_breakdown_chart(_make_snapshots())
        assert fig is not None
        assert len(fig.data) >= 1

    def test_empty_snapshots(self):
        fig = error_breakdown_chart([])
        assert len(fig.data) == 0

    def test_no_errors_returns_empty_figure(self):
        snapshots = [_make_snapshot(float(i), errors=0) for i in range(5)]
        fig = error_breakdown_chart(snapshots)
        assert len(fig.data) == 0

    def test_multiple_status_codes(self):
        snap = _make_snapshot(0.0)
        snap.errors_by_status = {500: 3, 404: 2}
        fig = error_breakdown_chart([snap])
        assert len(fig.data) == 2


# ---------------------------------------------------------------------------
# Error pie chart
# ---------------------------------------------------------------------------


class TestErrorPieChart:
    def test_returns_figure(self):
        fig = error_pie_chart(_make_endpoints())
        assert fig is not None
        assert len(fig.data) == 1

    def test_no_errors(self):
        eps = {
            "ep1": EndpointMetrics(name="ep1", error_count=0),
        }
        fig = error_pie_chart(eps)
        assert len(fig.data) == 0

    def test_empty_endpoints(self):
        fig = error_pie_chart({})
        assert len(fig.data) == 0


# ---------------------------------------------------------------------------
# Concurrency chart
# ---------------------------------------------------------------------------


class TestConcurrencyChart:
    def test_returns_figure(self):
        fig = concurrency_chart(_make_snapshots())
        assert fig is not None
        assert len(fig.data) == 1

    def test_empty_snapshots(self):
        fig = concurrency_chart([])
        assert len(fig.data) == 0

    def test_y_values_match_active_users(self):
        snapshots = [_make_snapshot(float(i), active=i + 1) for i in range(5)]
        fig = concurrency_chart(snapshots)
        y_vals = list(fig.data[0].y)
        assert y_vals == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# figure_to_json
# ---------------------------------------------------------------------------


class TestFigureToJson:
    def test_returns_valid_json(self):
        fig = throughput_chart(_make_snapshots())
        result = figure_to_json(fig)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_data_and_layout_keys(self):
        fig = throughput_chart(_make_snapshots())
        result = figure_to_json(fig)
        parsed = json.loads(result)
        assert "data" in parsed
        assert "layout" in parsed
