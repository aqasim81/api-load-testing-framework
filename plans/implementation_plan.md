# LoadForge — Detailed Implementation Plan

## Project Structure

```
api_load_testing_framework/
├── CLAUDE.md                          # Project-specific Claude Code guidance
├── prd.md                             # Product Requirements Document
├── implementation_plan.md             # This file
├── pyproject.toml                     # uv-managed dependencies and config
├── .python-version                    # Python 3.12+
├── .gitignore
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Lint, type-check, test on PR
│       └── release.yml                # PyPI publish on tag
│
├── src/
│   └── loadforge/                     # Main Python package
│       ├── __init__.py                # Public exports, version
│       ├── py.typed                   # PEP 561 marker
│       │
│       ├── dsl/                       # Scenario DSL
│       │   ├── __init__.py
│       │   ├── decorators.py          # @scenario, @task, @setup, @teardown
│       │   ├── scenario.py            # ScenarioDefinition, TaskDefinition dataclasses
│       │   ├── http_client.py         # Instrumented aiohttp wrapper with auto-timing
│       │   └── loader.py             # Dynamic scenario file import (importlib)
│       │
│       ├── patterns/                  # Traffic pattern generators
│       │   ├── __init__.py
│       │   ├── base.py               # LoadPattern ABC
│       │   ├── constant.py           # Fixed concurrent users
│       │   ├── ramp.py               # Linear ramp up/down
│       │   ├── step.py               # Staircase steps
│       │   ├── spike.py              # Sudden burst then sustain
│       │   ├── diurnal.py            # Sine-wave day/night cycle
│       │   └── composite.py          # Chain patterns sequentially
│       │
│       ├── engine/                    # Load generation engine
│       │   ├── __init__.py
│       │   ├── runner.py             # Top-level orchestrator
│       │   ├── worker.py             # Single-process async worker (uvloop)
│       │   ├── coordinator.py        # Multi-process coordinator
│       │   ├── scheduler.py          # Pattern → concurrency schedule
│       │   ├── rate_limiter.py       # Token-bucket rate limiter
│       │   └── session.py            # Test session lifecycle
│       │
│       ├── metrics/                   # Metrics collection and aggregation
│       │   ├── __init__.py
│       │   ├── collector.py          # Per-worker metric collection
│       │   ├── aggregator.py         # Cross-worker aggregation (shared memory)
│       │   ├── histogram.py          # HDR histogram wrapper
│       │   ├── store.py              # Time-series storage
│       │   └── models.py             # RequestMetric, MetricSnapshot, TestResult
│       │
│       ├── dashboard/                 # Live WebSocket dashboard backend
│       │   ├── __init__.py
│       │   ├── server.py             # FastAPI app with /ws/metrics endpoint
│       │   ├── broadcaster.py        # Fan-out snapshots to WS clients
│       │   └── static/               # Bundled React frontend (built assets)
│       │
│       ├── reports/                   # Post-run report generation
│       │   ├── __init__.py
│       │   ├── generator.py          # Report orchestrator
│       │   ├── charts.py             # Plotly chart generation
│       │   ├── exporters.py          # HTML, JSON, CSV export
│       │   └── templates/
│       │       ├── report.html.j2    # Main Jinja2 template
│       │       └── partials/
│       │           ├── summary.html.j2
│       │           ├── latency.html.j2
│       │           ├── throughput.html.j2
│       │           └── errors.html.j2
│       │
│       ├── cli/                       # Typer CLI
│       │   ├── __init__.py
│       │   ├── app.py                # Main typer app
│       │   ├── run.py                # loadforge run command
│       │   ├── report.py             # loadforge report command
│       │   ├── dashboard.py          # loadforge dashboard command
│       │   └── init.py               # loadforge init command
│       │
│       └── _internal/                # Shared utilities
│           ├── __init__.py
│           ├── config.py             # Configuration loading
│           ├── logging.py            # Structured logging
│           ├── types.py              # Shared type aliases and protocols
│           └── errors.py             # Custom exception hierarchy
│
├── dashboard/                         # React frontend source
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── hooks/
│       │   └── useWebSocket.ts       # WebSocket connection hook
│       ├── components/
│       │   ├── Dashboard.tsx          # Main layout
│       │   ├── MetricsPanel.tsx       # Top metric cards (RPS, p99, errors)
│       │   ├── LatencyChart.tsx       # Real-time latency percentile bands
│       │   ├── ThroughputChart.tsx    # RPS over time
│       │   ├── ErrorChart.tsx         # Error rate breakdown
│       │   ├── ConcurrencyChart.tsx   # Active users vs target
│       │   ├── StatusTable.tsx        # Per-endpoint breakdown table
│       │   └── ConnectionStatus.tsx   # WS connection indicator
│       └── types/
│           └── metrics.ts             # TypeScript types matching Python models
│
├── tests/
│   ├── conftest.py                    # Shared fixtures (echo HTTP server, etc.)
│   ├── unit/
│   │   ├── test_decorators.py
│   │   ├── test_scenario.py
│   │   ├── test_patterns.py
│   │   ├── test_scheduler.py
│   │   ├── test_rate_limiter.py
│   │   ├── test_histogram.py
│   │   ├── test_collector.py
│   │   ├── test_aggregator.py
│   │   └── test_charts.py
│   ├── integration/
│   │   ├── test_worker.py
│   │   ├── test_coordinator.py
│   │   ├── test_runner.py
│   │   └── test_dashboard.py
│   └── e2e/
│       ├── test_cli.py
│       └── scenarios/
│           └── example_scenario.py
│
└── examples/
    ├── basic_get.py                   # Simplest scenario
    ├── rest_api.py                    # Multi-endpoint REST API test
    ├── auth_flow.py                   # Login → authenticated requests
    ├── spike_test.py                  # Spike traffic pattern
    ├── diurnal_simulation.py          # 24-hour traffic simulation
    └── composite_pattern.py           # Chained patterns
```

