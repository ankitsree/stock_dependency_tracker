"""Portfolio concentration math (Track A Phase 3) — pure functions, no I/O.

The question this module answers: *of the variance in a user's portfolio, how
much is driven by each anchor?* Everything here takes an already-assembled
holdings x anchors correlation matrix and returns a decomposition that sums to
exactly 1, so the frontend can render it as a pie without re-normalising.

**The decomposition.** For one holding with correlation vector `rho` against
the anchors and anchor-vs-anchor correlation matrix `C`, the standardised
multiple-regression coefficients are `beta = C^-1 rho`, and the multiple
R-squared is `rho . beta`. Splitting that total per anchor as `beta_a * rho_a`
is Pratt's measure, which is the only additive decomposition that sums exactly
to R-squared. Using it (rather than the tempting `rho_a^2` per anchor) is what
stops correlated anchors from double-counting the same variance: NVDA and TSM
move together, so a semiconductor holding would otherwise be reported as ~90%
NVDA-driven *and* ~85% TSM-driven, which sums to well over 100% of a variance
that only ever added up to one.

Pratt's measure can go negative under suppression (an anchor whose regression
coefficient flips sign against its raw correlation). Negative "share of
variance" is not renderable and not meaningful to a retail user, so negatives
are clipped and the survivors rescaled back up to the true R-squared — the
total stays honest even though the split becomes approximate in that case.

The portfolio-level roll-up is the weight-average of the per-holding
attributions. That is exact only if holdings have equal volatility; with
unequal vols it is a first-order approximation. Documented rather than
silently assumed — pricing in per-holding vol would require a full covariance
model, which is a Phase 5 concern, not something to smuggle in here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Bucket name for the share of variance no anchor explains. Kept as a
#: constant because the API, the risk summary, and the frontend legend all
#: need to agree on the exact string.
IDIOSYNCRATIC = "idiosyncratic"

#: A single factor above this share of portfolio variance gets called out as
#: concentration risk in the summary. 0.4 is a judgement call, not a
#: statistic — it's the point at which one anchor going wrong dominates the
#: outcome regardless of how many names are held.
CONCENTRATION_ALERT_SHARE = 0.4

#: Below this explained share the portfolio is essentially uncorrelated with
#: the tracked anchors, and the pie is mostly "we can't say".
DIVERSIFIED_IDIOSYNCRATIC_SHARE = 0.6


def resolve_weights(
    shares: pd.Series,
    last_prices: pd.Series,
) -> tuple[pd.Series, str, pd.Series | None]:
    """Position weights, value-based when possible and equal-weight otherwise.

    Value weighting needs a share count *and* a usable last price for **every**
    holding — a portfolio where two of five positions are value-weighted and
    the rest are guessed would silently misstate the concentration. All-or-
    nothing keeps the reported `weighting` mode honest.

    Returns `(weights summing to 1, "market_value" | "equal", position values
    or None)`.
    """
    tickers = list(shares.index)
    if not tickers:
        return pd.Series(dtype=float), "equal", None

    values = shares.astype(float) * last_prices.reindex(shares.index).astype(float)
    usable = values.notna() & np.isfinite(values) & (values > 0)
    if bool(usable.all()) and float(values.sum()) > 0:
        return values / float(values.sum()), "market_value", values

    return pd.Series(1.0 / len(tickers), index=tickers), "equal", None


def factor_attribution(
    correlations: pd.DataFrame,
    anchor_correlations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Per-holding variance attribution across the anchors.

    `correlations` is indexed by holding ticker with one column per anchor;
    `anchor_correlations` is the square anchor-vs-anchor matrix. Returns
    `(attribution, r_squared)` where each attribution row is non-negative and
    sums to that holding's R-squared in [0, 1].
    """
    anchors = list(correlations.columns)
    if correlations.empty or not anchors:
        return pd.DataFrame(index=correlations.index, columns=anchors, dtype=float), pd.Series(
            0.0, index=correlations.index, dtype=float
        )

    matrix = anchor_correlations.reindex(index=anchors, columns=anchors).to_numpy(dtype=float)

    rows: dict[str, np.ndarray] = {}
    totals: dict[str, float] = {}
    for ticker, row in correlations.iterrows():
        rho = row.reindex(anchors).to_numpy(dtype=float)
        # An anchor a holding has too little overlap with contributes nothing
        # rather than poisoning the whole solve with a NaN.
        known = np.isfinite(rho)

        contributions = np.zeros(len(anchors), dtype=float)
        if known.any():
            # lstsq, not inv/solve: anchors in the same sector are close to
            # collinear, and its minimum-norm solution degrades gracefully
            # where a direct inverse would blow the coefficients up.
            beta, *_ = np.linalg.lstsq(matrix[np.ix_(known, known)], rho[known], rcond=None)
            contributions[known] = beta * rho[known]

        rows[str(ticker)], totals[str(ticker)] = _clip_to_total(contributions)

    attribution = pd.DataFrame.from_dict(rows, orient="index", columns=anchors)
    return attribution, pd.Series(totals, name="r_squared", dtype=float)


