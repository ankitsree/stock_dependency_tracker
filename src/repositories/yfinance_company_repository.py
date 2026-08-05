from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.fetcher import fetch_company_facts, fetch_metadata
from src.data.universe import load_universe


class YFinanceCompanyRepository:
    """`CompanyRepository` backed by the hardcoded universe list + yfinance metadata.

    `list_universe()` is the seam a future Postgres `companies` table would
    replace — today it's src.data.universe.load_universe(), which is a
    static in-memory list rather than a live query, but callers only ever
    see the CompanyRepository interface.
    """

    def __init__(self, cache_dir: Path, cache_ttl_seconds: float | None = 6 * 3600):
        self._cache_dir = cache_dir
        self._cache_ttl_seconds = cache_ttl_seconds

    def list_universe(self) -> pd.DataFrame:
        return load_universe()

    def get_market_data(
        self,
        tickers: list[str],
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        max_age = 0 if force_refresh else self._cache_ttl_seconds
        return fetch_metadata(tickers, self._cache_dir, max_cache_age_seconds=max_age)

    def get_company_facts(self, ticker: str, force_refresh: bool = False) -> dict:
        max_age = 0 if force_refresh else self._cache_ttl_seconds
        facts = fetch_company_facts(ticker, self._cache_dir, max_cache_age_seconds=max_age)
        return {} if facts.empty else facts.iloc[0].to_dict()
