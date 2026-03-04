"""Plotly chart generation functions for LoadForge reports.

Each function accepts metric data and returns a fully configured
``plotly.graph_objects.Figure`` ready for HTML embedding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import plotly.graph_objects as go

if TYPE_CHECKING:
    from loadforge.metrics.models import EndpointMetrics, MetricSnapshot


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_COLORS = {
    "green": "#22c55e",
    "blue": "#3b82f6",
    "orange": "#f97316",
    "red": "#ef4444",
    "purple": "#a855f7",
    "cyan": "#06b6d4",
    "amber": "#f59e0b",
    "gray": "#6b7280",
}

_STATUS_COLORS: dict[int, str] = {
    400: "#f59e0b",
    401: "#f97316",
    403: "#ef4444",
    404: "#a855f7",
    429: "#06b6d4",
    500: "#dc2626",
    502: "#b91c1c",
    503: "#991b1b",
}


def _base_layout(
    title: str,
    xaxis_title: str,
    yaxis_title: str,
) -> dict[str, object]:
    """Build a shared Plotly layout dict.

    Args:
        title: Chart title.
        xaxis_title: X axis label.
        yaxis_title: Y axis label.

    Returns:
        Layout dict suitable for ``go.Figure(layout=...)``.
    """
    return {
        "title": {"text": title, "font": {"size": 16}},
        "xaxis": {"title": xaxis_title},
        "yaxis": {"title": yaxis_title},
        "template": "plotly_white",
        "hovermode": "x unified",
        "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
        "height": 400,
    }


def _empty_figure(message: str) -> go.Figure:
    """Return an empty figure with a centered annotation.

    Args:
        message: Text to display in the empty chart area.

    Returns:
        A Plotly figure with no data and a centered annotation.
    """
    fig = go.Figure()
    fig.update_layout(
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 16, "color": _COLORS["gray"]},
            }
        ],
        xaxis={"visible": False},
        yaxis={"visible": False},
        height=300,
    )
    return fig


# ---------------------------------------------------------------------------
# Chart functions
# ---------------------------------------------------------------------------


def throughput_chart(snapshots: list[MetricSnapshot]) -> go.Figure:
    """Build an RPS-over-time line chart.

    Args:
        snapshots: Time-series of ``MetricSnapshot`` objects.

    Returns:
        Interactive Plotly figure with RPS over elapsed seconds.
    """
    if not snapshots:
        return _empty_figure("No throughput data collected")

    x = [s.elapsed_seconds for s in snapshots]
    y = [s.requests_per_second for s in snapshots]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name="RPS",
            line={"color": _COLORS["green"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(34, 197, 94, 0.1)",
        )
    )
    fig.update_layout(**_base_layout("Throughput", "Elapsed (s)", "Requests/sec"))
    return fig


def latency_bands_chart(snapshots: list[MetricSnapshot]) -> go.Figure:
    """Build a latency percentile bands area chart (p50/p95/p99).

    Args:
        snapshots: Time-series of ``MetricSnapshot`` objects.

    Returns:
        Stacked area chart with p50, p95, p99 latency bands over time.
    """
    if not snapshots:
        return _empty_figure("No latency data collected")

    x = [s.elapsed_seconds for s in snapshots]

    fig = go.Figure()

    # p99 (outermost band)
    fig.add_trace(
        go.Scatter(
            x=x,
            y=[s.latency_p99 for s in snapshots],
            mode="lines",
            name="p99",
            line={"color": _COLORS["red"], "width": 1},
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.15)",
        )
    )
    # p95 (middle band)
    fig.add_trace(
        go.Scatter(
            x=x,
            y=[s.latency_p95 for s in snapshots],
            mode="lines",
            name="p95",
            line={"color": _COLORS["orange"], "width": 1},
            fill="tozeroy",
            fillcolor="rgba(249, 115, 22, 0.2)",
        )
    )
    # p50 (innermost band)
    fig.add_trace(
        go.Scatter(
            x=x,
            y=[s.latency_p50 for s in snapshots],
            mode="lines",
            name="p50",
            line={"color": _COLORS["blue"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.25)",
        )
    )

    fig.update_layout(**_base_layout("Latency Percentiles", "Elapsed (s)", "Latency (ms)"))
    return fig


def latency_histogram_chart(snapshots: list[MetricSnapshot]) -> go.Figure:
    """Build a latency distribution histogram from snapshot averages.

    Since raw per-request latencies are not stored, this uses per-snapshot
    average latencies weighted by request count as an approximation.

    Args:
        snapshots: Time-series of ``MetricSnapshot`` objects.

    Returns:
        Histogram figure showing approximate latency distribution.
    """
    if not snapshots:
        return _empty_figure("No latency data collected")

    # Use per-snapshot average latencies directly — one value per snapshot
    x_values = [s.latency_avg for s in snapshots if s.total_requests > 0]

    if not x_values:
        return _empty_figure("No latency data collected")

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=x_values,
            name="Latency",
            marker_color=_COLORS["blue"],
            opacity=0.8,
            nbinsx=50,
        )
    )
    fig.update_layout(
        **_base_layout("Latency Distribution", "Latency (ms)", "Frequency"),
        bargap=0.05,
    )
    return fig


def latency_by_endpoint_chart(endpoints: dict[str, EndpointMetrics]) -> go.Figure:
    """Build a grouped bar chart comparing p50/p95/p99 across endpoints.

    Args:
        endpoints: Per-endpoint metrics keyed by endpoint name.

    Returns:
        Grouped bar chart with one bar group per endpoint.
    """
    if not endpoints:
        return _empty_figure("No endpoint data collected")

    names = list(endpoints.keys())
    p50 = [endpoints[n].latency_p50 for n in names]
    p95 = [endpoints[n].latency_p95 for n in names]
    p99 = [endpoints[n].latency_p99 for n in names]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="p50", x=names, y=p50, marker_color=_COLORS["blue"]))
    fig.add_trace(go.Bar(name="p95", x=names, y=p95, marker_color=_COLORS["orange"]))
    fig.add_trace(go.Bar(name="p99", x=names, y=p99, marker_color=_COLORS["red"]))

    fig.update_layout(
        **_base_layout("Latency by Endpoint", "Endpoint", "Latency (ms)"),
        barmode="group",
    )
    return fig


def error_breakdown_chart(snapshots: list[MetricSnapshot]) -> go.Figure:
    """Build a stacked area chart of errors by status code over time.

    Args:
        snapshots: Time-series of ``MetricSnapshot`` objects.

    Returns:
        Stacked area chart with one trace per HTTP status code.
    """
    if not snapshots:
        return _empty_figure("No error data collected")

    # Collect all status codes seen across all snapshots
    all_codes: set[int] = set()
    for s in snapshots:
        all_codes.update(s.errors_by_status.keys())

    if not all_codes:
        return _empty_figure("No errors recorded")

    x = [s.elapsed_seconds for s in snapshots]

    fig = go.Figure()
    for code in sorted(all_codes):
        y = [s.errors_by_status.get(code, 0) for s in snapshots]
        color = _STATUS_COLORS.get(code, _COLORS["gray"])
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines",
                name=f"HTTP {code}",
                line={"width": 0.5, "color": color},
                stackgroup="errors",
            )
        )

    fig.update_layout(**_base_layout("Errors by Status Code", "Elapsed (s)", "Error Count"))
    return fig


def error_pie_chart(endpoints: dict[str, EndpointMetrics]) -> go.Figure:
    """Build a pie chart showing error distribution across endpoints.

    Args:
        endpoints: Per-endpoint metrics from the final summary.

    Returns:
        Pie chart with one slice per endpoint that has errors.
    """
    names: list[str] = []
    counts: list[int] = []
    for name, ep in endpoints.items():
        if ep.error_count > 0:
            names.append(name)
            counts.append(ep.error_count)

    if not names:
        return _empty_figure("No errors recorded")

    fig = go.Figure()
    fig.add_trace(
        go.Pie(
            labels=names,
            values=counts,
            hole=0.4,
            textinfo="label+percent",
            marker={
                "colors": [
                    _COLORS["red"],
                    _COLORS["orange"],
                    _COLORS["amber"],
                    _COLORS["purple"],
                    _COLORS["cyan"],
                    _COLORS["gray"],
                ]
            },
        )
    )
    fig.update_layout(
        title={"text": "Errors by Endpoint", "font": {"size": 16}},
        height=400,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return fig


def concurrency_chart(snapshots: list[MetricSnapshot]) -> go.Figure:
    """Build an active-users-over-time area chart.

    Args:
        snapshots: Time-series of ``MetricSnapshot`` objects.

    Returns:
        Area chart showing active virtual users over elapsed seconds.
    """
    if not snapshots:
        return _empty_figure("No concurrency data collected")

    x = [s.elapsed_seconds for s in snapshots]
    y = [s.active_users for s in snapshots]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name="Active Users",
            line={"color": _COLORS["purple"], "width": 2},
            fill="tozeroy",
            fillcolor="rgba(168, 85, 247, 0.15)",
        )
    )
    fig.update_layout(**_base_layout("Active Users", "Elapsed (s)", "Virtual Users"))
    return fig


# ---------------------------------------------------------------------------
# Serialization helper
# ---------------------------------------------------------------------------


def figure_to_json(fig: go.Figure) -> str:
    """Serialize a Plotly figure to a JSON string for HTML embedding.

    Args:
        fig: Plotly figure to serialize.

    Returns:
        JSON string representation of the figure.
    """
    result: str = fig.to_json()
    return result
