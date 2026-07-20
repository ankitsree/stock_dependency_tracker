from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class Config(BaseModel):
    anchors: list[str]
    lookback_days: int
    top_n: int
    correlation_threshold: float
    rolling_window: int
    data_dir: Path
    outputs_dir: Path
    market_proxy_ticker: str
    lag_max_days: int
    regime_recent_days: int
    regime_break_threshold: float
    price_cache_ttl_seconds: float
    cors_allowed_origins: list[str]


def load_config(path: str | Path = "config.yaml") -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config(**raw)
