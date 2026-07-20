from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.errors import DomainError, InsufficientDataError, TickerNotFoundError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TickerNotFoundError)
    async def _not_found(request: Request, exc: TickerNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "ticker": exc.ticker})

    @app.exception_handler(InsufficientDataError)
    async def _unprocessable(request: Request, exc: InsufficientDataError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc), "ticker": exc.ticker})

    @app.exception_handler(DomainError)
    async def _fallback(request: Request, exc: DomainError) -> JSONResponse:
        logger.exception("Unhandled domain error on %s", request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal error"})
