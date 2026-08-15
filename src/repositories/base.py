from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class PriceRepository(Protocol):
    """Source of daily adjusted-close price history.

    Structural typing (Protocol, not ABC) on purpose: services depend on
    this interface, never on a concrete implementation, so a future
    Postgres-backed repository satisfies the same contract with zero
    changes to services/routes/schemas — only src/api/deps.py's factory
    functions change.
    """

    def get_price_history(
        self,
        tickers: list[str],
        lookback_days: int,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Wide DataFrame: index=date, columns=ticker, values=adjusted close."""
        ...


class CompanyRepository(Protocol):
    """Source of the satellite universe and company market data."""

    def list_universe(self) -> pd.DataFrame:
        """ticker/name/sector for the satellite candidate pool.

        Backed today by a hardcoded list (src.data.universe.load_universe);
        a Postgres implementation would SELECT from a `companies` table
        instead.
        """
        ...

    def get_market_data(
        self,
        tickers: list[str],
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """ticker/market_cap/avg_volume."""
        ...

    def get_company_facts(self, ticker: str, force_refresh: bool = False) -> dict:
        """Valuation ratios (P/E, PEG, price/book, dividend yield, beta) for a
        single ticker — the slower per-ticker `.info` fetch, kept separate from
        the bulk `get_market_data` path. Missing ratios are None. A Postgres
        implementation would SELECT these columns from the `companies` table.
        """
        ...


@dataclass(frozen=True)
class CorrelationSnapshot:
    """A single (anchor, lookback_days) snapshot the repo hands back.

    `satellites` is the same wide-DataFrame the CorrelationService produces
    (ticker/name/sector/correlation + all Phase 4 diagnostics), so the graph
    endpoint can consume a cached snapshot exactly like a fresh compute
    result without a translation layer.
    """

    anchor: str
    lookback_days: int
    computed_at: dt.datetime
    satellites: pd.DataFrame


class CorrelationRepository(Protocol):
    """Storage for the daily correlation-recompute job's output.

    Read path: `get_latest(anchor, lookback_days)` returns the most recently
    computed snapshot, or None. The graph endpoint reads from here so
    `/api/graph` never runs the full diagnostic stack on the request path.

    Write path: `upsert_snapshot(...)` — the CLI's daily job builds one call
    per anchor from `CorrelationService.rank_with_full_diagnostics`.
    """

    def upsert_snapshot(
        self,
        anchor: str,
        satellites: pd.DataFrame,
        lookback_days: int,
        computed_at: dt.datetime,
    ) -> None:
        """Insert one row per satellite for this (anchor, lookback_days,
        computed_at) tuple. Composite PK on the table means re-running the
        job for the same computed_at replaces existing rows.
        """
        ...

    def get_latest(self, anchor: str, lookback_days: int) -> CorrelationSnapshot | None:
        """Most recent snapshot for `(anchor, lookback_days)`, or None if
        nothing has been persisted yet — the graph endpoint uses None as the
        "fall back to live compute" signal.
        """
        ...
