"""Unit tests for loadforge.reports.exporters."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import pytest

from loadforge._internal.errors import LoadForgeError
from loadforge.metrics.models import EndpointMetrics, MetricSnapshot
from loadforge.metrics.models import TestResult as _TestResult
from loadforge.reports.exporters import export_csv, export_html, export_json, load_result

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    elapsed: float,
    *,
    errors_by_status: dict[int, int] | None = None,
) -> MetricSnapshot:
    return MetricSnapshot(
        timestamp=time.monotonic(),
        elapsed_seconds=elapsed,
        active_users=10,
        total_requests=100,
        requests_per_second=100.0,
        latency_p50=50.0,
        latency_p75=75.0,
        latency_p90=90.0,
        latency_p95=95.0,
        latency_p99=99.0,
        latency_p999=150.0,
        latency_min=5.0,
        latency_max=200.0,
        latency_avg=55.0,
        total_errors=2,
        error_rate=0.02,
        errors_by_status=errors_by_status if errors_by_status is not None else {500: 2},
        errors_by_type={"ServerError": 2},
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
        },
    )


def _make_result(snapshot_count: int = 5) -> _TestResult:
    snapshots = [_make_snapshot(float(i)) for i in range(snapshot_count)]
    return _TestResult(
        scenario_name="test_scenario",
        start_time=1000.0,
        end_time=1005.0,
        duration_seconds=5.0,
        pattern_description="Constant 10 users",
        snapshots=snapshots,
        final_summary=snapshots[-1] if snapshots else None,
    )


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    def test_export_and_load_preserves_fields(self, tmp_path: Path):
        result = _make_result()
        json_path = tmp_path / "result.json"
        export_json(result, json_path)
        loaded = load_result(json_path)

        assert loaded.scenario_name == result.scenario_name
        assert loaded.duration_seconds == result.duration_seconds
        assert loaded.pattern_description == result.pattern_description
        assert len(loaded.snapshots) == len(result.snapshots)
        assert loaded.final_summary is not None
        assert loaded.final_summary.total_requests == result.final_summary.total_requests

    def test_errors_by_status_int_keys_preserved(self, tmp_path: Path):
        result = _make_result()
        result.snapshots[0].errors_by_status = {500: 3, 404: 1}
        json_path = tmp_path / "result.json"
        export_json(result, json_path)
        loaded = load_result(json_path)

        status_keys = loaded.snapshots[0].errors_by_status
        assert all(isinstance(k, int) for k in status_keys)
        assert status_keys[500] == 3
        assert status_keys[404] == 1

    def test_empty_snapshots(self, tmp_path: Path):
        result = _TestResult(
            scenario_name="empty",
            start_time=0.0,
            end_time=0.0,
            duration_seconds=0.0,
            pattern_description="none",
            snapshots=[],
            final_summary=None,
        )
        json_path = tmp_path / "result.json"
        export_json(result, json_path)
        loaded = load_result(json_path)

        assert loaded.snapshots == []
        assert loaded.final_summary is None

    def test_none_final_summary(self, tmp_path: Path):
        result = _make_result()
        result.final_summary = None
        json_path = tmp_path / "result.json"
        export_json(result, json_path)
        loaded = load_result(json_path)

        assert loaded.final_summary is None

    def test_endpoint_data_preserved(self, tmp_path: Path):
        result = _make_result()
        json_path = tmp_path / "result.json"
        export_json(result, json_path)
        loaded = load_result(json_path)

        snap = loaded.snapshots[0]
        assert "List Items" in snap.endpoints
        ep = snap.endpoints["List Items"]
        assert ep.request_count == 80
        assert ep.latency_p50 == 45.0

    def test_json_file_is_valid(self, tmp_path: Path):
        result = _make_result()
        json_path = tmp_path / "result.json"
        export_json(result, json_path)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["scenario_name"] == "test_scenario"
        assert len(data["snapshots"]) == 5

    def test_json_contains_all_top_level_fields(self, tmp_path: Path):
        result = _make_result()
        json_path = tmp_path / "result.json"
        export_json(result, json_path)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["start_time"] == 1000.0
        assert data["end_time"] == 1005.0
        assert data["duration_seconds"] == 5.0
        assert data["pattern_description"] == "Constant 10 users"
        assert data["final_summary"] is not None


class TestLoadResultErrors:
    def test_malformed_json_raises_loadforge_error(self, tmp_path: Path):
        bad_path = tmp_path / "bad.json"
        bad_path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(LoadForgeError, match="Failed to load"):
            load_result(bad_path)

    def test_missing_required_fields_raises_loadforge_error(self, tmp_path: Path):
        bad_path = tmp_path / "incomplete.json"
        bad_path.write_text('{"foo": "bar"}', encoding="utf-8")
        with pytest.raises(LoadForgeError, match="Failed to load"):
            load_result(bad_path)

    def test_file_not_found_raises_loadforge_error(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(LoadForgeError, match="Failed to load"):
            load_result(missing)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_csv_row_count_matches_snapshots(self, tmp_path: Path):
        result = _make_result(snapshot_count=5)
        csv_path = tmp_path / "report.csv"
        export_csv(result, csv_path)

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 1 header + 5 data rows
        assert len(rows) == 6

    def test_csv_headers_correct(self, tmp_path: Path):
        result = _make_result()
        csv_path = tmp_path / "report.csv"
        export_csv(result, csv_path)

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
        assert "elapsed_seconds" in headers
        assert "requests_per_second" in headers
        assert "latency_p50" in headers
        assert "latency_p999" in headers

    def test_csv_cell_values_match_snapshot(self, tmp_path: Path):
        result = _make_result(snapshot_count=1)
        csv_path = tmp_path / "report.csv"
        export_csv(result, csv_path)

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        snap = result.snapshots[0]
        assert float(row["elapsed_seconds"]) == snap.elapsed_seconds
        assert float(row["requests_per_second"]) == snap.requests_per_second
        assert float(row["latency_p50"]) == snap.latency_p50
        assert float(row["latency_p99"]) == snap.latency_p99
        assert int(row["total_requests"]) == snap.total_requests
        assert int(row["total_errors"]) == snap.total_errors

    def test_empty_snapshots_produces_header_only(self, tmp_path: Path):
        result = _TestResult(
            scenario_name="empty",
            start_time=0.0,
            end_time=0.0,
            duration_seconds=0.0,
            pattern_description="none",
            snapshots=[],
            final_summary=None,
        )
        csv_path = tmp_path / "report.csv"
        export_csv(result, csv_path)

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 1  # header only


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------


class TestExportHtml:
    def test_creates_file(self, tmp_path: Path):
        result = _make_result()
        html_path = tmp_path / "report.html"
        export_html(result, html_path)

        assert html_path.exists()
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_contains_chart_divs(self, tmp_path: Path):
        result = _make_result()
        html_path = tmp_path / "report.html"
        export_html(result, html_path)

        content = html_path.read_text(encoding="utf-8")
        assert 'id="chart-throughput"' in content
        assert 'id="chart-latency-bands"' in content
        assert 'id="chart-concurrency"' in content

    def test_contains_scenario_name(self, tmp_path: Path):
        result = _make_result()
        html_path = tmp_path / "report.html"
        export_html(result, html_path)

        content = html_path.read_text(encoding="utf-8")
        assert "test_scenario" in content

    def test_contains_all_report_sections(self, tmp_path: Path):
        result = _make_result()
        html_path = tmp_path / "report.html"
        export_html(result, html_path)

        content = html_path.read_text(encoding="utf-8")
        assert 'id="summary"' in content
        assert 'id="throughput"' in content
        assert 'id="concurrency"' in content
        assert 'id="latency"' in content
        assert 'id="errors"' in content
        assert 'id="raw-data"' in content
        assert "<details>" in content

    def test_contains_theme_toggle(self, tmp_path: Path):
        result = _make_result()
        html_path = tmp_path / "report.html"
        export_html(result, html_path)

        content = html_path.read_text(encoding="utf-8")
        assert "theme-toggle" in content
        assert "toggleTheme" in content
        assert 'data-theme="light"' in content

    def test_creates_parent_dirs(self, tmp_path: Path):
        result = _make_result()
        html_path = tmp_path / "nested" / "deep" / "report.html"
        export_html(result, html_path)

        assert html_path.exists()
