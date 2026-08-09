from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.api import deps
from src.api.errors import register_exception_handlers
from src.api.rate_limit import limiter
from src.api.routers import companies, correlations, graph, health, prices

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cheap, non-network startup work only: constructing/validating config
    # fails fast on a bad config.yaml before the app starts serving traffic.
    # Deliberately does NOT eagerly fetch/correlate anything over the network
    # here — that would make every restart slow and couple boot success to
    # Yahoo being reachable at that exact moment.
    config = deps.get_config()
    # `database_url_configured` doubles as the storage backend indicator:
    # deps.py builds Postgres-backed repositories when it's True, yfinance +
    # parquet ones when it's False.
    logger.info(
        "Starting API: anchors=%s, lookback_days=%d, database_url_configured=%s",
        config.anchors,
        config.lookback_days,
        bool(config.database_url),
    )
    yield


def create_app() -> FastAPI:
    """Factory, not just a module-level app: tests construct a fresh instance
    per test so `app.dependency_overrides` can be mutated without leaking
    between tests.
    """
    app = FastAPI(title="Stock Dependency Tracker API", lifespan=lifespan)
    app.state.limiter = limiter
    # slowapi's handler is typed narrowly for RateLimitExceeded; Starlette's
    # stub wants a general Exception handler. Sound at runtime (Starlette
    # only ever calls it for the registered type) — a known, widely hit
    # false positive, not a real type error.
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    config = deps.get_config()
    # Configure the root logger here rather than at import time so tests that
    # build an app don't fight over global logging state. LOG_LEVEL is env
    # driven: DEBUG locally, INFO in production.
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    for router in (health.router, prices.router, companies.router, correlations.router, graph.router):
        app.include_router(router, prefix="/api")

    return app


app = create_app()
