# Phase 1 — Proof of Concept

**Goal (from the roadmap):** a single anchor (NVIDIA) → static correlation graph + CSV.

*Run via `python -m src.cli phase1 [ANCHOR]` — the standalone `run_phase1.py` script described below was superseded by a shared CLI in the Phase 4.5 refactor; see [phase4-5.md](phase4-5.md).*

## What it does, in plain terms

1. Take one anchor stock (NVDA) and a pool of ~55 small/mid-cap semiconductor and hardware "satellite" candidates.
2. Download a year of daily prices for all of them.
3. Convert prices to daily log-returns (the standard way to compare price series without raw dollar amounts getting in the way).
4. Compute how strongly each satellite's returns move together with NVDA's (Pearson correlation).
5. Keep the top 10 satellites whose correlation is at least 0.5, and draw them as a hub-and-spoke graph with NVDA in the middle.

## Code map

| File | What it's responsible for |
|---|---|
| [src/config.py](../src/config.py) | Loads `config.yaml` (anchors, lookback window, thresholds) into a validated object. |
| [src/data/universe.py](../src/data/universe.py) | The hand-picked list of ~55 satellite candidate tickers (semiconductor equipment, materials, contract manufacturing). A stand-in for a proper index-constituent screener, which is future work. |
| [src/data/fetcher.py](../src/data/fetcher.py) | `fetch_price_history()` — downloads adjusted-close prices via `yfinance`, drops tickers with too little history or failed downloads, and caches results to `data/cache/` so repeat runs don't re-hit Yahoo. |
| [src/data/storage.py](../src/data/storage.py) | Generic parquet save/load + cache-key hashing used by the fetcher. |
| [src/analysis/returns.py](../src/analysis/returns.py) | `compute_log_returns()` — turns a price table into a daily log-return table. |
| [src/analysis/correlation.py](../src/analysis/correlation.py) | `compute_correlations()` — Pearson correlation between the anchor and each satellite, aligning each pair on its own overlapping dates first. |
| [src/analysis/ranking.py](../src/analysis/ranking.py) | `rank_top_n()` — filters to satellites above the correlation threshold and keeps the strongest N. |
| [src/graph/builder.py](../src/graph/builder.py) | `build_dependency_graph()` — turns the ranked satellite table into a NetworkX star graph (one anchor node, N satellite nodes, weighted edges). |
| [src/visualisation/static_plot.py](../src/visualisation/static_plot.py) | `plot_graph()` — renders the graph to a PNG with matplotlib (edge thickness/colour = correlation strength/sign). |
| [src/cli.py](../src/cli.py) (`phase1` subcommand) | Orchestrates all of the above for one anchor and writes `outputs/reports/<anchor>_top10.csv` + `outputs/graphs/<anchor>_dependency_graph.png`. Originally a standalone `run_phase1.py` script — see [phase4-5.md](phase4-5.md). |

## Key decisions

- **Satellite universe is a static, curated list**, not a downloaded Russell 2000/S&P 600 screen — that's flagged as a Phase 2+/future simplification in the roadmap, and re-confirmed here rather than silently pretended away.
- **Correlation threshold is 0.5**, not the roadmap's suggested 0.6 — at 0.6, NVDA's strongest real candidate (0.589) didn't clear the bar, and the roadmap itself calls 0.5–0.6 an acceptable range.
- Every pairwise correlation is computed on that **pair's own overlapping dates** (not one global date index), because different tickers have different listing dates and holiday calendars.

## Result

Running `python run_phase1.py` against live data produced a top-10 list for NVDA dominated by semiconductor equipment names (Nova, MKS Instruments, Advanced Energy Industries, Onto Innovation, Rambus, ...) — a sanity-check pass, since these are plausible real supply-chain/ecosystem names for NVDA.