---

## Architecture Overview

```
                                loadforge run scenario.py --dashboard
                                        │
                                        ▼
                                ┌───────────────┐
                                │   CLI (typer)  │
                                │   + rich live  │
                                └───────┬───────┘
                                        │
                                        ▼
                                ┌───────────────┐
                                │    Runner      │  Orchestrator
                                │  (runner.py)   │  - loads scenario
                                └───┬───┬───┬───┘  - starts coordinator
                                    │   │   │      - starts aggregator
                     ┌──────────────┘   │   └──────────────────┐
                     ▼                  ▼                      ▼
              ┌─────────────┐  ┌─────────────┐      ┌─────────────┐
              │  Worker P1   │  │  Worker P2   │      │  Worker Pn   │
              │  (uvloop)    │  │  (uvloop)    │      │  (uvloop)    │
              │              │  │              │      │              │
              │  N virtual   │  │  N virtual   │      │  N virtual   │
              │  users       │  │  users       │      │  users       │
              │  (coroutines)│  │  (coroutines)│      │  (coroutines)│
              └──────┬───────┘  └──────┬───────┘      └──────┬───────┘
                     │                 │                      │
                     └─── shared memory ring buffers ─────────┘
                                       │
                                       ▼
                             ┌─────────────────┐
                             │   Aggregator     │  Reads ring buffers at 1s intervals
                             │  - HDR histograms│  Computes MetricSnapshot per second
                             │  - per-endpoint  │
                             └────┬────────┬───┘
                                  │        │
                        ┌─────────┘        └──────────┐
                        ▼                              ▼
               ┌────────────────┐            ┌────────────────┐
               │   Dashboard     │            │   Store         │
               │  (FastAPI WS)   │            │ (time-series)   │
               │       │         │            │       │         │
               │  React + Charts │            │  Report Gen     │
               │  (live updates) │            │ (Plotly+Jinja2) │
               └────────────────┘            └────────────────┘
```

---

## Core Interfaces

### Scenario DSL — What Users Write

```python
from loadforge import scenario, task, setup, teardown, HttpClient

@scenario(
    name="REST API Load Test",
    base_url="https://api.example.com",
    default_headers={"Authorization": "Bearer ${TOKEN}"},
    think_time=(0.5, 1.5),  # random pause between tasks (seconds)
)
class ApiScenario:

    @setup
    async def on_start(self, client: HttpClient):
        """Called once per virtual user before tasks begin."""
        resp = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "secret",
        })
        data = await resp.json()
        client.headers["Authorization"] = f"Bearer {data['token']}"

    @task(weight=5)
    async def list_items(self, client: HttpClient):
        """GET /items — most common operation."""
        await client.get("/items", name="List Items")

    @task(weight=3)
    async def get_item(self, client: HttpClient):
        """GET /items/:id — second most common."""
        item_id = random.randint(1, 1000)
        await client.get(f"/items/{item_id}", name="Get Item")

    @task(weight=1)
    async def create_item(self, client: HttpClient):
        """POST /items — least common."""
        await client.post("/items", json={"name": "New Item"}, name="Create Item")

    @teardown
    async def on_stop(self, client: HttpClient):
        """Called once per virtual user on shutdown."""
        await client.post("/auth/logout")
```

### Key Python Classes

```python
# --- dsl/decorators.py ---

@dataclass
class TaskDefinition:
    name: str
    func: Callable
    weight: int = 1

@dataclass
class ScenarioDefinition:
    name: str
    cls: type
    base_url: str
    default_headers: dict[str, str]
    tasks: list[TaskDefinition]
    setup_func: Callable | None = None
    teardown_func: Callable | None = None
    think_time: tuple[float, float] = (0.5, 1.5)
```