def _clip_to_total(contributions: np.ndarray) -> tuple[np.ndarray, float]:
    """Drop negative (suppression) contributions, then rescale what's left so
    the row still sums to the R-squared the full decomposition produced.
    """
    total = float(np.clip(contributions.sum(), 0.0, 1.0))
    positive = np.clip(contributions, 0.0, None)
    positive_sum = float(positive.sum())
    if total <= 0 or positive_sum <= 0:
        return np.zeros_like(contributions), 0.0
    return positive * (total / positive_sum), total


def aggregate_exposure(attribution: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Roll per-holding attributions up into portfolio factor shares.

    The returned Series carries one entry per anchor plus `IDIOSYNCRATIC`, and
    sums to exactly 1 — it is the pie chart.
    """
    if attribution.empty:
        return pd.Series({IDIOSYNCRATIC: 1.0})

    aligned = weights.reindex(attribution.index).fillna(0.0)
    exposure = attribution.mul(aligned, axis=0).sum().astype(float)
    # Whatever the anchors don't explain is the remainder, by construction:
    # each row sums to its own R-squared, so 1 - sum is the weighted mean of
    # (1 - R-squared). max() only guards float drift past 1.
    exposure[IDIOSYNCRATIC] = max(0.0, 1.0 - float(exposure.sum()))

    total = float(exposure.sum())
    return exposure / total if total > 0 else exposure


def concentration_metrics(exposure: pd.Series) -> dict[str, float | str | None]:
    """Herfindahl concentration over the factor shares.

    HHI is computed across *all* buckets including `IDIOSYNCRATIC`, because a
    portfolio whose variance is mostly unexplained genuinely is less
    concentrated in any tracked factor. `effective_factors` (1/HHI) is the
    reader-friendly form: "your risk behaves like ~2.4 independent bets".
    """
    hhi = float((exposure**2).sum())
    factors = exposure.drop(labels=[IDIOSYNCRATIC], errors="ignore").sort_values(ascending=False)

    has_factor = not factors.empty and float(factors.iloc[0]) > 0
    return {
        "herfindahl_index": hhi,
        "effective_factors": (1.0 / hhi) if hhi > 0 else 0.0,
        "top_factor": str(factors.index[0]) if has_factor else None,
        "top_factor_share": float(factors.iloc[0]) if has_factor else 0.0,
        "top_three_share": float(factors.head(3).sum()),
    }


def summarize_risks(
    exposure: pd.Series,
    metrics: dict[str, float | str | None],
    weighting: str,
    unresolved_count: int,
) -> list[str]:
    """Plain-language read-out of the decomposition — the "so what?" the pie
    chart on its own doesn't deliver.
    """
    lines: list[str] = []
    factors = exposure.drop(labels=[IDIOSYNCRATIC], errors="ignore").sort_values(ascending=False)
    top_share = float(metrics["top_factor_share"] or 0.0)
    top_factor = metrics["top_factor"]
    idiosyncratic = float(exposure.get(IDIOSYNCRATIC, 0.0))

    if top_factor:
        lines.append(f"{top_factor} is your largest single exposure at {_pct(top_share)} of portfolio variance.")
        named = [str(t) for t in factors.head(3).index]
        if len(named) > 1:
            lines.append(f"Top {len(named)} factors ({', '.join(named)}) drive {_pct(metrics['top_three_share'])}.")
    else:
        lines.append("None of the tracked anchors explains a meaningful share of this portfolio's variance.")

    if top_share >= CONCENTRATION_ALERT_SHARE:
        lines.append(
            f"Concentrated: over {_pct(CONCENTRATION_ALERT_SHARE)} of your variance rides on {top_factor} alone."
        )
    elif idiosyncratic >= DIVERSIFIED_IDIOSYNCRATIC_SHARE:
        lines.append(
            f"{_pct(idiosyncratic)} of variance is unexplained by the anchors — diversified with respect to them, "
            "though it may be concentrated in factors this app doesn't track."
        )

    effective = float(metrics["effective_factors"] or 0.0)
    if effective > 0:
        lines.append(f"Your risk behaves like roughly {effective:.1f} independent bets.")

    if weighting == "equal":
        lines.append("Weights are equal per position — add share counts to weight by market value instead.")
    if unresolved_count:
        plural = "s" if unresolved_count > 1 else ""
        lines.append(f"{unresolved_count} holding{plural} had no usable price history and was left out.")

    return lines


def _pct(value: float | str | None) -> str:
    return f"{float(value or 0.0) * 100:.0f}%"
