from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis.portfolio import IDIOSYNCRATIC
from src.config import Config
from src.domain.models import PortfolioHoldingInput
from src.errors import InsufficientDataError
from src.services.portfolio_service import PortfolioService


class _FakePriceRepository:
    def __init__(self, prices: pd.DataFrame):
        self._prices = prices
        self.calls: list[tuple] = []

    def get_price_history(self, tickers, lookback_days, force_refresh=False):
        self.calls.append((tuple(tickers), lookback_days, force_refresh))
        cols = [t for t in tickers if t in self._prices.columns]
        return self._prices[cols]


def _prices_from_returns(returns: dict, start_price: float = 100.0) -> pd.DataFrame:
    n = len(next(iter(returns.values())))
    dates = pd.date_range("2023-01-01", periods=n + 1, freq="B")
    data = {}
    for ticker, rets in returns.items():
        log_prices = np.concatenate([[np.log(start_price)], np.log(start_price) + np.cumsum(rets)])
        data[ticker] = np.exp(log_prices)
    return pd.DataFrame(data, index=dates)


def _synthetic_prices(n: int = 200, seed: int = 7) -> pd.DataFrame:
    """NVDA and TSM share a common chip factor; AAPL is its own thing.
    TIED_TO_NVDA tracks NVDA closely, LOOSE is noise.
    """
    rng = np.random.default_rng(seed)
    chip = rng.normal(0, 0.012, n)
    nvda = chip + rng.normal(0, 0.004, n)
    tsm = chip * 0.9 + rng.normal(0, 0.005, n)
    aapl = rng.normal(0, 0.010, n)
    return _prices_from_returns(
        {
            "NVDA": nvda,
            "TSM": tsm,
            "AAPL": aapl,
            "TIED_TO_NVDA": nvda * 0.95 + rng.normal(0, 0.002, n),
            "TIED_TO_AAPL": aapl * 0.95 + rng.normal(0, 0.002, n),
            "LOOSE": rng.normal(0, 0.011, n),
        }
    )


def _config(**overrides) -> Config:
    defaults = dict(
        anchors=["NVDA", "TSM", "AAPL"],
        lookback_days=200,
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


def _service(prices=None, **config_overrides):
    repo = _FakePriceRepository(prices if prices is not None else _synthetic_prices())
    return PortfolioService(repo, _config(**config_overrides)), repo


def _holdings(*pairs) -> list[PortfolioHoldingInput]:
    return [PortfolioHoldingInput(ticker=t, shares=s) for t, s in pairs]


def _shares(analysis, ticker: str) -> float:
    return next(f.share for f in analysis.factor_exposure if f.factor == ticker)


# -- happy path ---------------------------------------------------------------


def test_factor_exposure_sums_to_one():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 100.0), ("TIED_TO_AAPL", 50.0)))

    assert sum(f.share for f in analysis.factor_exposure) == pytest.approx(1.0)
    assert {f.factor for f in analysis.factor_exposure} == {"NVDA", "TSM", "AAPL", IDIOSYNCRATIC}


def test_a_chip_heavy_portfolio_loads_on_the_chip_anchors_not_aapl():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 100.0)))

    assert _shares(analysis, "NVDA") + _shares(analysis, "TSM") > _shares(analysis, "AAPL")
    assert analysis.concentration.top_factor in {"NVDA", "TSM"}


def test_holdings_carry_their_per_anchor_correlations_and_r_squared():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 10.0)))

    holding = analysis.holdings[0]
    assert set(holding.correlations) == {"NVDA", "TSM", "AAPL"}
    assert holding.correlations["NVDA"] > 0.9
    assert holding.correlations["AAPL"] == pytest.approx(0.0, abs=0.25)
    assert 0.0 <= holding.r_squared <= 1.0


def test_an_anchor_held_directly_correlates_one_with_itself():
    service, _ = _service()

    analysis = service.analyze(_holdings(("NVDA", 5.0)))

    assert analysis.holdings[0].correlations["NVDA"] == pytest.approx(1.0)
    assert analysis.holdings[0].r_squared == pytest.approx(1.0, abs=1e-6)


def test_prices_are_fetched_once_for_holdings_and_anchors_together():
    service, repo = _service()

    service.analyze(_holdings(("TIED_TO_NVDA", 1.0), ("LOOSE", 1.0)))

    assert len(repo.calls) == 1
    requested, lookback, _ = repo.calls[0]
    assert set(requested) == {"TIED_TO_NVDA", "LOOSE", "NVDA", "TSM", "AAPL"}
    assert lookback == 200


