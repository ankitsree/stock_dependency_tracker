import numpy as np
import pandas as pd

from src.analysis.ranking import attach_metric, attach_stability, rank_top_n


def _metadata():
    return pd.DataFrame(
        [
            ("HIGH", "High Corr Co", "Semiconductors"),
            ("MID", "Mid Corr Co", "Semiconductors"),
            ("LOW", "Low Corr Co", "Semiconductors"),
            ("NEG", "Negative Corr Co", "Semiconductors"),
        ],
        columns=["ticker", "name", "sector"],
    )


def test_filters_below_threshold():
    correlations = pd.Series({"HIGH": 0.9, "MID": 0.65, "LOW": 0.3, "NEG": -0.8})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    assert set(ranked["ticker"]) == {"HIGH", "MID", "NEG"}


def test_sorted_descending_by_correlation():
    correlations = pd.Series({"HIGH": 0.9, "MID": 0.65, "NEG": -0.8})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    assert list(ranked["ticker"]) == ["HIGH", "NEG", "MID"]


def test_respects_top_n():
    correlations = pd.Series({"HIGH": 0.9, "MID": 0.65, "NEG": -0.8})
    ranked = rank_top_n(correlations, _metadata(), top_n=2, threshold=0.6)
    assert len(ranked) == 2
    assert list(ranked["ticker"]) == ["HIGH", "NEG"]


def test_attaches_metadata():
    correlations = pd.Series({"HIGH": 0.9})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    assert ranked.iloc[0]["name"] == "High Corr Co"
    assert ranked.iloc[0]["sector"] == "Semiconductors"


def test_attach_stability_joins_by_ticker():
    correlations = pd.Series({"HIGH": 0.9, "MID": 0.65})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    stability = pd.Series({"HIGH": 0.95, "MID": 0.4})

    with_stability = attach_stability(ranked, stability)

    assert with_stability.set_index("ticker")["stability"]["HIGH"] == 0.95
    assert with_stability.set_index("ticker")["stability"]["MID"] == 0.4


def test_attach_stability_missing_score_is_nan():
    correlations = pd.Series({"HIGH": 0.9})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    stability = pd.Series({}, dtype=float)

    with_stability = attach_stability(ranked, stability)

    assert np.isnan(with_stability.iloc[0]["stability"])


def test_attach_metric_joins_arbitrary_column_by_ticker():
    correlations = pd.Series({"HIGH": 0.9, "MID": 0.65})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    partial = pd.Series({"HIGH": 0.4, "MID": 0.1})

    with_partial = attach_metric(ranked, partial, "partial_correlation")

    assert with_partial.set_index("ticker")["partial_correlation"]["HIGH"] == 0.4
    assert with_partial.set_index("ticker")["partial_correlation"]["MID"] == 0.1


def test_attach_metric_missing_value_is_nan():
    correlations = pd.Series({"HIGH": 0.9})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    empty = pd.Series({}, dtype=float)

    with_metric = attach_metric(ranked, empty, "best_lag_correlation")

    assert np.isnan(with_metric.iloc[0]["best_lag_correlation"])


def test_attach_metric_can_be_chained_for_multiple_columns():
    correlations = pd.Series({"HIGH": 0.9})
    ranked = rank_top_n(correlations, _metadata(), top_n=10, threshold=0.6)
    ranked = attach_metric(ranked, pd.Series({"HIGH": 0.5}), "pearson_correlation")
    ranked = attach_metric(ranked, pd.Series({"HIGH": 0.3}), "partial_correlation")

    assert ranked.iloc[0]["pearson_correlation"] == 0.5
    assert ranked.iloc[0]["partial_correlation"] == 0.3
