# Developer + CI entry points. CI (Phase 4.9) runs these exact targets, so
# local and CI behavior stay identical. Assumes the dev tools are available
# (activate the venv, or run `make dev-install`).
.PHONY: dev-install format format-check lint lint-check typecheck test check \
        docker-build docker-run up down logs

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

# --- Containers (Phase 4.7) -------------------------------------------------
# Build the production API image (the same one CI builds and the host runs).
docker-build:
	docker build -t stockdep-api:local .

# Run the API image alone, no database — quickest check that the image works.
docker-run:
	docker run --rm -p 8000:8000 stockdep-api:local

# Full local stack: API + Postgres. `up` rebuilds so code changes take effect.
up:
	docker compose up -d --build

down:
	docker compose down

# Add `-v` to `down` to also drop the Postgres volume and start from empty.
logs:
	docker compose logs -f
