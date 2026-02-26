# Phase 3: Single-Worker Engine

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 4–7 |
| **Estimated effort** | 2.5 days |
| **Dependencies** | Phase 1, Phase 2 |

## Goal

One async worker process executing scenarios against a real HTTP endpoint. No
multi-process yet. Virtual users scale up/down based on pattern schedule.

## Files to Create

| File | Purpose |
|------|---------|
| `src/loadforge/engine/__init__.py` | Engine package init |
| `src/loadforge/engine/worker.py` | Single-process async worker with uvloop, N virtual user coroutines |
| `src/loadforge/engine/scheduler.py` | Reads `LoadPattern.iter_concurrency()`, emits `(timestamp, target_concurrency)` commands |
| `src/loadforge/engine/rate_limiter.py` | Token-bucket algorithm for concurrency and RPS-based load control |
| `src/loadforge/engine/session.py` | Test session lifecycle: start → running → stopping → completed; handles SIGINT/SIGTERM |
| `src/loadforge/metrics/__init__.py` | Metrics package init |
| `src/loadforge/metrics/collector.py` | In-memory `RequestMetric` collection (replaced by shared memory in Phase 4) |
| `src/loadforge/metrics/models.py` | `RequestMetric`, `MetricSnapshot`, `EndpointMetrics`, `TestResult` |
| `src/loadforge/_internal/logging.py` | Structured logging setup |
| `tests/unit/test_scheduler.py` | Scheduler produces correct concurrency timeline |
| `tests/unit/test_rate_limiter.py` | Token bucket rate limiting correctness |
| `tests/integration/test_worker.py` | Worker against local echo server fixture |

## Key Design Decisions

- Each virtual user is an `asyncio.Task` running an infinite loop. Scaling up =
  create new tasks. Scaling down = cancel most recently created (LIFO) to avoid
  disrupting long-running users.
- `uvloop.install()` called at worker startup — transparent to all async code.
- `HttpClient.metric_callback` in this phase appends to a thread-safe deque.
  The collector reads from the deque periodically.
- Think time uses `asyncio.sleep(random.uniform(min, max))` between tasks.

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/unit/test_scheduler.py` | Scheduler produces correct concurrency timeline from patterns |
| `tests/unit/test_rate_limiter.py` | Token bucket allows/denies requests at correct rates |
| `tests/integration/test_worker.py` | Worker executes scenario against local echo server |

## Acceptance Criteria

- [ ] Worker runs N virtual user coroutines on a uvloop event loop
- [ ] Virtual users execute the setup → task loop → teardown lifecycle
- [ ] Scheduler reads from pattern and emits correct scale commands
- [ ] Rate limiter correctly controls request rate via token bucket
- [ ] Session handles SIGINT/SIGTERM gracefully
- [ ] Collector accumulates `RequestMetric` objects in memory
- [ ] All metric model dataclasses are fully typed
- [ ] All tests pass: `make validate` + `uv run pytest tests/integration/ -v`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
