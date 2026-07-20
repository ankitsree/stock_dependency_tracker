from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.fetcher import fetch_price_history


class YFinancePriceRepository:
    """`PriceRepository` backed by yfinance + the on-disk parquet cache.

    Thin delegation only — all the actual fetch/cache logic stays in
    src.data.fetcher so it isn't duplicated between this repository and the
    CLI. `cache_ttl_seconds` is the repository's default staleness budget;
    `force_refresh=True` bypasses it for a single call without touching the
    default for subsequent calls.
    """

    def __init__(self, cache_dir: Path, cache_ttl_seconds: float | None = 6 * 3600):
        self._cache_dir = cache_dir
        self._cache_ttl_seconds = cache_ttl_seconds

    def get_price_history(
        self,
        tickers: list[str],
        lookback_days: int,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        max_age = 0 if force_refresh else self._cache_ttl_seconds
        return fetch_price_history(tickers, lookback_days, self._cache_dir, max_cache_age_seconds=max_age)
