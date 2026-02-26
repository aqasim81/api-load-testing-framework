# LoadForge — Product Requirements Document

## 1. Overview

**Product Name:** LoadForge
**Tagline:** Forge realistic load tests as Python code
**Category:** Portfolio Project — Developer Tools / Performance Engineering
**Target Users:** Backend engineers, SRE teams, performance engineers

### 1.1 Problem Statement

Existing load testing tools have significant gaps:

- **JMeter** — XML-based configuration, steep learning curve, poor developer ergonomics
- **k6** — JavaScript-only scenarios, limited traffic pattern modeling, advanced features locked behind a cloud service
- **Locust** — Python-based but lacks built-in realistic traffic patterns (spikes, diurnal cycles), uses ZMQ for worker communication (heavy), and its Flask-based web UI feels dated
- **Gatling** — Requires JVM + Scala knowledge, enterprise-focused

The common failure: teams either skip load testing entirely or run simplistic constant-traffic tests that miss real-world bottlenecks like traffic spikes, gradual ramp-ups, and day/night cycles.

### 1.2 Solution

A Python load testing framework where engineers:

1. **Define user scenarios as Python code** using an intuitive decorator-based DSL
2. **Model realistic traffic patterns** (ramps, spikes, diurnal cycles, composites) as first-class objects
3. **Monitor tests in real-time** via a modern React-based live dashboard
4. **Get detailed performance reports** as self-contained interactive HTML files

### 1.3 Why It Stands Out on GitHub

- Performance engineering is a high-demand, low-supply skill
- Demonstrates: async programming, HTTP protocol internals, statistical analysis, multiprocessing, full-stack (Python + React), WebSocket streaming, developer tool UX
- Visual appeal: live dashboard GIFs in README, interactive Plotly reports
- Practical utility: solves a real problem teams face daily

---

## 2. User Personas

### 2.1 Backend Engineer (Primary)

- Wants to load test their API before deploying
- Comfortable with Python, uncomfortable with JMeter XML or Scala
- Needs: quick setup, scenario-as-code, clear results
- Pain point: "I know I should load test but the tools are too complex to set up"

### 2.2 SRE / Performance Engineer (Secondary)

- Runs regular performance benchmarks
- Needs: realistic traffic patterns, CI integration, historical comparison
- Pain point: "Constant-traffic tests don't reflect production — we need spike tests and diurnal simulation"

### 2.3 Team Lead / Architect (Tertiary)

- Reviews performance reports, makes capacity planning decisions
- Needs: shareable HTML reports with clear visualizations
- Pain point: "I need a report I can share with stakeholders, not raw terminal output"

---

## 3. Functional Requirements

### 3.1 Scenario Definition (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| SC-1 | Define scenarios as Python classes with `@scenario` decorator | Must |
| SC-2 | Define tasks (HTTP operations) with `@task` decorator and weight-based distribution | Must |
| SC-3 | Support `@setup` and `@teardown` hooks per virtual user | Must |
| SC-4 | Instrumented HTTP client with auto-timing for GET, POST, PUT, PATCH, DELETE | Must |
| SC-5 | Named requests for per-endpoint metric grouping | Must |
| SC-6 | Environment variable interpolation in scenarios (e.g., `${TOKEN}`) | Should |
| SC-7 | Configurable think time between tasks (min/max seconds) | Must |
| SC-8 | Scaffold new scenario files via `loadforge init` command | Should |

### 3.2 Traffic Patterns (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| TP-1 | Constant: fixed number of concurrent users | Must |
| TP-2 | Ramp: linear ramp from start_users to end_users over duration | Must |
| TP-3 | Step: increase users in discrete staircase steps | Must |
| TP-4 | Spike: sudden burst to peak, then settle to sustain level | Must |
| TP-5 | Diurnal: sine-wave pattern simulating day/night traffic cycles | Must |
| TP-6 | Composite: chain multiple patterns sequentially (e.g., ramp -> constant -> spike -> ramp down) | Must |
| TP-7 | Patterns exposed as first-class objects with `iter_concurrency()` generator interface | Must |