```python
# --- dsl/http_client.py ---

@dataclass
class RequestMetric:
    """Raw metric emitted for every HTTP request."""
    timestamp: float           # time.monotonic()
    name: str                  # Logical name (e.g., "List Items")
    method: str                # GET, POST, etc.
    url: str                   # Full URL
    status_code: int           # HTTP status
    latency_ms: float          # Response time in milliseconds
    content_length: int        # Response body size
    error: str | None = None   # Error message if failed
    worker_id: int = 0         # Which worker process

class HttpClient:
    """Instrumented async HTTP client. Wraps aiohttp.ClientSession.
    Every request is auto-timed and emits a RequestMetric via callback."""

    async def get(self, path, name=None, **kwargs) -> aiohttp.ClientResponse: ...
    async def post(self, path, name=None, **kwargs) -> aiohttp.ClientResponse: ...
    async def put(self, path, name=None, **kwargs) -> aiohttp.ClientResponse: ...
    async def patch(self, path, name=None, **kwargs) -> aiohttp.ClientResponse: ...
    async def delete(self, path, name=None, **kwargs) -> aiohttp.ClientResponse: ...
```

```python
# --- patterns/base.py ---

class LoadPattern(ABC):
    """Abstract base for all traffic patterns."""

    @abstractmethod
    def iter_concurrency(self, duration_seconds: float, tick_interval: float = 1.0
    ) -> Iterator[tuple[float, int]]:
        """Yield (elapsed_seconds, target_concurrency) tuples."""
        ...

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description."""
        ...

# Implementations:
class ConstantPattern(LoadPattern):    # Fixed users
class RampPattern(LoadPattern):        # Linear ramp start → end
class StepPattern(LoadPattern):        # Staircase increments
class SpikePattern(LoadPattern):       # Burst → sustain
class DiurnalPattern(LoadPattern):     # Sine-wave cycle
class CompositePattern(LoadPattern):   # Chain patterns[(pattern, duration), ...]
```

```python
# --- metrics/models.py ---

@dataclass
class MetricSnapshot:
    """Point-in-time aggregated metrics. Emitted every second."""
    timestamp: float
    elapsed_seconds: float
    active_users: int
    total_requests: int
    requests_per_second: float
    latency_p50: float
    latency_p75: float
    latency_p90: float
    latency_p95: float
    latency_p99: float
    latency_p999: float
    latency_min: float
    latency_max: float
    latency_avg: float
    total_errors: int
    error_rate: float
    errors_by_status: dict[int, int]
    errors_by_type: dict[str, int]
    endpoints: dict[str, EndpointMetrics]

@dataclass
class TestResult:
    """Complete result of a load test run."""
    scenario_name: str
    start_time: float
    end_time: float
    duration_seconds: float
    pattern_description: str
    snapshots: list[MetricSnapshot]
    final_summary: MetricSnapshot
```

### Shared Memory Ring Buffer Design

```python
import struct

# Each RequestMetric packed into ~30 bytes:
# timestamp(d) + latency_ms(f) + status_code(H) + content_length(I) +
# name_hash(Q) + worker_id(B) + error_flag(B)
METRIC_STRUCT = struct.Struct("!dfHIQBB")

# Ring buffer: 65536 slots * 30 bytes = ~2MB per worker
RING_BUFFER_SIZE = 65536

# Layout per worker:
# [write_idx: uint64 (8 bytes)] [slot_0] [slot_1] ... [slot_65535]
# Workers increment write_idx atomically.
# Aggregator tracks last_read_idx per worker.
# Endpoint name lookup: separate multiprocessing.Queue for rare name registrations.
```

### WebSocket Message Format

```typescript
// Sent every 1 second during test execution
interface MetricsMessage {
  type: "snapshot";
  data: {
    timestamp: number;
    elapsed_seconds: number;
    active_users: number;
    rps: number;
    total_requests: number;
    latency: {
      p50: number; p75: number; p90: number;
      p95: number; p99: number; p999: number;
      min: number; max: number; avg: number;
    };
    errors: {
      total: number;
      rate: number;
      by_status: Record<number, number>;
    };
    endpoints: Array<{
      name: string;
      rps: number;
      request_count: number;
      latency_p50: number;
      latency_p95: number;
      latency_p99: number;
      error_count: number;
      error_rate: number;
    }>;
  };
}

// Sent on test state changes
interface TestStatusMessage {
  type: "test_status";
  data: {
    status: "running" | "ramping_up" | "ramping_down" | "completed" | "error";
    pattern: string;
    target_users: number;
    duration: number;
    elapsed: number;
  };
}
```

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  LoadForge Dashboard                          [● Connected] [Stop]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐│
│  │ Active   │  │ RPS      │  │ p95      │  │ p99      │  │ Error   ││
│  │ Users    │  │          │  │ Latency  │  │ Latency  │  │ Rate    ││
│  │  1,250   │  │  8,432   │  │  45ms    │  │  128ms   │  │  0.2%   ││
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └──────────┘│
│                                                                     │
│  ┌──────────────────────────────┐  ┌────────────────────────────── ┐│
│  │  Throughput (RPS over time)  │  │  Latency Percentile Bands    ││
│  │  Line chart                  │  │  Area chart (p50/p95/p99)    ││
│  └──────────────────────────────┘  └──────────────────────────────┘│
│                                                                     │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐│
│  │  Active Users / Concurrency  │  │  Error Breakdown             ││
│  │  Target (dashed) vs Actual   │  │  Stacked area by category    ││
│  └──────────────────────────────┘  └──────────────────────────────┘│
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐│
│  │  Per-Endpoint Table                                            ││
│  │  Endpoint │ RPS  │ p50  │ p95  │ p99  │ Errors │ Error Rate   ││
│  │  List     │ 4200 │ 12ms │ 32ms │ 89ms │   3    │ 0.07%        ││
│  │  Get Item │ 2500 │ 18ms │ 45ms │ 120ms│   1    │ 0.04%        ││
│  │  Create   │  850 │ 35ms │ 90ms │ 210ms│   8    │ 0.94%        ││
│  └────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### CLI Commands

