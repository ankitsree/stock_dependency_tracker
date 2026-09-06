"""Portfolio concentration analysis (Track A Phase 3).

Orchestration only — every formula lives in `src.analysis.portfolio`. The
service's job is turning a list of pasted tickers into the two matrices that
module needs (holdings x anchors, and anchors x anchors) and packaging the
result as domain models.

**Why this computes correlations live instead of reading the `correlations`
table.** The Phase 3 plan sketches this endpoint as a lookup against Phase 1's
precomputed table. That table only covers the curated small-cap satellite
universe, and real pasted portfolios are overwhelmingly large caps that are
not in it — the fast path would miss nearly every row, and the rows it did hit
would be Spearman-ranked figures mixed into a Pearson matrix, which is not a
coherent input to a variance decomposition. One price fetch over
(holdings + anchors) is a handful of tickers, hits the repository cache, and
keeps every number in the response computed the same way. The precomputed
table stays what it is: the graph's read path.

Nothing is persisted. The analysis is transient by design (plan §Phase 3:
"No persistence") — saved portfolios are a Phase 5b concern that would add a
`portfolio_id` and a repository here without touching any of the math.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

import pandas as pd

from src.analysis.correlation import MIN_OVERLAP_DAYS, compute_correlations
from src.analysis.portfolio import (
    IDIOSYNCRATIC,
    aggregate_exposure,
    concentration_metrics,
    factor_attribution,
    resolve_weights,
    summarize_risks,
)
from src.analysis.returns import compute_log_returns
from src.config import Config
from src.domain.models import (
    ConcentrationMetrics,
    FactorExposure,
    HoldingExposure,
    PortfolioAnalysis,
    PortfolioHoldingInput,
    UnresolvedHolding,
)
from src.errors import InsufficientDataError
from src.repositories.base import PriceRepository

logger = logging.getLogger(__name__)

#: `ticker` value used when an error is about the portfolio as a whole rather
#: than one symbol — `InsufficientDataError` is per-ticker by construction.
PORTFOLIO_SUBJECT = "portfolio"

IDIOSYNCRATIC_LABEL = "Unexplained"


class PortfolioService:
    def __init__(self, price_repo: PriceRepository, config: Config):
        self._price_repo = price_repo
        self._config = config

    def analyze(
        self,
        holdings: Sequence[PortfolioHoldingInput],
        anchors: list[str] | None = None,
    ) -> PortfolioAnalysis:
        requested = self._normalise(holdings)
        if not requested:
            raise InsufficientDataError(PORTFOLIO_SUBJECT, "no holdings supplied")

        anchor_list = [a.upper() for a in (anchors or self._config.anchors)]
        tickers = list(dict.fromkeys([*requested, *anchor_list]))
        prices = self._price_repo.get_price_history(tickers, self._config.lookback_days)

        available_anchors = [a for a in anchor_list if a in prices.columns and prices[a].notna().any()]
        if not available_anchors:
            raise InsufficientDataError(PORTFOLIO_SUBJECT, f"no price history for any anchor in {anchor_list}")

        returns = compute_log_returns(prices)
        correlations, unresolved = self._correlation_matrix(requested, returns, available_anchors)
        if correlations.empty:
            raise InsufficientDataError(
                PORTFOLIO_SUBJECT, "none of the supplied holdings had enough overlapping price history"
            )

        last_prices = prices.ffill().iloc[-1] if not prices.empty else pd.Series(dtype=float)
        shares = pd.Series({ticker: requested[ticker] for ticker in correlations.index}, dtype=float)
        weights, weighting, market_values = resolve_weights(shares, last_prices)

        attribution, r_squared = factor_attribution(correlations, self._anchor_matrix(returns, available_anchors))
        exposure = aggregate_exposure(attribution, weights)
        metrics = concentration_metrics(exposure)

        return PortfolioAnalysis(
            anchors=available_anchors,
            holdings=self._holding_models(correlations, weights, r_squared, shares, last_prices, market_values),
            unresolved=unresolved,
            weighting=weighting,
            total_value=float(market_values.sum()) if market_values is not None else None,
            factor_exposure=self._exposure_models(exposure),
            concentration=ConcentrationMetrics(**metrics),  # type: ignore[arg-type]
            risk_summary=summarize_risks(exposure, metrics, weighting, len(unresolved)),
            lookback_days=self._config.lookback_days,
            generated_at=dt.datetime.now(dt.timezone.utc),
        )

    # -- assembly --------------------------------------------------------------

    @staticmethod
    def _normalise(holdings: Sequence[PortfolioHoldingInput]) -> dict[str, float | None]:
        """Upper-case, strip, and merge repeats.

        Pasted lists routinely contain the same symbol twice (two lots of the
        same stock). Summing the share counts is the only reading that keeps
        the weights right; keeping both rows would double-count the position
        in the variance roll-up.
        """
        merged: dict[str, float | None] = {}
        for holding in holdings:
            ticker = holding.ticker.strip().upper()
            if not ticker:
                continue
            if ticker in merged and merged[ticker] is not None and holding.shares is not None:
                merged[ticker] = (merged[ticker] or 0.0) + holding.shares
            elif ticker in merged:
                # One of the two lots had no share count, so the position size
                # is unknowable — degrade the whole ticker to "unsized" rather
                # than reporting a total that omits a lot.
                merged[ticker] = None
            else:
                merged[ticker] = holding.shares
        return merged

    @staticmethod
    def _correlation_matrix(
        requested: dict[str, float | None],
        returns: pd.DataFrame,
        anchors: list[str],
    ) -> tuple[pd.DataFrame, list[UnresolvedHolding]]:
        """Holdings x anchors Pearson matrix, plus the holdings that fell out.

        `compute_correlations` is reused verbatim so pair alignment and the
        30-day minimum-overlap rule match the rest of the pipeline instead of
        being re-implemented with subtly different semantics here. A holding
        that is itself an anchor correlates 1.0 with that column, which falls
        out of the same call.
        """
        unresolved = [
            UnresolvedHolding(ticker=ticker, reason="No price history available")
            for ticker in requested
            if ticker not in returns.columns
        ]
        present = [ticker for ticker in requested if ticker in returns.columns]
        if not present:
            return pd.DataFrame(), unresolved

        matrix = pd.DataFrame(
            {anchor: compute_correlations(returns[anchor], returns[present], method="pearson") for anchor in anchors}
        ).reindex(index=present, columns=anchors)

        usable = matrix.notna().any(axis=1)
        unresolved += [
            UnresolvedHolding(
                ticker=str(ticker),
                reason=f"Fewer than {MIN_OVERLAP_DAYS} trading days overlapping with the anchors",
            )
            for ticker in matrix.index[~usable]
        ]
        return matrix[usable], unresolved

    @staticmethod
    def _anchor_matrix(returns: pd.DataFrame, anchors: list[str]) -> pd.DataFrame:
        """Anchor-vs-anchor Pearson matrix, the `C` in the Pratt decomposition.

        Pairs with no overlapping history come back NaN from `.corr()`; they
        become 0 (treat the two anchors as independent) so the solve still
        runs. Understating the overlap between two anchors can only spread
        variance across them rather than concentrate it, so the failure mode
        is a conservative one.
        """
        matrix = returns[anchors].corr(method="pearson").fillna(0.0)
        for anchor in anchors:
            matrix.loc[anchor, anchor] = 1.0
        return matrix

    @staticmethod
    def _holding_models(
        correlations: pd.DataFrame,
        weights: pd.Series,
        r_squared: pd.Series,
        shares: pd.Series,
        last_prices: pd.Series,
        market_values: pd.Series | None,
    ) -> list[HoldingExposure]:
        models = []
        for ticker, row in correlations.iterrows():
            key = str(ticker)
            last_price = last_prices.get(key)
            models.append(
                HoldingExposure(
                    ticker=key,
                    shares=_finite(shares.get(key)),
                    last_price=_finite(last_price),
                    market_value=_finite(market_values.get(key)) if market_values is not None else None,
                    weight=float(weights.get(key, 0.0)),
                    correlations={anchor: _finite(row.get(anchor)) for anchor in correlations.columns},
                    r_squared=float(r_squared.get(key, 0.0)),
                )
            )
        # Largest position first: the ordering the table and heatmap both want,
        # decided once here rather than re-sorted in two frontend components.
        return sorted(models, key=lambda m: m.weight, reverse=True)

    @staticmethod
    def _exposure_models(exposure: pd.Series) -> list[FactorExposure]:
        anchors = exposure.drop(labels=[IDIOSYNCRATIC], errors="ignore").sort_values(ascending=False)
        models = [
            FactorExposure(factor=str(factor), label=str(factor), share=float(share))
            for factor, share in anchors.items()
        ]
        # Always last, whatever its size — it's the residual, and a pie that
        # re-sorts the "everything else" slice into the middle reads as a
        # peer of the named factors when it isn't one.
        models.append(
            FactorExposure(
                factor=IDIOSYNCRATIC,
                label=IDIOSYNCRATIC_LABEL,
                share=float(exposure.get(IDIOSYNCRATIC, 0.0)),
                is_idiosyncratic=True,
            )
        )
        return models


def _finite(value: object) -> float | None:
    """NaN/inf -> None, mirroring `src.domain.serialization`: pydantic's strict
    JSON encoder rejects non-finite floats, and pandas hands them back freely.
    """
    if value is None:
        return None
    number = float(value)  # type: ignore[arg-type]
    return number if pd.notna(number) and abs(number) != float("inf") else None
