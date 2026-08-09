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
import logging

import pandas as pd

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


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(prog="python -m src.cli")
    subparsers = parser.add_subparsers(dest="phase", required=True)
    phase1_parser = subparsers.add_parser("phase1", help="single anchor -> static graph + CSV")
    phase1_parser.add_argument("anchor", nargs="?", default=None)
    subparsers.add_parser("phase2", help="multi-anchor + stability -> static graph")
    subparsers.add_parser("phase3", help="multi-anchor + stability -> interactive HTML graph")
    subparsers.add_parser("phase4", help="multi-anchor + full diagnostics -> interactive HTML graph")
    args = parser.parse_args(argv)

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
