"""`CorrelationRepository` backed by Postgres.

Written by the daily correlation-recompute job (Track A Phase 1); read by
the graph endpoint so `/api/graph` no longer runs the full analytic stack
per request. Composite PK includes `computed_at` so previous snapshots stay
queryable — Phase 4 regime surfacing reads the delta between snapshots.

Unlike the price/company repos, there is no yfinance fallback here: the
"cache miss" path lives in `CorrelationService` (fall back to live
computation), because computing correlations requires running the analytics
pipeline, not fetching from a vendor.
"""

from __future__ import annotations

import datetime as dt
import math

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from src.repositories.base import CorrelationSnapshot
from src.repositories.postgres.models import CompanyRow, CorrelationRow

# The DataFrame column names produced by CorrelationService._compute_full_diagnostics
# don't all line up with the DB column names (the primary "correlation"
# column is Spearman by design, and "stability" is the "stability_score").
# One mapping table keeps the read and write paths in sync.
_DF_TO_DB: dict[str, str] = {
    "correlation": "spearman_correlation",
    "pearson_correlation": "pearson_correlation",
    "partial_correlation": "partial_correlation",
    "sector_relative_correlation": "sector_relative_correlation",
    "stability": "stability_score",
    "best_lag": "best_lag",
    "best_lag_correlation": "best_lag_correlation",
    "regime_break": "regime_break",
    "regime_drift": "regime_drift",
}
_DB_TO_DF = {db: dfcol for dfcol, db in _DF_TO_DB.items()}


class PostgresCorrelationRepository:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def upsert_snapshot(
        self,
        anchor: str,
        satellites: pd.DataFrame,
        lookback_days: int,
        computed_at: dt.datetime,
    ) -> None:
        if satellites.empty:
            return
        rows = self._rows_from_dataframe(anchor, satellites, lookback_days, computed_at)
        with self._session_factory() as session:
            self._ensure_company_placeholders(session, [anchor, *satellites["ticker"].tolist()])
            stmt = pg_insert(CorrelationRow).values(rows)
            # Composite PK == (anchor, satellite, lookback_days, computed_at).
            # Same-second re-runs of the job land on the same row and update
            # in place; different `computed_at` values keep as history.
            stmt = stmt.on_conflict_do_update(
                index_elements=["anchor", "satellite", "lookback_days", "computed_at"],
                set_={col: stmt.excluded[col] for col in {"rank", *_DF_TO_DB.values()}},
            )
            session.execute(stmt)
            session.commit()

    def get_latest(self, anchor: str, lookback_days: int) -> CorrelationSnapshot | None:
        with self._session_factory() as session:
            # Find the newest computed_at for this (anchor, lookback_days),
            # then fetch every satellite row that shares it. Two round-trips
            # is fine — the alternative (window function) doesn't win at N=55.
            latest_computed_at = session.execute(
                select(CorrelationRow.computed_at)
                .where(CorrelationRow.anchor == anchor, CorrelationRow.lookback_days == lookback_days)
                .order_by(CorrelationRow.computed_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_computed_at is None:
                return None
            rows = session.execute(
                select(CorrelationRow, CompanyRow.name, CompanyRow.sector)
                .join(CompanyRow, CompanyRow.ticker == CorrelationRow.satellite)
                .where(
                    CorrelationRow.anchor == anchor,
                    CorrelationRow.lookback_days == lookback_days,
                    CorrelationRow.computed_at == latest_computed_at,
                )
                .order_by(CorrelationRow.rank.asc().nullslast(), CorrelationRow.satellite.asc())
            ).all()
        satellites = self._dataframe_from_rows(rows)
        return CorrelationSnapshot(
            anchor=anchor,
            lookback_days=lookback_days,
            computed_at=latest_computed_at,
            satellites=satellites,
        )

    # -- row conversion --------------------------------------------------------

    @staticmethod
    def _rows_from_dataframe(
        anchor: str,
        satellites: pd.DataFrame,
        lookback_days: int,
        computed_at: dt.datetime,
    ) -> list[dict]:
        rows = []
        for rank, record in enumerate(satellites.to_dict(orient="records"), start=1):
            row: dict = {
                "anchor": anchor,
                "satellite": record["ticker"],
                "lookback_days": lookback_days,
                "computed_at": computed_at,
                "rank": rank,
            }
            for dfcol, dbcol in _DF_TO_DB.items():
                value = record.get(dfcol)
                row[dbcol] = _clean(value)
            rows.append(row)
        return rows

    @staticmethod
    def _dataframe_from_rows(rows) -> pd.DataFrame:
        records = []
        for row, name, sector in rows:
            record: dict = {"ticker": row.satellite, "name": name, "sector": sector}
            for dbcol, dfcol in _DB_TO_DF.items():
                record[dfcol] = getattr(row, dbcol)
            records.append(record)
        if not records:
            return pd.DataFrame()
        columns = [
            "ticker",
            "name",
            "sector",
            "correlation",
            "stability",
            "pearson_correlation",
            "partial_correlation",
            "sector_relative_correlation",
            "best_lag",
            "best_lag_correlation",
            "regime_break",
            "regime_drift",
        ]
        return pd.DataFrame(records)[columns]

    @staticmethod
    def _ensure_company_placeholders(session, tickers: list[str]) -> None:
        """`correlations.anchor`/`.satellite` don't have foreign keys, but the
        read path joins to `companies` for name/sector — a satellite the
        universe doesn't know about would drop out of the join and vanish
        silently. Placeholder rows here mirror the pattern
        `PostgresPriceRepository` uses for anchors outside the curated universe.
        """
        now = dt.datetime.now(dt.timezone.utc)
        deduped = list(dict.fromkeys(tickers))
        stmt = pg_insert(CompanyRow).values(
            [
                {"ticker": t, "name": t, "sector": "Unknown", "is_satellite_universe": False, "updated_at": now}
                for t in deduped
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker"])
        session.execute(stmt)


def _clean(value):
    """NaN/inf must become None so the DB stores a real NULL, not a float
    that pydantic rejects on the read side. Same trick as
    `src.domain.serialization._is_non_finite`, applied on the write path.
    Booleans need explicit handling because pandas stores them as object dtype
    with NaN for missing values.
    """
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    # pandas surfaces missing regime_break as NaN in an object-typed column;
    # bool(NaN) == True, which would poison the DB.
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
