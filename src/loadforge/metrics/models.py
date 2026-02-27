"""Metric aggregation dataclasses for LoadForge."""

from __future__ import annotations

from dataclasses import dataclass, field

# NOTE: RequestMetric lives in dsl/http_client.py. Imported here for
# re-export convenience — consumers can import from either location.
from loadforge.dsl.http_client import RequestMetric

__all__ = [
    "EndpointMetrics",
    "MetricSnapshot",
    "RequestMetric",
    "TestResult",
]


@dataclass
class EndpointMetrics:
    """Aggregated metrics for a single endpoint (logical request name).

    Attributes:
        name: Logical endpoint name (e.g., "List Items").
        request_count: Total number of requests to this endpoint.
        error_count: Number of failed requests (status >= 400 or error).
        error_rate: Fraction of requests that failed (0.0 to 1.0).
        requests_per_second: Requests per second to this endpoint.
        latency_min: Minimum response time in milliseconds.
        latency_max: Maximum response time in milliseconds.
        latency_avg: Mean response time in milliseconds.
        latency_p50: 50th percentile response time in milliseconds.
        latency_p75: 75th percentile response time in milliseconds.
        latency_p90: 90th percentile response time in milliseconds.
        latency_p95: 95th percentile response time in milliseconds.
        latency_p99: 99th percentile response time in milliseconds.
    """

    name: str
    request_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    requests_per_second: float = 0.0
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_avg: float = 0.0
    latency_p50: float = 0.0
    latency_p75: float = 0.0
    latency_p90: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0


@dataclass
class MetricSnapshot:
    """Point-in-time aggregated metrics, emitted every tick (typically 1s).

    Attributes:
        timestamp: Monotonic timestamp of the snapshot.
        elapsed_seconds: Seconds since the test started.
        active_users: Number of active virtual user coroutines.
        total_requests: Total requests in this interval.
        requests_per_second: Overall RPS in this interval.
        latency_min: Minimum latency in milliseconds.
        latency_max: Maximum latency in milliseconds.
        latency_avg: Mean latency in milliseconds.
        latency_p50: 50th percentile latency (ms).
        latency_p75: 75th percentile latency (ms).
        latency_p90: 90th percentile latency (ms).
        latency_p95: 95th percentile latency (ms).
        latency_p99: 99th percentile latency (ms).
        latency_p999: 99.9th percentile latency (ms).
        total_errors: Total error count in this interval.
        error_rate: Fraction of requests that errored (0.0 to 1.0).
        errors_by_status: Error count breakdown by HTTP status code.
        errors_by_type: Error count breakdown by error type string.
        endpoints: Per-endpoint metrics keyed by endpoint name.
    """

    timestamp: float
    elapsed_seconds: float
    active_users: int
    total_requests: int = 0
    requests_per_second: float = 0.0
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_avg: float = 0.0
    latency_p50: float = 0.0
    latency_p75: float = 0.0
    latency_p90: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_p999: float = 0.0
    total_errors: int = 0
    error_rate: float = 0.0
    errors_by_status: dict[int, int] = field(default_factory=dict)
    errors_by_type: dict[str, int] = field(default_factory=dict)
    endpoints: dict[str, EndpointMetrics] = field(default_factory=dict)


@dataclass
class TestResult:
    """Complete result of a load test run.

    Attributes:
        scenario_name: Name of the scenario that was executed.
        start_time: Monotonic time when the test started.
        end_time: Monotonic time when the test completed.
        duration_seconds: Total wall-clock duration of the test.
        pattern_description: Human-readable description of the load pattern.
        snapshots: Time-series of MetricSnapshot objects (one per tick).
        final_summary: Aggregate MetricSnapshot summarizing the entire test.
    """

    scenario_name: str
    start_time: float
    end_time: float
    duration_seconds: float
    pattern_description: str
    snapshots: list[MetricSnapshot] = field(default_factory=list)
    final_summary: MetricSnapshot | None = None
