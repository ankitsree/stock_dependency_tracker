"""Business logic for ranking satellites against an anchor.

Three graduated methods mirror the actual evolution of the pipeline across
phases 1-4 (Phase 4's diagnostics genuinely are Phase 2/3's ranking with more
steps appended) so each phase's exact historical output shape is preserved
for the CLI, while the API only ever needs the richest one.

All the actual math is untouched, reused verbatim from src.analysis.* — this
service is orchestration (fetch -> shape -> call analysis functions in the
right order -> attach results), not a reimplementation.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass

import pandas as pd

from src.analysis.correlation import (
    SECTOR_ETF_MAP,
    compute_correlations,
    compute_lagged_correlations,
    compute_partial_correlations,
    compute_rolling_correlations,
    compute_sector_relative_correlations,
    compute_stability_scores,
    detect_regime_breaks,
)
from src.analysis.ranking import attach_metric, attach_stability, rank_top_n
from src.analysis.returns import compute_log_returns
from src.config import Config
from src.domain.models import RankedSatellite
from src.domain.serialization import dataframe_to_models
from src.errors import InsufficientDataError, TickerNotFoundError
from src.repositories.base import CompanyRepository, PriceRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiagnosticsResult:
    """Return type of `rank_with_full_diagnostics` — the ranked satellites
    plus enough metadata for an API caller to know whether it's looking at a
    just-computed or cached result."""

    anchor: str
    satellites: pd.DataFrame
    generated_at: dt.datetime
    cache_hit: bool

    def as_domain(self) -> list[RankedSatellite]:
        return dataframe_to_models(self.satellites, RankedSatellite)


class CorrelationService:
    def __init__(
        self,
        price_repo: PriceRepository,
        company_repo: CompanyRepository,
        config: Config,
        result_cache_ttl_seconds: float = 3600,
    ):
        self._price_repo = price_repo
        self._company_repo = company_repo
        self._config = config
        self._result_cache_ttl_seconds = result_cache_ttl_seconds
        self._result_cache: dict[tuple, DiagnosticsResult] = {}

    # -- Phase 1 equivalent --------------------------------------------------

    def rank_correlations(
        self,
        anchor: str,
        top_n: int | None = None,
        threshold: float | None = None,
        method: str = "pearson",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        top_n, threshold = self._resolve_defaults(top_n, threshold)
        returns, universe = self._fetch_returns(anchor, extra_tickers=[], force_refresh=force_refresh)
        anchor_returns, satellite_returns = self._split(returns, anchor, exclude={anchor})
        correlations = compute_correlations(anchor_returns, satellite_returns, method=method)
        return rank_top_n(correlations, universe, top_n, threshold)

    # -- Phase 2/3 equivalent -------------------------------------------------

    def rank_with_stability(
        self,
        anchor: str,
        exclude_tickers: set[str] | None = None,
        top_n: int | None = None,
        threshold: float | None = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        top_n, threshold = self._resolve_defaults(top_n, threshold)
        exclude = {anchor, *(exclude_tickers or ())}
        returns, universe = self._fetch_returns(anchor, extra_tickers=[], force_refresh=force_refresh)
        anchor_returns, satellite_returns = self._split(returns, anchor, exclude=exclude)

        correlations = compute_correlations(anchor_returns, satellite_returns, method="pearson")
        rolling = compute_rolling_correlations(anchor_returns, satellite_returns, self._config.rolling_window)
        stability = compute_stability_scores(rolling)

        ranked = rank_top_n(correlations, universe, top_n, threshold)
        if ranked.empty:
            return ranked
        return attach_stability(ranked, stability)

    # -- Phase 4 equivalent / what the API exposes -----------------------------

    def rank_with_full_diagnostics(
        self,
        anchor: str,
        exclude_tickers: set[str] | None = None,
        top_n: int | None = None,
        threshold: float | None = None,
        force_refresh: bool = False,
    ) -> DiagnosticsResult:
        top_n, threshold = self._resolve_defaults(top_n, threshold)
        cache_key = (anchor, frozenset(exclude_tickers or ()), top_n, threshold)

        if not force_refresh:
            cached = self._result_cache.get(cache_key)
            if cached is not None and (time.time() - cached.generated_at.timestamp()) < self._result_cache_ttl_seconds:
                return DiagnosticsResult(cached.anchor, cached.satellites, cached.generated_at, cache_hit=True)

        satellites = self._compute_full_diagnostics(anchor, exclude_tickers, top_n, threshold, force_refresh)
        result = DiagnosticsResult(anchor, satellites, dt.datetime.now(dt.timezone.utc), cache_hit=False)
        self._result_cache[cache_key] = result
        return result

    def _compute_full_diagnostics(
        self,
        anchor: str,
        exclude_tickers: set[str] | None,
        top_n: int,
        threshold: float,
        force_refresh: bool,
    ) -> pd.DataFrame:
        sector_etf_tickers = sorted(set(SECTOR_ETF_MAP.values()))
        extra_tickers = [self._config.market_proxy_ticker, *sector_etf_tickers]

        returns, universe = self._fetch_returns(anchor, extra_tickers=extra_tickers, force_refresh=force_refresh)
        if self._config.market_proxy_ticker not in returns.columns:
            raise InsufficientDataError(anchor, f"no data for market proxy {self._config.market_proxy_ticker!r}")
        missing_etfs = set(sector_etf_tickers) - set(returns.columns)
        if missing_etfs:
            raise InsufficientDataError(anchor, f"no data for sector ETF(s) {sorted(missing_etfs)}")

        market_returns = returns[self._config.market_proxy_ticker]
        sector_etf_returns = {ticker: returns[ticker] for ticker in sector_etf_tickers}

        exclude = {anchor, self._config.market_proxy_ticker, *sector_etf_tickers, *(exclude_tickers or ())}
        anchor_returns, satellite_returns = self._split(returns, anchor, exclude=exclude)

        spearman = compute_correlations(anchor_returns, satellite_returns, method="spearman")
        pearson = compute_correlations(anchor_returns, satellite_returns, method="pearson")
        rolling = compute_rolling_correlations(anchor_returns, satellite_returns, self._config.rolling_window)
        stability = compute_stability_scores(rolling)

        # Spearman drives the top-N filter; Pearson is attached as a secondary,
        # more interpretable figure (roadmap Phase 4).
        ranked = rank_top_n(spearman, universe, top_n, threshold)
        if ranked.empty:
            return ranked
        ranked = attach_stability(ranked, stability)
        ranked = attach_metric(ranked, pearson, "pearson_correlation")

        # Remaining diagnostics only run for satellites that already cleared
        # the primary filter.
        top_tickers = ranked["ticker"].tolist()
        top_returns = satellite_returns[top_tickers]

        partial = compute_partial_correlations(anchor_returns, top_returns, market_returns)
        ranked = attach_metric(ranked, partial, "partial_correlation")

        lagged = compute_lagged_correlations(anchor_returns, top_returns, self._config.lag_max_days)
        if not lagged.empty:
            ranked = attach_metric(ranked, lagged["best_lag"], "best_lag")
            ranked = attach_metric(ranked, lagged["best_lag_correlation"], "best_lag_correlation")

        satellite_sectors = ranked.set_index("ticker")["sector"]
        sector_relative = compute_sector_relative_correlations(anchor_returns, top_returns, satellite_sectors, sector_etf_returns)
        ranked = attach_metric(ranked, sector_relative, "sector_relative_correlation")

        top_rolling = {t: rolling[t] for t in top_tickers if t in rolling}
        regime = detect_regime_breaks(top_rolling, spearman, self._config.regime_recent_days, self._config.regime_break_threshold)
        if not regime.empty:
            ranked = attach_metric(ranked, regime["regime_break"], "regime_break")
            ranked = attach_metric(ranked, regime["drift"], "regime_drift")

        return ranked

    # -- shared helpers --------------------------------------------------------

    def _resolve_defaults(self, top_n: int | None, threshold: float | None) -> tuple[int, float]:
        return (
            top_n if top_n is not None else self._config.top_n,
            threshold if threshold is not None else self._config.correlation_threshold,
        )

    def _fetch_returns(self, anchor: str, extra_tickers: list[str], force_refresh: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
        universe = self._company_repo.list_universe()
        satellite_tickers = universe["ticker"].tolist()
        all_tickers = list(dict.fromkeys([anchor, *satellite_tickers, *extra_tickers]))
        prices = self._price_repo.get_price_history(all_tickers, self._config.lookback_days, force_refresh=force_refresh)
        if anchor not in prices.columns:
            raise TickerNotFoundError(anchor)
        return compute_log_returns(prices), universe

    @staticmethod
    def _split(returns: pd.DataFrame, anchor: str, exclude: set[str]) -> tuple[pd.Series, pd.DataFrame]:
        satellite_cols = [c for c in returns.columns if c not in exclude]
        return returns[anchor], returns[satellite_cols]
