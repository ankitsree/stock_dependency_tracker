import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.errors import TickerNotFoundError
from src.services.price_service import PriceService


class _FakePriceRepository:
    def __init__(self, prices: pd.DataFrame):
        self._prices = prices
        self.calls = []

    def get_price_history(self, tickers, lookback_days, force_refresh=False):
        self.calls.append((tickers, lookback_days, force_refresh))
        return self._prices


def _prices(tickers=("NVDA",), n=5):
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({t: np.arange(n, dtype=float) + 100 for t in tickers}, index=dates)


def test_returns_price_points_for_known_ticker():
    repo = _FakePriceRepository(_prices())
    service = PriceService(repo, default_lookback_days=365)

    points = service.get_price_history("NVDA")

    assert len(points) == 5
    assert points[0].date == dt.date(2024, 1, 1)
    assert points[0].adjusted_close == 100.0


def test_uses_default_lookback_when_not_specified():
    repo = _FakePriceRepository(_prices())
    service = PriceService(repo, default_lookback_days=365)

    service.get_price_history("NVDA")

    assert repo.calls[0] == (["NVDA"], 365, False)


def test_explicit_lookback_overrides_default():
    repo = _FakePriceRepository(_prices())
    service = PriceService(repo, default_lookback_days=365)

    service.get_price_history("NVDA", lookback_days=30)

    assert repo.calls[0] == (["NVDA"], 30, False)


def test_force_refresh_forwarded():
    repo = _FakePriceRepository(_prices())
    service = PriceService(repo, default_lookback_days=365)

    service.get_price_history("NVDA", force_refresh=True)

    assert repo.calls[0] == (["NVDA"], 365, True)


def test_unknown_ticker_raises_ticker_not_found():
    repo = _FakePriceRepository(_prices(tickers=("NVDA",)))
    service = PriceService(repo, default_lookback_days=365)

    with pytest.raises(TickerNotFoundError):
        service.get_price_history("NOTATICKER")
