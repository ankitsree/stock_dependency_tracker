import datetime as dt

import pandas as pd

from src.repositories.postgres import company_repository as module
from src.repositories.postgres.company_repository import PostgresCompanyRepository
from src.repositories.postgres.models import CompanyRow


def _universe():
    return pd.DataFrame(
        [("SAT1", "Satellite One", "Semiconductors"), ("SAT2", "Satellite Two", "Networking Hardware")],
        columns=["ticker", "name", "sector"],
    )


def test_list_universe_empty_before_backfill(tmp_path, session_factory):
    repo = PostgresCompanyRepository(session_factory, tmp_path)
    assert repo.list_universe().empty


def test_upsert_universe_then_list_universe_returns_seeded_rows(tmp_path, session_factory):
    repo = PostgresCompanyRepository(session_factory, tmp_path)
    repo.upsert_universe(_universe())

    universe = repo.list_universe()

    assert set(universe["ticker"]) == {"SAT1", "SAT2"}
    assert universe.set_index("ticker").loc["SAT1", "name"] == "Satellite One"


def test_upsert_universe_does_not_list_non_universe_companies(tmp_path, session_factory):
    with session_factory() as session:
        session.add(CompanyRow(ticker="NVDA", name="NVIDIA", sector="Semiconductors", is_satellite_universe=False))
        session.commit()

    repo = PostgresCompanyRepository(session_factory, tmp_path)
    assert repo.list_universe().empty  # NVDA isn't flagged is_satellite_universe


def test_get_market_data_cache_miss_fetches_and_persists(tmp_path, session_factory, monkeypatch):
    calls = []

    def fake_fetch_metadata(tickers, cache_dir, max_cache_age_seconds=None):
        calls.append(tuple(sorted(tickers)))
        return pd.DataFrame([{"ticker": t, "market_cap": 1e9, "avg_volume": 1e6} for t in tickers])

    monkeypatch.setattr(module, "fetch_metadata", fake_fetch_metadata)
    repo = PostgresCompanyRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    result = repo.get_market_data(["NVDA"])

    assert calls == [("NVDA",)]
    assert result.iloc[0]["market_cap"] == 1e9


def test_get_market_data_second_call_is_cache_hit(tmp_path, session_factory, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "fetch_metadata",
        lambda tickers, cache_dir, max_cache_age_seconds=None: (
            calls.append(1) or pd.DataFrame([{"ticker": t, "market_cap": 1.0, "avg_volume": 1.0} for t in tickers])
        ),
    )
    repo = PostgresCompanyRepository(session_factory, tmp_path, cache_ttl_seconds=3600)

    repo.get_market_data(["NVDA"])
    repo.get_market_data(["NVDA"])

    assert len(calls) == 1


def test_get_market_data_placeholder_does_not_overwrite_universe_name(tmp_path, session_factory, monkeypatch):
    repo = PostgresCompanyRepository(session_factory, tmp_path, cache_ttl_seconds=3600)
    repo.upsert_universe(_universe())

    monkeypatch.setattr(
        module,
        "fetch_metadata",
        lambda tickers, cache_dir, max_cache_age_seconds=None: pd.DataFrame(
            [{"ticker": t, "market_cap": 5.0, "avg_volume": 5.0} for t in tickers]
        ),
    )
    repo.get_market_data(["SAT1"], force_refresh=True)

    with session_factory() as session:
        row = session.get(CompanyRow, "SAT1")
    assert row.name == "Satellite One"  # not overwritten with the ticker placeholder
    assert row.market_cap == 5.0


def test_get_company_facts_delegates_straight_to_yfinance(tmp_path, session_factory, monkeypatch):
    calls = []

    def fake_fetch_facts(ticker, cache_dir, max_cache_age_seconds=None):
        calls.append(ticker)
        return pd.DataFrame([{"ticker": ticker, "trailing_pe": 42.0}])

    monkeypatch.setattr(module, "fetch_company_facts", fake_fetch_facts)
    repo = PostgresCompanyRepository(session_factory, tmp_path)

    facts = repo.get_company_facts("NVDA")

    assert calls == ["NVDA"]
    assert facts["trailing_pe"] == 42.0


def test_stale_row_beyond_ttl_triggers_refetch(tmp_path, session_factory, monkeypatch):
    monkeypatch.setattr(
        module,
        "fetch_metadata",
        lambda tickers, cache_dir, max_cache_age_seconds=None: pd.DataFrame(
            [{"ticker": t, "market_cap": 1.0, "avg_volume": 1.0} for t in tickers]
        ),
    )
    repo = PostgresCompanyRepository(session_factory, tmp_path, cache_ttl_seconds=3600)
    repo.get_market_data(["NVDA"])

    with session_factory() as session:
        session.query(CompanyRow).update(
            {CompanyRow.updated_at: dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)}
        )
        session.commit()

    calls = []
    monkeypatch.setattr(
        module,
        "fetch_metadata",
        lambda tickers, cache_dir, max_cache_age_seconds=None: (
            calls.append(1) or pd.DataFrame([{"ticker": t, "market_cap": 2.0, "avg_volume": 2.0} for t in tickers])
        ),
    )
    repo.get_market_data(["NVDA"])

    assert len(calls) == 1
