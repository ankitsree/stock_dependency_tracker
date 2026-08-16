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
        # Passed explicitly, not left to default: `Config` is a pydantic-settings
        # model, so an unset field falls through to the environment (or `.env`).
        # CI's test job and a local `make up` both export DATABASE_URL, which
        # would otherwise leak into this sandbox and point the CLI at a real
        # database instead of tmp_path.
        database_url=None,
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


@pytest.mark.parametrize("command", ["compute-correlations", "daily-jobs"])
def test_correlation_refresh_commands_require_database_url(sandbox, command):
    """The Postgres-only correlation-refresh job refuses to run when
    DATABASE_URL is unset — writing to nothing would be silent data loss,
    not a no-op. Both the scheduled name (`daily-jobs`) and the manual
    alias (`compute-correlations`) share this guard, so both are
    parametrised here.
    """
    with pytest.raises(SystemExit) as exc_info:
        main([command])

    assert "DATABASE_URL" in str(exc_info.value)


def test_weekly_jobs_runs_cleanly_without_database_url(sandbox, caplog):
    """Phase 2 scaffolding — the weekly job's body is a no-op until Phase 7
    wires the universe screener, but the command has to exit 0 today or
    every Monday Render Cron run marks itself failed.
    """
    with caplog.at_level("INFO"):
        main(["weekly-jobs"])

    assert any("weekly-jobs" in record.message for record in caplog.records)


def test_scheduled_jobs_flush_sentry_before_exit(sandbox, monkeypatch):
    """`sentry_sdk.flush()` is what actually guarantees delivery for a
    short-lived CLI process — the async transport can otherwise drop the
    exit-time event. If someone removes the flush wrapper, this test fails
    loudly instead of the failure only surfacing as "why did that 4 AM
    crash never show up in Sentry?"
    """
    flush_calls = []
    monkeypatch.setattr("src.cli.sentry_sdk.flush", lambda timeout=5: flush_calls.append(timeout))

    main(["weekly-jobs"])

    assert flush_calls, "sentry_sdk.flush() must run for every scheduled command"


def test_sentry_not_initialised_without_dsn(sandbox, monkeypatch):
    """Presence-gated init mirrors src/api/main.py — an interactive
    `phaseN` dev run must never boot the Sentry SDK just because the CLI
    imported the module.
    """
    init_calls = []
    monkeypatch.setattr("src.cli.sentry_sdk.init", lambda **kw: init_calls.append(kw))

    main(["weekly-jobs"])  # config from sandbox has no sentry_dsn.

    assert init_calls == []


def test_sentry_initialised_and_tagged_when_dsn_configured(sandbox, monkeypatch):
    """When SENTRY_DSN is set, the CLI wires the SDK before running the
    command so any escape gets captured. Command name lands in a
    `cli_command` tag so job runs are filterable in the Sentry UI instead
    of piling up under one undifferentiated transaction.
    """
    from src.cli import load_config as cli_load_config
    from src.config import Config

    dsn = "https://public@o0.ingest.us.sentry.io/0"
    base_config_dict = cli_load_config().model_dump()
    base_config_dict["sentry_dsn"] = dsn
    monkeypatch.setattr("src.cli.load_config", lambda: Config(**base_config_dict))

    init_calls = []
    tag_calls = []
    monkeypatch.setattr("src.cli.sentry_sdk.init", lambda **kw: init_calls.append(kw))
    monkeypatch.setattr("src.cli.sentry_sdk.set_tag", lambda *args: tag_calls.append(args))

    main(["weekly-jobs"])

    assert len(init_calls) == 1
    assert init_calls[0]["dsn"] == dsn
    assert init_calls[0]["enable_logs"] is True
    assert ("cli_command", "weekly-jobs") in tag_calls
