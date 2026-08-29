"""Unit tests for the pure portfolio math (src/analysis/portfolio.py)."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.portfolio import (
    IDIOSYNCRATIC,
    aggregate_exposure,
    concentration_metrics,
    factor_attribution,
    resolve_weights,
    summarize_risks,
)


def _independent(anchors):
    return pd.DataFrame(np.eye(len(anchors)), index=anchors, columns=anchors)


# -- resolve_weights ----------------------------------------------------------


def test_resolve_weights_uses_market_value_when_every_position_is_priced():
    shares = pd.Series({"AAPL": 100.0, "MSFT": 50.0})
    prices = pd.Series({"AAPL": 200.0, "MSFT": 400.0})

    weights, mode, values = resolve_weights(shares, prices)

    assert mode == "market_value"
    # 20_000 and 20_000 -> equal by value even though the share counts differ.
    assert weights.to_dict() == pytest.approx({"AAPL": 0.5, "MSFT": 0.5})
    assert values is not None and values.sum() == pytest.approx(40_000.0)


def test_resolve_weights_falls_back_to_equal_when_any_share_count_is_missing():
    shares = pd.Series({"AAPL": 100.0, "MSFT": np.nan})
    prices = pd.Series({"AAPL": 200.0, "MSFT": 400.0})

    weights, mode, values = resolve_weights(shares, prices)

    assert mode == "equal"
    assert values is None
    assert weights.to_dict() == pytest.approx({"AAPL": 0.5, "MSFT": 0.5})


def test_resolve_weights_falls_back_to_equal_when_a_price_is_unknown():
    shares = pd.Series({"AAPL": 100.0, "MSFT": 50.0})
    prices = pd.Series({"AAPL": 200.0})

    _, mode, values = resolve_weights(shares, prices)

    assert mode == "equal"
    assert values is None


def test_resolve_weights_handles_no_holdings():
    weights, mode, values = resolve_weights(pd.Series(dtype=float), pd.Series(dtype=float))

    assert weights.empty and mode == "equal" and values is None


# -- factor_attribution -------------------------------------------------------


def test_attribution_of_a_single_orthogonal_anchor_is_r_squared():
    correlations = pd.DataFrame({"NVDA": [0.8]}, index=["SAT"])

    attribution, r_squared = factor_attribution(correlations, _independent(["NVDA"]))

    assert attribution.loc["SAT", "NVDA"] == pytest.approx(0.64)
    assert r_squared["SAT"] == pytest.approx(0.64)


def test_correlated_anchors_do_not_double_count_the_same_variance():
    """The whole reason for the Pratt decomposition: two anchors that are 0.9
    correlated with each other must not each claim ~0.64 of the same variance.
    """
    anchors = ["NVDA", "TSM"]
    anchor_corr = pd.DataFrame([[1.0, 0.9], [0.9, 1.0]], index=anchors, columns=anchors)
    correlations = pd.DataFrame({"NVDA": [0.8], "TSM": [0.8]}, index=["SAT"])

    attribution, r_squared = factor_attribution(correlations, anchor_corr)

    naive = 0.8**2 + 0.8**2  # what summing r^2 per anchor would have produced
    assert naive > 1.0
    assert r_squared["SAT"] <= 1.0
    assert attribution.loc["SAT"].sum() == pytest.approx(r_squared["SAT"])


def test_attribution_rows_sum_to_r_squared_and_stay_in_range():
    anchors = ["NVDA", "AAPL", "TSM"]
    anchor_corr = pd.DataFrame([[1.0, 0.4, 0.7], [0.4, 1.0, 0.3], [0.7, 0.3, 1.0]], index=anchors, columns=anchors)
    correlations = pd.DataFrame({"NVDA": [0.7, -0.5], "AAPL": [0.2, 0.1], "TSM": [0.6, -0.4]}, index=["SAT_A", "SAT_B"])

    attribution, r_squared = factor_attribution(correlations, anchor_corr)

    assert (attribution >= 0).all().all()
    for ticker in correlations.index:
        assert 0.0 <= r_squared[ticker] <= 1.0
        assert attribution.loc[ticker].sum() == pytest.approx(r_squared[ticker])


def test_missing_correlation_against_one_anchor_contributes_nothing():
    anchors = ["NVDA", "TSM"]
    correlations = pd.DataFrame({"NVDA": [0.8], "TSM": [np.nan]}, index=["SAT"])

    attribution, r_squared = factor_attribution(correlations, _independent(anchors))

    assert attribution.loc["SAT", "TSM"] == pytest.approx(0.0)
    assert r_squared["SAT"] == pytest.approx(0.64)


def test_a_holding_uncorrelated_with_everything_is_all_idiosyncratic():
    correlations = pd.DataFrame({"NVDA": [0.0]}, index=["SAT"])

    attribution, r_squared = factor_attribution(correlations, _independent(["NVDA"]))

    assert r_squared["SAT"] == pytest.approx(0.0)
    assert attribution.loc["SAT"].sum() == pytest.approx(0.0)


def test_factor_attribution_on_empty_input():
    attribution, r_squared = factor_attribution(pd.DataFrame(), pd.DataFrame())

    assert attribution.empty and r_squared.empty


# -- aggregate_exposure -------------------------------------------------------


def test_exposure_sums_to_one_including_the_idiosyncratic_remainder():
    attribution = pd.DataFrame({"NVDA": [0.64, 0.09]}, index=["SAT_A", "SAT_B"])
    weights = pd.Series({"SAT_A": 0.75, "SAT_B": 0.25})

    exposure = aggregate_exposure(attribution, weights)

    assert exposure.sum() == pytest.approx(1.0)
    assert exposure["NVDA"] == pytest.approx(0.75 * 0.64 + 0.25 * 0.09)
    assert exposure[IDIOSYNCRATIC] == pytest.approx(1.0 - exposure["NVDA"])


def test_exposure_is_weight_sensitive():
    attribution = pd.DataFrame({"NVDA": [0.9, 0.0]}, index=["SAT_A", "SAT_B"])

    heavy = aggregate_exposure(attribution, pd.Series({"SAT_A": 0.9, "SAT_B": 0.1}))
    light = aggregate_exposure(attribution, pd.Series({"SAT_A": 0.1, "SAT_B": 0.9}))

    assert heavy["NVDA"] > light["NVDA"]


def test_exposure_with_no_holdings_is_fully_idiosyncratic():
    exposure = aggregate_exposure(pd.DataFrame(), pd.Series(dtype=float))

    assert exposure[IDIOSYNCRATIC] == pytest.approx(1.0)


# -- concentration_metrics ----------------------------------------------------


def test_concentration_metrics_identify_the_dominant_factor():
    exposure = pd.Series({"NVDA": 0.5, "TSM": 0.2, "AAPL": 0.1, IDIOSYNCRATIC: 0.2})

    metrics = concentration_metrics(exposure)

    assert metrics["top_factor"] == "NVDA"
    assert metrics["top_factor_share"] == pytest.approx(0.5)
    assert metrics["top_three_share"] == pytest.approx(0.8)
    assert metrics["herfindahl_index"] == pytest.approx(0.5**2 + 0.2**2 + 0.1**2 + 0.2**2)
    assert metrics["effective_factors"] == pytest.approx(1 / metrics["herfindahl_index"])


def test_a_spread_portfolio_has_more_effective_factors_than_a_concentrated_one():
    spread = concentration_metrics(pd.Series({"A": 0.25, "B": 0.25, "C": 0.25, IDIOSYNCRATIC: 0.25}))
    concentrated = concentration_metrics(pd.Series({"A": 0.9, "B": 0.05, "C": 0.05, IDIOSYNCRATIC: 0.0}))

    assert spread["effective_factors"] > concentrated["effective_factors"]


def test_concentration_metrics_when_nothing_is_explained():
    metrics = concentration_metrics(pd.Series({"NVDA": 0.0, IDIOSYNCRATIC: 1.0}))

    assert metrics["top_factor"] is None
    assert metrics["top_factor_share"] == pytest.approx(0.0)


# -- summarize_risks ----------------------------------------------------------


def test_risk_summary_flags_a_concentrated_portfolio():
    exposure = pd.Series({"NVDA": 0.7, IDIOSYNCRATIC: 0.3})

    lines = summarize_risks(exposure, concentration_metrics(exposure), "market_value", 0)

    assert any("NVDA" in line and "70%" in line for line in lines)
    assert any("Concentrated" in line for line in lines)


def test_risk_summary_mentions_equal_weighting_and_dropped_holdings():
    exposure = pd.Series({"NVDA": 0.2, IDIOSYNCRATIC: 0.8})

    lines = summarize_risks(exposure, concentration_metrics(exposure), "equal", 2)

    assert any("share counts" in line for line in lines)
    assert any("2 holdings" in line for line in lines)
    assert any("unexplained" in line.lower() for line in lines)


def test_risk_summary_when_no_anchor_explains_anything():
    exposure = pd.Series({"NVDA": 0.0, IDIOSYNCRATIC: 1.0})

    lines = summarize_risks(exposure, concentration_metrics(exposure), "market_value", 0)

    assert any("None of the tracked anchors" in line for line in lines)
