# Phase 4 — Advanced Analytics

**Goal (from the roadmap):** make the correlations smarter and more useful.

*Run via `python -m src.cli phase4` — the standalone `run_phase4.py` script described below was superseded by a shared CLI in the Phase 4.5 refactor; see [phase4-5.md](phase4-5.md).*

## What it does, in plain terms

Same fetch → correlate → rank → stability → combined graph pipeline as Phase 2/3, but the correlation engine now runs six additional checks per satellite instead of reporting a single Pearson `r`:

1. **Spearman rank correlation drives ranking**, not Pearson. Spearman correlates the *rank order* of daily returns rather than their raw values, so a single outlier day (a small-cap satellite gapping 30%+ on an M&A rumour or halt) can't dominate a whole year's score the way it can with Pearson. Pearson is still computed and attached to every edge as a secondary, more familiar figure.
2. **Partial (market-adjusted) correlation** strips out the part of the anchor-satellite relationship that's just "both of these stocks follow the S&P 500." What's left is co-movement specific to the anchor, not general market beta.
3. **Time-lagged cross-correlation** checks whether a satellite tends to move 1-3 days *after* the anchor rather than the same day — a candidate "leading indicator" signal, since a same-day correlation isn't actionable but a lagged one potentially is.
4. **Sector-relative correlation** strips out the part of the relationship that's just "both of these stocks follow the same sector ETF" (analogous to #2, but at sector rather than whole-market granularity).
5. **Regime-break detection** compares each satellite's most recent 30-day rolling correlation against its full-period value and flags a break when they've diverged sharply — i.e. a relationship the full-period number says is strong but that has since fallen apart.
6. **Anchor relatedness ("correlation of correlations")** — a new anchor × anchor matrix scoring how strongly two anchors' ecosystems overlap, inferred purely from the satellites they share (extends Phase 2/3's `shared_satellites`/`strongest_cross_link` from "the single strongest link" to a full weighted matrix).

