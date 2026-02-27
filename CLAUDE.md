# CLAUDE.md — LoadForge

## Project

LoadForge — Python load testing framework with realistic traffic patterns,
a live React dashboard, and interactive HTML reports.

## Stack

- Python 3.12+, `uv` for package management
- Async: `aiohttp` + `uvloop` (falls back to asyncio on Windows)
- Multi-core: `multiprocessing` + `shared_memory`
- CLI: `typer` + `rich`
- Dashboard: `FastAPI` + `uvicorn` (backend), React 18 + Recharts (frontend)
- Reports: `plotly` + `jinja2`
- Statistics: `numpy` + `hdrhistogram`

## Architecture

See `plans/implementation_plan.md` for the full architecture diagram. Key points:
- `src/loadforge/` is the main Python package (PEP 561 typed)
- `dashboard/` is the React frontend source (built assets go to `src/loadforge/dashboard/static/`)
- `tests/` mirrors `src/` structure: `unit/`, `integration/`, `e2e/`

## Commands

```bash
# Install all dependencies (including dev)
uv sync --all-extras

# --- Quality checks (fastest first) ---
uv run ruff format --check src/ tests/     # Format check (~2s)
uv run ruff check src/ tests/              # Lint (~3s)
uv run mypy src/                           # Type check (~15-45s)
uv run pytest tests/unit/ -v --cov=loadforge --cov-branch --cov-fail-under=80  # Tests + coverage

# --- Auto-fix ---
uv run ruff format src/ tests/             # Format (modifies files)
uv run ruff check --fix src/ tests/        # Lint with auto-fix

# --- Run all checks before committing ---
make validate

# --- Run specific test suites ---
uv run pytest tests/unit/ -v               # Unit tests only
uv run pytest tests/integration/ -v        # Integration tests only
uv run pytest -v                           # All tests

# Pre-commit hooks
uv run pre-commit run --all-files
```

## Coding Conventions

### General
- `from __future__ import annotations` at the top of EVERY Python file (ruff enforces this)
- Use `X | Y` union syntax, not `Union[X, Y]` or `Optional[X]`
- Use `Path` from pathlib, never `os.path`
- Result pattern for error handling: return result types, never throw in business logic
- Custom exceptions inherit from `LoadForgeError` (defined in `_internal/errors.py`)

### Type Safety
- ZERO `Any` types in source code. If a library returns `Any`, cast it immediately.
- ZERO bare `# type: ignore`. Always specify the error code: `# type: ignore[assignment]`
- All public functions and methods MUST have full type annotations
- All dataclasses MUST annotate every field

### Async
- All I/O-bound operations MUST be async
- Never call `time.sleep()` in async code — use `asyncio.sleep()`
- Never call blocking I/O (file reads, subprocess) in async code — use `asyncio.to_thread()`
- Always use `async with` for aiohttp sessions and responses
- Use `asyncio.TaskGroup` (Python 3.11+) instead of `gather()` where appropriate

### Testing
- Every public function/method gets at least one test
- Tests are in `tests/unit/`, `tests/integration/`, `tests/e2e/`
- Unit tests: no I/O, no network, fast (< 100ms each)
- Integration tests: use the echo server fixture from conftest.py
- Async tests: just use `async def test_...` — pytest-asyncio handles it (auto mode)
- Name tests: `test_<function_name>_<scenario>` (e.g., `test_ramp_pattern_increases_linearly`)

### Docstrings
- Google-style docstrings on all public classes, methods, and functions
- Include `Args:`, `Returns:`, `Raises:` sections where applicable
- Module-level docstrings on every non-`__init__.py` file

### Git
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`
- One commit per logical change
- Run `make validate` before every commit

### Security
- NEVER hardcode secrets, API keys, tokens, or passwords in source code
- All sensitive configuration MUST use environment variables (see `.env.example`)
- Configuration is loaded via `_internal/config.py` using `os.environ.get()`
- `.gitignore` excludes `.env*`, `*.pem`, `*.key`, `secrets.toml`
- Pre-commit: Gitleaks scans for leaked secrets before every commit
- CI: Gitleaks GitHub Action scans full history on every push/PR
- Ruff Bandit rules (`S` prefix) flag hardcoded secrets in linting
- Tests must use fake/mock credentials (e.g., `"test-token-12345"`), never real ones
- When adding new configuration, add the env var to `.env.example` with a comment

## Anti-Patterns to AVOID

- `import *` — never
- Mutable default arguments — ruff B006 catches this
- `except Exception:` without re-raising — always handle specifically or re-raise
- `# type: ignore` without an error code
- `Any` in type annotations
- `time.sleep()` in async code
- `print()` for logging — use structured logging
- Global mutable state — pass dependencies explicitly
- Hardcoded ports in tests — use `_get_free_port()` from conftest
- Hardcoded secrets, API keys, or tokens — use environment variables

## Current Status

- [x] Phase 0: Code quality infrastructure
- [x] Phase 1: Foundation + Scenario DSL
- [x] Phase 2: Traffic Patterns
- [x] Phase 3: Single-Worker Engine
- [ ] Phase 4: Multi-Worker Distribution
- [ ] Phase 5: CLI Interface
- [ ] Phase 6: Post-Run Reports
- [ ] Phase 7: Live React Dashboard
- [ ] Phase 8: Polish, Documentation, Examples
