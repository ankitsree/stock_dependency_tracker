"""Framework-agnostic data contracts shared by services and the API layer.

Plain pydantic models (validation only, no FastAPI/HTTP concepts) so the
same types are meaningful to the CLI as well as the API. src/api/schemas/
wraps these in thin response envelopes rather than re-declaring their
fields.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    date: dt.date
    adjusted_close: float


class CompanyProfile(BaseModel):
    ticker: str
    name: str
    sector: str
    market_cap: float | None = None
    avg_volume: float | None = None
    # Valuation ratios, profitability metrics, and a business summary — populated
    # only on the single-company profile lookup (get_company_profile), None in
    # the bulk universe list.
    trailing_pe: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    price_to_book: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    ebit: float | None = None
    profit_margin: float | None = None
    return_on_equity: float | None = None
    business_summary: str | None = None


class RankedSatellite(BaseModel):
    ticker: str
    name: str
    sector: str
    correlation: float
    stability: float | None = None
    pearson_correlation: float | None = None
    partial_correlation: float | None = None
    sector_relative_correlation: float | None = None
    best_lag: int | None = None
    best_lag_correlation: float | None = None
    regime_break: bool | None = None
    regime_drift: float | None = None


class GraphNode(BaseModel):
    ticker: str
    kind: str  # "anchor" | "satellite"
    name: str
    sector: str
    market_cap: float | None = None
    avg_volume: float | None = None


class GraphEdge(BaseModel):
    anchor: str
    satellite: str
    weight: float
    stability: float | None = None
    pearson_correlation: float | None = None
    partial_correlation: float | None = None
    sector_relative_correlation: float | None = None
    best_lag: int | None = None
    best_lag_correlation: float | None = None
    regime_break: bool | None = None
    regime_drift: float | None = None


class PortfolioHoldingInput(BaseModel):
    """One line of a user's pasted holdings. `shares` is optional — without it
    (for any holding) the whole portfolio falls back to equal weighting.
    """

    ticker: str
    shares: float | None = Field(default=None, gt=0)


class HoldingExposure(BaseModel):
    """A resolved holding: its weight in the portfolio, its correlation to each
    anchor, and how much of its own variance the anchors jointly explain.
    """

    ticker: str
    shares: float | None = None
    last_price: float | None = None
    market_value: float | None = None
    weight: float
    # anchor ticker -> Pearson r. None where the pair had too few overlapping
    # trading days to correlate.
    correlations: dict[str, float | None]
    r_squared: float


class UnresolvedHolding(BaseModel):
    """A ticker the user supplied that couldn't be analysed, with the reason —
    surfaced rather than silently dropped, since a typo'd ticker vanishing
    without a trace would quietly skew every percentage on the screen.
    """

    ticker: str
    reason: str


class FactorExposure(BaseModel):
    """One slice of the variance pie. Shares across a response sum to 1."""

    factor: str
    label: str
    share: float
    is_idiosyncratic: bool = False


class ConcentrationMetrics(BaseModel):
    herfindahl_index: float
    effective_factors: float
    top_factor: str | None = None
    top_factor_share: float
    top_three_share: float


class PortfolioAnalysis(BaseModel):
    anchors: list[str]
    holdings: list[HoldingExposure]
    unresolved: list[UnresolvedHolding]
    weighting: str  # "market_value" | "equal"
    total_value: float | None = None
    factor_exposure: list[FactorExposure]
    concentration: ConcentrationMetrics
    risk_summary: list[str]
    lookback_days: int
    generated_at: dt.datetime
