"""Command-line entry point: `python -m src.cli {phase1,phase2,phase3,phase4}`.

Replaces run_phase1.py..run_phase4.py. Same output paths and behavior as
before, but built on the same services the API uses instead of duplicating
fetch/rank/report orchestration across four near-identical scripts — the
duplication phase2/3/4 had (byte-identical fetch-and-validate blocks,
byte-identical shared-satellite/cross-link printing) collapses into the two
shared helpers below.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging

import pandas as pd
import sentry_sdk

from src.config import Config, load_config
from src.errors import DomainError
from src.graph.builder import build_dependency_graph, build_multi_anchor_graph
from src.graph.queries import anchor_relatedness_matrix, shared_satellites, strongest_cross_link
from src.repositories.yfinance_company_repository import YFinanceCompanyRepository
from src.repositories.yfinance_price_repository import YFinancePriceRepository
from src.services.correlation_service import CorrelationService
from src.visualisation.interactive import build_interactive_graph
from src.visualisation.static_plot import plot_graph

logger = logging.getLogger(__name__)

# Scheduled jobs — the exact strings the Render Cron blueprint dispatches to.
# Kept as constants so the CLI and render.yaml can't drift apart without at
# least one of them failing loudly.
DAILY_JOBS_COMMAND = "daily-jobs"
WEEKLY_JOBS_COMMAND = "weekly-jobs"


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(prog="python -m src.cli")
    subparsers = parser.add_subparsers(dest="phase", required=True)
    phase1_parser = subparsers.add_parser("phase1", help="single anchor -> static graph + CSV")
    phase1_parser.add_argument("anchor", nargs="?", default=None)
    subparsers.add_parser("phase2", help="multi-anchor + stability -> static graph")
    subparsers.add_parser("phase3", help="multi-anchor + stability -> interactive HTML graph")
    subparsers.add_parser("phase4", help="multi-anchor + full diagnostics -> interactive HTML graph")
    subparsers.add_parser(
        "backfill-postgres", help="one-off: seed Postgres companies+prices from the hardcoded universe + yfinance"
    )
    subparsers.add_parser(
        "compute-correlations",
        help="Manual, ad-hoc invocation of the correlations recompute (same body as `daily-jobs`; "
        "kept as a self-describing alias for one-off re-seeds).",
    )
    subparsers.add_parser(
        DAILY_JOBS_COMMAND,
        help="Track A Phase 2: scheduled entry point — refresh prices, recompute correlations, "
        "upsert into the `correlations` table. Dispatched by Render Cron (see render.yaml).",
    )
    subparsers.add_parser(
        WEEKLY_JOBS_COMMAND,
        help="Track A Phase 2: scheduled weekly entry point. No-op until Phase 7 wires the "
        "universe screener — the schedule and infra are declared now so nothing is left to "
        "'remember to set up later'.",
    )
    args = parser.parse_args(argv)

    # Sentry captures anything that escapes below — enabled for every command
    # but only actually initialised when SENTRY_DSN is set, mirroring
    # src/api/main.py. Free for interactive `phaseN` runs (no DSN in the
    # dev shell), essential for the scheduled jobs (a crash at 4 AM UTC in a
    # Render Cron log nobody watches is invisible without this).
    _init_sentry_for_cli(load_config(), command=args.phase)

    if args.phase == "backfill-postgres":
        _run_backfill_postgres(load_config())
        return
    if args.phase in {"compute-correlations", DAILY_JOBS_COMMAND}:
        _run_with_sentry_flush(lambda: _run_daily_correlation_refresh(load_config()))
        return
    if args.phase == WEEKLY_JOBS_COMMAND:
        _run_with_sentry_flush(lambda: _run_weekly_jobs(load_config()))
        return

    config = load_config()
    # No cache TTL for the CLI (matches the original scripts' behavior:
    # cache never expires within/across runs unless the file is deleted).
    # The API sets a real TTL via config.price_cache_ttl_seconds instead,
    # since it's a long-running process that must not serve arbitrarily
    # stale prices — see src/api/deps.py.
    price_repo = YFinancePriceRepository(config.data_dir / "cache", cache_ttl_seconds=None)
    company_repo = YFinanceCompanyRepository(config.data_dir / "cache", cache_ttl_seconds=None)
    correlation_service = CorrelationService(price_repo, company_repo, config)

    try:
        if args.phase == "phase1":
            _run_phase1(config, correlation_service, args.anchor or config.anchors[0])
        elif args.phase == "phase2":
            _run_phase2_or_3(config, correlation_service, company_repo, interactive=False)
        elif args.phase == "phase3":
            _run_phase2_or_3(config, correlation_service, company_repo, interactive=True)
        elif args.phase == "phase4":
            _run_phase4(config, correlation_service, company_repo)
    except DomainError as exc:
        raise SystemExit(str(exc)) from exc


def _run_phase1(config: Config, correlation_service: CorrelationService, anchor: str) -> None:
    print(f"Fetching {config.lookback_days}d of price history for {anchor} + satellite candidates...")
    ranked = correlation_service.rank_correlations(anchor, method="pearson")
    if ranked.empty:
        print(f"No satellites met the correlation threshold ({config.correlation_threshold}) for {anchor}.")
        return

    print(f"\nTop {len(ranked)} satellites for {anchor}:")
    print(ranked.to_string(index=False))

    report_path = config.outputs_dir / "reports" / f"{anchor}_top{config.top_n}.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(report_path, index=False)
    print(f"\nSaved report to {report_path}")

    graph = build_dependency_graph(anchor, ranked)
    graph_path = config.outputs_dir / "graphs" / f"{anchor}_dependency_graph.png"
    plot_graph(graph, graph_path, title=f"{anchor} — Correlated Satellites ({config.lookback_days}d)")
    print(f"Saved graph to {graph_path}")


def _run_phase2_or_3(
    config: Config,
    correlation_service: CorrelationService,
    company_repo: YFinanceCompanyRepository,
    interactive: bool,
) -> None:
    print(
        f"Fetching {config.lookback_days}d of price history for {len(config.anchors)} anchors + satellite candidates..."
    )

    anchor_rankings: dict[str, pd.DataFrame] = {}
    active_anchors: list[str] = []
    for anchor in config.anchors:
        try:
            ranked = correlation_service.rank_with_stability(anchor, exclude_tickers=set(config.anchors))
        except DomainError:
            print(f"  no data for anchor {anchor}; skipping")
            continue
        active_anchors.append(anchor)
        if ranked.empty:
            print(f"  {anchor}: no satellites met the correlation threshold ({config.correlation_threshold})")
            continue
        anchor_rankings[anchor] = ranked
        # Phase 2 and Phase 3 have always shared this filename (same ranking
        # logic; they only differ in which renderer runs on the result).
        report_path = config.outputs_dir / "reports" / f"{anchor}_top{config.top_n}_phase2.csv"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        ranked.to_csv(report_path, index=False)
        print(f"  {anchor}: saved {len(ranked)} satellites -> {report_path}")

    if not active_anchors:
        raise SystemExit("No anchors have usable price data; aborting.")
    if not anchor_rankings:
        print("No anchor produced any satellites above threshold; nothing to graph.")
        return

    print("Fetching market cap / volume metadata...")
    metadata = company_repo.get_market_data(_graphed_tickers(active_anchors, anchor_rankings))

    graph = build_multi_anchor_graph(anchor_rankings, metadata)
    title = f"Multi-Anchor Dependency Graph ({config.lookback_days}d)"
    if interactive:
        graph_path = config.outputs_dir / "graphs" / "multi_anchor_dependency_graph.html"
        build_interactive_graph(graph, graph_path, title=title)
    else:
        graph_path = config.outputs_dir / "graphs" / "multi_anchor_dependency_graph.png"
        plot_graph(graph, graph_path, title=title)
    print(f"\nSaved graph to {graph_path}")

    _print_cross_anchor_summary(graph)


def _run_phase4(
    config: Config, correlation_service: CorrelationService, company_repo: YFinanceCompanyRepository
) -> None:
    print(
        f"Fetching {config.lookback_days}d of price history for {len(config.anchors)} anchors "
        "+ satellite candidates + market/sector proxies..."
    )

    anchor_rankings: dict[str, pd.DataFrame] = {}
    active_anchors: list[str] = []
    leading_indicators: list[tuple] = []
    regime_alerts: list[tuple] = []

    for anchor in config.anchors:
        try:
            result = correlation_service.rank_with_full_diagnostics(anchor, exclude_tickers=set(config.anchors))
        except DomainError as exc:
            print(f"  {anchor}: {exc}; skipping")
            continue
        active_anchors.append(anchor)
        ranked = result.satellites
        if ranked.empty:
            print(f"  {anchor}: no satellites met the correlation threshold ({config.correlation_threshold})")
            continue

        for _, row in ranked.iterrows():
            if pd.notna(row.get("regime_break")) and row["regime_break"]:
                regime_alerts.append((anchor, row["ticker"], row["correlation"], row.get("regime_drift")))
            if (
                pd.notna(row.get("best_lag"))
                and abs(row.get("best_lag_correlation") or 0) >= config.correlation_threshold
            ):
                leading_indicators.append((anchor, row["ticker"], int(row["best_lag"]), row["best_lag_correlation"]))

        anchor_rankings[anchor] = ranked
        report_path = config.outputs_dir / "reports" / f"{anchor}_top{config.top_n}_phase4.csv"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        ranked.to_csv(report_path, index=False)
        print(f"  {anchor}: {len(ranked)} satellites -> {report_path}")

    if not active_anchors:
        raise SystemExit("No anchors have usable price data; aborting.")
    if not anchor_rankings:
        print("No anchor produced any satellites above threshold; nothing to graph.")
        return

    metadata = company_repo.get_market_data(_graphed_tickers(active_anchors, anchor_rankings))

    graph = build_multi_anchor_graph(anchor_rankings, metadata)
    graph_path = config.outputs_dir / "graphs" / "multi_anchor_dependency_graph_phase4.html"
    build_interactive_graph(
        graph, graph_path, title=f"Multi-Anchor Dependency Graph — Phase 4 ({config.lookback_days}d)"
    )
    print(f"\nSaved interactive graph to {graph_path}")

    _print_cross_anchor_summary(graph)

    relatedness = anchor_relatedness_matrix(graph)
    relatedness_path = config.outputs_dir / "reports" / "anchor_relatedness_phase4.csv"
    relatedness.to_csv(relatedness_path)
    print(f"\nAnchor relatedness matrix (correlation of correlations) -> {relatedness_path}")
    print(relatedness.round(2).to_string())

    if leading_indicators:
        leading_indicators.sort(key=lambda row: abs(row[3]), reverse=True)
        print("\nLeading indicators (anchor move today -> satellite move `lag` days later):")
        for anchor, ticker, lag, corr in leading_indicators:
            print(f"  {anchor} -> {ticker}: lag={lag}d, correlation={corr:.2f}")
        leading_path = config.outputs_dir / "reports" / "leading_indicators_phase4.csv"
        pd.DataFrame(leading_indicators, columns=["anchor", "ticker", "lag_days", "lag_correlation"]).to_csv(
            leading_path, index=False
        )
        print(f"  -> {leading_path}")

    if regime_alerts:
        print("\nRegime-break alerts (recent correlation has drifted from full-period value):")
        for anchor, ticker, full_corr, drift in regime_alerts:
            print(f"  {anchor} -> {ticker}: full-period={full_corr:.2f}, drift={drift:.2f}")
        alerts_path = config.outputs_dir / "reports" / "regime_alerts_phase4.csv"
        pd.DataFrame(regime_alerts, columns=["anchor", "ticker", "full_period_correlation", "drift"]).to_csv(
            alerts_path, index=False
        )
        print(f"  -> {alerts_path}")


def _run_backfill_postgres(config: Config) -> None:
    """One-off seed: moves the hardcoded `SATELLITE_UNIVERSE` list and its
    price/market-data history into Postgres. Run once after `alembic upgrade
    head` on a fresh database — see production-roadmap.md §6 step 3. Not
    idempotent-sensitive: every write here is an upsert, so re-running is
    safe (just re-fetches from yfinance).
    """
    if not config.database_url:
        raise SystemExit("DATABASE_URL is not set; nothing to backfill into (see .env.example).")

    from src.data.universe import load_universe
    from src.repositories.postgres.company_repository import PostgresCompanyRepository
    from src.repositories.postgres.db import make_engine, make_session_factory
    from src.repositories.postgres.price_repository import PostgresPriceRepository

    session_factory = make_session_factory(make_engine(config.database_url))
    company_repo = PostgresCompanyRepository(session_factory, config.data_dir / "cache", cache_ttl_seconds=None)
    price_repo = PostgresPriceRepository(session_factory, config.data_dir / "cache", cache_ttl_seconds=None)

    universe = load_universe()
    print(f"Seeding {len(universe)} satellite-universe companies (name/sector/is_satellite_universe=true)...")
    company_repo.upsert_universe(universe)

    all_tickers = sorted(set(config.anchors) | set(universe["ticker"]))
    print(
        f"Backfilling {config.lookback_days}d of price history for {len(all_tickers)} tickers (anchors + universe)..."
    )
    prices = price_repo.get_price_history(all_tickers, config.lookback_days, force_refresh=True)
    print(f"  -> {len(prices.columns)} tickers, {len(prices)} trading days written.")

    print("Backfilling market cap / volume metadata...")
    company_repo.get_market_data(all_tickers, force_refresh=True)

    print("Backfill complete.")


def _run_daily_correlation_refresh(config: Config) -> None:
    """Track A Phase 1 write path / Phase 2 daily job body: run the full
    diagnostic stack once per anchor and upsert the results into
    `correlations`. The graph endpoint reads this table instead of running
    the analytics stack per request.

    Dispatched by Render Cron under the `daily-jobs` command (see
    render.yaml) and callable directly as `compute-correlations` for
    manual/one-off re-seeds — same body, two names, one Sentry breadcrumb
    trail per run.

    Prefetches prices once for the union of every anchor's universe so we
    hit Yahoo once, not once per anchor — same optimisation the API's
    GraphService uses for `force_refresh=True` requests.
    """
    if not config.database_url:
        raise SystemExit(
            "DATABASE_URL is not set; nothing to write to (see .env.example). "
            "The daily correlation-refresh job is Postgres-only by design."
        )

    from src.repositories.postgres.company_repository import PostgresCompanyRepository
    from src.repositories.postgres.correlation_repository import PostgresCorrelationRepository
    from src.repositories.postgres.db import make_engine, make_session_factory
    from src.repositories.postgres.price_repository import PostgresPriceRepository

    session_factory = make_session_factory(make_engine(config.database_url))
    price_repo = PostgresPriceRepository(session_factory, config.data_dir / "cache", cache_ttl_seconds=None)
    company_repo = PostgresCompanyRepository(session_factory, config.data_dir / "cache", cache_ttl_seconds=None)
    correlation_repo = PostgresCorrelationRepository(session_factory)
    correlation_service = CorrelationService(price_repo, company_repo, config)

    computed_at = dt.datetime.now(dt.timezone.utc)
    print(
        f"Recomputing correlations for {len(config.anchors)} anchors "
        f"(lookback={config.lookback_days}d, computed_at={computed_at.isoformat()})..."
    )
    # `force_refresh=True` on the prefetch so cache TTL never hides yesterday's
    # prices from the nightly job; the analytics themselves don't need it.
    prefetched_prices = correlation_service.prefetch_prices(config.anchors, force_refresh=True)

    successes = 0
    for anchor in config.anchors:
        try:
            result = correlation_service.rank_with_full_diagnostics(
                anchor,
                exclude_tickers=set(config.anchors),
                force_refresh=True,
                prefetched_prices=prefetched_prices,
            )
        except DomainError as exc:
            print(f"  {anchor}: {exc}; skipping")
            continue
        if result.satellites.empty:
            print(f"  {anchor}: no satellites met threshold {config.correlation_threshold}; nothing written")
            continue
        correlation_repo.upsert_snapshot(
            anchor=anchor,
            satellites=result.satellites,
            lookback_days=config.lookback_days,
            computed_at=computed_at,
        )
        successes += 1
        print(f"  {anchor}: {len(result.satellites)} satellites persisted")

    print(f"\nWrote correlations for {successes}/{len(config.anchors)} anchors.")


def _run_weekly_jobs(config: Config) -> None:
    """Track A Phase 2 weekly entry point — declared and scheduled now, empty
    body today. Phase 7 (universe-roadmap.md) wires the screener-driven
    universe rebuild here: fetch the screener output, diff against the
    current `companies` table, upsert additions, mark removals inactive.
    The schedule + the Render Cron declaration land in this phase so the
    later change is drop-in.
    """
    logger.info("weekly-jobs: no work scheduled yet (Phase 7 will wire the universe rebuild).")
    _ = config  # silence unused-arg warning; the config plug is intentional for the eventual body.


def _init_sentry_for_cli(config: Config, command: str) -> None:
    """Presence-gated Sentry init for CLI runs. Mirrors src/api/main.py's
    behaviour and no-ops silently when SENTRY_DSN is unset, so interactive
    `phaseN` runs from a dev shell stay quiet. `command` becomes the
    transaction/tag so Render Cron runs show up in the Sentry UI grouped by
    which job crashed instead of one undifferentiated blob.
    """
    if not config.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        # Traces are cheap here (a handful of runs per day) and give
        # per-anchor timing without extra instrumentation.
        traces_sample_rate=1.0,
        enable_logs=True,
    )
    # `set_tag` lets a filter in the Sentry UI split job runs by name; the
    # transaction name is what shows up in the Performance view.
    sentry_sdk.set_tag("cli_command", command)


def _run_with_sentry_flush(func) -> None:
    """Sentry's transport is async and buffered — a CLI process that exits
    the microsecond after an event is captured can lose it. Explicit
    `flush()` at exit is the documented way to guarantee delivery for
    short-lived scripts (see Sentry Python SDK docs). No-op when Sentry
    isn't initialised, so this is safe to wrap around every scheduled command.
    """
    try:
        func()
    except BaseException:
        # Capture, then let it propagate — argparse's/Python's default handler
        # still prints a traceback and exits non-zero, which is what Render Cron
        # uses to mark the job as failed.
        sentry_sdk.capture_exception()
        raise
    finally:
        sentry_sdk.flush(timeout=5)


def _graphed_tickers(active_anchors: list[str], anchor_rankings: dict[str, pd.DataFrame]) -> list[str]:
    """Anchors plus only the satellites that actually made it into a
    ranking — narrower (and cheaper to fetch metadata for) than the full
    ~55-ticker universe, since only these ever end up as graph nodes.
    """
    satellite_tickers = {ticker for df in anchor_rankings.values() for ticker in df["ticker"]}
    return sorted(set(active_anchors) | satellite_tickers)


def _print_cross_anchor_summary(graph) -> None:
    shared = shared_satellites(graph)
    if not shared:
        print("\nNo satellites are shared across anchors in this run.")
        return

    print("\nSatellites shared across multiple anchors:")
    for ticker, anchors in shared.items():
        print(f"  {ticker}: {', '.join(anchors)}")

    cross_link = strongest_cross_link(graph)
    if cross_link:
        a, b, satellite, strength = cross_link
        print(f"\nStrongest cross-anchor link: {a} <-> {b} via {satellite} (strength={strength:.2f})")


if __name__ == "__main__":
    main()
