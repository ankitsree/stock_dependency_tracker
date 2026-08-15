"""SQLAlchemy 2.0 declarative models for the `companies` / `prices` tables.

Deliberately separate from `src/domain/models.py` (the framework-agnostic
pydantic models services and the API return) — the project's domain layer
stays free of a storage-framework dependency, and rows are translated to/from
domain models at the repository boundary only. See
docs/prod_roadmap/target-architecture.md §5.1/§5.2 for the rationale and the
schema this mirrors.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLAlchemy's declarative mapper evaluates `Mapped[...]` annotations at
# runtime (unlike pydantic/FastAPI, `eval_type_backport` doesn't cover this
# path) — `X | None` (PEP 604) isn't evaluable on the Python 3.9 the local
# venv runs, so this file uses `Optional[X]` instead, unlike the rest of the
# codebase.


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"

    ticker: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str] = mapped_column(String, nullable=False)
    # Populated by Phase 7's screener job; unused (always NULL) until then.
    industry: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Flag, not table membership: get_company_profile() must resolve any
    # ticker (anchors like NVDA are never in the universe) — list_universe()
    # is the one query that filters on this.
    is_satellite_universe: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PriceRow(Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_prices_ticker_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String, ForeignKey("companies.ticker"), nullable=False, index=True)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    adjusted_close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CorrelationRow(Base):
    """One row per (anchor, satellite) per computation run.

    Written by the daily correlation-recompute job (Phase 1 of Track A) and
    read by the graph endpoint so `/api/graph` no longer runs the full
    diagnostic stack on the request path. Composite PK includes
    `computed_at` so a full run's rows are inserted as a batch and previous
    snapshots stay queryable (Phase 4 regime surfacing reads them).
    """

    __tablename__ = "correlations"

    anchor: Mapped[str] = mapped_column(String, primary_key=True)
    satellite: Mapped[str] = mapped_column(String, primary_key=True)
    lookback_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), primary_key=True)

    # Ranking + core correlations. Nullable because a satellite that clears
    # the top-N filter on Spearman may not have every downstream diagnostic
    # (e.g. lag/regime require enough overlap in the rolling window).
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spearman_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pearson_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    partial_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector_relative_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_lag: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    best_lag_correlation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    regime_break: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    regime_drift: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
