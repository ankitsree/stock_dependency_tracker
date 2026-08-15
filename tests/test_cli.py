import numpy as np
import pandas as pd
import pytest

from src.cli import main
from src.config import Config
from src.data import fetcher
from src.repositories import yfinance_company_repository as company_repo_module


class _FakeFastInfo:
    def get(self, key):
        return {"marketCap": 1_000_000_000, "threeMonthAverageVolume": 500_000}.get(key)


class _FakeTicker:
    def __init__(self, ticker):
        self._ticker = ticker

    @property
    def fast_info(self):
        return _FakeFastInfo()


def _fake_download(tickers, **kwargs):
    """Every requested ticker moves almost identically (shared base series +
    tiny per-ticker noise), so every anchor/satellite pair correlates
    strongly regardless of exactly which tickers get requested. This test
    exercises CLI orchestration (right files written, right phase wired to
    the right service method) — statistical correctness of the correlation
    math itself is covered by tests/test_correlation.py and
    tests/services/test_correlation_service.py.
    """
    n = 60
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(7)
    base = rng.normal(0, 0.01, n)
    data = {}
    for ticker in tickers:
        if "NODATA" in ticker:
            continue  # simulate yfinance genuinely having nothing for this ticker
        noise = rng.normal(0, 0.0008, n)
        log_prices = np.log(100.0) + np.cumsum(base + noise)
        data[(ticker, "Close")] = np.exp(log_prices)
    return pd.DataFrame(data, index=dates)


def _small_universe():
    return pd.DataFrame(
        [("SAT1", "Satellite One", "Semiconductors"), ("SAT2", "Satellite Two", "Semiconductors")],
        columns=["ticker", "name", "sector"],
    )


def _small_config(tmp_path) -> Config:
    return Config(
        anchors=["ANCHOR1", "ANCHOR2"],
        lookback_days=60,
        top_n=5,
        correlation_threshold=0.1,
        rolling_window=10,
        data_dir=tmp_path / "data",
        outputs_dir=tmp_path / "outputs",
        market_proxy_ticker="MARKET",
        lag_max_days=2,
        regime_recent_days=5,
        regime_break_threshold=0.9,
        price_cache_ttl_seconds=3600,
        cors_allowed_origins=[],
    )


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(fetcher.yf, "download", _fake_download)
    monkeypatch.setattr(fetcher.yf, "Ticker", lambda ticker: _FakeTicker(ticker))
    monkeypatch.setattr(company_repo_module, "load_universe", _small_universe)
    monkeypatch.setattr("src.cli.load_config", lambda: _small_config(tmp_path))
    return tmp_path


def test_phase1_writes_report_and_graph(sandbox):
    main(["phase1", "ANCHOR1"])

    assert (sandbox / "outputs" / "reports" / "ANCHOR1_top5.csv").exists()
    assert (sandbox / "outputs" / "graphs" / "ANCHOR1_dependency_graph.png").exists()


def test_phase1_defaults_to_first_configured_anchor(sandbox):
    main(["phase1"])

    assert (sandbox / "outputs" / "reports" / "ANCHOR1_top5.csv").exists()


def test_phase2_writes_combined_graph_and_stability_report(sandbox):
    main(["phase2"])

    assert (sandbox / "outputs" / "graphs" / "multi_anchor_dependency_graph.png").exists()
    report = pd.read_csv(sandbox / "outputs" / "reports" / "ANCHOR1_top5_phase2.csv")
    assert "stability" in report.columns


def test_phase3_writes_interactive_html(sandbox):
    main(["phase3"])

    assert (sandbox / "outputs" / "graphs" / "multi_anchor_dependency_graph.html").exists()
    # Phase 2 and Phase 3 share the same report filename (same ranking logic).
    assert (sandbox / "outputs" / "reports" / "ANCHOR1_top5_phase2.csv").exists()


def test_phase4_writes_full_diagnostics_and_relatedness(sandbox):
    main(["phase4"])

    assert (sandbox / "outputs" / "graphs" / "multi_anchor_dependency_graph_phase4.html").exists()
    assert (sandbox / "outputs" / "reports" / "anchor_relatedness_phase4.csv").exists()
    report = pd.read_csv(sandbox / "outputs" / "reports" / "ANCHOR1_top5_phase4.csv")
    for column in ("pearson_correlation", "partial_correlation", "sector_relative_correlation"):
        assert column in report.columns


def test_unrecognized_phase_argument_exits(sandbox):
    with pytest.raises(SystemExit):
        main(["not-a-real-phase"])


def test_unknown_anchor_exits_cleanly_with_message(sandbox):
    with pytest.raises(SystemExit) as exc_info:
        main(["phase1", "NODATA_TICKER"])

    assert "NODATA_TICKER" in str(exc_info.value)


def test_compute_correlations_requires_database_url(sandbox):
    """The Postgres-only compute-correlations job (Track A Phase 1) refuses
    to run when DATABASE_URL is unset — writing to nothing would be silent
    data loss, not a no-op.
    """
    with pytest.raises(SystemExit) as exc_info:
        main(["compute-correlations"])

    assert "DATABASE_URL" in str(exc_info.value)
