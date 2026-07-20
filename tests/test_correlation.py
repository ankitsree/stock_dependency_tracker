import numpy as np
import pandas as pd

from src.analysis.correlation import (
    compute_correlations,
    compute_lagged_correlations,
    compute_partial_correlations,
    compute_rolling_correlations,
    compute_sector_relative_correlations,
    compute_stability_scores,
    detect_regime_breaks,
    sector_etf_for,
)


def _synthetic_returns(n=100, seed=0):
    rng = np.random.default_rng(seed)
    anchor = pd.Series(rng.normal(0, 0.01, n))
    return anchor


def test_perfectly_correlated_series():
    anchor = _synthetic_returns()
    satellites = pd.DataFrame({"SAT_SAME": anchor})
    correlations = compute_correlations(anchor, satellites)
    assert np.isclose(correlations["SAT_SAME"], 1.0)


def test_uncorrelated_series_near_zero():
    rng = np.random.default_rng(1)
    anchor = pd.Series(rng.normal(0, 0.01, 500))
    satellites = pd.DataFrame({"SAT_RANDOM": rng.normal(0, 0.01, 500)})
    correlations = compute_correlations(anchor, satellites)
    assert abs(correlations["SAT_RANDOM"]) < 0.2


def test_inverse_correlation():
    anchor = _synthetic_returns()
    satellites = pd.DataFrame({"SAT_INVERSE": -anchor})
    correlations = compute_correlations(anchor, satellites)
    assert np.isclose(correlations["SAT_INVERSE"], -1.0)


def test_short_overlap_is_excluded():
    anchor = pd.Series([0.01] * 10, index=range(10))
    satellites = pd.DataFrame({"SAT_SHORT": pd.Series([0.01] * 10, index=range(10))})
    correlations = compute_correlations(anchor, satellites)
    assert "SAT_SHORT" not in correlations.index


def test_rolling_correlation_constant_for_perfectly_tracking_satellite():
    anchor = _synthetic_returns(n=200)
    satellites = pd.DataFrame({"SAT_SAME": anchor})
    rolling = compute_rolling_correlations(anchor, satellites, window=60)
    assert "SAT_SAME" in rolling
    assert np.allclose(rolling["SAT_SAME"], 1.0, atol=1e-8)


def test_rolling_correlation_skips_series_too_short_for_one_window():
    anchor = _synthetic_returns(n=50)
    satellites = pd.DataFrame({"SAT_SHORT": anchor})
    rolling = compute_rolling_correlations(anchor, satellites, window=60)
    assert "SAT_SHORT" not in rolling


def test_stability_high_for_consistently_correlated_satellite():
    anchor = _synthetic_returns(n=200)
    satellites = pd.DataFrame({"SAT_SAME": anchor})
    rolling = compute_rolling_correlations(anchor, satellites, window=60)
    stability = compute_stability_scores(rolling)
    assert stability["SAT_SAME"] > 0.99


def test_stability_low_for_regime_switching_satellite():
    rng = np.random.default_rng(2)
    anchor = pd.Series(rng.normal(0, 0.01, 250))
    # Tracks the anchor for the first half, inverts for the second half —
    # a high full-period correlation could still hide this kind of flip.
    switched = pd.concat([anchor.iloc[:125], -anchor.iloc[125:]]).reset_index(drop=True)
    satellites = pd.DataFrame({"SAT_FLIP": switched})
    rolling = compute_rolling_correlations(anchor, satellites, window=60)
    stability = compute_stability_scores(rolling)
    assert stability["SAT_FLIP"] < 0.5


# --- Phase 4: Spearman -----------------------------------------------------


def test_spearman_perfect_for_monotonic_but_nonlinear_relationship():
    anchor = pd.Series(np.arange(50, dtype=float))
    satellites = pd.DataFrame({"SAT": anchor**3})  # monotonic, not linear
    pearson = compute_correlations(anchor, satellites, method="pearson")
    spearman = compute_correlations(anchor, satellites, method="spearman")
    assert np.isclose(spearman["SAT"], 1.0)
    assert pearson["SAT"] < spearman["SAT"]


def test_spearman_robust_to_single_outlier_pearson_is_not():
    anchor = pd.Series(np.arange(50, dtype=float))
    satellite = anchor.copy()
    satellite.iloc[-1] = 100_000.0  # extreme outlier, rank unchanged (still the max)
    satellites = pd.DataFrame({"SAT": satellite})

    pearson = compute_correlations(anchor, satellites, method="pearson")
    spearman = compute_correlations(anchor, satellites, method="spearman")

    assert np.isclose(spearman["SAT"], 1.0)
    assert pearson["SAT"] < 0.5


# --- Phase 4: partial (market-adjusted) correlation -------------------------


