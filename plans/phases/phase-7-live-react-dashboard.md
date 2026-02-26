# Phase 7: Live React Dashboard

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 13–17 |
| **Estimated effort** | 3.5 days |
| **Dependencies** | Phase 4 (Aggregator), Phase 5 (CLI) |
| **Risk level** | Second highest |

## Goal

Real-time WebSocket dashboard showing live metrics during test execution.

## Files to Create — Python

| File | Purpose |
|------|---------|
| `src/loadforge/dashboard/__init__.py` | Dashboard package init |
| `src/loadforge/dashboard/server.py` | FastAPI app with `/ws/metrics` endpoint, serves React SPA via `StaticFiles` |
| `src/loadforge/dashboard/broadcaster.py` | Receives `MetricSnapshot`, serializes to JSON, fans out to WebSocket clients |

## Files to Create — React (`dashboard/` directory)

| File | Purpose |
|------|---------|
| `dashboard/package.json` | React 18, TypeScript, Vite, Recharts, Tailwind CSS |
| `dashboard/vite.config.ts` | Build config, output to `../src/loadforge/dashboard/static/` |
| `dashboard/tsconfig.json` | Strict TypeScript |
| `dashboard/tailwind.config.ts` | Minimal Tailwind config |
| `dashboard/index.html` | Entry HTML |
| `dashboard/src/main.tsx` | Entry point |
| `dashboard/src/App.tsx` | Root component, WebSocket provider |
| `dashboard/src/hooks/useWebSocket.ts` | WebSocket connection, reconnect with backoff, circular buffer (300 snapshots) |
| `dashboard/src/components/Dashboard.tsx` | Grid layout for all panels |
| `dashboard/src/components/MetricsPanel.tsx` | Top row — 5 metric cards (Active Users, RPS, p95, p99, Error Rate) with trend arrows |
| `dashboard/src/components/LatencyChart.tsx` | Recharts `<AreaChart>` — stacked p50/p95/p99 bands |
| `dashboard/src/components/ThroughputChart.tsx` | Recharts `<LineChart>` — RPS over time |
| `dashboard/src/components/ErrorChart.tsx` | Recharts `<AreaChart>` — stacked by error category |
| `dashboard/src/components/ConcurrencyChart.tsx` | Recharts `<AreaChart>` — target (dashed) vs actual (filled) |
| `dashboard/src/components/StatusTable.tsx` | Sortable table with color-coded latency cells |
| `dashboard/src/components/ConnectionStatus.tsx` | Green/red dot + "Connected"/"Disconnected" |
| `dashboard/src/types/metrics.ts` | TypeScript interfaces matching WebSocket message format |

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/integration/test_dashboard.py` | WebSocket connection, message format, client lifecycle |

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  LoadForge Dashboard                          [● Connected] [Stop]  │
├─────────────────────────────────────────────────────────────────────┤
│  [Active Users] [RPS] [p95 Latency] [p99 Latency] [Error Rate]    │
│                                                                     │
│  ┌─ Throughput (RPS) ──────────┐  ┌─ Latency Percentile Bands ──┐ │
│  │  Line chart                 │  │  Area chart (p50/p95/p99)    │ │
│  └─────────────────────────────┘  └──────────────────────────────┘ │
│                                                                     │
│  ┌─ Active Users / Concurrency ┐  ┌─ Error Breakdown ───────────┐ │
│  │  Target (dashed) vs Actual  │  │  Stacked area by category   │ │
│  └─────────────────────────────┘  └──────────────────────────────┘ │
│                                                                     │
│  ┌─ Per-Endpoint Table ────────────────────────────────────────────┐│
│  │  Endpoint │ RPS │ p50 │ p95 │ p99 │ Errors │ Error Rate       ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Build Pipeline

```bash
cd dashboard && npm run build
# Outputs to src/loadforge/dashboard/static/
# Built assets committed to repo — end users get the dashboard without Node.js
```

## Key Design Decisions

- Dashboard is entirely optional. `--dashboard` flag starts the server; without
  it, zero overhead.
- React SPA is minimal: no React Router, no Redux/Zustand — just hooks +
  Recharts. Bundle target < 500KB.
- Charts use `requestAnimationFrame` batching — re-render once per snapshot
  (1/sec), not per data point.
- The WebSocket hook maintains a circular buffer (300 entries = 5 min) for chart
  data. Older data scrolls off.
- Tailwind CSS for styling — utility-first, small bundle, dark mode built-in.
- Server starts in a background thread (not separate process) when
  `--dashboard` flag is used.

## Acceptance Criteria

- [ ] FastAPI WebSocket server streams `MetricSnapshot` at 1s intervals
- [ ] Broadcaster fans out to multiple connected clients
- [ ] React dashboard displays all 6 chart panels + 1 data table
- [ ] MetricsPanel shows 5 top cards with trend arrows
- [ ] WebSocket hook reconnects with exponential backoff
- [ ] Circular buffer maintains 300 snapshots (5 min window)
- [ ] Connection status indicator works correctly
- [ ] `npm run build` produces static assets under 500KB
- [ ] Built assets serve correctly via FastAPI StaticFiles
- [ ] All tests pass: `make validate` + `uv run pytest tests/integration/test_dashboard.py -v`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
