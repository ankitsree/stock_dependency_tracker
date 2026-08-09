from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import Config
from src.errors import InsufficientDataError, TickerNotFoundError
from src.services.correlation_service import CorrelationService


class _FakePriceRepository:
    def __init__(self, prices: pd.DataFrame):
        self._prices = prices
        self.calls = []

    def get_price_history(self, tickers, lookback_days, force_refresh=False):
        self.calls.append((tuple(tickers), lookback_days, force_refresh))
        cols = [t for t in tickers if t in self._prices.columns]
        return self._prices[cols]


class _FakeCompanyRepository:
    def __init__(self, universe: pd.DataFrame):
        self._universe = universe

    def list_universe(self):
        return self._universe

    def get_market_data(self, tickers, force_refresh=False):
        return pd.DataFrame(columns=["ticker", "market_cap", "avg_volume"])


def _prices_from_returns(returns: dict, start_price: float = 100.0) -> pd.DataFrame:
    n = len(next(iter(returns.values())))
    dates = pd.date_range("2023-01-01", periods=n + 1, freq="B")
    data = {}
    for ticker, rets in returns.items():
        log_prices = np.concatenate([[np.log(start_price)], np.log(start_price) + np.cumsum(rets)])
        data[ticker] = np.exp(log_prices)
    return pd.DataFrame(data, index=dates)


def _synthetic_prices(n=150, seed=42):
    rng = np.random.default_rng(seed)
    market = rng.normal(0, 0.01, n)
    soxx = rng.normal(0, 0.01, n)
    anchor = market * 0.6 + rng.normal(0, 0.008, n)
    sat_high = anchor * 0.9 + rng.normal(0, 0.002, n)  # strongly correlated with ANCHOR
    sat_low = rng.normal(0, 0.01, n)  # uncorrelated
    return _prices_from_returns(
        {
            "ANCHOR": anchor,
            "SAT_HIGH": sat_high,
            "SAT_LOW": sat_low,
            "MARKET": market,
            "SOXX": soxx,
            "XLK": rng.normal(0, 0.01, n),
        }
    )


def _universe():
    return pd.DataFrame(
        [("SAT_HIGH", "High Corr Co", "Semiconductors"), ("SAT_LOW", "Low Corr Co", "Semiconductors")],
        columns=["ticker", "name", "sector"],
    )


def _config(**overrides) -> Config:
    defaults = dict(
        anchors=["ANCHOR"],
        lookback_days=150,
        top_n=5,
        correlation_threshold=0.3,
        rolling_window=20,
        data_dir=Path("unused"),
        outputs_dir=Path("unused"),
        market_proxy_ticker="MARKET",
        lag_max_days=2,
        regime_recent_days=10,
        regime_break_threshold=0.9,
        price_cache_ttl_seconds=3600,
        cors_allowed_origins=[],
    )
    defaults.update(overrides)
    return Config(**defaults)


def _service(prices=None, universe=None, **config_overrides):
    price_repo = _FakePriceRepository(prices if prices is not None else _synthetic_prices())
    company_repo = _FakeCompanyRepository(universe if universe is not None else _universe())
    return CorrelationService(price_repo, company_repo, _config(**config_overrides)), price_repo


def test_rank_correlations_ranks_by_pearson_by_default():
    service, _ = _service()
    ranked = service.rank_correlations("ANCHOR")

    assert list(ranked["ticker"])[0] == "SAT_HIGH"
    assert "SAT_LOW" not in list(ranked["ticker"])  # below threshold


def test_rank_correlations_respects_method_param():
    service, _ = _service()
    spearman = service.rank_correlations("ANCHOR", method="spearman")
    assert "SAT_HIGH" in list(spearman["ticker"])


def test_rank_correlations_unknown_anchor_raises():
    service, _ = _service()
    with pytest.raises(TickerNotFoundError):
        service.rank_correlations("NOTANANCHOR")


def test_rank_with_stability_attaches_stability_column():
    service, _ = _service()
    ranked = service.rank_with_stability("ANCHOR")

    assert "stability" in ranked.columns
    assert not ranked.empty


def test_rank_with_stability_excludes_given_tickers():
    service, _ = _service()
    ranked = service.rank_with_stability("ANCHOR", exclude_tickers={"SAT_HIGH"})

    assert "SAT_HIGH" not in list(ranked["ticker"])


def test_rank_with_full_diagnostics_attaches_all_phase4_columns():
    service, _ = _service()
    result = service.rank_with_full_diagnostics("ANCHOR")

    expected_columns = {
        "stability",
        "pearson_correlation",
        "partial_correlation",
        "sector_relative_correlation",
    }
    assert expected_columns.issubset(set(result.satellites.columns))
    assert result.cache_hit is False


def test_rank_with_full_diagnostics_as_domain_converts_nan_to_none():
    service, _ = _service()
    result = service.rank_with_full_diagnostics("ANCHOR")

    models = result.as_domain()
    assert len(models) == len(result.satellites)
    assert all(m.ticker for m in models)


def test_rank_with_full_diagnostics_second_call_is_cache_hit():
    service, price_repo = _service()
    service.rank_with_full_diagnostics("ANCHOR")
    fetch_count_after_first = len(price_repo.calls)

    result2 = service.rank_with_full_diagnostics("ANCHOR")

    assert result2.cache_hit is True
    assert len(price_repo.calls) == fetch_count_after_first  # no re-fetch


def test_rank_with_full_diagnostics_force_refresh_bypasses_cache():
    service, price_repo = _service()
    service.rank_with_full_diagnostics("ANCHOR")
    fetch_count_after_first = len(price_repo.calls)

    result2 = service.rank_with_full_diagnostics("ANCHOR", force_refresh=True)

    assert result2.cache_hit is False
    assert len(price_repo.calls) > fetch_count_after_first


def test_rank_with_full_diagnostics_missing_market_proxy_raises_insufficient_data():
    prices = _synthetic_prices().drop(columns=["MARKET"])
    service, _ = _service(prices=prices)

    with pytest.raises(InsufficientDataError):
        service.rank_with_full_diagnostics("ANCHOR")


def test_rank_with_full_diagnostics_missing_sector_etf_raises_insufficient_data():
    prices = _synthetic_prices().drop(columns=["SOXX"])
    service, _ = _service(prices=prices)

    with pytest.raises(InsufficientDataError):
        service.rank_with_full_diagnostics("ANCHOR")


def test_top_n_and_threshold_overrides_respected():
    service, _ = _service()
    ranked = service.rank_correlations("ANCHOR", top_n=1, threshold=0.0)
    assert len(ranked) == 1
