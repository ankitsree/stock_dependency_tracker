from __future__ import annotations

from pydantic import BaseModel, Field

from src.domain.models import PortfolioHoldingInput

#: Upper bound on holdings per request. Each unique ticker can become a
#: yfinance fetch on a cache miss, so this caps the fan-out one request can
#: provoke against Yahoo's unofficial API (CLAUDE.md: "throttle requests").
#: Comfortably above a realistic retail portfolio.
MAX_HOLDINGS = 50


class PortfolioAnalyzeRequest(BaseModel):
    holdings: list[PortfolioHoldingInput] = Field(min_length=1, max_length=MAX_HOLDINGS)
    # Omitted => config.anchors. Present => analyse against exactly these,
    # which is what lets a caller ask "how exposed am I to just NVDA and TSM?"
    anchors: list[str] | None = Field(default=None, min_length=1)
