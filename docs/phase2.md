# Phase 2 — Multi-Anchor & Stability

**Goal (from the roadmap):** expand to all anchor stocks and add correlation stability analysis.

*Run via `python -m src.cli phase2` — the standalone `run_phase2.py` script described below was superseded by a shared CLI in the Phase 4.5 refactor; see [phase4-5.md](phase4-5.md).*

## What it does, in plain terms

Phase 1 only ever looked at one anchor. Phase 2 asks the same questions across **several anchors at once** (NVDA, AAPL, TSM, ASML), and adds a second layer of analysis on top of the raw correlation: *is this correlation actually reliable, or did it just get lucky over the full year?*

1. Fetch price history for all anchors + the satellite pool in a single batch (instead of one fetch per anchor — same data, one API round-trip, same cache).
2. For each anchor independently, compute correlations and rank the top satellites exactly as in Phase 1.
3. Additionally compute a **60-day rolling correlation** for each anchor/satellite pair — the same correlation, but recalculated on a sliding 60-day window instead of the whole year at once.
4. Turn the *spread* of those rolling values into a **stability score** between 0 and 1: a satellite whose rolling correlation barely moves scores close to 1 (reliable); one that swings from strongly positive to strongly negative across the year scores low (a fluke).
5. Fetch **market cap and average volume** for every ticker and attach it to the graph nodes, so the graph isn't just tickers and lines — it carries the metadata needed to actually evaluate a satellite.
6. Build one **combined graph** with all anchors as hubs. Satellites correlated with more than one anchor appear once but connect to every anchor they're tied to — this is what surfaces cross-anchor supply-chain overlap (e.g. a chip-equipment maker showing up under both NVDA and TSM).
7. Report which satellites are shared across anchors, and which pair of anchors has the strongest indirect link through a shared satellite.

## Code map (new/changed since Phase 1)

| File | What's new |
|---|---|
| [config.yaml](../config.yaml) / [src/config.py](../src/config.py) | `anchors` is now a list of 4 tickers instead of 1; added `rolling_window: 60`. `run_phase1.py` is untouched — it just reads `anchors[0]`. |
| [src/analysis/correlation.py](../src/analysis/correlation.py) | Added `compute_rolling_correlations()` (per-satellite rolling-window correlation series) and `compute_stability_scores()` (collapses each series into one 0–1 score via `1 - std`). |
| [src/analysis/ranking.py](../src/analysis/ranking.py) | Added `attach_stability()` — left-joins a stability score onto an already-ranked satellite table. Kept separate from `rank_top_n()` so Phase 1's ranking logic and tests didn't need to change. |
| [src/data/fetcher.py](../src/data/fetcher.py) | Added `fetch_metadata()` — pulls market cap + 3-month average volume per ticker via `yfinance`'s `fast_info`, cached the same way as price history. Skips tickers that error out instead of failing the whole batch. |
| [src/graph/builder.py](../src/graph/builder.py) | `build_dependency_graph()` now optionally attaches `market_cap`/`avg_volume` to nodes and `stability` to edges (both optional, so Phase 1's calls still work unchanged). Added `build_multi_anchor_graph()`, which composes multiple per-anchor star graphs into one graph, automatically merging shared satellite nodes. |
| [src/graph/queries.py](../src/graph/queries.py) *(new)* | Three read-only graph queries called out in the roadmap: `top_satellites_for_anchor()`, `shared_satellites()`, and `strongest_cross_link()` (the pair of anchors most strongly linked through a common satellite — strength = the *weaker* of the two edges, since a chain is only as strong as its weakest link). |
| [src/visualisation/static_plot.py](../src/visualisation/static_plot.py) | Layout and figure size now scale with node count so a 4-anchor, ~30-satellite graph doesn't collapse into an unreadable blob. |
| [src/cli.py](../src/cli.py) (`phase2` subcommand) | Orchestrates the above: one shared price/metadata fetch, per-anchor ranking + stability, one combined graph, plus a printed summary of shared satellites and the strongest cross-anchor link. Originally a standalone `run_phase2.py` script — see [phase4-5.md](phase4-5.md). |

## Key decisions

- **Stability score = `max(0, 1 - std(rolling_correlation))`.** Simple and transparent: since correlation is bounded in [-1, 1], a rolling series that barely moves has a small standard deviation and scores near 1; one that swings across the full range scores near 0. It's a heuristic, not a statistical test — good enough to flag "this one's noisier" at a glance.
- **Anchors are never candidate satellites for each other.** The graph only ever draws anchor→satellite edges, not anchor→anchor; cross-anchor relationships only show up indirectly, through a shared satellite.
- **Anchor list (NVDA, AAPL, TSM, ASML)** was chosen to match tickers the roadmap names *and* that plausibly connect to the existing semiconductor/hardware satellite pool. Netflix and SpaceX (also named in the roadmap) were left out — Netflix isn't in the same supply-chain theme as the current universe, and SpaceX has no public stock (a risk the roadmap itself flags).
- **Metadata fetch is a separate, cached step** from price history, since `yfinance`'s `fast_info` needs one request per ticker (no batch call) — keeping it separate means a change in lookback window doesn't force a metadata re-fetch, and vice versa.

## Result

Running `python run_phase2.py` against live data:

- NVDA, TSM, and ASML share a dense cluster of satellites (MKS Instruments, Nova, Advanced Energy Industries, Onto Innovation, Lattice, ...) with stability scores mostly in the 0.8–0.9 range — consistent with the real-world story that TSM (foundry) and ASML (lithography equipment) sit in NVDA's actual supply chain.
- AAPL came back nearly isolated (one weak link, QRVO) — expected, since the satellite pool is semiconductor-equipment-themed and Apple's ecosystem doesn't overlap much with it. This is a useful negative result: the pipeline doesn't force a fit where there isn't one.
- Strongest cross-anchor link found: **TSM ↔ ASML via MKSI**, strength 0.71 — i.e., MKS Instruments (semiconductor equipment) ties TSM and ASML together at least as strongly as their weaker individual correlation to it.
