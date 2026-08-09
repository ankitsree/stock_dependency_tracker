"""`PriceRepository` backed by Postgres, with yfinance as the cache-miss
fallback — Postgres is a durable, queryable cache, not a new data vendor
(target-architecture.md §5.3).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from src.data.fetcher import fetch_price_history
from src.repositories.postgres.models import CompanyRow, PriceRow


class PostgresPriceRepository:
    """Reads/writes `prices`, matching `YFinancePriceRepository`'s
    constructor shape (`cache_dir`, `cache_ttl_seconds`) — `cache_dir` is
    passed straight through to the same `fetch_price_history` used by the
    yfinance-backed repository, so a cache miss here fetches and validates
    prices exactly the same way, just durably upserted into Postgres instead
    of only written to parquet.
    """

    def __init__(self, session_factory: sessionmaker, cache_dir: Path, cache_ttl_seconds: float | None = 6 * 3600):
        self._session_factory = session_factory
        self._cache_dir = cache_dir
        self._cache_ttl_seconds = cache_ttl_seconds

    def get_price_history(
        self,
        tickers: list[str],
        lookback_days: int,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        max_age = 0 if force_refresh else self._cache_ttl_seconds
        stale = self._stale_tickers(tickers, max_age)
        if stale:
            fresh = fetch_price_history(stale, lookback_days, self._cache_dir, max_cache_age_seconds=0)
            self._upsert_prices(fresh)

        cutoff = dt.date.today() - dt.timedelta(days=lookback_days)
        with self._session_factory() as session:
            rows = session.execute(
                select(PriceRow.ticker, PriceRow.date, PriceRow.adjusted_close)
                .where(PriceRow.ticker.in_(tickers), PriceRow.date >= cutoff)
                .order_by(PriceRow.date)
            ).all()
        return self._to_wide(rows)

    def _stale_tickers(self, tickers: list[str], max_age: float | None) -> list[str]:
        """A ticker is stale if it has no rows yet, or its most recent
        `fetched_at` is older than `max_age` seconds. `max_age=0`
        (force_refresh) short-circuits to "everything is stale" without a
        query — matches `YFinancePriceRepository`'s force_refresh semantics.
        """
        if not tickers:
            return []
        if max_age == 0:
            return list(tickers)
        with self._session_factory() as session:
            latest = dict(
                session.execute(
                    select(PriceRow.ticker, func.max(PriceRow.fetched_at))
                    .where(PriceRow.ticker.in_(tickers))
                    .group_by(PriceRow.ticker)
                ).all()
            )
        if max_age is None:
            return [t for t in tickers if t not in latest]
        now = dt.datetime.now(dt.timezone.utc)
        return [t for t in tickers if t not in latest or (now - latest[t]).total_seconds() > max_age]

    # Postgres caps bound parameters per query at 65535. Each row binds 4
    # (ticker, date, adjusted_close, fetched_at), so a full backfill — tens of
    # tickers x a year of trading days — comfortably exceeds that in one
    # INSERT. 2000 rows/batch (8000 params) stays well clear with headroom.
    _UPSERT_BATCH_SIZE = 2000

    def _upsert_prices(self, wide: pd.DataFrame) -> None:
        if wide.empty:
            return
        tickers = list(wide.columns)
        now = dt.datetime.now(dt.timezone.utc)
        rows = [
            {"ticker": ticker, "date": pd.Timestamp(date_).date(), "adjusted_close": float(close), "fetched_at": now}
            for ticker in tickers
            for date_, close in wide[ticker].dropna().items()
        ]
        if not rows:
            return
        with self._session_factory() as session:
            self._ensure_company_placeholders(session, tickers)
            for batch_start in range(0, len(rows), self._UPSERT_BATCH_SIZE):
                batch = rows[batch_start : batch_start + self._UPSERT_BATCH_SIZE]
                stmt = pg_insert(PriceRow).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ticker", "date"],
                    set_={"adjusted_close": stmt.excluded.adjusted_close, "fetched_at": stmt.excluded.fetched_at},
                )
                session.execute(stmt)
            session.commit()

    @staticmethod
    def _ensure_company_placeholders(session, tickers: list[str]) -> None:
        """`prices.ticker` has a foreign key to `companies.ticker`, so a
        ticker with no company row yet (an anchor never in the curated
        universe, e.g.) needs a minimal placeholder before its price rows can
        be inserted. `name=ticker, sector="Unknown"` matches the existing
        fallback CompanyService.get_company_profile() already applies for any
        ticker outside the universe — not a new behavior, just where it now
        also has to be written down. ON CONFLICT DO NOTHING: never overwrites
        a real name/sector already seeded by the universe backfill.
        """
        now = dt.datetime.now(dt.timezone.utc)
        stmt = pg_insert(CompanyRow).values(
            [
                {"ticker": t, "name": t, "sector": "Unknown", "is_satellite_universe": False, "updated_at": now}
                for t in tickers
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker"])
        session.execute(stmt)

    @staticmethod
    def _to_wide(rows) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["ticker", "date", "adjusted_close"])
        wide = df.pivot(index="date", columns="ticker", values="adjusted_close")
        wide.index = pd.to_datetime(wide.index)
        wide.index.name = "date"
        wide.columns.name = None
        return wide
