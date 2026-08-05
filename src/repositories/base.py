from __future__ import annotations

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
