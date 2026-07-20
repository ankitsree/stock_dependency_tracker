from src.repositories import yfinance_company_repository as module
from src.repositories.yfinance_company_repository import YFinanceCompanyRepository


def test_list_universe_delegates_to_load_universe(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "load_universe", lambda: "the-universe")

    repo = YFinanceCompanyRepository(tmp_path)

    assert repo.list_universe() == "the-universe"


def test_get_market_data_delegates_to_fetch_metadata(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(tickers, cache_dir, max_cache_age_seconds=None):
        calls.append((tickers, cache_dir, max_cache_age_seconds))
        return "the-metadata"

    monkeypatch.setattr(module, "fetch_metadata", fake_fetch)

    repo = YFinanceCompanyRepository(tmp_path, cache_ttl_seconds=3600)
    result = repo.get_market_data(["NVDA"])

    assert result == "the-metadata"
    assert calls == [(["NVDA"], tmp_path, 3600)]


def test_get_market_data_force_refresh_bypasses_ttl(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "fetch_metadata",
        lambda tickers, cache_dir, max_cache_age_seconds=None: calls.append(max_cache_age_seconds),
    )

    repo = YFinanceCompanyRepository(tmp_path, cache_ttl_seconds=3600)
    repo.get_market_data(["NVDA"], force_refresh=True)

    assert calls == [0]