```
loadforge run <scenario_file> [OPTIONS]
  --users, -u         Target concurrent users (default: 10)
  --duration, -d      Test duration in seconds (default: 60)
  --pattern, -p       Pattern: constant|ramp|step|spike|diurnal (default: constant)
  --ramp-to           Ramp pattern: target users
  --step-size         Step pattern: users per step
  --step-duration     Step pattern: seconds per step
  --workers, -w       Worker processes (default: CPU count)
  --dashboard         Start live dashboard
  --dashboard-port    Dashboard port (default: 8089)
  --output, -o        Output directory (default: ./results)
  --format, -f        Report format: html|json|csv (default: html)
  --no-report         Skip report generation
  --fail-on-error-rate  Max error rate before non-zero exit (e.g., 0.05)
  --verbose, -v       Verbose logging

loadforge report <results_dir> [--format html|json|csv]
loadforge init [scenario_name]
loadforge dashboard <results_dir> [--port 8089]
```

---

## Implementation Phases

### Phase 1: Foundation + Scenario DSL
**Days 1-3 | No dependencies | Estimated: 2 days**

**Goal:** Project scaffolding, decorator-based DSL, scenario loading, and instrumented HTTP client. At phase end, a scenario file can be parsed and its structure inspected.

**Create:**
- `pyproject.toml` — All dependencies, build config, tool config (ruff, mypy, pytest)
- `src/loadforge/__init__.py` — Public exports
- `src/loadforge/dsl/decorators.py` — `@scenario` class decorator, `@task` method decorator (with weight), `@setup`, `@teardown`
- `src/loadforge/dsl/scenario.py` — `ScenarioDefinition`, `TaskDefinition` dataclasses, global scenario registry
- `src/loadforge/dsl/loader.py` — `load_scenario(file_path) -> ScenarioDefinition` using `importlib.util.spec_from_file_location`
- `src/loadforge/dsl/http_client.py` — `HttpClient` wrapping `aiohttp.ClientSession`. Every HTTP method call: (1) records `time.monotonic()` before/after, (2) creates `RequestMetric`, (3) invokes `metric_callback`
- `src/loadforge/_internal/types.py` — Shared type aliases
- `src/loadforge/_internal/errors.py` — `LoadForgeError`, `ScenarioError`, `ConfigError`
- `src/loadforge/_internal/config.py` — Configuration loading (env vars, defaults)
- `tests/unit/test_decorators.py` — Verify decorators correctly populate `ScenarioDefinition`
- `tests/unit/test_scenario.py` — Verify scenario registry and loading
- `examples/basic_get.py` — Simplest possible scenario

**Key decisions:**
- `@scenario` transforms a class into a `ScenarioDefinition` by inspecting decorated methods. No subclassing required.
- `HttpClient.metric_callback: Callable[[RequestMetric], None]` — this is the extension point. In Phase 3 it writes to an in-memory list; in Phase 4 it writes to shared memory.
- `loader.py` uses `importlib` to dynamically import `.py` files, then scans module globals for `ScenarioDefinition` instances.

---

### Phase 2: Traffic Patterns
**Days 3-4 | No dependencies (can overlap with Phase 1) | Estimated: 1 day**

**Goal:** All 6 traffic pattern generators implemented and tested. Pure math, no I/O.

**Create:**
- `src/loadforge/patterns/base.py` — `LoadPattern` ABC with `iter_concurrency(duration, tick_interval) -> Iterator[(float, int)]`
- `src/loadforge/patterns/constant.py` — `ConstantPattern(users=N)` yields `(t, N)` every tick
- `src/loadforge/patterns/ramp.py` — `RampPattern(start, end, ramp_duration)` linearly interpolates
- `src/loadforge/patterns/step.py` — `StepPattern(start, step_size, step_duration, steps)` staircase
- `src/loadforge/patterns/spike.py` — `SpikePattern(base, spike_users, spike_duration)` instant burst then decay
- `src/loadforge/patterns/diurnal.py` — `DiurnalPattern(min, max, period)` uses `sin()` for day/night curve
- `src/loadforge/patterns/composite.py` — `CompositePattern([(pattern, duration), ...])` chains patterns sequentially
- `tests/unit/test_patterns.py` — Each pattern produces the expected concurrency curve over time

