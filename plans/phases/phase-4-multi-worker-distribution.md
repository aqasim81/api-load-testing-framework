# Phase 4: Multi-Worker Distribution

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 7–10 |
| **Estimated effort** | 3 days |
| **Dependencies** | Phase 3 |
| **Risk level** | **HIGHEST** (hardest phase) |

## Goal

Scale to all CPU cores. Coordinator spawns N worker processes. Metrics flow
through shared memory ring buffers. Aggregator computes cross-worker
percentiles.

## Files to Create

| File | Purpose |
|------|---------|
| `src/loadforge/engine/coordinator.py` | Spawns N `multiprocessing.Process` workers, distributes concurrency, health monitoring |
| `src/loadforge/engine/runner.py` | Top-level orchestrator: scenario loading → coordinator → aggregator → dashboard/reports |
| `src/loadforge/metrics/aggregator.py` | Reads worker ring buffers at 1s intervals, computes `MetricSnapshot`, emits via callback |
| `src/loadforge/metrics/histogram.py` | HDR histogram wrapper (range: 1μs to 60s, 3 significant digits) |
| `src/loadforge/metrics/store.py` | In-memory time-series of `MetricSnapshot` |
| `tests/unit/test_histogram.py` | HDR histogram accuracy and percentile correctness |
| `tests/unit/test_collector.py` | Collector correctness |
| `tests/unit/test_aggregator.py` | Aggregation from multiple sources |
| `tests/integration/test_coordinator.py` | Multi-process coordination |
| `tests/integration/test_runner.py` | Full orchestration test |

## Shared Memory Ring Buffer Design

```
Each RequestMetric packed into ~30 bytes:
timestamp(d) + latency_ms(f) + status_code(H) + content_length(I) +
name_hash(Q) + worker_id(B) + error_flag(B)

Ring buffer: 65536 slots × 30 bytes ≈ 2MB per worker

Layout per worker:
[write_idx: uint64 (8 bytes)] [slot_0] [slot_1] ... [slot_65535]
```

## Key Design Decisions

- **Start with `multiprocessing.Queue` for correctness**, then optimize to
  shared memory after. Keep Queue as fallback.
- Each worker gets its own `SharedMemory` (~2MB). Write index is an atomic
  uint64 at buffer start.
- Endpoint name registration: separate `Queue` (rare events — only when a new
  endpoint name is first seen). Aggregator maintains `hash → name` lookup.
- Coordinator divides users evenly: `per_worker = total_users // num_workers`
  (remainder to first worker).
- Two histogram modes: per-second (reset each tick) and cumulative (for final
  summary).

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/unit/test_histogram.py` | HDR histogram records values and reports correct percentiles |
| `tests/unit/test_collector.py` | Collector accumulates and drains metrics correctly |
| `tests/unit/test_aggregator.py` | Aggregator merges metrics from multiple workers into correct snapshots |
| `tests/integration/test_coordinator.py` | Coordinator spawns workers, distributes load, handles shutdown |
| `tests/integration/test_runner.py` | Full lifecycle: init → start → run → stop → report |

## Acceptance Criteria

- [ ] Coordinator spawns N worker processes and distributes concurrency
- [ ] Workers communicate via `multiprocessing.Queue` (or shared memory)
- [ ] Aggregator reads metrics and produces `MetricSnapshot` every second
- [ ] HDR histogram computes accurate percentiles (p50, p75, p90, p95, p99, p999)
- [ ] MetricStore accumulates time-series and provides summary
- [ ] Runner orchestrates the full lifecycle end-to-end
- [ ] Graceful shutdown on SIGINT/SIGTERM — all workers terminate cleanly
- [ ] All tests pass: `make validate` + `uv run pytest tests/integration/ -v`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
