"""Unit tests pinning the public API surface of the ``loadforge`` package.

These are snapshot tests: when one fails, the public API has changed. If the
change is intended, update the expected value here and record it in
``docs/changelog.md``.
"""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING, cast

import pytest
import typer.main

import loadforge
from loadforge._internal import errors
from loadforge.cli.app import app
from loadforge.metrics.models import EndpointMetrics, MetricSnapshot
from loadforge.metrics.models import TestResult as _TestResult
from loadforge.reports.exporters import export_csv, export_json

if TYPE_CHECKING:
    from pathlib import Path

    import click

_CHANGED = "public API changed: update this snapshot and the changelog deliberately"

EXPECTED_ALL = [
    "CompositePattern",
    "ConfigError",
    "ConstantPattern",
    "DashboardError",
    "DiurnalPattern",
    "EndpointMetrics",
    "EngineError",
    "HttpClient",
    "LoadForgeError",
    "LoadPattern",
    "LoadTestRunner",
    "MetricSnapshot",
    "RampPattern",
    "ReportGenerator",
    "RequestMetric",
    "ScenarioError",
    "SpikePattern",
    "StepPattern",
    "TestResult",
    "export_csv",
    "export_html",
    "export_json",
    "run_worker",
    "scenario",
    "setup",
    "task",
    "teardown",
]

# Command name -> {parameter name: option strings (or argument name)}.
EXPECTED_CLI: dict[str, dict[str, list[str]]] = {
    "run": {
        "scenario_file": ["scenario_file"],
        "users": ["--users", "-u"],
        "duration": ["--duration", "-d"],
        "pattern": ["--pattern", "-p"],
        "ramp_to": ["--ramp-to"],
        "step_size": ["--step-size"],
        "step_duration": ["--step-duration"],
        "workers": ["--workers", "-w"],
        "output": ["--output", "-o"],
        "fmt": ["--format", "-f"],
        "no_report": ["--no-report"],
        "fail_on_error_rate": ["--fail-on-error-rate"],
        "verbose": ["--verbose", "-v"],
        "enable_dashboard": ["--dashboard"],
        "dashboard_port": ["--dashboard-port"],
    },
    "init": {"name": ["name"]},
    "report": {"results_dir": ["results_dir"], "fmt": ["--format", "-f"]},
    "dashboard": {"results_dir": ["results_dir"], "port": ["--port", "-p"]},
}

EXPECTED_RESULT_KEYS = {
    "scenario_name",
    "start_time",
    "end_time",
    "duration_seconds",
    "pattern_description",
    "snapshots",
    "final_summary",
}

EXPECTED_SNAPSHOT_KEYS = {
    "timestamp",
    "elapsed_seconds",
    "active_users",
    "total_requests",
    "requests_per_second",
    "latency_min",
    "latency_max",
    "latency_avg",
    "latency_p50",
    "latency_p75",
    "latency_p90",
    "latency_p95",
    "latency_p99",
    "latency_p999",
    "total_errors",
    "error_rate",
    "errors_by_status",
    "errors_by_type",
    "endpoints",
}

EXPECTED_ENDPOINT_KEYS = {
    "name",
    "request_count",
    "error_count",
    "error_rate",
    "requests_per_second",
    "latency_min",
    "latency_max",
    "latency_avg",
    "latency_p50",
    "latency_p75",
    "latency_p90",
    "latency_p95",
    "latency_p99",
}

EXPECTED_CSV_HEADER = [
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


def _make_result() -> _TestResult:
    endpoint = EndpointMetrics(
        name="List Items",
        request_count=10,
        error_count=0,
        error_rate=0.0,
        requests_per_second=10.0,
        latency_p50=5.0,
        latency_p95=9.0,
        latency_p99=10.0,
        latency_min=1.0,
        latency_max=12.0,
        latency_avg=5.5,
        latency_p75=7.0,
        latency_p90=8.0,
    )
    snapshot = MetricSnapshot(
        timestamp=1.0,
        elapsed_seconds=1.0,
        active_users=1,
        total_requests=10,
        requests_per_second=10.0,
        latency_p50=5.0,
        latency_p75=7.0,
        latency_p90=8.0,
        latency_p95=9.0,
        latency_p99=10.0,
        latency_p999=11.0,
        latency_min=1.0,
        latency_max=12.0,
        latency_avg=5.5,
        total_errors=0,
        error_rate=0.0,
        errors_by_status={},
        errors_by_type={},
        endpoints={"List Items": endpoint},
    )
    return _TestResult(
        scenario_name="api_snapshot",
        start_time=0.0,
        end_time=1.0,
        duration_seconds=1.0,
        pattern_description="Constant 1 users",
        snapshots=[snapshot],
        final_summary=snapshot,
    )


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


def test_all_matches_snapshot() -> None:
    """``loadforge.__all__`` is exactly the pinned list."""
    assert sorted(loadforge.__all__) == sorted(EXPECTED_ALL), _CHANGED


def test_all_names_resolve() -> None:
    """Every name in ``__all__`` is importable from the package."""
    missing = [name for name in loadforge.__all__ if not hasattr(loadforge, name)]
    assert missing == []


@pytest.mark.parametrize(
    "name",
    ["LoadForgeError", "ScenarioError", "ConfigError", "EngineError", "DashboardError"],
)
def test_error_exported_from_package(name: str) -> None:
    """Each exception is re-exported unchanged and derives from LoadForgeError."""
    exported = getattr(loadforge, name)
    assert name in loadforge.__all__
    assert exported is getattr(errors, name)
    assert issubclass(exported, loadforge.LoadForgeError)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_commands_and_flags_match_snapshot() -> None:
    """Every CLI command and its arguments/options match the pinned set."""
    group = cast("click.Group", typer.main.get_command(app))
    actual = {
        name: {str(param.name): [*param.opts, *param.secondary_opts] for param in command.params}
        for name, command in group.commands.items()
    }
    assert actual == EXPECTED_CLI, _CHANGED


# ---------------------------------------------------------------------------
# Report formats
# ---------------------------------------------------------------------------


def test_json_report_fields_match_snapshot(tmp_path: Path) -> None:
    """JSON report keys at every level match the pinned sets."""
    path = export_json(_make_result(), tmp_path / "result.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert set(data) == EXPECTED_RESULT_KEYS, _CHANGED
    assert set(data["snapshots"][0]) == EXPECTED_SNAPSHOT_KEYS, _CHANGED
    assert set(data["final_summary"]) == EXPECTED_SNAPSHOT_KEYS, _CHANGED
    endpoint = data["snapshots"][0]["endpoints"]["List Items"]
    assert set(endpoint) == EXPECTED_ENDPOINT_KEYS, _CHANGED


def test_csv_report_header_matches_snapshot(tmp_path: Path) -> None:
    """CSV report columns and their order match the pinned header."""
    path = export_csv(_make_result(), tmp_path / "report.csv")
    with path.open(encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == EXPECTED_CSV_HEADER, _CHANGED
