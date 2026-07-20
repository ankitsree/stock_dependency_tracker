import os
import time

import pandas as pd

from src.data.storage import cache_key, load_parquet, save_parquet


def test_cache_key_stable_regardless_of_ticker_order():
    assert cache_key(["NVDA", "AMD"], 365) == cache_key(["AMD", "NVDA"], 365)


def test_cache_key_differs_by_lookback():
    assert cache_key(["NVDA"], 365) != cache_key(["NVDA"], 180)


def test_save_and_load_parquet_roundtrip(tmp_path):
    df = pd.DataFrame({"NVDA": [1.0, 2.0], "AMD": [3.0, 4.0]})
    path = tmp_path / "prices.parquet"
    save_parquet(df, path)
    loaded = load_parquet(path)
    pd.testing.assert_frame_equal(df, loaded)


def test_load_parquet_missing_file_returns_none(tmp_path):
    assert load_parquet(tmp_path / "does_not_exist.parquet") is None


def test_load_parquet_none_max_age_never_expires(tmp_path):
    df = pd.DataFrame({"a": [1]})
    path = tmp_path / "prices.parquet"
    save_parquet(df, path)
    ancient = time.time() - 10_000_000
    os.utime(path, (ancient, ancient))

    assert load_parquet(path) is not None  # max_age_seconds=None (default) never expires


def test_load_parquet_within_ttl_is_a_hit(tmp_path):
    df = pd.DataFrame({"a": [1]})
    path = tmp_path / "prices.parquet"
    save_parquet(df, path)

    assert load_parquet(path, max_age_seconds=1000) is not None


def test_load_parquet_past_ttl_is_a_miss(tmp_path):
    df = pd.DataFrame({"a": [1]})
    path = tmp_path / "prices.parquet"
    save_parquet(df, path)
    stale = time.time() - 2000
    os.utime(path, (stale, stale))

    assert load_parquet(path, max_age_seconds=1000) is None