### 3.3 Load Generation Engine (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| EN-1 | Async load generation using uvloop + aiohttp | Must |
| EN-2 | Multi-core distribution via multiprocessing (spread load across CPU cores) | Must |
| EN-3 | Support 10,000-20,000 RPS from a single machine | Must |
| EN-4 | Graceful shutdown on SIGINT/SIGTERM | Must |
| EN-5 | Token-bucket rate limiter for RPS-based load control | Should |
| EN-6 | Virtual user lifecycle: setup -> task loop -> teardown | Must |
| EN-7 | Connection pooling (100+ connections per worker) | Must |
| EN-8 | Worker health monitoring via heartbeats | Should |

### 3.4 Metrics Collection (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| MT-1 | Per-request metrics: timestamp, name, method, status code, latency, content length, error | Must |
| MT-2 | Streaming HDR histograms for accurate percentile computation (p50, p75, p90, p95, p99, p999) | Must |
| MT-3 | Per-second metric snapshots: RPS, active users, latency percentiles, error rate | Must |
| MT-4 | Per-endpoint metric breakdown | Must |
| MT-5 | Error categorization by status code and error type | Must |
| MT-6 | Zero-copy metric transfer via shared memory ring buffers | Should |
| MT-7 | Fallback to multiprocessing.Queue if shared memory is unavailable | Should |

### 3.5 Live Dashboard (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| DB-1 | FastAPI WebSocket server streaming metrics at 1-second intervals | Must |
| DB-2 | React + Recharts frontend with real-time updating charts | Must |
| DB-3 | Dashboard panels: Active Users, RPS, p95 Latency, p99 Latency, Error Rate (top cards) | Must |
| DB-4 | Throughput over time chart (RPS line chart) | Must |
| DB-5 | Latency percentile bands chart (p50/p95/p99 area chart) | Must |
| DB-6 | Active users / concurrency chart (target vs actual) | Must |
| DB-7 | Error breakdown chart (stacked area by status code category) | Must |
| DB-8 | Per-endpoint metrics table (sortable, color-coded) | Must |
| DB-9 | Connection status indicator and test status display | Must |
| DB-10 | Dashboard is optional — tool works fully as CLI-only | Must |
| DB-11 | Built React assets bundled with Python package (no Node.js required at runtime) | Must |

### 3.6 Post-Run Reports (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| RP-1 | Generate self-contained interactive HTML report (single file) | Must |
| RP-2 | Report sections: summary card, throughput over time, latency distribution, latency by endpoint, error breakdown, active users, raw data table | Must |
| RP-3 | Plotly charts embedded as JSON (interactive zoom, hover, export) | Must |
| RP-4 | JSON export of full test results | Should |
| RP-5 | CSV export of time-series metric snapshots | Should |
| RP-6 | Report auto-saved to output directory with timestamped filename | Must |

### 3.7 CLI Interface (Must Have)

| ID | Requirement | Priority |
|----|-------------|----------|
| CL-1 | `loadforge run <scenario.py>` with flags: --users, --duration, --pattern, --workers, --dashboard, --output, --format | Must |
| CL-2 | `loadforge report <results_dir>` — regenerate reports from saved data | Should |
| CL-3 | `loadforge init [name]` — scaffold a new scenario file | Should |
| CL-4 | `loadforge dashboard <results_dir>` — serve dashboard for saved results | Nice to Have |
| CL-5 | Rich terminal live display: elapsed, active users, RPS, p95, error rate | Must |
| CL-6 | `--fail-on-error-rate` threshold for CI integration (non-zero exit code) | Should |
| CL-7 | Verbose logging with `--verbose` flag | Must |
| CL-8 | Pattern-specific flags: --ramp-to, --step-size, --step-duration | Must |
| CL-9 | Complex patterns via TOML config file: `--config loadtest.toml` | Nice to Have |

---

## 4. Non-Functional Requirements

### 4.1 Performance

- Sustain 10,000-20,000 HTTP requests per second from a single machine (4+ cores)
- Metric aggregation latency < 100ms (from request completion to dashboard display)
- Dashboard chart rendering at 60fps with 1-second data updates
- Memory usage < 500MB for a 10-minute test at 10,000 RPS

### 4.2 Reliability

- Graceful degradation: if a worker process crashes, the test continues with remaining workers
- No data loss: metric snapshots persisted to disk for post-run reporting even if dashboard disconnects
- Clean shutdown: all workers terminate cleanly on SIGINT, final report is always generated

### 4.3 Usability

