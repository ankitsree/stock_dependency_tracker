"""Portfolio concentration analysis (Track A Phase 3).

POST rather than GET despite being a pure read: the input is a holdings list
that doesn't belong in a URL (length, and it's the user's own position data —
query strings end up in access logs and browser history).

Blocking route (a price fetch sits underneath): plain `def`, not `async def`
— see src/api/routers/prices.py's note.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.api import deps
from src.api.rate_limit import limiter
from src.api.schemas.portfolio import PortfolioAnalyzeRequest
from src.domain.models import PortfolioAnalysis
from src.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyze", response_model=PortfolioAnalysis)
# Stricter than the 60/minute default: a portfolio of unfamiliar tickers is
# the one endpoint a user can point at arbitrary symbols, so it's the easiest
# way to drive uncached yfinance traffic. Still far above interactive use —
# a person edits and re-runs a holdings list a few times a minute at most.
@limiter.limit("20/minute")
def analyze_portfolio(
    request: Request,
    payload: PortfolioAnalyzeRequest,
    portfolio_service: PortfolioService = Depends(deps.get_portfolio_service),
) -> PortfolioAnalysis:
    return portfolio_service.analyze(payload.holdings, anchors=payload.anchors)
