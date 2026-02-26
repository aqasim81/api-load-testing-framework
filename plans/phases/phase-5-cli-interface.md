# Phase 5: CLI Interface

> **Full architecture, interfaces, and dependency diagrams:**
> [`../implementation_plan.md`](../implementation_plan.md)

## Summary

| | |
|---|---|
| **Timeline** | Days 10–11 |
| **Estimated effort** | 1.5 days |
| **Dependencies** | Phase 4 |

## Goal

Full typer CLI that wires everything together. Users can run load tests from
the command line with live terminal output.

## Files to Create

| File | Purpose |
|------|---------|
| `src/loadforge/cli/__init__.py` | CLI package init |
| `src/loadforge/cli/app.py` | Main `typer.Typer()` app with subcommands |
| `src/loadforge/cli/run.py` | `loadforge run` — parses flags, starts `rich.live.Live` display |
| `src/loadforge/cli/report.py` | `loadforge report` — regenerate reports from saved data |
| `src/loadforge/cli/init.py` | `loadforge init` — scaffold new scenario from template |
| `src/loadforge/cli/dashboard.py` | Placeholder for Phase 7 |
| `tests/e2e/test_cli.py` | End-to-end CLI tests |
| `tests/e2e/scenarios/example_scenario.py` | Test scenario file |
| `examples/rest_api.py` | Multi-endpoint REST API test |
| `examples/auth_flow.py` | Login → authenticated requests |

## CLI Commands

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

## Key Design Decisions

- `rich.live.Live` provides a beautiful terminal experience without a full TUI
  framework.
- The live display uses a `rich.table.Table` that refreshes every second with
  the latest `MetricSnapshot`.
- Pattern-to-flag mapping: simple patterns via flags, complex patterns via TOML
  config.
- `loadforge init` writes a templated scenario file to the current directory.

## Tests

| Test File | What It Validates |
|-----------|-------------------|
| `tests/e2e/test_cli.py` | Full end-to-end CLI invocations and exit codes |

## Acceptance Criteria

- [ ] `loadforge run` executes a scenario with live rich terminal output
- [ ] Pattern flags (`--pattern`, `--ramp-to`, `--step-size`, etc.) configure patterns correctly
- [ ] `--fail-on-error-rate` returns non-zero exit code when threshold exceeded
- [ ] `loadforge init` scaffolds a scenario file
- [ ] `loadforge report` regenerates reports from saved data
- [ ] Rich live display shows elapsed time, active users, RPS, p95, error rate
- [ ] All tests pass: `make validate` + `uv run pytest tests/e2e/ -v`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Lint passes: `uv run ruff check src/ tests/`