- `pip install loadforge` / `uv add loadforge` — single command installation
- Zero configuration needed for basic usage: `loadforge run scenario.py`
- Scenario DSL feels natural to Python developers (similar mental model to pytest fixtures)
- Reports are self-explanatory (no load testing expertise needed to interpret)

### 4.4 Compatibility

- Python 3.12+
- macOS, Linux (full support with uvloop)
- Windows (degraded: no uvloop, falls back to default asyncio)
- Dashboard works in all modern browsers (Chrome, Firefox, Safari, Edge)

### 4.5 Code Quality

- TypeScript strict mode for React dashboard
- Python strict mypy type checking, zero `any` types
- ruff for linting and formatting
- 80%+ test coverage on business logic
- Pre-commit hooks for automated quality checks

---

## 5. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Async Runtime | `uvloop` | 2-4x faster than default asyncio, libuv-based |
| HTTP Client | `aiohttp` | Battle-tested async HTTP, connection pooling, HTTP/1.1 |
| Multi-core | `multiprocessing` + `shared_memory` | Zero-copy metric transfer, no pickling overhead |
| CLI | `typer` + `rich` | Modern CLI framework with beautiful terminal output |
| Dashboard Backend | `FastAPI` + `uvicorn` | Async WebSocket support, minimal overhead |
| Dashboard Frontend | React 18 + TypeScript + Recharts + Vite | Lightweight, performant charting, modern DX |
| Statistics | `numpy` + `hdrhistogram` (C extension) | Accurate streaming percentiles at high throughput |
| Reports | `plotly` + `jinja2` | Interactive charts in self-contained HTML |
| Project Management | `uv` + `pyproject.toml` | Fast, modern Python project management |
| Linting/Types | `ruff` + `mypy` | Fast linting, strict type safety |
| Testing | `pytest` + `pytest-asyncio` | Standard Python testing with async support |

---

## 6. Success Criteria

### 6.1 Functional

- [ ] A user can write a scenario file and run it with a single command
- [ ] All 6 traffic patterns produce correct concurrency curves
- [ ] Dashboard shows real-time metrics during test execution
- [ ] HTML report is generated automatically after each test run
- [ ] Tool works without dashboard (CLI-only mode)
- [ ] CI integration works via exit code thresholds

### 6.2 Performance

- [ ] Sustains 10,000 RPS against a local echo server on a 4-core machine
- [ ] Metric aggregation delay < 1 second
- [ ] Dashboard renders smoothly at 60fps

### 6.3 Portfolio / GitHub

- [ ] README with architecture diagram, quick start guide, and demo GIF
- [ ] At least 5 example scenarios demonstrating different patterns
- [ ] CI/CD pipeline passing (lint, type-check, test)
- [ ] Installable via `pip install` from PyPI

---

## 7. Out of Scope (v1)

- Distributed load testing across multiple machines (v2)
- Cloud dashboard / hosted results (v2)
- gRPC / WebSocket / GraphQL protocol support (v2)
- Historical result comparison and trend analysis (v2)
- Plugin/extension system for custom protocols (v2)
- Authentication provider integrations (OAuth flows, etc.) (v2)
- Automated performance regression detection (v2)

---

## 8. Competitive Landscape

| Feature | LoadForge | Locust | k6 | Gatling |
|---------|-----------|--------|-----|---------|
| Language | Python | Python | JavaScript | Scala |
| Scenario authoring | Decorator DSL | Class-based | JS scripts | Scala DSL |
| Traffic patterns | 6 built-in + composite | Manual coding | Limited built-in | Built-in |
| Multi-core | Shared-memory multiprocessing | ZMQ distributed | Go goroutines (single process) | Akka actors |
| Live UI | React + WebSocket | Flask + jQuery | Cloud-only | Enterprise-only |
| Reports | Plotly interactive HTML | Basic stats | Cloud-only | HTML reports |
| Percentile accuracy | HDR Histogram | Approximate | HDR Histogram | HDR Histogram |
| Installation | pip / uv | pip | Binary download | JVM + sbt |
| CI integration | Exit codes + thresholds | No built-in | Cloud-only | Maven plugin |

**LoadForge's differentiators:**
1. Traffic patterns as first-class composable objects
2. Shared-memory metrics (zero-copy, lower overhead than ZMQ)
3. Modern React + WebSocket dashboard (vs Flask + jQuery)
4. Self-contained interactive HTML reports (vs cloud-locked)
5. Zero-config CI integration via exit code thresholds
