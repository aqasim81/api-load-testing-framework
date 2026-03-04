"""Export functions for HTML reports, JSON persistence, and CSV data."""

from __future__ import annotations

import csv
import dataclasses
import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    from loadforge.metrics.models import EndpointMetrics, MetricSnapshot, TestResult


def export_html(result: TestResult, output_path: Path) -> Path:
    """Generate and write a self-contained HTML report.

    Args:
        result: Completed test result to report on.
        output_path: File path to write the HTML report to.

    Returns:
        The resolved path of the written report file.
    """
    from loadforge.reports.generator import ReportGenerator

    generator = ReportGenerator(result)
    html = generator.render_html()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()


def export_json(result: TestResult, output_path: Path) -> Path:
    """Serialize a TestResult to a JSON file for later re-use.

    The JSON file is the canonical format used by ``loadforge report``
    to regenerate reports without re-running the test.

    Args:
        result: Completed test result to serialize.
        output_path: File path to write the JSON to.

    Returns:
        The resolved path of the written JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = _result_to_dict(result)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path.resolve()


def export_csv(result: TestResult, output_path: Path) -> Path:
    """Write a CSV file with one row per MetricSnapshot.

    Columns: elapsed_seconds, active_users, requests_per_second,
    total_requests, total_errors, error_rate, latency_min, latency_avg,
    latency_p50, latency_p75, latency_p90, latency_p95, latency_p99,
    latency_p999, latency_max.

    Args:
        result: Completed test result to export.
        output_path: File path to write the CSV to.

    Returns:
        The resolved path of the written CSV file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "elapsed_seconds",
        "active_users",
        "requests_per_second",
        "total_requests",
        "total_errors",
        "error_rate",
        "latency_min",
        "latency_avg",
        "latency_p50",
        "latency_p75",
        "latency_p90",
        "latency_p95",
        "latency_p99",
        "latency_p999",
        "latency_max",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for snap in result.snapshots:
            writer.writerow(_snapshot_to_csv_row(snap))
    return output_path.resolve()


def load_result(json_path: Path) -> TestResult:
    """Deserialize a TestResult from a JSON file.

    Args:
        json_path: Path to a JSON file previously written by ``export_json``.

    Returns:
        Deserialized TestResult.

    Raises:
        LoadForgeError: If the JSON is malformed or missing required fields.
    """
    from loadforge._internal.errors import LoadForgeError

    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        return _dict_to_result(cast("dict[str, object]", raw))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        msg = f"Failed to load test result from {json_path}: {exc}"
        raise LoadForgeError(msg) from exc


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _result_to_dict(result: TestResult) -> dict[str, object]:
    """Convert a TestResult to a JSON-serializable dict.

    Args:
        result: TestResult to convert.

    Returns:
        Dict suitable for ``json.dumps()``.
    """
    return cast("dict[str, object]", dataclasses.asdict(result))


def _dict_to_result(data: dict[str, object]) -> TestResult:
    """Reconstruct a TestResult from a plain dict (JSON round-trip).

    Args:
        data: Dict produced by ``_result_to_dict()``.

    Returns:
        Reconstructed TestResult.
    """
    from loadforge.metrics.models import TestResult

    raw_snapshots = cast("list[dict[str, object]]", data.get("snapshots", []))
    snapshots = [_dict_to_snapshot(s) for s in raw_snapshots]

    raw_final = data.get("final_summary")
    final_summary = (
        _dict_to_snapshot(cast("dict[str, object]", raw_final)) if raw_final is not None else None
    )

    return TestResult(
        scenario_name=cast("str", data["scenario_name"]),
        start_time=cast("float", data["start_time"]),
        end_time=cast("float", data["end_time"]),
        duration_seconds=cast("float", data["duration_seconds"]),
        pattern_description=cast("str", data["pattern_description"]),
        snapshots=snapshots,
        final_summary=final_summary,
    )


