import pandas as pd

MIN_OVERLAP_DAYS = 30

# Sector color-group -> representative sector ETF, reusing the same coarse
# 7-group taxonomy the graph already uses for color-coding
# (visualisation.style.sector_group) so sector-relative correlation and the
# chart legend agree on what counts as "the same sector". The satellite
# universe is overwhelmingly chip-adjacent, so the three chip-related groups
# map to a semiconductor ETF (SOXX) and everything else falls back to a
# broad tech ETF (XLK) rather than inventing a bespoke ETF per fine-grained
# sector label.
SECTOR_ETF_MAP = {
    "Semiconductor Equipment": "SOXX",
    "Semiconductors": "SOXX",
    "Chip IP, Materials & Memory": "SOXX",
    "Photonics & Optical": "XLK",
    "Contract Manufacturing": "XLK",
    "Networking & Systems": "XLK",
    "Other Components": "XLK",
}


def sector_etf_for(sector: str) -> str:
    """The representative sector ETF for a satellite's fine-grained sector label."""
    from src.visualisation.style import sector_group

    return SECTOR_ETF_MAP[sector_group(sector)]


def compute_correlations(
    anchor_returns: pd.Series,
    satellite_returns: pd.DataFrame,
    method: str = "pearson",
) -> pd.Series:
    """Correlation between one anchor's returns and each satellite's returns.

    Each pair is aligned on its own common dates (inner join) before correlating,
    since different tickers can have different gaps (halts, listing dates, etc).

    `method` is passed straight to pandas' `Series.corr` ("pearson", "spearman",
    or "kendall"). Spearman correlates ranks rather than raw return values, so a
    handful of outlier days (a small-cap satellite gapping 30% on M&A rumours)
    can't dominate the full-period score the way they can with Pearson — this is
    why Phase 4 uses Spearman as the primary ranking metric while still reporting
    Pearson alongside it for interpretability.

    Returns a Series indexed by satellite ticker.
    """
    correlations = {}
    for ticker in satellite_returns.columns:
        pair = pd.concat([anchor_returns, satellite_returns[ticker]], axis=1).dropna()
        if len(pair) < MIN_OVERLAP_DAYS:
            continue
        correlations[ticker] = pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method)
    return pd.Series(correlations, name="correlation")


def compute_rolling_correlations(
    anchor_returns: pd.Series,
    satellite_returns: pd.DataFrame,
    window: int,
) -> dict[str, pd.Series]:
    """Rolling Pearson correlation per satellite, used to gauge how stable each
    full-period correlation is (roadmap Phase 2: a stock that's 0.85 over the
    full year but swings between 0.3 and 0.95 in rolling windows is less
    reliable than one that stays consistently at 0.75).

    Satellites with too little overlapping history to fill even one window
    are skipped. Returns a dict of ticker -> rolling correlation Series.
    """
    rolling = {}
    for ticker in satellite_returns.columns:
        pair = pd.concat([anchor_returns, satellite_returns[ticker]], axis=1).dropna()
        if len(pair) < window + MIN_OVERLAP_DAYS:
            continue
        series = pair.iloc[:, 0].rolling(window).corr(pair.iloc[:, 1]).dropna()
        if series.empty:
            continue
        rolling[ticker] = series
    return rolling


def compute_stability_scores(rolling_correlations: dict[str, pd.Series]) -> pd.Series:
    """Turn each satellite's rolling-correlation series into a single stability
    score in [0, 1]: 1 means the rolling correlation barely moved (reliable),
    0 means it swung wildly across the full [-1, 1] range (unreliable).
    """
    scores = {ticker: max(0.0, 1.0 - series.std()) for ticker, series in rolling_correlations.items()}
    return pd.Series(scores, name="stability")


def compute_partial_correlations(
    anchor_returns: pd.Series,
    satellite_returns: pd.DataFrame,
    market_returns: pd.Series,
) -> pd.Series:
    """Anchor-satellite Pearson correlation with the market's influence removed
    (roadmap Phase 4: "market-adjusted correlation").

    In a bull market most stocks drift up together, so a raw anchor-satellite
    correlation can just be "both of these follow the S&P 500" rather than any
    relationship specific to the anchor. The classic first-order partial
    correlation formula strips that shared factor out:

        r(a,s|m) = (r_as - r_am * r_sm) / sqrt((1 - r_am^2) * (1 - r_sm^2))

    where r_as, r_am, r_sm are the ordinary Pearson correlations between
    anchor/satellite, anchor/market, and satellite/market respectively, all
    computed on the same three-way-aligned date range. A satellite that's
    highly correlated with the anchor but nearly as correlated with the
    market has that shared component subtracted out — the residual reflects
    anchor-specific co-movement, not market beta.

    Pairs (anchor, satellite, market) are inner-joined on date; pairs with
    fewer than MIN_OVERLAP_DAYS overlapping days, or a denominator of zero
    (one leg perfectly correlated with the market), are skipped.
    """
    partials = {}
    for ticker in satellite_returns.columns:
        combined = pd.concat([anchor_returns, satellite_returns[ticker], market_returns], axis=1).dropna()
        if len(combined) < MIN_OVERLAP_DAYS:
            continue
        combined.columns = ["anchor", "satellite", "market"]
        r_as = combined["anchor"].corr(combined["satellite"])
        r_am = combined["anchor"].corr(combined["market"])
        r_sm = combined["satellite"].corr(combined["market"])
        denom = ((1 - r_am**2) * (1 - r_sm**2)) ** 0.5
        if not denom or pd.isna(denom):
            continue
        partials[ticker] = (r_as - r_am * r_sm) / denom
    return pd.Series(partials, name="partial_correlation")


