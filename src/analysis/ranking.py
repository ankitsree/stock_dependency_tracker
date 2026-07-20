import pandas as pd


def rank_top_n(
    correlations: pd.Series,
    metadata: pd.DataFrame,
    top_n: int,
    threshold: float,
) -> pd.DataFrame:
    """Filter satellites to those at/above `threshold` correlation, then take the top N.

    `metadata` must be indexed or joinable by ticker (expects a "ticker" column).
    Returns a DataFrame sorted by correlation descending, with metadata attached.
    """
    filtered = correlations[correlations.abs() >= threshold]
    ranked = filtered.reindex(filtered.abs().sort_values(ascending=False).index).head(top_n)

    result = ranked.rename("correlation").reset_index().rename(columns={"index": "ticker"})
    result = result.merge(metadata, on="ticker", how="left")
    return result[["ticker", "name", "sector", "correlation"]]


def attach_metric(ranked: pd.DataFrame, values: pd.Series, column: str) -> pd.DataFrame:
    """Left-join an arbitrary per-ticker metric onto a ranked satellite table
    (e.g. a secondary correlation method, partial correlation, sector-relative
    correlation, lag). Tickers without a computable value get NaN rather than
    being dropped from the ranking.
    """
    result = ranked.merge(values.rename(column), left_on="ticker", right_index=True, how="left")
    return result


def attach_stability(ranked: pd.DataFrame, stability: pd.Series) -> pd.DataFrame:
    """Left-join rolling-correlation stability scores onto a ranked satellite table.

    Satellites without a computable stability score (e.g. too little history
    to fill a rolling window) get NaN rather than being dropped from the ranking.
    """
    return attach_metric(ranked, stability, "stability")
