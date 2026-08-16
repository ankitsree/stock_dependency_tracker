from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config import Config
from src.errors import InsufficientDataError, TickerNotFoundError
from src.repositories.base import CorrelationSnapshot
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


def _service(prices=None, universe=None, correlation_repo=None, **config_overrides):
    price_repo = _FakePriceRepository(prices if prices is not None else _synthetic_prices())
    company_repo = _FakeCompanyRepository(universe if universe is not None else _universe())
    service = CorrelationService(
        price_repo, company_repo, _config(**config_overrides), correlation_repo=correlation_repo
    )
    return service, price_repo


class _FakeCorrelationRepository:
    """Enough of the CorrelationRepository Protocol to exercise the
    service's "read stored snapshot, don't compute" path."""

    def __init__(self, snapshot: CorrelationSnapshot | None = None):
        self._snapshot = snapshot
        self.upsert_calls = []
        self.get_calls = []

    def upsert_snapshot(self, anchor, satellites, lookback_days, computed_at):
        self.upsert_calls.append((anchor, len(satellites), lookback_days, computed_at))

    def get_latest(self, anchor, lookback_days):
        self.get_calls.append((anchor, lookback_days))
        return self._snapshot


def _snapshot_with(satellites: pd.DataFrame) -> CorrelationSnapshot:
    return CorrelationSnapshot(
        anchor="ANCHOR",
        lookback_days=150,
        computed_at=dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc),
        satellites=satellites,
    )


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


def test_prefetch_prices_fetches_union_of_anchors_universe_and_proxies_once():
    service, price_repo = _service()

    service.prefetch_prices(["ANCHOR", "OTHER_ANCHOR"])

    assert len(price_repo.calls) == 1
    fetched_tickers, lookback_days, force_refresh = price_repo.calls[0]
    assert set(fetched_tickers) == {"ANCHOR", "OTHER_ANCHOR", "SAT_HIGH", "SAT_LOW", "MARKET", "SOXX", "XLK"}
    assert lookback_days == 150
    assert force_refresh is False


def test_rank_with_full_diagnostics_reuses_prefetched_prices_without_refetching():
    service, price_repo = _service()
    prefetched = service.prefetch_prices(["ANCHOR"])
    fetch_count_after_prefetch = len(price_repo.calls)

    result = service.rank_with_full_diagnostics("ANCHOR", prefetched_prices=prefetched)

    assert len(price_repo.calls) == fetch_count_after_prefetch  # no additional fetch
    assert not result.satellites.empty


def test_rank_with_full_diagnostics_prefetched_prices_missing_anchor_raises():
    service, _ = _service()
    prefetched = service.prefetch_prices(["OTHER_ANCHOR"])  # doesn't include "ANCHOR"

    with pytest.raises(TickerNotFoundError):
        service.rank_with_full_diagnostics("ANCHOR", prefetched_prices=prefetched)


# --- Track A Phase 1: stored-snapshot read path ---------------------------


def _stored_satellites():
    """The shape the CorrelationRepository hands back — same columns
    _compute_full_diagnostics produces, so the service treats a stored
    snapshot and a fresh compute interchangeably."""
    return pd.DataFrame(
        [
            {
                "ticker": "SAT_HIGH",
                "name": "High Corr Co",
                "sector": "Semiconductors",
                "correlation": 0.85,
                "stability": 0.7,
                "pearson_correlation": 0.82,
                "partial_correlation": 0.5,
                "sector_relative_correlation": 0.3,
                "best_lag": 0,
                "best_lag_correlation": 0.4,
                "regime_break": False,
                "regime_drift": 0.0,
            },
            {
                "ticker": "SAT_LOW",
                "name": "Low Corr Co",
                "sector": "Semiconductors",
                "correlation": 0.20,
                "stability": 0.1,
                "pearson_correlation": 0.20,
                "partial_correlation": 0.1,
                "sector_relative_correlation": 0.1,
                "best_lag": 0,
                "best_lag_correlation": 0.1,
                "regime_break": False,
                "regime_drift": 0.0,
            },
        ]
    )


def test_stored_snapshot_bypasses_live_compute():
    repo = _FakeCorrelationRepository(_snapshot_with(_stored_satellites()))
    service, price_repo = _service(correlation_repo=repo)

    result = service.rank_with_full_diagnostics("ANCHOR")

    assert result.cache_hit is True
    assert price_repo.calls == []  # no yfinance/postgres round-trip needed
    assert list(result.satellites["ticker"]) == ["SAT_HIGH"]  # SAT_LOW filtered by threshold=0.3


def test_stored_snapshot_respects_threshold_override():
    repo = _FakeCorrelationRepository(_snapshot_with(_stored_satellites()))
    service, _ = _service(correlation_repo=repo)

    result = service.rank_with_full_diagnostics("ANCHOR", threshold=0.1)

    assert set(result.satellites["ticker"]) == {"SAT_HIGH", "SAT_LOW"}


def test_stored_snapshot_respects_top_n_override():
    repo = _FakeCorrelationRepository(_snapshot_with(_stored_satellites()))
    service, _ = _service(correlation_repo=repo)

    result = service.rank_with_full_diagnostics("ANCHOR", top_n=1, threshold=0.0)

    assert len(result.satellites) == 1


def test_stored_snapshot_respects_exclude_tickers():
    repo = _FakeCorrelationRepository(_snapshot_with(_stored_satellites()))
    service, _ = _service(correlation_repo=repo)

    result = service.rank_with_full_diagnostics("ANCHOR", exclude_tickers={"SAT_HIGH"}, threshold=0.0)

    assert "SAT_HIGH" not in list(result.satellites["ticker"])


def test_force_refresh_bypasses_stored_snapshot():
    repo = _FakeCorrelationRepository(_snapshot_with(_stored_satellites()))
    service, price_repo = _service(correlation_repo=repo)

    result = service.rank_with_full_diagnostics("ANCHOR", force_refresh=True)

    assert result.cache_hit is False
    assert len(price_repo.calls) > 0  # live compute pulled prices
    assert repo.get_calls == []  # snapshot never consulted


def test_missing_snapshot_falls_back_to_live_compute():
    repo = _FakeCorrelationRepository(snapshot=None)
    service, price_repo = _service(correlation_repo=repo)

    result = service.rank_with_full_diagnostics("ANCHOR")

    assert result.cache_hit is False
    assert repo.get_calls == [("ANCHOR", 150)]
    assert len(price_repo.calls) > 0