**Key decisions:**
- Patterns are generators yielding `(elapsed_seconds, target_concurrency)` — trivially composable
- `DiurnalPattern` uses `sin()` with configurable period — a 24-hour cycle can be compressed to 10 minutes for testing
- `CompositePattern` enables real-world scenarios: "ramp 0→500 over 2min, hold 500 for 5min, spike to 2000 for 30s, ramp down to 0 over 1min"

---

### Phase 3: Single-Worker Engine
**Days 4-7 | Depends on: Phase 1, Phase 2 | Estimated: 2.5 days**

**Goal:** One async worker process executing scenarios against a real HTTP endpoint. No multi-process yet. Virtual users scale up/down based on pattern schedule.

**Create:**
- `src/loadforge/engine/worker.py` — Runs a `uvloop` event loop with N virtual user coroutines. Each virtual user: (1) calls `@setup` once, (2) loops: pick weighted-random `@task`, execute, sleep(think_time), (3) calls `@teardown` on shutdown. Receives scale commands to add/remove virtual user tasks.
- `src/loadforge/engine/scheduler.py` — Reads from `LoadPattern.iter_concurrency()` and emits `(timestamp, target_concurrency)` commands at each tick interval
- `src/loadforge/engine/rate_limiter.py` — Token-bucket algorithm. Virtual users acquire a token before each request. Supports both concurrency-based and RPS-based load control.
- `src/loadforge/engine/session.py` — Test session lifecycle: start, running, stopping, completed. Handles SIGINT/SIGTERM.
- `src/loadforge/metrics/collector.py` — Simple in-memory list of `RequestMetric` (will be replaced by shared memory in Phase 4)
- `src/loadforge/metrics/models.py` — `RequestMetric`, `MetricSnapshot`, `EndpointMetrics`, `TestResult`
- `src/loadforge/_internal/logging.py` — Structured logging setup
- `tests/unit/test_scheduler.py`
- `tests/unit/test_rate_limiter.py`
- `tests/integration/test_worker.py` — Uses `aiohttp.web` to create a local echo server as fixture

**Key decisions:**
- Each virtual user is an `asyncio.Task` running an infinite loop. Scaling up = create new tasks. Scaling down = cancel most recently created (LIFO) to avoid disrupting long-running users.
- `uvloop.install()` called at worker startup — transparent to all async code
- `HttpClient.metric_callback` in this phase appends to a thread-safe deque. The collector reads from the deque periodically.
- Think time uses `asyncio.sleep(random.uniform(min, max))` between tasks

---

### Phase 4: Multi-Worker Distribution
**Days 7-10 | Depends on: Phase 3 | Estimated: 3 days | HARDEST PHASE**

**Goal:** Scale to all CPU cores. Coordinator spawns N worker processes. Metrics flow through shared memory ring buffers. Aggregator computes cross-worker percentiles.

**Create:**
- `src/loadforge/engine/coordinator.py`:
  - Spawns N `multiprocessing.Process` workers
  - Distributes target concurrency: `per_worker = total_users // num_workers` (remainder to first worker)
  - Control channel: `multiprocessing.Queue` for commands (scale, stop, status)
  - Worker health monitoring via heartbeat (timestamp in shared memory)
- `src/loadforge/engine/runner.py`:
  - Top-level orchestrator. Wires together: scenario loading → coordinator → aggregator → dashboard/reports
  - Lifecycle: init shared memory → start workers → start aggregator → feed schedule → wait → shutdown → generate report
  - Handles SIGINT/SIGTERM gracefully
- `src/loadforge/metrics/aggregator.py`:
  - Runs in main process (background thread)
  - Reads all worker ring buffers at 1-second intervals
  - Feeds raw metrics into per-endpoint HDR histograms
  - Emits `MetricSnapshot` every tick via `on_snapshot` callback
  - Two histogram modes: per-second (reset each tick) and cumulative (for final summary)
- `src/loadforge/metrics/histogram.py`:
  - Wraps `hdrhistogram` C extension
  - Pre-allocated with range 1us to 60s, 3 significant digits
  - Methods: `record_value(latency_ms)`, `get_percentile(p)`, `reset()`
- `src/loadforge/metrics/store.py`:
  - In-memory list of `MetricSnapshot` (the time-series)
  - Methods: `append(snapshot)`, `get_all()`, `get_summary() -> MetricSnapshot`
