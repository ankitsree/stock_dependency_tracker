# Developer + CI entry points. CI (Phase 4.9) runs these exact targets, so
# local and CI behavior stay identical. Assumes the dev tools are available
# (activate the venv, or run `make dev-install`).
.PHONY: dev-install format format-check lint lint-check typecheck test check

# Install the package + dev/test tooling and wire the git pre-commit hook.
dev-install:
	pip install -e ".[dev,test]"
	pre-commit install

# Auto-format the code (writes changes).
format:
	ruff format src tests

# Verify formatting without changing files (used by CI).
format-check:
	ruff format --check src tests

# Lint with autofix.
lint:
	ruff check --fix src tests

# Lint without fixing (used by CI).
lint-check:
	ruff check src tests

# Static type-check.
typecheck:
	mypy src

# Run the test suite.
test:
	pytest -q

# The full gate CI enforces: lint + format + types + tests.
check: lint-check format-check typecheck test
