from __future__ import annotations

import pandas as pd

from src.domain.models import CompanyProfile
from src.domain.serialization import dataframe_to_models
from src.errors import TickerNotFoundError
from src.repositories.base import CompanyRepository


class CompanyService:
    def __init__(self, company_repo: CompanyRepository):
        self._company_repo = company_repo

    def list_universe(self, include_market_data: bool = False, force_refresh: bool = False) -> list[CompanyProfile]:
        universe = self._company_repo.list_universe()
        merged = universe
        if include_market_data and not universe.empty:
            market_data = self._company_repo.get_market_data(universe["ticker"].tolist(), force_refresh=force_refresh)
            merged = universe.merge(market_data, on="ticker", how="left")
        return dataframe_to_models(merged, CompanyProfile)

    def get_company_profile(self, ticker: str, force_refresh: bool = False) -> CompanyProfile:
        """A company profile works for any real ticker, not just the
        satellite universe — anchors like NVDA aren't in `list_universe()`
        but are still a valid lookup here. Name/sector fall back to
        generic values when the ticker isn't in the curated universe list;
        only a genuinely empty market-data fetch (yfinance has nothing for
        this ticker at all) is treated as "not found."
        """
        universe = self._company_repo.list_universe()
        match = universe.loc[universe["ticker"] == ticker]
        name = match.iloc[0]["name"] if not match.empty else ticker
        sector = match.iloc[0]["sector"] if not match.empty else "Unknown"

        market_data = self._company_repo.get_market_data([ticker], force_refresh=force_refresh)
        if market_data.empty:
            raise TickerNotFoundError(ticker)
        market_row = market_data.iloc[0]

        # Valuation ratios come from the separate, slower per-ticker `.info`
        # fetch — only worth it for this single-company lookup.
        facts = self._company_repo.get_company_facts(ticker, force_refresh=force_refresh)

        return CompanyProfile(
            ticker=ticker,
            name=name,
            sector=sector,
            market_cap=_clean(market_row.get("market_cap")),
            avg_volume=_clean(market_row.get("avg_volume")),
            trailing_pe=_clean(facts.get("trailing_pe")),
            forward_pe=_clean(facts.get("forward_pe")),
            peg_ratio=_clean(facts.get("peg_ratio")),
            price_to_book=_clean(facts.get("price_to_book")),
            dividend_yield=_clean(facts.get("dividend_yield")),
            beta=_clean(facts.get("beta")),
            ebit=_clean(facts.get("ebit")),
            profit_margin=_clean(facts.get("profit_margin")),
            return_on_equity=_clean(facts.get("return_on_equity")),
            business_summary=_clean(facts.get("business_summary")),
        )


def _clean(value):
    return None if pd.isna(value) else value