- `tests/unit/test_histogram.py`
- `tests/unit/test_collector.py`
- `tests/unit/test_aggregator.py`
- `tests/integration/test_coordinator.py`
- `tests/integration/test_runner.py`

**Key decisions:**
- **Start with `multiprocessing.Queue` for correctness**, then optimize to shared memory. Keep Queue as fallback.
- Shared memory ring buffers: each worker gets its own `SharedMemory` (~2MB). Write index is an atomic uint64 at buffer start. Workers `struct.pack_into`, aggregator reads between `last_read_idx` and `write_idx`. Overflow handled by overwriting old entries (aggregator reads faster than writes).
- Endpoint name registration: separate `Queue` (rare events — only when a new endpoint name is first seen). Aggregator maintains `hash -> name` lookup.
- `coordinator.py` divides users evenly across workers. If pattern says "scale to 500" with 4 workers: 125 each.

---

### Phase 5: CLI Interface
**Days 10-11 | Depends on: Phase 4 | Estimated: 1.5 days**

**Goal:** Full typer CLI that wires everything together. Users can run load tests from the command line with live terminal output.

**Create:**
- `src/loadforge/cli/app.py` — Main `typer.Typer()` app with subcommands
- `src/loadforge/cli/run.py` — `loadforge run` implementation:
  - Parses CLI flags into `LoadPattern` + `LoadTestRunner` config
  - Starts `rich.live.Live` display showing: elapsed time, active users, RPS, p95 latency, error rate — updating every second
  - Pattern selection: `--pattern constant --users 100` or `--pattern ramp --users 10 --ramp-to 500`
  - Complex patterns: `--config loadtest.toml` (TOML defines pattern chain)
  - Exit code: non-zero if `--fail-on-error-rate` threshold exceeded
- `src/loadforge/cli/report.py` — `loadforge report` implementation
- `src/loadforge/cli/init.py` — `loadforge init` scaffolds scenario from embedded template
- `src/loadforge/cli/dashboard.py` — Placeholder, wired in Phase 7
- `tests/e2e/test_cli.py` — End-to-end CLI tests
- `tests/e2e/scenarios/example_scenario.py`
- `examples/rest_api.py`
- `examples/auth_flow.py`

**Key decisions:**
- `rich.live.Live` provides a beautiful terminal experience without a full TUI framework
- The live display uses a `rich.table.Table` that refreshes every second with the latest `MetricSnapshot`
- Pattern-to-flag mapping: simple patterns via flags, complex patterns via TOML config
- `loadforge init` writes a templated scenario file to the current directory

---

### Phase 6: Post-Run Reports
**Days 11-13 | Depends on: Phase 4 (MetricStore) | Estimated: 2 days**

**Goal:** Beautiful, interactive HTML reports generated after each test run. Also JSON and CSV export.

**Create:**
- `src/loadforge/reports/charts.py` — Plotly chart generation functions:
  - `throughput_chart(snapshots)` — Line chart: RPS over time, with pattern overlay (dashed)
  - `latency_bands_chart(snapshots)` — Area chart: p50/p95/p99 bands over time
  - `latency_histogram(snapshots)` — Distribution histogram of all request latencies
  - `latency_by_endpoint(summary)` — Grouped bar chart comparing p50/p95/p99 across endpoints
  - `error_breakdown_chart(snapshots)` — Stacked area: errors by status code over time
  - `error_pie_chart(summary)` — Pie chart of total errors by type
  - `concurrency_chart(snapshots)` — Area: target concurrency (dashed) vs actual active users
- `src/loadforge/reports/generator.py` — Orchestrates chart generation + template rendering
- `src/loadforge/reports/exporters.py` — `export_html(result, path)`, `export_json(result, path)`, `export_csv(result, path)`
- `src/loadforge/reports/templates/report.html.j2` — Main template (clean, modern CSS, dark/light toggle)
- `src/loadforge/reports/templates/partials/summary.html.j2` — Summary card section
- `src/loadforge/reports/templates/partials/latency.html.j2` — Latency charts section
- `src/loadforge/reports/templates/partials/throughput.html.j2` — Throughput section
- `src/loadforge/reports/templates/partials/errors.html.j2` — Error section
- `tests/unit/test_charts.py`

**Report sections:**
1. Summary card: total requests, duration, avg RPS, p50/p95/p99, error rate, pass/fail
2. Throughput over time (RPS line + pattern overlay)
3. Latency percentile bands over time
4. Latency distribution histogram
5. Latency comparison by endpoint (bar chart)
6. Error breakdown timeline + pie
7. Active users over time (target vs actual)
8. Raw data table (collapsible)

**Key decisions:**
- Report is a single self-contained HTML file. Plotly.js loaded from CDN (with optional offline bundle).
- Plotly charts embedded as JSON — fully interactive (zoom, hover, pan, export PNG)
- CSS is inline (no external dependencies). Minimal, modern design with dark/light toggle.
- JSON export: full `TestResult` serialized. CSV export: one row per `MetricSnapshot` per second.

