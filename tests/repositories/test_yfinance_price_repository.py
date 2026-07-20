from src.repositories import yfinance_price_repository as module
from src.repositories.yfinance_price_repository import YFinancePriceRepository


def test_delegates_to_fetch_price_history(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(tickers, lookback_days, cache_dir, max_cache_age_seconds=None):
        calls.append((tickers, lookback_days, cache_dir, max_cache_age_seconds))
        return "the-dataframe"

    monkeypatch.setattr(module, "fetch_price_history", fake_fetch)

    repo = YFinancePriceRepository(tmp_path, cache_ttl_seconds=3600)
    result = repo.get_price_history(["NVDA"], 365)

    assert result == "the-dataframe"
    assert calls == [(["NVDA"], 365, tmp_path, 3600)]


def test_force_refresh_bypasses_ttl(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "fetch_price_history",
        lambda tickers, lookback_days, cache_dir, max_cache_age_seconds=None: calls.append(max_cache_age_seconds),
    )

    repo = YFinancePriceRepository(tmp_path, cache_ttl_seconds=3600)
    repo.get_price_history(["NVDA"], 365, force_refresh=True)

    assert calls == [0]


def test_default_ttl_used_when_not_forcing_refresh(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "fetch_price_history",
        lambda tickers, lookback_days, cache_dir, max_cache_age_seconds=None: calls.append(max_cache_age_seconds),
    )

    repo = YFinancePriceRepository(tmp_path, cache_ttl_seconds=3600)
    repo.get_price_history(["NVDA"], 365, force_refresh=False)

    assert calls == [3600]