Every one of these (except #6, which lives at the graph level) is computed **only for the satellites that already cleared the primary Spearman threshold** — the diagnostics are meant to add texture to an already-selected shortlist, not to re-run the full universe six more times.

## Code map (new/changed since Phase 3)

| File | What's new |
|---|---|
| [src/analysis/correlation.py](../src/analysis/correlation.py) | `compute_correlations()` takes a `method` param (`"pearson"` / `"spearman"`) instead of being Pearson-only. Added `compute_partial_correlations()`, `compute_lagged_correlations()`, `compute_sector_relative_correlations()`, `detect_regime_breaks()`, and the `SECTOR_ETF_MAP` / `sector_etf_for()` mapping (reuses `visualisation.style.sector_group()`'s 7-group taxonomy — chip-related groups → `SOXX`, everything else → `XLK` — so the correlation engine and the graph's color legend agree on what counts as "the same sector"). |
| [src/analysis/ranking.py](../src/analysis/ranking.py) | Added `attach_metric()`, a generic left-join-by-ticker helper. `attach_stability()` is now a one-line wrapper around it — Phase 4 needed to attach five more per-ticker metrics (Pearson, partial, sector-relative, lag, regime) and didn't want five near-duplicate join functions. |
| [src/graph/builder.py](../src/graph/builder.py) | `build_dependency_graph()`'s hardcoded `stability`-only edge attribute changed to a generic `OPTIONAL_EDGE_COLUMNS` table (column name → cast function) that carries whichever of the new metrics are present on `ranked_satellites` onto the edge. Phase 1-3 callers, whose ranked tables don't have these columns, are unaffected. |
| [src/graph/queries.py](../src/graph/queries.py) | Added `anchor_relatedness_matrix()` — the "correlation of correlations" view. |
| [src/visualisation/interactive.py](../src/visualisation/interactive.py) | Edge tooltips and the summary table now show Pearson, partial, sector-relative, lag, and a ⚠ regime-break marker whenever an edge carries that data (Phase 1-3 graphs, which don't, render exactly as before — the extra table columns only appear when at least one edge has Phase 4 data). |
| [config.yaml](../config.yaml) / [src/config.py](../src/config.py) | Added `market_proxy_ticker` (`^GSPC`, for partial correlation), `lag_max_days` (3), `regime_recent_days` (30), and `regime_break_threshold` (0.35). |
| [src/cli.py](../src/cli.py) (`phase4` subcommand) | Orchestrates all of the above: fetches the anchor/satellite universe plus the market proxy and sector ETFs in one batch, ranks by Spearman, attaches every secondary metric to the top-N satellites only, builds the combined graph, and additionally prints/saves the anchor relatedness matrix, a cross-anchor "leading indicators" list, and a "regime alerts" list. Originally a standalone `run_phase4.py` script; the ranking/diagnostics logic now lives in `CorrelationService.rank_with_full_diagnostics` so the API exposes the identical computation — see [phase4-5.md](phase4-5.md). |

## Key decisions

- **Spearman is the primary filter; Pearson is kept, not replaced.** The satellite universe is small/mid-cap and prone to sporadic gap moves that a linear correlation over-weights. Switching the *ranking* metric to Spearman while still reporting Pearson keeps the existing `correlation_threshold` (0.5) convention meaningful for comparison without silently changing what a "0.6 correlation" means in old reports.
- **Diagnostics run on the shortlist, not the full universe.** Partial/lagged/sector-relative correlation and regime detection are only computed for satellites that already passed the Spearman/threshold filter (typically ≤10 per anchor), not all ~55 candidates. This keeps the extra computation cheap and keeps the output focused on satellites that already matter.
- **Sector ETF mapping reuses the existing 7-group taxonomy**, not a new one. Rather than hand-map ~15 fine-grained sector labels to bespoke ETFs, `sector_etf_for()` reuses `visualisation.style.sector_group()` (already validated for the graph's color-coding) and maps its 7 groups to just two liquid ETFs: `SOXX` for the three chip-related groups, `XLK` (broad tech) for everything else. This is a deliberate simplification, not a precise sector taxonomy — see the correlation-mechanism doc for the caveat.
- **Regime detection compares recent-vs-full-period, not a formal statistical test.** `abs(full_period_correlation - mean(recent_30d_rolling_correlation)) >= 0.35` is a heuristic threshold, consistent with Phase 2's stability score (`1 - std`) also being a heuristic rather than a hypothesis test — good enough to flag "this one's shifted" at a glance, not a rigorous regime-change model.
- **Anchor relatedness is inferred, not measured directly.** No anchor-anchor price correlation is computed; `anchor_relatedness_matrix()` only aggregates how strongly two anchors are each individually tied to their shared satellites (mean of `min(|weight_a|, |weight_b|)` per shared satellite, same "chain is as strong as its weakest link" logic as `strongest_cross_link`). This stays honest about what the data actually supports — see the correlation-mechanism doc's note on correlation vs. causation.

## Result

Running `python run_phase4.py` against live data:

- NVDA (6), TSM (10), and ASML (10) all produced satellites above the Spearman threshold; AAPL again produced none — consistent with Phase 2/3's finding that this semiconductor-equipment-themed universe just doesn't overlap with Apple's ecosystem.
- Every top satellite's **partial correlation dropped substantially from its raw correlation** (e.g. TSM/ONTO: 0.63 raw → 0.35 partial), confirming a meaningful share of the raw NVDA/TSM/ASML ↔ satellite correlation in this universe is shared-market-driven rather than anchor-specific — exactly the market-beta contamination the roadmap flags as a risk.
- **Sector-relative correlations came out small** (mostly |r| < 0.1) for the top satellites, which makes sense: this universe is almost entirely semiconductor-equipment names, so most of what partial correlation attributes to "the market" and sector-relative correlation attributes to "the sector" overlap heavily here.
- **No satellite triggered a regime-break alert** and no lagged correlation cleared the 0.5 threshold in this run — a useful negative result, not a bug: it means the top-ranked relationships are currently both same-day (not offering a lag-based edge) and stable (no evidence of recent breakdown).
- **Anchor relatedness matrix**: TSM ↔ ASML scored highest (0.61), NVDA ↔ TSM and NVDA ↔ ASML both scored 0.52 — consistent with Phase 2/3's finding that TSM and ASML (foundry + lithography equipment) share the densest satellite cluster, with NVDA connected to both somewhat less densely.
