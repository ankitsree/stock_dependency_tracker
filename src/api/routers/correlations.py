"""Blocking route (yfinance + the full correlation stack underneath):
plain `def`, not `async def` — see src/api/routers/prices.py's note.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api import deps
from src.api.schemas.correlations import CorrelationResponse
from src.services.correlation_service import CorrelationService

router = APIRouter(prefix="/anchors", tags=["correlations"])


@router.get("/{ticker}/correlations", response_model=CorrelationResponse)
def get_correlations(
    ticker: str,
    top_n: int | None = Query(default=None, gt=0),
    threshold: float | None = Query(default=None, ge=0, le=1),
    correlation_service: CorrelationService = Depends(deps.get_correlation_service),
) -> CorrelationResponse:
    return _rank(ticker, top_n, threshold, force_refresh=False, correlation_service=correlation_service)


@router.post("/{ticker}/refresh", response_model=CorrelationResponse)
def refresh_correlations(
    ticker: str,
    top_n: int | None = Query(default=None, gt=0),
    threshold: float | None = Query(default=None, ge=0, le=1),
    correlation_service: CorrelationService = Depends(deps.get_correlation_service),
) -> CorrelationResponse:
    return _rank(ticker, top_n, threshold, force_refresh=True, correlation_service=correlation_service)


def _rank(
    ticker: str,
    top_n: int | None,
    threshold: float | None,
    force_refresh: bool,
    correlation_service: CorrelationService,
) -> CorrelationResponse:
    ticker = ticker.upper()
    result = correlation_service.rank_with_full_diagnostics(
        ticker, top_n=top_n, threshold=threshold, force_refresh=force_refresh
    )
    return CorrelationResponse(
        anchor=ticker,
        satellites=result.as_domain(),
        generated_at=result.generated_at,
        cache_hit=result.cache_hit,
    )
