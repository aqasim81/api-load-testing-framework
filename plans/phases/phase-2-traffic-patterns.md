# Phase 2: Traffic Patterns

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 3–4 |
| **Estimated effort** | 1 day |
| **Dependencies** | None (can overlap with Phase 1) |

## Goal

All 6 traffic pattern generators implemented and tested. Pure math, no I/O.

## Files to Create

| File | Purpose |
|------|---------|
| `src/loadforge/patterns/__init__.py` | Patterns package init |
| `src/loadforge/patterns/base.py` | `LoadPattern` ABC with `iter_concurrency()` and `describe()` |
| `src/loadforge/patterns/constant.py` | `ConstantPattern(users=N)` — fixed concurrent users |
| `src/loadforge/patterns/ramp.py` | `RampPattern(start, end, ramp_duration)` — linear interpolation |
| `src/loadforge/patterns/step.py` | `StepPattern(start, step_size, step_duration, steps)` — staircase |
| `src/loadforge/patterns/spike.py` | `SpikePattern(base, spike_users, spike_duration)` — burst then decay |
| `src/loadforge/patterns/diurnal.py` | `DiurnalPattern(min, max, period)` — sine-wave day/night cycle |
| `src/loadforge/patterns/composite.py` | `CompositePattern([(pattern, duration), ...])` — chain patterns |
| `tests/unit/test_patterns.py` | Each pattern produces expected concurrency curve |

## Key Design Decisions

- Patterns are generators yielding `(elapsed_seconds, target_concurrency)` —
  trivially composable.
- `DiurnalPattern` uses `sin()` with configurable period — a 24-hour cycle can
  be compressed to 10 minutes for testing.
- `CompositePattern` enables real-world scenarios: "ramp 0→500 over 2min, hold
  500 for 5min, spike to 2000 for 30s, ramp down to 0 over 1min".

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/unit/test_patterns.py` | Each pattern produces the expected concurrency curve over time |

## Acceptance Criteria

- [ ] All 6 pattern types implemented with `iter_concurrency()` and `describe()`
- [ ] `ConstantPattern` yields constant `N` at every tick
- [ ] `RampPattern` linearly interpolates between start and end
- [ ] `StepPattern` produces staircase increments
- [ ] `SpikePattern` produces burst then decay
- [ ] `DiurnalPattern` produces sine-wave curve
- [ ] `CompositePattern` chains patterns sequentially
- [ ] All tests pass: `uv run pytest tests/unit/ -v`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
