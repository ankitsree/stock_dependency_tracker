import os
import time

import pandas as pd

from src.data import fetcher


def _fake_download_multiindex(tickers, **kwargs):
    """Mimics yfinance's actual behavior: `group_by="ticker"` returns a
    (ticker, field) MultiIndex even for a single-ticker request — the shape
    fetch_price_history used to get wrong by guessing from len(tickers)
    instead of checking what came back.
    """
    dates = pd.date_range("2024-01-01", periods=40, freq="B")
    data = {(ticker, "Close"): [100.0 + i for i in range(len(dates))] for ticker in tickers}
    return pd.DataFrame(data, index=dates)


class _FakeFastInfo:
    def __init__(self, data):
        self._data = data

    def get(self, key):
        return self._data.get(key)


class _FakeTicker:
    def __init__(self, ticker):
        self._ticker = ticker

    @property
    def fast_info(self):
        if self._ticker == "BROKEN":
            raise RuntimeError("no data for delisted ticker")
        return _FakeFastInfo({"marketCap": 1_000_000_000, "threeMonthAverageVolume": 500_000})


def test_fetch_metadata_uses_cache_on_second_call(tmp_path, monkeypatch):
    calls = []

    def fake_ticker(ticker):
        calls.append(ticker)
        return _FakeTicker(ticker)

    monkeypatch.setattr(fetcher.yf, "Ticker", fake_ticker)

    first = fetcher.fetch_metadata(["NVDA"], tmp_path)
    second = fetcher.fetch_metadata(["NVDA"], tmp_path)

    assert len(calls) == 1  # second call was served from cache
    pd.testing.assert_frame_equal(first, second)
    assert first.iloc[0]["market_cap"] == 1_000_000_000
    assert first.iloc[0]["avg_volume"] == 500_000


def test_fetch_metadata_skips_broken_ticker(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher.yf, "Ticker", lambda ticker: _FakeTicker(ticker))

    metadata = fetcher.fetch_metadata(["NVDA", "BROKEN"], tmp_path)

    assert list(metadata["ticker"]) == ["NVDA"]


def test_fetch_metadata_cache_expires_after_ttl(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(fetcher.yf, "Ticker", lambda ticker: calls.append(ticker) or _FakeTicker(ticker))

    fetcher.fetch_metadata(["NVDA"], tmp_path, max_cache_age_seconds=1000)
    assert len(calls) == 1

    fetcher.fetch_metadata(["NVDA"], tmp_path, max_cache_age_seconds=1000)
    assert len(calls) == 1  # still within TTL -> cache hit

    cache_path = tmp_path / f"metadata_{fetcher.cache_key(['NVDA'], 'metadata')}.parquet"
    stale = time.time() - 2000
    os.utime(cache_path, (stale, stale))

    fetcher.fetch_metadata(["NVDA"], tmp_path, max_cache_age_seconds=1000)
    assert len(calls) == 2  # past TTL -> refetched


def test_fetch_price_history_single_ticker_multiindex_columns(tmp_path, monkeypatch):
    # Regression test: fetch_price_history used to assume a single-ticker
    # request gets back flat (non-MultiIndex) columns from yf.download,
    # which silently dropped the ticker whenever that assumption was wrong
    # (as it is with the currently pinned yfinance version).
    monkeypatch.setattr(fetcher.yf, "download", _fake_download_multiindex)

    prices = fetcher.fetch_price_history(["NVDA"], lookback_days=40, cache_dir=tmp_path)

    assert list(prices.columns) == ["NVDA"]
    assert len(prices) == 40


def test_fetch_price_history_multi_ticker_multiindex_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher.yf, "download", _fake_download_multiindex)

    prices = fetcher.fetch_price_history(["NVDA", "AMD"], lookback_days=40, cache_dir=tmp_path)

    assert set(prices.columns) == {"NVDA", "AMD"}


def test_fetch_price_history_cache_expires_after_ttl(tmp_path, monkeypatch):
    calls = []

    def fake_download(tickers, **kwargs):
        calls.append(tickers)
        return _fake_download_multiindex(tickers, **kwargs)

    monkeypatch.setattr(fetcher.yf, "download", fake_download)

    fetcher.fetch_price_history(["NVDA"], 40, tmp_path, max_cache_age_seconds=1000)
    assert len(calls) == 1

    fetcher.fetch_price_history(["NVDA"], 40, tmp_path, max_cache_age_seconds=1000)
    assert len(calls) == 1  # still within TTL -> cache hit

    cache_path = tmp_path / f"prices_{fetcher.cache_key(['NVDA'], 40)}.parquet"
    stale = time.time() - 2000
    os.utime(cache_path, (stale, stale))

    fetcher.fetch_price_history(["NVDA"], 40, tmp_path, max_cache_age_seconds=1000)
    assert len(calls) == 2  # past TTL -> refetched
