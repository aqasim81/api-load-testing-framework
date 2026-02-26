# Makefile — LoadForge development commands

.PHONY: fmt fmt-check lint typecheck test test-all test-integration validate clean

# Format code (modifies files)
fmt:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Check formatting without modifying
fmt-check:
	uv run ruff format --check src/ tests/

# Run linter
lint:
	uv run ruff check src/ tests/

# Run type checker
typecheck:
	uv run mypy src/

# Run unit tests with coverage
test:
	uv run pytest tests/unit/ -v --cov=loadforge --cov-branch --cov-fail-under=80 --cov-report=term-missing

# Run all tests (unit + integration + e2e)
test-all:
	uv run pytest -v --cov=loadforge --cov-branch --cov-report=term-missing

# Run integration tests only
test-integration:
	uv run pytest tests/integration/ -v --timeout=60

# THE GATE: must pass before every commit (fastest checks first)
validate: fmt-check lint typecheck test
	@echo ""
	@echo "All checks passed. Safe to commit."

# Clean build artifacts
clean:
	rm -rf htmlcov/ .coverage coverage.json .mypy_cache/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
