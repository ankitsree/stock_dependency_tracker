from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import deps
from src.api.errors import register_exception_handlers
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
    logger.info("Starting API: anchors=%s, lookback_days=%d", config.anchors, config.lookback_days)
    yield


def create_app() -> FastAPI:
    """Factory, not just a module-level app: tests construct a fresh instance
    per test so `app.dependency_overrides` can be mutated without leaking
    between tests.
    """
    app = FastAPI(title="Stock Dependency Tracker API", lifespan=lifespan)

    config = deps.get_config()
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
