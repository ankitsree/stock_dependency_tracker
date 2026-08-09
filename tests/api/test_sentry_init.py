"""Sentry init is gated on SENTRY_DSN, exactly like the Postgres cutover is
gated on DATABASE_URL (deps.py). `get_config` is `lru_cache`d, so each test
clears it after mutating the environment — otherwise whichever test runs
first would freeze the config for the rest of the session.
"""

from __future__ import annotations

from unittest.mock import patch

from src.api import deps
from src.api.main import create_app


def test_sentry_initialized_when_dsn_configured(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://public@o0.ingest.us.sentry.io/0")
    deps.get_config.cache_clear()
    try:
        with patch("src.api.main.sentry_sdk.init") as mock_init:
            create_app()
        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["dsn"] == "https://public@o0.ingest.us.sentry.io/0"
        assert mock_init.call_args.kwargs["enable_logs"] is True
    finally:
        deps.get_config.cache_clear()


def test_sentry_not_initialized_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    deps.get_config.cache_clear()
    try:
        with patch("src.api.main.sentry_sdk.init") as mock_init:
            create_app()
        mock_init.assert_not_called()
    finally:
        deps.get_config.cache_clear()
