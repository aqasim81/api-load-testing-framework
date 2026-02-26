# Phase 1: Foundation + Scenario DSL

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 1–3 |
| **Estimated effort** | 2 days |
| **Dependencies** | None |

## Goal

Project scaffolding, decorator-based DSL, scenario loading, and instrumented
HTTP client. At phase end, a scenario file can be parsed and its structure
inspected.

## Files to Create

| File | Purpose |
|------|---------|
| `src/loadforge/__init__.py` | Public exports (update existing) |
| `src/loadforge/dsl/__init__.py` | DSL package init |
| `src/loadforge/dsl/decorators.py` | `@scenario`, `@task`, `@setup`, `@teardown` decorators |
| `src/loadforge/dsl/scenario.py` | `ScenarioDefinition`, `TaskDefinition` dataclasses, global scenario registry |
| `src/loadforge/dsl/loader.py` | `load_scenario(file_path)` using `importlib.util.spec_from_file_location` |
| `src/loadforge/dsl/http_client.py` | `HttpClient` wrapping `aiohttp.ClientSession` with auto-timing and `RequestMetric` emission |
| `src/loadforge/_internal/__init__.py` | Internal package init |
| `src/loadforge/_internal/types.py` | Shared type aliases |
| `src/loadforge/_internal/errors.py` | `LoadForgeError`, `ScenarioError`, `ConfigError` |
| `src/loadforge/_internal/config.py` | Configuration loading (env vars, defaults) |
| `tests/unit/test_decorators.py` | Verify decorators correctly populate `ScenarioDefinition` |
| `tests/unit/test_scenario.py` | Verify scenario registry and loading |
| `examples/basic_get.py` | Simplest possible scenario |

## Key Design Decisions

- `@scenario` transforms a class into a `ScenarioDefinition` by inspecting
  decorated methods. No subclassing required.
- `HttpClient.metric_callback: Callable[[RequestMetric], None]` is the
  extension point. In Phase 3 it writes to an in-memory list; in Phase 4 it
  writes to shared memory.
- `loader.py` uses `importlib` to dynamically import `.py` files, then scans
  module globals for `ScenarioDefinition` instances.

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/unit/test_decorators.py` | Decorators correctly populate `ScenarioDefinition` |
| `tests/unit/test_scenario.py` | Scenario registry, loading, and dataclass integrity |

## Acceptance Criteria

- [ ] `@scenario` decorator transforms a class into a `ScenarioDefinition` with correct metadata
- [ ] `@task(weight=N)` registers tasks with correct weights
- [ ] `@setup` and `@teardown` register lifecycle hooks
- [ ] `load_scenario()` loads a `.py` file and returns a `ScenarioDefinition`
- [ ] `HttpClient` wraps aiohttp and emits `RequestMetric` for each request
- [ ] `LoadForgeError` hierarchy is defined
- [ ] All tests pass: `uv run pytest tests/unit/ -v`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
