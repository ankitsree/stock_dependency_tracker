import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.main import create_app


class FakePriceRepository:
    def __init__(self, prices: pd.DataFrame):
        self.prices = prices

    def get_price_history(self, tickers, lookback_days, force_refresh=False):
        cols = [t for t in tickers if t in self.prices.columns]
        return self.prices[cols]


class FakeCompanyRepository:
    def __init__(self, universe: pd.DataFrame, market_data: pd.DataFrame):
        self.universe = universe
        self.market_data = market_data

    def list_universe(self):
        return self.universe

    def get_market_data(self, tickers, force_refresh=False):
        return self.market_data[self.market_data["ticker"].isin(tickers)]

    def get_company_facts(self, ticker, force_refresh=False):
        return {}


def _synthetic_prices(n: int = 150, seed: int = 42) -> pd.DataFrame:
    """NVDA correlates strongly with SAT_HIGH, not at all with SAT_LOW.
    Ticker names match config.yaml's real market_proxy_ticker (^GSPC) and
    sector ETF map (SOXX/XLK) so the full Phase 4 diagnostic stack runs
    end-to-end against this fixture, not just the ranking step.
    """
    rng = np.random.default_rng(seed)
    market = rng.normal(0, 0.01, n)
    soxx = rng.normal(0, 0.01, n)
    anchor = market * 0.6 + rng.normal(0, 0.008, n)
    sat_high = anchor * 0.9 + rng.normal(0, 0.002, n)
    sat_low = rng.normal(0, 0.01, n)
    returns = {
        "NVDA": anchor,
        "TSM": anchor * 0.8 + rng.normal(0, 0.006, n),
        "SAT_HIGH": sat_high,
        "SAT_LOW": sat_low,
        "^GSPC": market,
        "SOXX": soxx,
        "XLK": rng.normal(0, 0.01, n),
    }
    dates = pd.date_range("2023-01-01", periods=n + 1, freq="B")
    data = {}
    for ticker, rets in returns.items():
        log_prices = np.concatenate([[np.log(100.0)], np.log(100.0) + np.cumsum(rets)])
        data[ticker] = np.exp(log_prices)
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def fake_price_repo():
    return FakePriceRepository(_synthetic_prices())


@pytest.fixture
def fake_company_repo():
    universe = pd.DataFrame(
        [("SAT_HIGH", "High Corr Co", "Semiconductors"), ("SAT_LOW", "Low Corr Co", "Semiconductors")],
        columns=["ticker", "name", "sector"],
    )
    market_data = pd.DataFrame(
        [
            ("SAT_HIGH", 1_000_000_000.0, 500_000.0),
            ("SAT_LOW", 2_000_000_000.0, 600_000.0),
            ("NVDA", 3_000_000_000_000.0, 200_000_000.0),
            ("TSM", 800_000_000_000.0, 100_000_000.0),
        ],
        columns=["ticker", "market_cap", "avg_volume"],
    )
    return FakeCompanyRepository(universe, market_data)


@pytest.fixture
def client(fake_price_repo, fake_company_repo):
    app = create_app()
    # Override at the repository level (not the service level) so real
    # service orchestration and error-raising logic runs end-to-end —
    # only the yfinance/parquet I/O boundary is faked.
    app.dependency_overrides[deps.get_price_repository] = lambda: fake_price_repo
    app.dependency_overrides[deps.get_company_repository] = lambda: fake_company_repo
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
