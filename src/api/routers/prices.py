"""Blocking route (yfinance + pandas underneath): declared as plain `def`,
not `async def`, so FastAPI runs it in Starlette's threadpool automatically
instead of blocking the event loop. See docs/phase4-5.md for why.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query

from src.api import deps
from src.api.schemas.prices import PriceHistoryResponse
from src.services.price_service import PriceService

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{ticker}", response_model=PriceHistoryResponse)
def get_price_history(
    ticker: str,
    lookback_days: int | None = Query(default=None, gt=0),
    force_refresh: bool = Query(default=False),
    price_service: PriceService = Depends(deps.get_price_service),
) -> PriceHistoryResponse:
    ticker = ticker.upper()
    points = price_service.get_price_history(ticker, lookback_days=lookback_days, force_refresh=force_refresh)
    resolved_lookback = lookback_days if lookback_days is not None else price_service.default_lookback_days
    return PriceHistoryResponse(
        ticker=ticker,
        lookback_days=resolved_lookback,
        points=points,
        generated_at=dt.datetime.now(dt.timezone.utc),
    )
