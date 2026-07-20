import numpy as np
import pandas as pd
import pytest

from src.errors import TickerNotFoundError
from src.services.company_service import CompanyService


class _FakeCompanyRepository:
    def __init__(self, universe: pd.DataFrame, market_data: pd.DataFrame):
        self._universe = universe
        self._market_data = market_data
        self.market_data_calls = []

    def list_universe(self):
        return self._universe

    def get_market_data(self, tickers, force_refresh=False):
        self.market_data_calls.append((tuple(tickers), force_refresh))
        return self._market_data[self._market_data["ticker"].isin(tickers)]


def _universe():
    return pd.DataFrame(
        [("SAT1", "Satellite One", "Semiconductors"), ("SAT2", "Satellite Two", "Semiconductors")],
        columns=["ticker", "name", "sector"],
    )


def _market_data():
    return pd.DataFrame(
        [("SAT1", 1_000_000_000, 500_000), ("SAT2", np.nan, np.nan)],
        columns=["ticker", "market_cap", "avg_volume"],
    )


def test_list_universe_without_market_data_does_not_call_repo():
    repo = _FakeCompanyRepository(_universe(), _market_data())
    service = CompanyService(repo)

    profiles = service.list_universe(include_market_data=False)

    assert len(profiles) == 2
    assert repo.market_data_calls == []
    assert profiles[0].market_cap is None


def test_list_universe_with_market_data_merges_in_values():
    repo = _FakeCompanyRepository(_universe(), _market_data())
    service = CompanyService(repo)

    profiles = service.list_universe(include_market_data=True)

    by_ticker = {p.ticker: p for p in profiles}
    assert by_ticker["SAT1"].market_cap == 1_000_000_000
    assert by_ticker["SAT2"].market_cap is None  # NaN cleaned to None, not left as NaN


def test_get_company_profile_known_satellite_uses_universe_name_and_sector():
    repo = _FakeCompanyRepository(_universe(), _market_data())
    service = CompanyService(repo)

    profile = service.get_company_profile("SAT1")

    assert profile.name == "Satellite One"
    assert profile.sector == "Semiconductors"
    assert profile.market_cap == 1_000_000_000


def test_get_company_profile_ticker_not_in_universe_falls_back_gracefully():
    # e.g. an anchor like NVDA, which isn't in the satellite universe list
    # but should still resolve if yfinance has market data for it.
    universe = _universe()
    market_data = pd.DataFrame([("NVDA", 3_000_000_000_000, 200_000_000)], columns=["ticker", "market_cap", "avg_volume"])
    repo = _FakeCompanyRepository(universe, market_data)
    service = CompanyService(repo)

    profile = service.get_company_profile("NVDA")

    assert profile.ticker == "NVDA"
    assert profile.name == "NVDA"
    assert profile.sector == "Unknown"
    assert profile.market_cap == 3_000_000_000_000


def test_get_company_profile_raises_when_market_data_empty():
    repo = _FakeCompanyRepository(_universe(), pd.DataFrame(columns=["ticker", "market_cap", "avg_volume"]))
    service = CompanyService(repo)

    with pytest.raises(TickerNotFoundError):
        service.get_company_profile("NOTATICKER")
