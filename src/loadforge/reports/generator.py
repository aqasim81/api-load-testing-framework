"""Report orchestrator — generates all charts and renders the HTML template."""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

import jinja2

from loadforge.reports import charts

if TYPE_CHECKING:
    from loadforge.metrics.models import TestResult


class ReportGenerator:
    """Orchestrates chart generation and Jinja2 template rendering.

    Attributes:
        _result: The ``TestResult`` to generate a report for.
        _env: Jinja2 template environment.
    """

    def __init__(self, result: TestResult) -> None:
        """Initialize the generator with a test result.

        Args:
            result: Completed test result to visualize.
        """
        self._result = result
        self._env = _build_jinja_env()

    def render_html(self) -> str:
        """Render the full HTML report as a string.

        Returns:
            Complete HTML document as a string.
        """
        result = self._result
        snapshots = result.snapshots
        summary = result.final_summary

        # Generate all charts and serialize to JSON
        figures: dict[str, str] = {
            "chart-throughput": charts.figure_to_json(
                charts.throughput_chart(snapshots),
            ),
            "chart-concurrency": charts.figure_to_json(
                charts.concurrency_chart(snapshots),
            ),
            "chart-latency-bands": charts.figure_to_json(
                charts.latency_bands_chart(snapshots),
            ),
            "chart-latency-hist": charts.figure_to_json(
                charts.latency_histogram_chart(snapshots),
            ),
            "chart-latency-endpoint": charts.figure_to_json(
                charts.latency_by_endpoint_chart(
                    summary.endpoints if summary else {},
                ),
            ),
            "chart-error-breakdown": charts.figure_to_json(
                charts.error_breakdown_chart(snapshots),
            ),
            "chart-error-pie": charts.figure_to_json(
                charts.error_pie_chart(
                    summary.endpoints if summary else {},
                ),
            ),
        }

        context = _build_context(result, figures)
        template = self._env.get_template("report.html.j2")
        return template.render(**context)


def _build_jinja_env() -> jinja2.Environment:
    """Create a Jinja2 Environment loading templates from the package.

    Returns:
        Configured Jinja2 Environment with autoescape enabled.  Use the
        ``|safe`` filter in templates for trusted content (chart JSON).
    """
    loader = jinja2.PackageLoader("loadforge.reports", "templates")
    return jinja2.Environment(loader=loader, autoescape=True)


def _build_context(
    result: TestResult,
    figures: dict[str, str],
) -> dict[str, object]:
    """Build the template context dict from a TestResult.

    Args:
        result: Completed test result.
        figures: Dict mapping chart div IDs to Plotly JSON strings.

    Returns:
        Context dict for Jinja2 template rendering.
    """
    summary = result.final_summary
    return {
        "scenario_name": result.scenario_name,
        "pattern_description": result.pattern_description,
        "duration_seconds": result.duration_seconds,
        "total_requests": summary.total_requests if summary else 0,
        "avg_rps": summary.requests_per_second if summary else 0.0,
        "p50": summary.latency_p50 if summary else 0.0,
        "p95": summary.latency_p95 if summary else 0.0,
        "p99": summary.latency_p99 if summary else 0.0,
        "total_errors": summary.total_errors if summary else 0,
        "error_rate_pct": (summary.error_rate * 100) if summary else 0.0,
        "snapshots": result.snapshots,
        "chart_figures_json": json.dumps(figures),
        "generated_at": datetime.datetime.now(tz=datetime.UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC",
        ),
    }
