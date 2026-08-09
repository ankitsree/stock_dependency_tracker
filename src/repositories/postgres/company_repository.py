"""`CompanyRepository` backed by Postgres, with yfinance as the cache-miss
fallback for market data — same "durable cache, not a new vendor" design as
`PostgresPriceRepository`.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from src.data.fetcher import fetch_company_facts, fetch_metadata
from src.repositories.postgres.models import CompanyRow


class PostgresCompanyRepository:
    def __init__(self, session_factory: sessionmaker, cache_dir: Path, cache_ttl_seconds: float | None = 6 * 3600):
        self._session_factory = session_factory
        self._cache_dir = cache_dir
        self._cache_ttl_seconds = cache_ttl_seconds

    def list_universe(self) -> pd.DataFrame:
        """No yfinance fallback: Postgres is the source of truth for the
        universe now, not a cache in front of one. An empty result means the
        `companies` table hasn't been backfilled yet
        (`python -m src.cli backfill-postgres`), not a fetch failure.
        """
        with self._session_factory() as session:
            rows = session.execute(
                select(CompanyRow.ticker, CompanyRow.name, CompanyRow.sector)
                .where(CompanyRow.is_satellite_universe.is_(True))
                .order_by(CompanyRow.ticker)
            ).all()
        return pd.DataFrame(rows, columns=["ticker", "name", "sector"])

    def get_market_data(
        self,
        tickers: list[str],
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        max_age = 0 if force_refresh else self._cache_ttl_seconds
        stale = self._stale_tickers(tickers, max_age)
        if stale:
            fresh = fetch_metadata(stale, self._cache_dir, max_cache_age_seconds=0)
            self._upsert_market_data(fresh)

        with self._session_factory() as session:
            rows = session.execute(
                select(CompanyRow.ticker, CompanyRow.market_cap, CompanyRow.avg_volume).where(
                    CompanyRow.ticker.in_(tickers)
                )
            ).all()
        return pd.DataFrame(rows, columns=["ticker", "market_cap", "avg_volume"])

    def get_company_facts(self, ticker: str, force_refresh: bool = False) -> dict:
        """Valuation ratios (P/E, PEG, beta, ...) were deliberately left out
        of the `companies` schema (target-architecture.md §5.2) — a
        single-ticker detail-view fact, not universe/graph data — so this
        goes straight to yfinance, same as YFinanceCompanyRepository.
        """
        max_age = 0 if force_refresh else self._cache_ttl_seconds
        facts = fetch_company_facts(ticker, self._cache_dir, max_cache_age_seconds=max_age)
        return {} if facts.empty else facts.iloc[0].to_dict()

    def upsert_universe(self, universe: pd.DataFrame) -> None:
        """Seed/refresh the satellite-universe rows with real name/sector and
        `is_satellite_universe=True`. Used by the one-off backfill CLI
        command to move the hardcoded `SATELLITE_UNIVERSE` list into
        Postgres; Phase 7's screener job calls the equivalent on a schedule
        instead of a Python list.
        """
        if universe.empty:
            return
        now = dt.datetime.now(dt.timezone.utc)
        rows = [
            {"ticker": r.ticker, "name": r.name, "sector": r.sector, "is_satellite_universe": True, "updated_at": now}
            for r in universe.itertuples()
        ]
        with self._session_factory() as session:
            stmt = pg_insert(CompanyRow).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "name": stmt.excluded.name,
                    "sector": stmt.excluded.sector,
                    "is_satellite_universe": stmt.excluded.is_satellite_universe,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()

    def _stale_tickers(self, tickers: list[str], max_age: float | None) -> list[str]:
        if not tickers:
            return []
        if max_age == 0:
            return list(tickers)
        with self._session_factory() as session:
            rows = session.execute(
                select(CompanyRow.ticker, CompanyRow.updated_at).where(CompanyRow.ticker.in_(tickers))
            ).all()
        updated_at = dict(rows)
        if max_age is None:
            return [t for t in tickers if t not in updated_at]
        now = dt.datetime.now(dt.timezone.utc)
        return [t for t in tickers if t not in updated_at or (now - updated_at[t]).total_seconds() > max_age]

    def _upsert_market_data(self, metadata: pd.DataFrame) -> None:
        if metadata.empty:
            return
        now = dt.datetime.now(dt.timezone.utc)

        def _clean(value):
            return None if pd.isna(value) else float(value)

        rows = [
            {
                "ticker": r.ticker,
                # Placeholders only used on first INSERT for a ticker with no
                # existing row (e.g. an anchor never in the curated
                # universe) — ON CONFLICT leaves a real name/sector alone.
                "name": r.ticker,
                "sector": "Unknown",
                "market_cap": _clean(r.market_cap),
                "avg_volume": _clean(r.avg_volume),
                "is_satellite_universe": False,
                "updated_at": now,
            }
            for r in metadata.itertuples()
        ]
        with self._session_factory() as session:
            stmt = pg_insert(CompanyRow).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "market_cap": stmt.excluded.market_cap,
                    "avg_volume": stmt.excluded.avg_volume,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            session.execute(stmt)
            session.commit()