def test_partial_correlation_removes_shared_market_component():
    rng = np.random.default_rng(3)
    n = 300
    market = pd.Series(rng.normal(0, 0.01, n))
    # Anchor and satellite share the market factor but have independent
    # idiosyncratic noise — raw correlation should be inflated by the shared
    # market factor; partial correlation should strip it out.
    anchor = market + pd.Series(rng.normal(0, 0.005, n))
    satellite = market + pd.Series(rng.normal(0, 0.005, n))
    satellites = pd.DataFrame({"SAT": satellite})

    raw = compute_correlations(anchor, satellites)["SAT"]
    partial = compute_partial_correlations(anchor, satellites, market)["SAT"]

    assert raw > 0.6
    assert abs(partial) < 0.2


def test_partial_correlation_preserves_idiosyncratic_relationship():
    rng = np.random.default_rng(7)
    n = 300
    market = pd.Series(rng.normal(0, 0.01, n))
    idio = pd.Series(rng.normal(0, 0.005, n))
    anchor = market + idio
    satellite = market + idio  # shares idiosyncratic component too
    satellites = pd.DataFrame({"SAT": satellite})

    partial = compute_partial_correlations(anchor, satellites, market)["SAT"]
    assert partial > 0.5


# --- Phase 4: time-lagged cross-correlation ----------------------------------


def test_lagged_correlation_finds_the_true_lag():
    anchor = _synthetic_returns(n=100, seed=4)
    lag = 2
    satellite = anchor.shift(lag)  # satellite[t] = anchor[t - lag]
    satellites = pd.DataFrame({"SAT": satellite})

    result = compute_lagged_correlations(anchor, satellites, max_lag=5)

    assert result.loc["SAT", "best_lag"] == lag
    assert np.isclose(result.loc["SAT", "best_lag_correlation"], 1.0)


def test_lagged_correlation_skips_satellite_with_no_usable_overlap():
    anchor = pd.Series([0.01] * 10, index=range(10))
    satellites = pd.DataFrame({"SAT_SHORT": pd.Series([0.01] * 10, index=range(10))})
    result = compute_lagged_correlations(anchor, satellites, max_lag=3)
    assert "SAT_SHORT" not in result.index


# --- Phase 4: sector-relative correlation ------------------------------------


def test_sector_relative_correlation_removes_shared_sector_component():
    rng = np.random.default_rng(6)
    n = 300
    etf = pd.Series(rng.normal(0, 0.01, n))
    anchor = etf + pd.Series(rng.normal(0, 0.005, n))
    satellite = etf + pd.Series(rng.normal(0, 0.005, n))
    satellites = pd.DataFrame({"SAT": satellite})
    sectors = pd.Series({"SAT": "Semiconductors"})
    etf_returns = {"SOXX": etf}

    raw = compute_correlations(anchor, satellites)["SAT"]
    sector_relative = compute_sector_relative_correlations(anchor, satellites, sectors, etf_returns)["SAT"]

    assert raw > 0.6
    assert abs(sector_relative) < 0.2


def test_sector_relative_correlation_skips_sector_without_etf_data():
    anchor = _synthetic_returns(n=100, seed=8)
    satellites = pd.DataFrame({"SAT": anchor})
    sectors = pd.Series({"SAT": "Semiconductors"})
    result = compute_sector_relative_correlations(anchor, satellites, sectors, sector_etf_returns={})
    assert "SAT" not in result.index


def test_sector_etf_for_maps_chip_sectors_to_soxx_and_others_to_xlk():
    assert sector_etf_for("Semiconductors") == "SOXX"
    assert sector_etf_for("Semiconductor Equipment") == "SOXX"
    assert sector_etf_for("Contract Manufacturing") == "XLK"
    assert sector_etf_for("Some Unlisted Sector") == "XLK"  # falls back to "Other Components" group


# --- Phase 4: regime-break detection -----------------------------------------


def test_regime_break_flagged_for_correlation_that_recently_inverted():
    rng = np.random.default_rng(2)
    anchor = pd.Series(rng.normal(0, 0.01, 250))
    switched = pd.concat([anchor.iloc[:125], -anchor.iloc[125:]]).reset_index(drop=True)
    satellites = pd.DataFrame({"SAT_FLIP": switched, "SAT_SAME": anchor.copy()})

    rolling = compute_rolling_correlations(anchor, satellites, window=60)
    full_period = compute_correlations(anchor, satellites)
    breaks = detect_regime_breaks(rolling, full_period, recent_days=30, break_threshold=0.35)

    assert breaks.loc["SAT_FLIP", "regime_break"] == True  # noqa: E712 (numpy bool, not python bool)
    assert breaks.loc["SAT_SAME", "regime_break"] == False  # noqa: E712


def test_regime_break_omits_satellite_without_rolling_series():
    full_period = pd.Series({"SAT": 0.8})
    breaks = detect_regime_breaks({}, full_period, recent_days=30, break_threshold=0.35)
    assert breaks.empty
