# Changelog

All notable changes to LoadForge are documented here.

## [Unreleased]

### Added
- `LoadForgeError` and its subclasses (`ScenarioError`, `ConfigError`, `EngineError`,
  `DashboardError`) are now exported from `loadforge` (#4)

### Changed
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
