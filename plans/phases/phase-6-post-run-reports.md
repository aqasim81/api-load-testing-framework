# Phase 6: Post-Run Reports

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 11–13 |
| **Estimated effort** | 2 days |
| **Dependencies** | Phase 4 (MetricStore) |

## Goal

Beautiful, interactive HTML reports generated after each test run. Also JSON
and CSV export.

## Files to Create

| File | Purpose |
|------|---------|
| `src/loadforge/reports/__init__.py` | Reports package init |
| `src/loadforge/reports/charts.py` | 7 Plotly chart generation functions |
| `src/loadforge/reports/generator.py` | Report orchestrator — chart generation + template rendering |
| `src/loadforge/reports/exporters.py` | `export_html()`, `export_json()`, `export_csv()` |
| `src/loadforge/reports/templates/report.html.j2` | Main Jinja2 template (clean, modern CSS, dark/light toggle) |
| `src/loadforge/reports/templates/partials/summary.html.j2` | Summary card section |
| `src/loadforge/reports/templates/partials/latency.html.j2` | Latency charts section |
| `src/loadforge/reports/templates/partials/throughput.html.j2` | Throughput section |
| `src/loadforge/reports/templates/partials/errors.html.j2` | Error section |
| `tests/unit/test_charts.py` | Chart generation correctness |

## Chart Functions (`charts.py`)

| Function | Chart Type |
|----------|-----------|
| `throughput_chart(snapshots)` | Line chart — RPS over time with pattern overlay (dashed) |
| `latency_bands_chart(snapshots)` | Area chart — p50/p95/p99 bands over time |
| `latency_histogram(snapshots)` | Distribution histogram of all request latencies |
| `latency_by_endpoint(summary)` | Grouped bar chart — p50/p95/p99 across endpoints |
| `error_breakdown_chart(snapshots)` | Stacked area — errors by status code over time |
| `error_pie_chart(summary)` | Pie chart — total errors by type |
| `concurrency_chart(snapshots)` | Area — target concurrency (dashed) vs actual active users |

## Report Sections

1. Summary card: total requests, duration, avg RPS, p50/p95/p99, error rate, pass/fail
2. Throughput over time (RPS line + pattern overlay)
3. Latency percentile bands over time
4. Latency distribution histogram
5. Latency comparison by endpoint (bar chart)
6. Error breakdown timeline + pie
7. Active users over time (target vs actual)
8. Raw data table (collapsible)

## Key Design Decisions

- Report is a single self-contained HTML file. Plotly.js loaded from CDN (with
  optional offline bundle).
- Plotly charts embedded as JSON — fully interactive (zoom, hover, pan, export
  PNG).
- CSS is inline (no external dependencies). Minimal, modern design with
  dark/light toggle.
- JSON export: full `TestResult` serialized. CSV export: one row per
  `MetricSnapshot` per second.

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/unit/test_charts.py` | Chart functions produce valid Plotly figure objects |

## Acceptance Criteria

- [ ] All 7 chart functions produce valid Plotly figures
- [ ] HTML report is a single self-contained file with interactive charts
- [ ] Report includes all 8 sections (summary through raw data table)
- [ ] Dark/light toggle works in generated report
- [ ] JSON export produces valid, complete `TestResult` serialization
- [ ] CSV export produces one row per second with correct fields
- [ ] All tests pass: `make validate`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
