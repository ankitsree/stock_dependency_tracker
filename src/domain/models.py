"""Framework-agnostic data contracts shared by services and the API layer.

Plain pydantic models (validation only, no FastAPI/HTTP concepts) so the
same types are meaningful to the CLI as well as the API. src/api/schemas/
wraps these in thin response envelopes rather than re-declaring their
fields.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


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