---

### Phase 7: Live React Dashboard
**Days 13-17 | Depends on: Phase 4 (Aggregator), Phase 5 (CLI) | Estimated: 3.5 days**

**Goal:** Real-time WebSocket dashboard showing live metrics during test execution.

**Create (Python):**
- `src/loadforge/dashboard/server.py`:
  - FastAPI app with `@app.websocket("/ws/metrics")` endpoint
  - Serves bundled React SPA via `StaticFiles` mount at `/`
  - Starts in a background thread (not a separate process) when `--dashboard` flag is used
- `src/loadforge/dashboard/broadcaster.py`:
  - Receives `MetricSnapshot` from Aggregator's `on_snapshot` callback
  - Serializes to JSON WebSocket message format
  - Fans out to all connected WebSocket clients
  - Handles client connect/disconnect gracefully

**Create (React — `dashboard/` directory):**
- `package.json` — React 18, TypeScript, Vite, Recharts, Tailwind CSS
- `vite.config.ts` — Build config, output to `../src/loadforge/dashboard/static/`
- `tsconfig.json` — Strict TypeScript
- `tailwind.config.ts` — Minimal Tailwind config
- `src/main.tsx` — Entry point
- `src/App.tsx` — Root component, WebSocket provider
- `src/hooks/useWebSocket.ts`:
  - Connects to `ws://localhost:{port}/ws/metrics`
  - Reconnects on disconnect with exponential backoff
  - Maintains circular buffer of last 300 snapshots (5 minutes)
  - Exposes: `{ connected, snapshots, latestSnapshot, testStatus }`
- `src/components/Dashboard.tsx` — Grid layout for all panels
- `src/components/MetricsPanel.tsx` — Top row: 5 metric cards (Active Users, RPS, p95, p99, Error Rate) with trend arrows
- `src/components/LatencyChart.tsx` — Recharts `<AreaChart>` with stacked p50/p95/p99 bands
- `src/components/ThroughputChart.tsx` — Recharts `<LineChart>` RPS over time (green line)
- `src/components/ErrorChart.tsx` — Recharts `<AreaChart>` stacked by error category
- `src/components/ConcurrencyChart.tsx` — Recharts `<AreaChart>` target (dashed) vs actual (filled)
- `src/components/StatusTable.tsx` — Sortable table with color-coded latency cells
- `src/components/ConnectionStatus.tsx` — Green/red dot + "Connected"/"Disconnected"
- `src/types/metrics.ts` — TypeScript interfaces matching WebSocket message format
- `tests/integration/test_dashboard.py` — Test WebSocket connection and message format

**Build pipeline:**
- `npm run build` in `dashboard/` outputs to `src/loadforge/dashboard/static/`
- Built assets committed to repo — end users get the dashboard without Node.js
- `pyproject.toml` script: `build-dashboard = "cd dashboard && npm run build"`

**Key decisions:**
- Dashboard is entirely optional. `--dashboard` flag starts the server; without it, no overhead.
- React SPA is minimal: no React Router, no Redux/Zustand — just hooks + Recharts. Bundle target < 500KB.
- Charts use `requestAnimationFrame` batching — re-render once per snapshot (1/sec), not per data point.
- The WebSocket hook maintains a circular buffer (300 entries = 5 min) for chart data. Older data scrolls off.
- Tailwind CSS for styling — utility-first, small bundle, dark mode built-in.

---

### Phase 8: Polish, Documentation, Examples
**Days 17-20 | Depends on: All phases | Estimated: 2.5 days**

**Tasks:**

**Code quality:**
- Add `py.typed` marker for PEP 561
- Run `mypy --strict` — fix all type errors
- Run `ruff check` and `ruff format` — fix all violations
- Add thorough docstrings to all public APIs
- Set up pre-commit hooks (ruff, mypy)

**Testing:**
- Ensure 80%+ coverage on business logic
- Add any missing edge case tests
- Integration test: full end-to-end run against echo server

**Documentation:**
- `README.md` — Problem statement, quick start, architecture diagram (Mermaid), CLI reference, examples, comparison table, demo GIF
- `CLAUDE.md` — Project-specific guidance for future Claude Code sessions
- Example scenarios: `spike_test.py`, `diurnal_simulation.py`, `composite_pattern.py`

**CI/CD:**
- `.github/workflows/ci.yml` — On PR: `ruff check`, `mypy`, `pytest` (Python 3.12+)
- `.github/workflows/release.yml` — On tag: build + publish to PyPI

**Polish:**
- Record GIF/video of running a test with live dashboard
- Ensure `pip install loadforge` works end-to-end
- Test on macOS + Linux
- Verify Windows fallback (no uvloop)

---

## Phase Dependencies and Critical Path