def compute_lagged_correlations(
    anchor_returns: pd.Series,
    satellite_returns: pd.DataFrame,
    max_lag: int,
) -> pd.DataFrame:
    """Time-lagged cross-correlation: for lag = 1..max_lag days, correlate the
    anchor's return on day t against the satellite's return on day t+lag —
    i.e. does the satellite tend to move `lag` days *after* the anchor
    (roadmap Phase 4: "does satellite X move 1-3 days after anchor Y? This is
    more predictive.").

    A satellite whose strongest correlation shows up at lag > 0 rather than
    lag 0 is a candidate "leading indicator" signal: the anchor's move today
    is informative about that satellite's move a few days from now, not just
    a same-day echo.

    Returns a DataFrame indexed by ticker with columns `best_lag` (the lag in
    [1, max_lag] with the largest |correlation|) and `best_lag_correlation`
    (that correlation value). Satellites with too little overlapping history
    at every lag are omitted.
    """
    rows = {}
    for ticker in satellite_returns.columns:
        lag_correlations = {}
        for lag in range(1, max_lag + 1):
            shifted = satellite_returns[ticker].shift(-lag)
            pair = pd.concat([anchor_returns, shifted], axis=1).dropna()
            if len(pair) < MIN_OVERLAP_DAYS:
                continue
            lag_correlations[lag] = pair.iloc[:, 0].corr(pair.iloc[:, 1])
        if not lag_correlations:
            continue
        best_lag = max(lag_correlations, key=lambda lag: abs(lag_correlations[lag]))
        rows[ticker] = {"best_lag": best_lag, "best_lag_correlation": lag_correlations[best_lag]}
    return pd.DataFrame.from_dict(rows, orient="index", columns=["best_lag", "best_lag_correlation"])


def compute_sector_relative_correlations(
    anchor_returns: pd.Series,
    satellite_returns: pd.DataFrame,
    satellite_sectors: pd.Series,
    sector_etf_returns: dict[str, pd.Series],
) -> pd.Series:
    """Anchor-satellite correlation after subtracting each satellite's sector
    ETF return from both series (roadmap Phase 4: "sector-relative
    correlation"). Isolates co-movement beyond "both of these stocks just
    track the same sector ETF" the same way `compute_partial_correlations`
    isolates co-movement beyond "both stocks just track the market" — but at
    sector rather than whole-market granularity.

    `satellite_sectors` maps ticker -> fine-grained sector label (as used in
    the universe metadata); `sector_etf_returns` maps sector ETF ticker (see
    `sector_etf_for`) -> that ETF's log-return Series. A satellite whose
    sector has no corresponding entry in `sector_etf_returns` is skipped.
    """
    results = {}
    for ticker in satellite_returns.columns:
        sector = satellite_sectors.get(ticker)
        if sector is None:
            continue
        etf_ticker = sector_etf_for(sector)
        etf_returns = sector_etf_returns.get(etf_ticker)
        if etf_returns is None:
            continue
        combined = pd.concat([anchor_returns, satellite_returns[ticker], etf_returns], axis=1).dropna()
        if len(combined) < MIN_OVERLAP_DAYS:
            continue
        combined.columns = ["anchor", "satellite", "sector_etf"]
        anchor_excess = combined["anchor"] - combined["sector_etf"]
        satellite_excess = combined["satellite"] - combined["sector_etf"]
        results[ticker] = anchor_excess.corr(satellite_excess)
    return pd.Series(results, name="sector_relative_correlation")


def detect_regime_breaks(
    rolling_correlations: dict[str, pd.Series],
    full_period_correlation: pd.Series,
    recent_days: int,
    break_threshold: float,
) -> pd.DataFrame:
    """Flag satellites whose correlation has recently diverged sharply from
    its full-period value (roadmap Phase 4: "flag when a previously strong
    correlation breaks down").

    For each satellite, averages the trailing `recent_days` of its rolling
    correlation series (from `compute_rolling_correlations`) and compares
    that to the full-period correlation. A large gap means the relationship
    that held over the whole window has since shifted — the full-period
    number alone would overstate how much to trust it *today*.

    Returns a DataFrame indexed by ticker with columns `recent_correlation`,
    `drift` (full-period minus recent), and `regime_break` (True if
    `abs(drift) >= break_threshold`). Satellites without a rolling series, or
    without enough of one to cover `recent_days`, are omitted.
    """
    rows = {}
    for ticker, series in rolling_correlations.items():
        if ticker not in full_period_correlation.index:
            continue
        recent = series.tail(recent_days)
        if recent.empty:
            continue
        recent_corr = recent.mean()
        drift = full_period_correlation[ticker] - recent_corr
        rows[ticker] = {
            "recent_correlation": recent_corr,
            "drift": drift,
            "regime_break": bool(abs(drift) >= break_threshold),
        }
    return pd.DataFrame.from_dict(rows, orient="index", columns=["recent_correlation", "drift", "regime_break"])