def _dict_to_snapshot(data: dict[str, object]) -> MetricSnapshot:
    """Reconstruct a MetricSnapshot from a plain dict.

    Handles the JSON gotcha where ``errors_by_status`` int keys become
    strings after ``json.loads()``.

    Args:
        data: Dict from JSON representing a MetricSnapshot.

    Returns:
        Reconstructed MetricSnapshot.
    """
    from loadforge.metrics.models import MetricSnapshot

    # Restore int keys for errors_by_status
    raw_by_status = cast("dict[str, int]", data.get("errors_by_status", {}))
    errors_by_status = {int(k): v for k, v in raw_by_status.items()}

    # Reconstruct endpoints
    raw_endpoints = cast("dict[str, dict[str, object]]", data.get("endpoints", {}))
    endpoints = {name: _dict_to_endpoint(ep_data) for name, ep_data in raw_endpoints.items()}

    return MetricSnapshot(
        timestamp=float(cast("float", data["timestamp"])),
        elapsed_seconds=float(cast("float", data["elapsed_seconds"])),
        active_users=int(cast("int", data["active_users"])),
        total_requests=int(cast("int", data.get("total_requests", 0))),
        requests_per_second=float(cast("float", data.get("requests_per_second", 0.0))),
        latency_min=float(cast("float", data.get("latency_min", 0.0))),
        latency_max=float(cast("float", data.get("latency_max", 0.0))),
        latency_avg=float(cast("float", data.get("latency_avg", 0.0))),
        latency_p50=float(cast("float", data.get("latency_p50", 0.0))),
        latency_p75=float(cast("float", data.get("latency_p75", 0.0))),
        latency_p90=float(cast("float", data.get("latency_p90", 0.0))),
        latency_p95=float(cast("float", data.get("latency_p95", 0.0))),
        latency_p99=float(cast("float", data.get("latency_p99", 0.0))),
        latency_p999=float(cast("float", data.get("latency_p999", 0.0))),
        total_errors=int(cast("int", data.get("total_errors", 0))),
        error_rate=float(cast("float", data.get("error_rate", 0.0))),
        errors_by_status=errors_by_status,
        errors_by_type=cast("dict[str, int]", data.get("errors_by_type", {})),
        endpoints=endpoints,
    )


def _dict_to_endpoint(data: dict[str, object]) -> EndpointMetrics:
    """Reconstruct an EndpointMetrics from a plain dict.

    Args:
        data: Dict from JSON representing an EndpointMetrics.

    Returns:
        Reconstructed EndpointMetrics.
    """
    from loadforge.metrics.models import EndpointMetrics

    return EndpointMetrics(
        name=cast("str", data["name"]),
        request_count=int(cast("int", data.get("request_count", 0))),
        error_count=int(cast("int", data.get("error_count", 0))),
        error_rate=float(cast("float", data.get("error_rate", 0.0))),
        requests_per_second=float(cast("float", data.get("requests_per_second", 0.0))),
        latency_min=float(cast("float", data.get("latency_min", 0.0))),
        latency_max=float(cast("float", data.get("latency_max", 0.0))),
        latency_avg=float(cast("float", data.get("latency_avg", 0.0))),
        latency_p50=float(cast("float", data.get("latency_p50", 0.0))),
        latency_p75=float(cast("float", data.get("latency_p75", 0.0))),
        latency_p90=float(cast("float", data.get("latency_p90", 0.0))),
        latency_p95=float(cast("float", data.get("latency_p95", 0.0))),
        latency_p99=float(cast("float", data.get("latency_p99", 0.0))),
    )


def _snapshot_to_csv_row(snap: MetricSnapshot) -> dict[str, object]:
    """Extract CSV fields from a MetricSnapshot.

    Args:
        snap: MetricSnapshot to extract fields from.

    Returns:
        Dict with CSV column names as keys.
    """
    return {
        "elapsed_seconds": snap.elapsed_seconds,
        "active_users": snap.active_users,
        "requests_per_second": snap.requests_per_second,
        "total_requests": snap.total_requests,
        "total_errors": snap.total_errors,
        "error_rate": snap.error_rate,
        "latency_min": snap.latency_min,
        "latency_avg": snap.latency_avg,
        "latency_p50": snap.latency_p50,
        "latency_p75": snap.latency_p75,
        "latency_p90": snap.latency_p90,
        "latency_p95": snap.latency_p95,
        "latency_p99": snap.latency_p99,
        "latency_p999": snap.latency_p999,
        "latency_max": snap.latency_max,
    }