```
Phase 1 (DSL)         ─────┐
                            ├──→ Phase 3 (Single Worker) ──→ Phase 4 (Multi-Worker)
Phase 2 (Patterns)    ─────┘                                       │
                                                    ┌──────────────┼───────────────┐
                                                    ▼              ▼               ▼
                                              Phase 5 (CLI)  Phase 6 (Reports)    │
                                                    │              │               │
                                                    └──────┬───────┘               │
                                                           ▼                       │
                                                     Phase 7 (Dashboard) ◄─────────┘
                                                           │
                                                           ▼
                                                     Phase 8 (Polish)
```

**Critical path:** Phase 1 → Phase 3 → Phase 4 → Phase 7 → Phase 8

**Highest risk:** Phase 4 (shared memory multiprocessing) — mitigated by starting with Queue fallback.
**Second highest risk:** Phase 7 (React dashboard) — mitigated by keeping the SPA minimal.

---

## Dependencies

### Python Runtime Dependencies

```
aiohttp>=3.9              # Async HTTP client
uvloop>=0.19              # Fast event loop (non-Windows)
typer>=0.12               # CLI framework
rich>=13.0                # Terminal formatting and live display
numpy>=1.26               # Numerical computation
hdrhistogram>=0.10        # HDR histogram (C extension)
jinja2>=3.1               # HTML report templates
plotly>=5.18              # Interactive charts
fastapi>=0.110            # WebSocket dashboard server
uvicorn>=0.27             # ASGI server
websockets>=12.0          # WebSocket protocol
```

### Python Dev Dependencies

```
pytest>=8.0               # Testing framework
pytest-asyncio>=0.23      # Async test support
pytest-cov>=4.1           # Coverage reporting
aioresponses>=0.7         # Mock aiohttp requests
ruff>=0.3                 # Linter and formatter
mypy>=1.8                 # Type checker
pre-commit>=3.6           # Git hooks
```

### Dashboard (React) Dependencies

```
react@18                  # UI framework
react-dom@18
typescript@5              # Type safety
vite@5                    # Build tool
recharts@2                # Charting library
tailwindcss@3             # Utility CSS
```

---

## Risk Register

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|------------|
| 1 | Shared memory ring buffer bugs (races, corruption) | High | Medium | Start with `multiprocessing.Queue`; optimize to shared memory after correctness proven. Keep Queue as fallback. |
| 2 | Cannot achieve 10-20k RPS target | Medium | Low | Profile early with `aiohttp` connection pooling (100 conn/worker). Bottleneck is likely target server, not framework. Test against local uvicorn echo server. |
| 3 | HDR histogram C extension performance | Medium | Low | Pre-allocate with 1us-60s range, 3 significant digits. If pure-Python fallback is too slow, the C extension is mandatory. |
| 4 | Dashboard React bundle too large | Low | Low | No routing, no state management library. Just hooks + Recharts. Target < 500KB. Tree-shake aggressively. |
| 5 | uvloop not available on Windows | Low | Certain | Conditional dependency: `uvloop>=0.19; sys_platform != 'win32'`. Runtime detection: `try: import uvloop` with asyncio fallback. |
| 6 | Scope creep on dashboard features | Medium | Medium | Strict feature freeze after Phase 7. Dashboard shows exactly 6 panels + 1 table. No filters, no historical comparison, no settings. |
| 7 | Multiprocessing pickling issues | Medium | Medium | Workers receive scenario as file path (string), not as object. Each worker re-imports the scenario file independently. |

---

## Verification Plan

### Unit Tests
```bash
uv run pytest tests/unit/ -v --cov=loadforge --cov-report=term-missing
# Target: 80%+ coverage on business logic
```

### Integration Tests
```bash
uv run pytest tests/integration/ -v
# Uses local aiohttp echo server as fixture
```

### End-to-End Manual Verification

1. **Basic run:**
   ```bash
   loadforge run examples/basic_get.py --users 50 --duration 30
   ```
   Verify: rich terminal output updates every second, report generated in `./results/`

2. **Ramp pattern:**
   ```bash
   loadforge run examples/rest_api.py --users 10 --duration 60 --pattern ramp --ramp-to 200
   ```
   Verify: active users ramp from 10 to 200 over 60 seconds

3. **Dashboard:**
   ```bash
   loadforge run examples/rest_api.py --users 100 --duration 120 --pattern step --step-size 25 --step-duration 30 --dashboard
   ```
   Open `http://localhost:8089`. Verify: all 6 charts update live, per-endpoint table populates, connection status shows green

4. **Report inspection:**
   Open generated HTML report. Verify: all Plotly charts are interactive (zoom, hover, pan). Dark/light toggle works.

5. **CI integration:**
   ```bash
   loadforge run examples/basic_get.py --users 10 --duration 10 --fail-on-error-rate 0.01
   echo $?  # Should be non-zero if target server returns errors
   ```

6. **Type check and lint:**
   ```bash
   uv run mypy src/            # Zero errors in strict mode
   uv run ruff check src/ tests/  # Zero violations
   ```
