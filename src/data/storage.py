from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pandas as pd


def cache_key(tickers: list[str], salt: int | str) -> str:
    raw = f"{sorted(tickers)}::{salt}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def load_parquet(path: Path, max_age_seconds: float | None = None) -> pd.DataFrame | None:
    """Load a cached parquet file, or None if it's missing or stale.

    `max_age_seconds=None` (the default) means "never expires" — today's
    behavior, unchanged. Passing a value makes a cache entry older than that
    many seconds count as a miss, so long-running callers (e.g. the API) can
    avoid serving arbitrarily stale prices without the CLI's one-shot runs
    having to think about staleness at all.
    """
    if not path.exists():
        return None
    if max_age_seconds is not None and (time.time() - path.stat().st_mtime) > max_age_seconds:
        return None
    return pd.read_parquet(path)
