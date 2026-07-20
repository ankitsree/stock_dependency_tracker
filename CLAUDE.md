# Stock Correlation Dependency Graph

## What this is

A Python tool that takes large-cap "anchor" stocks (NVIDIA, Apple, TSMC, etc.) and discovers smaller "satellite" stocks whose prices are statistically correlated with each anchor, producing a weighted, explorable dependency graph.

Full design and rationale live in [stock_correlation_graph_roadmap.md](stock_correlation_graph_roadmap.md) — read it before making architectural decisions. This file is the quick-reference summary for day-to-day work. For what's actually been built so far, see [docs/](docs/README.md).

**Status:** Phases 1-4 implemented and tested. Phase 4.5 (not in the original roadmap, done ahead of Phase 5) refactored the four `run_phaseN.py` scripts into a layered backend — `src/repositories/` (Postgres-ready interfaces) → `src/services/` → a FastAPI REST API (`src/api/`) — plus a single `python -m src.cli {phase1,phase2,phase3,phase4}` entry point replacing the old scripts. See [docs/phase4-5.md](docs/phase4-5.md). Phase 4's analytics are unchanged — see [docs/phase4.md](docs/phase4.md) and [docs/correlation-mechanism.md](docs/correlation-mechanism.md). Phase 5 (frontend) not started.

## Key concepts

- **Anchor stock** — large, well-known company acting as a hub node (e.g. NVDA).
- **Satellite stock** — smaller company (market-cap filtered) whose returns correlate with an anchor.
- **Correlation weight** — Pearson r between anchor and satellite daily log-returns, in [-1, 1]. Focus on ≥ 0.6 positive (and flag strong inverse).
- **Stability score** — how consistent the correlation is across rolling windows (e.g. 60-day), not just the full-period value.
- **Dependency graph** — NetworkX graph; anchors and satellites as nodes, correlation-weighted edges. A satellite can attach to multiple anchors.

## Architecture (5 layers, run in sequence)

1. **Data ingestion** — fetch/store daily adjusted-close prices (`yfinance`).
2. **Universe filtering** — define the satellite candidate pool (market cap, volume, exchange).
3. **Correlation engine** — log-returns → Pearson correlation → rank top-N per anchor.
4. **Graph construction** — build the weighted NetworkX graph with node/edge metadata.
5. **Visualisation & output** — static (matplotlib) → interactive (Pyvis) → dashboard (Streamlit).

## Project structure

```
src/
  config.py                 # load/validate config.yaml (pydantic)
  errors.py                  # typed domain exceptions (TickerNotFoundError, ...)
  cli.py                      # python -m src.cli {phase1,phase2,phase3,phase4}
  data/
    fetcher.py                # yfinance downloads (TTL-aware cache, threaded metadata fetch)
    universe.py                 # satellite universe filtering
    storage.py                    # parquet persistence
  repositories/                   # Postgres-ready data-access seam (Protocol interfaces)
    base.py                        # PriceRepository, CompanyRepository
    yfinance_price_repository.py, yfinance_company_repository.py
  analysis/
    returns.py               # log-returns
    correlation.py            # pearson/spearman, rolling, partial, lagged, sector-relative, regime
    ranking.py                 # top-N filtering, generic attach_metric()
  graph/
    builder.py                # NetworkX graph construction
    queries.py                  # traversal/query helpers, JSON serialization
  domain/
    models.py                # framework-agnostic pydantic models shared by services + API
    serialization.py          # DataFrame -> pydantic models (NaN/inf -> None)
  services/                   # business logic: PriceService, CompanyService,
                                # CorrelationService, GraphService
  api/                         # FastAPI REST API
    main.py, deps.py, errors.py
    routers/                    # prices, companies, correlations, graph, health
    schemas/                     # response envelopes
  visualisation/
    static_plot.py             # matplotlib
    interactive.py              # pyvis HTML
    dashboard.py                # streamlit (Phase 5 — not started)
data/{raw,processed,cache}/
outputs/{graphs,reports}/
tests/
config.yaml                  # anchor tickers, thresholds, time windows, API/cache settings
pyproject.toml                # installable package (needed for `uvicorn src.api.main:app`)
```

## Tech stack

| Layer | Library |
|---|---|
| Price data | `yfinance` |
| Wrangling | `pandas`, `numpy` |
| Storage | Parquet → SQLite as it grows |
| Correlation | `scipy.stats`, `pandas.DataFrame.corr()` |
| Graph | `networkx` |
| Visualisation | `pyvis` (interactive), `matplotlib` (static) |
| API | `fastapi`, `uvicorn` (Phase 4.5) |
| Dashboard/Frontend | `streamlit`, or a custom frontend against the REST API (Phase 5) |
| Config | `pydantic` + YAML |

## Build order

Follow the phases in the roadmap — don't jump ahead. Each phase has a concrete deliverable:

1. **PoC** — single anchor (NVDA), static graph + CSV of top-10 satellites.
2. **Multi-anchor & stability** — parameterised anchor list, rolling-correlation stability scores.
3. **Interactive viz** — Pyvis HTML output with hover tooltips.
4. **Advanced analytics** — market-adjusted (partial) correlation, lagged cross-correlation, regime detection.
5. **Dashboard** — Streamlit UI, scheduled refresh, watchlists.

Don't build Phase N+1 features while Phase N is incomplete.

## Conventions & things to get right

- Use **log-returns**, not simple percentage returns, for all correlation math.
- Always **inner-join on dates** before correlating two series — exchanges have different holiday calendars (esp. international tickers).
- Use **ADR tickers** (ASML, TSM) for non-US anchors rather than home-exchange listings, for simpler alignment.
- A raw correlation threshold alone isn't enough — pair it with the **rolling-window stability score** before treating a satellite as reliable.
- Correlation ≠ causation: don't claim a "dependency" without noting it's price-correlation-based, not verified supply-chain data (see Future Enhancements in the roadmap for the real thing).
- SpaceX has no public stock — drop it from anchors or substitute a proxy (RKLB, ARKX).
- Cache aggressively and throttle requests — `yfinance` hits Yahoo's unofficial API and can get an IP rate-limited.

## Risks to watch for (see roadmap for detail)

Spurious correlations from large-N testing, market-beta contamination (most stocks move together in a bull market — Phase 4's partial correlation addresses this), survivorship bias in the universe list, and Yahoo Finance data quality gaps.

## System prompt to use when designing UI
DISTILLED_AESTHETICS_PROMPT = """
<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight. Focus on:
 
Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.
 
Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration.
 
Motion: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.
 
Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.
 
Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character
 
Interpret creatively and make unexpected choices that feel genuinely designed for the context. Vary between light and dark themes, different fonts, different aesthetics. You still tend to converge on common choices (Space Grotesk, for example) across generations. Avoid this: it is critical that you think outside the box!
</frontend_aesthetics>
"""
