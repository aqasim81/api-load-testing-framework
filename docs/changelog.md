# Changelog

All notable changes to LoadForge are documented here.

## [Unreleased]

## [0.3.0] — 2026-09-25

### Added
- `DashboardServer` accepts an optional `host` argument; the default is still all interfaces
  (`0.0.0.0`) (#21)

### Changed
- HTML reports load the plotly.js version bundled with the installed plotly.py (now plotly 7 /
  plotly.js 4.1.1) instead of a hardcoded plotly.js 2.35.2, which no longer matched the figure
  JSON (#27)
- Dependencies: rich 15, plotly 7 and starlette 1.x (through fastapi) are supported and locked,
  along with the latest minor and patch releases of the rest (#17, #25, #27, #29)
- Development: mypy 2, GitHub Actions on Node 24, and a test-suite guard that enforces
  loopback-only networking and no hardcoded ports (invariant 5) (#19, #21, #23)

### Fixed
- HTML report: chart grid, zero and axis lines use the page's border colour in the dark theme
  instead of Plotly's near-white light-theme grid (#31)

### Removed
- The unused `websockets` runtime dependency; the dashboard uses `wsproto` through uvicorn (#25)

## [0.2.0] — 2026-09-25

### Added
- `LoadForgeError` and its subclasses (`ScenarioError`, `ConfigError`, `EngineError`,
  `DashboardError`) are now exported from `loadforge` (#4)

### Fixed
- Dashboard: the WebSocket subscribes to snapshots before accepting the handshake, so no early
  snapshot is missed (#2)
- `Coordinator.stop()` records a broken result pipe as a failed worker instead of swallowing every
  error as "No result received"; unexpected errors propagate, and all queues are still closed (#10)
- `LoadTestRunner.run()` raises `EngineError` when worker or metric aggregator shutdown fails after
  an otherwise successful run; during an already-failing run the shutdown failure is logged and the
  original error is kept. SIGINT/SIGTERM handlers are always restored (#12, #14)

## [0.1.0] — 2025

Initial release.

### Phase 0: Code Quality Infrastructure
- Ruff formatting and linting, mypy strict mode, pytest with coverage
- Pre-commit hooks (ruff, gitleaks), CI pipeline (GitHub Actions)

### Phase 1: Foundation + Scenario DSL
- `@scenario`, `@task`, `@setup`, `@teardown` decorators
- `HttpClient` with automatic request timing and `RequestMetric` collection
- Dynamic scenario file loading

### Phase 2: Traffic Patterns
- Seven traffic patterns: constant, ramp, step, spike, diurnal, composite
- `LoadPattern` ABC for custom pattern implementations

### Phase 3: Single-Worker Engine
- Async load generation engine with virtual user scheduling
- Token-bucket rate limiter
- HDR histogram-based latency tracking
- Metric collection and aggregation pipeline

### Phase 4: Multi-Worker Distribution
- Multi-process coordinator distributing VUs across CPU cores
- Queue-based cross-worker metric aggregation
- `MetricStore` for time-series snapshots

### Phase 5: CLI Interface
- `loadforge run` — execute scenarios with live Rich terminal output
- `loadforge init` — scaffold new scenario files
- `loadforge report` — regenerate reports from saved data
- `loadforge dashboard` — replay results in the live dashboard
- Pattern selection via CLI flags, error-rate thresholds

### Phase 6: Post-Run Reports
- Interactive HTML reports with Plotly charts (latency, throughput, errors)
- JSON and CSV export formats
- Jinja2-based report templates with summary, per-endpoint breakdowns

### Phase 7: Live React Dashboard
- FastAPI + uvicorn WebSocket server
- React 18 + Recharts real-time dashboard
- Snapshot broadcasting to connected clients
- Integration with `loadforge run --dashboard`

### Phase 8: Polish, Documentation, Examples
- Comprehensive README with architecture diagram, CLI reference, examples
- Three additional example scenarios (spike, diurnal, composite)
- MIT LICENSE file
- Release workflow for automated PyPI publishing
- Project documentation (changelog, status)
