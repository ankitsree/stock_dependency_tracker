"""Real-Postgres tests for `PostgresCorrelationRepository`.

Same pattern as the price/company repo tests (see conftest.py header):
skipped when no reachable database, run for real in CI against a
throwaway `postgres:16` service container.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from src.repositories.postgres.correlation_repository import PostgresCorrelationRepository
from src.repositories.postgres.models import CompanyRow, CorrelationRow


def _diagnostics(rows):
    """Build a satellites DataFrame in the exact shape
    CorrelationService._compute_full_diagnostics returns — the shape
    the repo has to persist and hand back untouched.
    """
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
    return pd.DataFrame(rows, columns=columns)


def test_upsert_and_get_latest_roundtrip(session_factory):
    repo = PostgresCorrelationRepository(session_factory)
    computed_at = dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc)
    satellites = _diagnostics(
        [
            ("SAT_A", "Sat A", "Semiconductors", 0.85, 0.7, 0.82, 0.5, 0.3, 1, 0.4, False, 0.05),
            ("SAT_B", "Sat B", "Software", 0.72, 0.6, 0.70, 0.4, 0.2, 0, 0.1, True, 0.20),
        ]
    )

    repo.upsert_snapshot("NVDA", satellites, lookback_days=365, computed_at=computed_at)

    snapshot = repo.get_latest("NVDA", lookback_days=365)
    assert snapshot is not None
    assert snapshot.anchor == "NVDA"
    assert snapshot.lookback_days == 365
    assert snapshot.computed_at == computed_at
    assert list(snapshot.satellites["ticker"]) == ["SAT_A", "SAT_B"]
    assert snapshot.satellites.loc[0, "correlation"] == 0.85
    assert bool(snapshot.satellites.loc[0, "regime_break"]) is False
    assert bool(snapshot.satellites.loc[1, "regime_break"]) is True


def test_get_latest_returns_none_when_nothing_persisted(session_factory):
    repo = PostgresCorrelationRepository(session_factory)
    assert repo.get_latest("NVDA", lookback_days=365) is None


def test_get_latest_returns_newest_snapshot(session_factory):
    repo = PostgresCorrelationRepository(session_factory)
    older = dt.datetime(2026, 8, 14, 16, 0, tzinfo=dt.timezone.utc)
    newer = dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc)

    repo.upsert_snapshot(
        "NVDA",
        _diagnostics([("SAT_A", "Sat A", "Semis", 0.5, 0.4, 0.5, 0.3, 0.2, 0, 0.1, False, 0.0)]),
        lookback_days=365,
        computed_at=older,
    )
    repo.upsert_snapshot(
        "NVDA",
        _diagnostics([("SAT_A", "Sat A", "Semis", 0.9, 0.8, 0.9, 0.7, 0.6, 0, 0.1, False, 0.0)]),
        lookback_days=365,
        computed_at=newer,
    )

    snapshot = repo.get_latest("NVDA", lookback_days=365)
    assert snapshot.computed_at == newer
    assert snapshot.satellites.loc[0, "correlation"] == 0.9


def test_same_computed_at_upserts_in_place(session_factory):
    """Composite PK includes computed_at; re-running the job for the same
    timestamp replaces existing rows rather than duplicating them.
    """
    repo = PostgresCorrelationRepository(session_factory)
    ts = dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc)

    repo.upsert_snapshot(
        "NVDA",
        _diagnostics([("SAT_A", "Sat A", "Semis", 0.5, 0.4, 0.5, 0.3, 0.2, 0, 0.1, False, 0.0)]),
        lookback_days=365,
        computed_at=ts,
    )
    repo.upsert_snapshot(
        "NVDA",
        _diagnostics([("SAT_A", "Sat A", "Semis", 0.99, 0.98, 0.99, 0.9, 0.8, 0, 0.1, False, 0.0)]),
        lookback_days=365,
        computed_at=ts,
    )

    with session_factory() as session:
        count = session.query(CorrelationRow).filter(CorrelationRow.anchor == "NVDA").count()
    assert count == 1
    snapshot = repo.get_latest("NVDA", lookback_days=365)
    assert snapshot.satellites.loc[0, "correlation"] == 0.99


def test_nan_and_inf_become_null(session_factory):
    """The DataFrame CorrelationService returns can have NaN (missing
    diagnostic) or +/-inf (near-zero denominator in partial correlation).
    Both must round-trip as SQL NULL and pandas-side None/NaN, or the
    pydantic response models would refuse to serialize.
    """
    repo = PostgresCorrelationRepository(session_factory)
    ts = dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc)
    satellites = _diagnostics(
        [
            ("SAT_A", "Sat A", "Semis", 0.6, np.nan, np.nan, float("inf"), np.nan, np.nan, np.nan, np.nan, np.nan),
        ]
    )

    repo.upsert_snapshot("NVDA", satellites, lookback_days=365, computed_at=ts)

    with session_factory() as session:
        row = session.query(CorrelationRow).one()
    assert row.stability_score is None
    assert row.pearson_correlation is None
    assert row.partial_correlation is None  # inf -> NULL
    assert row.regime_break is None  # NaN was float, not bool


def test_placeholder_company_row_created_for_unknown_ticker(session_factory):
    """The read path joins to `companies` for name/sector — an anchor or
    satellite the universe doesn't know about would drop out of the join
    otherwise. Placeholder rows keep the shape consistent.
    """
    repo = PostgresCorrelationRepository(session_factory)
    ts = dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc)
    satellites = _diagnostics([("BRAND_NEW", "Brand New", "Unknown", 0.6, 0.5, 0.6, 0.3, 0.2, 0, 0.1, False, 0.0)])

    repo.upsert_snapshot("ALSO_NEW", satellites, lookback_days=365, computed_at=ts)

    with session_factory() as session:
        anchor_row = session.get(CompanyRow, "ALSO_NEW")
        sat_row = session.get(CompanyRow, "BRAND_NEW")
    assert anchor_row is not None
    assert sat_row is not None


def test_empty_satellites_is_noop(session_factory):
    repo = PostgresCorrelationRepository(session_factory)
    ts = dt.datetime(2026, 8, 15, 16, 0, tzinfo=dt.timezone.utc)

    repo.upsert_snapshot("NVDA", _diagnostics([]), lookback_days=365, computed_at=ts)

    assert repo.get_latest("NVDA", lookback_days=365) is None
