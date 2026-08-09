"""The `client` fixture in conftest.py disables the limiter (a module-level
singleton — every TestClient shares the "testclient" address, so leaving it
enabled there would leak rate-limit state across unrelated tests). This file
re-enables it deliberately to exercise the real thing, and resets storage
before/after so it can't leak into whatever test runs next.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app
from src.api.rate_limit import limiter


def test_refresh_endpoint_enforces_stricter_limit(fake_price_repo, fake_company_repo):
    app = create_app()
    app.dependency_overrides[deps.get_price_repository] = lambda: fake_price_repo
    app.dependency_overrides[deps.get_company_repository] = lambda: fake_company_repo

    limiter.reset()
    limiter.enabled = True
    try:
        with TestClient(app) as test_client:
            responses = [test_client.post("/api/anchors/NVDA/refresh") for _ in range(6)]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert [r.status_code for r in responses[:5]] == [200] * 5
    assert responses[5].status_code == 429


def test_default_limit_does_not_block_ordinary_use(fake_price_repo, fake_company_repo):
    app = create_app()
    app.dependency_overrides[deps.get_price_repository] = lambda: fake_price_repo
    app.dependency_overrides[deps.get_company_repository] = lambda: fake_company_repo

    limiter.reset()
    limiter.enabled = True
    try:
        with TestClient(app) as test_client:
            responses = [test_client.get("/api/companies") for _ in range(10)]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert all(r.status_code == 200 for r in responses)
