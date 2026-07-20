from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

from src.data.storage import cache_key, load_parquet, save_parquet

MIN_TRADING_DAYS = 30  # drop tickers with too little history to correlate meaningfully

logger = logging.getLogger(__name__)


def fetch_price_history(
    tickers: list[str],
    lookback_days: int,
    cache_dir: Path,
    max_cache_age_seconds: float | None = None,
) -> pd.DataFrame:
    """Fetch daily adjusted-close prices for `tickers` over the trailing `lookback_days`.

    Results are cached to `cache_dir` keyed by the ticker set + lookback window,
    so repeated runs during development don't re-hit the yfinance API.
    `max_cache_age_seconds` (default None = never expires) lets long-running
    callers such as the API treat a cache entry older than that many seconds
    as a miss, without changing behavior for one-shot CLI runs.
    Tickers that fail to download or have too little history are dropped
    (and logged) rather than failing the whole batch.
    Returns a wide DataFrame: index = date, columns = ticker, values = adjusted close.
    """
    key = cache_key(tickers, lookback_days)
    cache_path = cache_dir / f"prices_{key}.parquet"
    cached = load_parquet(cache_path, max_age_seconds=max_cache_age_seconds)
    if cached is not None:
        return cached

    period = f"{lookback_days}d"
    raw = yf.download(
        tickers,
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    # yfinance's column shape for `group_by="ticker"` isn't reliably
    # predictable from `len(tickers)` alone (a single-ticker request can
    # still come back as a (ticker, field) MultiIndex depending on version) —
    # check the actual structure returned rather than guessing from the input.
    is_multi_ticker = isinstance(raw.columns, pd.MultiIndex)
    prices: dict[str, pd.Series] = {}
    for ticker in tickers:
        try:
            series = raw[ticker]["Close"] if is_multi_ticker else raw["Close"]
        except KeyError:
            logger.warning("No price data returned for %s; dropping from candidate pool", ticker)
            continue
        series = series.dropna()
        if len(series) < MIN_TRADING_DAYS:
            logger.warning(
                "Only %d trading day(s) for %s (< %d minimum); dropping", len(series), ticker, MIN_TRADING_DAYS
            )
            continue
        prices[ticker] = series

    wide = pd.DataFrame(prices)
    wide.index.name = "date"
    save_parquet(wide, cache_path)
    return wide


def fetch_metadata(
    tickers: list[str],
    cache_dir: Path,
    max_cache_age_seconds: float | None = None,
) -> pd.DataFrame:
    """Fetch market cap and average volume for each ticker (node metadata for
    the graph). Cached the same way as price history, with the same optional
    TTL via `max_cache_age_seconds`.

    Requests run on a thread pool (`yfinance`'s `fast_info` has no batched
    equivalent to `yf.download`, so this is the closest thing to the threaded
    price fetch above). Tickers that error out (delisted, no fast_info
    available) are dropped (and logged) rather than failing the whole batch.
    """
    key = cache_key(tickers, "metadata")
    cache_path = cache_dir / f"metadata_{key}.parquet"
    cached = load_parquet(cache_path, max_age_seconds=max_cache_age_seconds)
    if cached is not None:
        return cached

    def _fetch_one(ticker: str) -> dict | None:
        try:
            info = yf.Ticker(ticker).fast_info
            return {
                "ticker": ticker,
                "market_cap": info.get("marketCap"),
                "avg_volume": info.get("threeMonthAverageVolume"),
            }
        except Exception as exc:
            logger.warning("Could not fetch metadata for %s: %s", ticker, exc)
            return None

    rows: list[dict] = []
    if tickers:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(tickers))) as executor:
            rows = [row for row in executor.map(_fetch_one, tickers) if row is not None]

    metadata = pd.DataFrame(rows, columns=["ticker", "market_cap", "avg_volume"])
    save_parquet(metadata, cache_path)
    return metadata