# -- weighting ----------------------------------------------------------------


def test_share_counts_produce_market_value_weights():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 100.0), ("LOOSE", 1.0)))

    assert analysis.weighting == "market_value"
    assert analysis.total_value is not None and analysis.total_value > 0
    by_ticker = {h.ticker: h for h in analysis.holdings}
    assert by_ticker["TIED_TO_NVDA"].weight > by_ticker["LOOSE"].weight
    assert sum(h.weight for h in analysis.holdings) == pytest.approx(1.0)


def test_missing_share_counts_fall_back_to_equal_weighting():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", None), ("LOOSE", None)))

    assert analysis.weighting == "equal"
    assert analysis.total_value is None
    assert all(h.weight == pytest.approx(0.5) for h in analysis.holdings)


def test_holdings_come_back_largest_position_first():
    service, _ = _service()

    analysis = service.analyze(_holdings(("LOOSE", 1.0), ("TIED_TO_NVDA", 500.0)))

    assert [h.ticker for h in analysis.holdings] == ["TIED_TO_NVDA", "LOOSE"]


def test_repeated_tickers_are_merged_into_one_position():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 60.0), ("tied_to_nvda", 40.0)))

    assert len(analysis.holdings) == 1
    assert analysis.holdings[0].shares == pytest.approx(100.0)


def test_a_repeated_ticker_with_one_unsized_lot_degrades_to_equal_weighting():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 60.0), ("TIED_TO_NVDA", None), ("LOOSE", 5.0)))

    assert analysis.weighting == "equal"
    assert next(h for h in analysis.holdings if h.ticker == "TIED_TO_NVDA").shares is None


def test_tickers_are_upper_cased_and_stripped():
    service, _ = _service()

    analysis = service.analyze(_holdings(("  tied_to_nvda  ", 1.0)))

    assert analysis.holdings[0].ticker == "TIED_TO_NVDA"


# -- unresolved holdings ------------------------------------------------------


def test_unknown_tickers_are_reported_rather_than_silently_dropped():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 1.0), ("NOPE", 1.0)))

    assert [u.ticker for u in analysis.unresolved] == ["NOPE"]
    assert [h.ticker for h in analysis.holdings] == ["TIED_TO_NVDA"]
    # Weights renormalise over what survived, so the pie still totals 100%.
    assert sum(h.weight for h in analysis.holdings) == pytest.approx(1.0)


def test_a_holding_with_too_little_overlapping_history_is_unresolved():
    prices = _synthetic_prices()
    # Only ~10 usable days, well under the 30-day minimum overlap.
    prices["SHORT_HISTORY"] = np.nan
    prices.iloc[-11:, prices.columns.get_loc("SHORT_HISTORY")] = np.linspace(10, 12, 11)
    service, _ = _service(prices=prices)

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 1.0), ("SHORT_HISTORY", 1.0)))

    assert [u.ticker for u in analysis.unresolved] == ["SHORT_HISTORY"]
    assert "overlapping" in analysis.unresolved[0].reason


def test_an_unknown_ticker_dragging_weighting_does_not_break_market_value_mode():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 10.0), ("NOPE", 10.0)))

    assert analysis.weighting == "market_value"


# -- anchors ------------------------------------------------------------------


def test_explicit_anchors_override_the_configured_ones():
    service, _ = _service()

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 1.0)), anchors=["nvda"])

    assert analysis.anchors == ["NVDA"]
    assert {f.factor for f in analysis.factor_exposure} == {"NVDA", IDIOSYNCRATIC}


def test_anchors_without_price_data_are_dropped_from_the_analysis():
    service, _ = _service(anchors=["NVDA", "GHOST"])

    analysis = service.analyze(_holdings(("TIED_TO_NVDA", 1.0)))

    assert analysis.anchors == ["NVDA"]


# -- error paths --------------------------------------------------------------


def test_empty_holdings_raise():
    service, _ = _service()

    with pytest.raises(InsufficientDataError):
        service.analyze([])


def test_no_usable_anchor_raises():
    service, _ = _service(anchors=["GHOST"])

    with pytest.raises(InsufficientDataError):
        service.analyze(_holdings(("TIED_TO_NVDA", 1.0)))


def test_no_usable_holding_raises():
    service, _ = _service()

    with pytest.raises(InsufficientDataError):
        service.analyze(_holdings(("NOPE", 1.0), ("ALSO_NOPE", 1.0)))
