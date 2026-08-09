import datetime as dt

import pandas as pd

from src.repositories.postgres import price_repository as module
from src.repositories.postgres.models import CompanyRow, PriceRow
from src.repositories.postgres.price_repository import PostgresPriceRepository


def _fake_prices(tickers, n=5):
    # Recent dates, not a fixed past date: the repo filters reads to
    # `date >= today - lookback_days`, so fixture data has to stay inside
    # whatever window each test queries with.
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame({t: [100.0 + i for i in range(n)] for t in tickers}, index=dates)


def test_cache_miss_fetches_from_yfinance_and_persists(tmp_path, session_factory, monkeypatch):
    calls = []

    def fake_fetch(tickers, lookback_days, cache_dir, max_cache_age_seconds=None):
        calls.append(tuple(sorted(tickers)))
        return _fake_prices(tickers)

    monkeypatch.setattr(module, "fetch_price_history", fake_fetch)
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    result = repo.get_price_history(["NVDA", "AMD"], lookback_days=30)

    assert calls == [("AMD", "NVDA")]
    assert set(result.columns) == {"NVDA", "AMD"}
    assert len(result) == 5


def test_second_call_is_cache_hit_no_refetch(tmp_path, session_factory, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "fetch_price_history",
        lambda tickers, lookback_days, cache_dir, max_cache_age_seconds=None: calls.append(1) or _fake_prices(tickers),
    )
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    repo.get_price_history(["NVDA"], lookback_days=30)
    repo.get_price_history(["NVDA"], lookback_days=30)

    assert len(calls) == 1  # second call served from Postgres, not yfinance


def test_force_refresh_always_refetches(tmp_path, session_factory, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "fetch_price_history",
        lambda tickers, lookback_days, cache_dir, max_cache_age_seconds=None: calls.append(1) or _fake_prices(tickers),
    )
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    repo.get_price_history(["NVDA"], lookback_days=30)
    repo.get_price_history(["NVDA"], lookback_days=30, force_refresh=True)

    assert len(calls) == 2


def test_stale_row_beyond_ttl_triggers_refetch(tmp_path, session_factory, monkeypatch):
    monkeypatch.setattr(module, "fetch_price_history", lambda *a, **k: _fake_prices(["NVDA"]))
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)
    repo.get_price_history(["NVDA"], lookback_days=30)

    # Backdate the row's fetched_at well past the TTL, bypassing the repo.
    with session_factory() as session:
        session.query(PriceRow).update({PriceRow.fetched_at: dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)})
        session.commit()

    calls = []
    monkeypatch.setattr(
        module,
        "fetch_price_history",
        lambda tickers, lookback_days, cache_dir, max_cache_age_seconds=None: calls.append(1) or _fake_prices(tickers),
    )
    repo.get_price_history(["NVDA"], lookback_days=30)

    assert len(calls) == 1


def test_missing_company_row_gets_placeholder_for_fk(tmp_path, session_factory, monkeypatch):
    monkeypatch.setattr(module, "fetch_price_history", lambda *a, **k: _fake_prices(["ZZZZ"]))
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    repo.get_price_history(["ZZZZ"], lookback_days=30)

    with session_factory() as session:
        row = session.get(CompanyRow, "ZZZZ")
    assert row is not None
    assert row.name == "ZZZZ"
    assert row.sector == "Unknown"
    assert row.is_satellite_universe is False


def test_placeholder_never_overwrites_real_company_row(tmp_path, session_factory, monkeypatch):
    with session_factory() as session:
        session.add(
            CompanyRow(ticker="NVDA", name="NVIDIA Corporation", sector="Semiconductors", is_satellite_universe=False)
        )
        session.commit()

    monkeypatch.setattr(module, "fetch_price_history", lambda *a, **k: _fake_prices(["NVDA"]))
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)
    repo.get_price_history(["NVDA"], lookback_days=30)

    with session_factory() as session:
        row = session.get(CompanyRow, "NVDA")
    assert row.name == "NVIDIA Corporation"


def test_upsert_on_conflict_updates_rather_than_duplicates(tmp_path, session_factory, monkeypatch):
    monkeypatch.setattr(module, "fetch_price_history", lambda *a, **k: _fake_prices(["NVDA"], n=3))
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    repo.get_price_history(["NVDA"], lookback_days=30)
    repo.get_price_history(["NVDA"], lookback_days=30, force_refresh=True)

    with session_factory() as session:
        count = session.query(PriceRow).filter(PriceRow.ticker == "NVDA").count()
    assert count == 3  # not 6 — same (ticker, date) rows updated, not duplicated


def test_upsert_spanning_multiple_batches_writes_every_row(tmp_path, session_factory, monkeypatch):
    # Exercises the Postgres bound-parameter limit (65535/query): enough rows
    # across a few tickers to force `_upsert_prices` to split into more than
    # one `_UPSERT_BATCH_SIZE` batch, confirming every batch actually commits
    # rather than only the first.
    n = PostgresPriceRepository._UPSERT_BATCH_SIZE + 500
    tickers = ["A", "B", "C"]
    monkeypatch.setattr(module, "fetch_price_history", lambda *a, **k: _fake_prices(tickers, n=n))
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    repo.get_price_history(tickers, lookback_days=n * 2)

    with session_factory() as session:
        count = session.query(PriceRow).count()
    assert count == n * len(tickers)


def test_lookback_window_excludes_older_rows(tmp_path, session_factory, monkeypatch):
    old_dates = pd.date_range("2020-01-01", periods=3, freq="B")
    monkeypatch.setattr(
        module, "fetch_price_history", lambda *a, **k: pd.DataFrame({"NVDA": [1.0, 2.0, 3.0]}, index=old_dates)
    )
    repo = PostgresPriceRepository(session_factory, tmp_path, cache_ttl_seconds=3600)
    repo.get_price_history(["NVDA"], lookback_days=30)

    # Second call sees the same rows are within TTL (no refetch) but they're
    # outside the (much smaller) lookback window, so the returned frame is empty.
    result = repo.get_price_history(["NVDA"], lookback_days=5)

    assert result.empty or "NVDA" not in result.columns or result["NVDA"].dropna().empty
