"""Fixtures for the Postgres repository tests.

These run against a *real* Postgres, not mocks (production-roadmap.md §6
step 6 / target-architecture.md §11) — a mocked session would never catch a
real constraint, upsert, or dialect issue. `DATABASE_URL` points at the
`docker compose` `db` service locally (`make up`) and at CI's `postgres:16`
service container (Phase 4.9). Tests are skipped, not failed, when no
database is reachable, so `pytest -q` from a plain `venv` (no Docker/CI)
still passes.
"""

from __future__ import annotations

import os

import pytest

from src.repositories.postgres.db import make_engine, make_session_factory
from src.repositories.postgres.models import Base

TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:5432/stockdep")


@pytest.fixture
def session_factory():
    engine = make_engine(TEST_DATABASE_URL)
    try:
        engine.connect().close()
    except Exception as exc:
        pytest.skip(f"no reachable Postgres at {TEST_DATABASE_URL!r} ({exc.__class__.__name__}); run `make up`")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield make_session_factory(engine)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
