# Phase 4.5 — Modular REST API Refactor

**Goal (not in the original roadmap — added ahead of the roadmap's Phase 5):** turn the batch pipeline into a real backend before building a frontend against it, and clean up the duplication four phases of copy-pasted orchestration scripts had accumulated.

## Why this phase exists

Phases 1-4 were four scripts (`run_phase1.py`..`run_phase4.py`) that each inlined the same fetch → correlate → rank → graph → render pipeline — `run_phase2.py` and `run_phase3.py` were byte-identical except the renderer call, and `run_phase4.py` was the same skeleton with more metrics spliced in. There was no HTTP interface (a frontend would have had to shell out to a script and read a CSV), no packaging, no `logging` (51 `print()` calls, zero `logging` usage), silent failure handling, and a price cache with no expiry (the same ticker list + window silently served arbitrarily stale data forever).

This phase addresses all of that at once: a layered, modular backend (repositories → services → API routes) with a real REST API, built so a future Postgres-backed data layer is a non-invasive swap, not a rewrite.

## What it does, in plain terms

1. **Repositories** (`src/repositories/`) are the only code that talks to yfinance/parquet, hidden behind two `Protocol` interfaces (`PriceRepository`, `CompanyRepository`). Every service depends on the interface, never the concrete class — only `src/api/deps.py` ever imports `YFinancePriceRepository`/`YFinanceCompanyRepository`. A future `PostgresPriceRepository` implementing the same two methods is a change to `deps.py`'s two factory functions, nothing else.
2. **Services** (`src/services/`) hold the business logic, orchestrating repositories + the (unchanged) `src/analysis/*` and `src/graph/*` functions into use-cases: `PriceService`, `CompanyService`, `GraphService`, and `CorrelationService` — the last with three graduated methods (`rank_correlations` / `rank_with_stability` / `rank_with_full_diagnostics`) mirroring Phases 1 / 2-3 / 4, since Phase 4's diagnostics genuinely are Phase 2/3's ranking with more steps appended and each phase's exact historical CSV schema had to keep working.
3. **A FastAPI REST API** (`src/api/`) exposes the same functionality over HTTP: prices, companies, correlations (with the full Phase 4 diagnostic stack), and the combined multi-anchor graph.
4. **A single CLI** (`src/cli.py`, `python -m src.cli {phase1,phase2,phase3,phase4}`) replaces the four scripts, calling the exact same services the API uses, and writing to the exact same output paths as before.

## Code map

| File | What it's responsible for |
|---|---|
| [src/repositories/base.py](../src/repositories/base.py) | `PriceRepository`/`CompanyRepository` — `typing.Protocol` interfaces, not ABCs (structural typing, no forced inheritance). This is the seam a Postgres backend plugs into later. |
| [src/repositories/yfinance_price_repository.py](../src/repositories/yfinance_price_repository.py), [yfinance_company_repository.py](../src/repositories/yfinance_company_repository.py) | Thin delegating wrappers around `src/data/fetcher.py` — all the actual fetch/cache logic stays there so it isn't duplicated. |
| [src/data/fetcher.py](../src/data/fetcher.py), [storage.py](../src/data/storage.py) | `load_parquet()`/`fetch_price_history()`/`fetch_metadata()` gained an additive, backward-compatible `max_cache_age_seconds` param (`None` = never expires, today's behavior, unchanged for existing callers). `fetch_metadata()`'s per-ticker loop is now thread-pooled instead of serial. Both silent `except: continue` sites now log a warning instead of dropping a ticker with zero visibility. |
| [src/domain/models.py](../src/domain/models.py) | Framework-agnostic pydantic models (`PricePoint`, `CompanyProfile`, `RankedSatellite`, `GraphNode`, `GraphEdge`) shared by services and the API — not re-declared per-endpoint. |
| [src/domain/serialization.py](../src/domain/serialization.py) | `dataframe_to_models()` — the one place NaN/±inf get cleaned to `None` before anything reaches pydantic/JSON. See "A real bug this surfaced" below. |
| [src/services/correlation_service.py](../src/services/correlation_service.py) | `CorrelationService` — `rank_correlations()` (Phase 1), `rank_with_stability()` (Phase 2/3), `rank_with_full_diagnostics()` (Phase 4, what the API calls). The last holds an in-memory TTL result cache (`DiagnosticsResult.cache_hit`) so repeated requests for the same anchor don't re-run the whole Spearman/partial/lagged/sector-relative/regime-break stack. |
| [src/services/price_service.py](../src/services/price_service.py), [company_service.py](../src/services/company_service.py), [graph_service.py](../src/services/graph_service.py) | The remaining use-cases. `CompanyService.get_company_profile()` works for *any* ticker, not just the satellite universe — an anchor like NVDA isn't in `universe.py`'s list but still needs a working profile lookup. |
| [src/graph/queries.py](../src/graph/queries.py) | Added `graph_to_node_link_dict()` — the missing typed query flagged before this phase started ("no function converts a graph to a plain dict for JSON"); now the API's `/graph` response is built from it directly. |
| [src/api/deps.py](../src/api/deps.py) | FastAPI `Depends()` providers. Singletons via `functools.lru_cache` on functions whose only args are hashable repository objects — `Config` (a pydantic model, not hashable without extra work) is deliberately never passed as a cached function's argument, only fetched via a plain `get_config()` call inside each factory. |
| [src/api/main.py](../src/api/main.py) | `create_app()` factory (not just a module-level `app`) so tests get a fresh instance with mutable `dependency_overrides`. `lifespan` does cheap config validation only — no eager network fetch at boot. |
| [src/api/errors.py](../src/api/errors.py), [src/errors.py](../src/errors.py) | `TickerNotFoundError` → 404, `InsufficientDataError` → 422, any other `DomainError` → 500. |
| [src/api/routers/](../src/api/routers/) | One router per resource: `prices.py`, `companies.py`, `correlations.py`, `graph.py`, `health.py`. |
| [src/cli.py](../src/cli.py) | Replaces `run_phase1.py`..`run_phase4.py`. Same output paths, same behavior, built on the services above instead of duplicating fetch/rank/report orchestration four times. |
| [pyproject.toml](../pyproject.toml) | Makes the project an installable package (`packages = ["src"]`) — needed because `uvicorn src.api.main:app` doesn't get the implicit `sys.path` entry that `python run_phaseN.py` relied on. |

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | liveness check |
| GET | `/api/prices/{ticker}?lookback_days=` | |
| GET | `/api/companies?include_market_data=` | the satellite universe list |
| GET | `/api/companies/{ticker}` | works for any real ticker, including anchors |
| GET | `/api/anchors/{ticker}/correlations?top_n=&threshold=` | full Phase 4 diagnostics; any ticker, not just `config.anchors` |
| POST | `/api/anchors/{ticker}/refresh` | same, bypasses the result cache |
| GET | `/api/graph?anchors=` | combined multi-anchor graph as `{nodes, edges}` |
| GET | `/api/graph/relatedness?anchors=` | anchor-relatedness matrix as JSON |

## Key decisions

- **Blocking routes are plain `def`, not `async def`.** FastAPI runs a plain `def` path operation in Starlette's threadpool automatically (`run_in_threadpool`) — the documented, correct pattern for a blocking third-party library with no async variant (yfinance has none), not a workaround. Only `/health` is `async def`. Repositories/services stay fully synchronous for now; forcing async signatures with nothing async underneath would be indirection with no payoff — see "Explicitly deferred" below.
- **Caching happens at two levels, not per-request recomputation.** The TTL-fixed parquet cache avoids redundant yfinance round-trips (the dominant cost); `CorrelationService`'s in-memory result cache avoids redundant Spearman/partial/lagged/sector-relative/regime recomputation on the *already-fetched* data. `POST /anchors/{ticker}/refresh` threads `force_refresh=True` through both layers as an explicit cache-bust.
- **`Config` is never passed as an argument to an `lru_cache`d function.** A plain (unfrozen) pydantic `BaseModel` defines `__eq__` without `__hash__`, which makes it explicitly unhashable — confirmed directly (`hash(load_config())` raises `TypeError`) before this became a runtime bug. `get_config()` is cached and called directly inside each factory instead.
- **`X | None` needed `eval_type_backport`.** Pydantic v2 evaluates model-field and FastAPI route-parameter annotations at registration time; on this project's Python 3.9 venv, `float | None` (PEP 604) fails with `Unable to evaluate type annotation` unless `eval_type_backport` is installed — confirmed directly, then fixed with one dependency addition rather than rewriting every annotation to `Optional[X]`.
- **`CorrelationService` needed three methods, not one**, because Phase 1/2/3's CSV schemas (columns, filenames) had to keep working unchanged for the CLI, and Phase 4's logic really is Phase 2/3's logic with more steps appended — collapsing to a single "full diagnostics always" method would have silently changed Phase 1-3's output shape.

## A real bug this phase surfaced (and fixed)

Building the `/prices/{ticker}` endpoint was the **first time anything ever called `fetch_price_history()` with a single ticker** — every prior caller (all four old scripts) always fetched anchors + the full satellite universe together. `fetch_price_history()` picked its column-parsing branch from `len(tickers) > 1`, assuming a single-ticker request gets flat (non-MultiIndex) columns back from `yf.download()`. Confirmed directly that the currently-pinned yfinance version returns a `(ticker, field)` MultiIndex **even for one ticker** — so the single-ticker branch silently dropped every single-ticker request via the existing (now-logged) `except KeyError: continue`. Fixed by checking the actual returned column structure (`isinstance(raw.columns, pd.MultiIndex)`) instead of guessing from input length — a regression test (`test_fetch_price_history_single_ticker_multiindex_columns`) now locks this in. A second real bug — `DataFrame.where(df.notna(), None)` silently failing to turn NaN into `None` for float64 columns (pandas coerces the replacement back to NaN, which then breaks JSON serialization) — was caught the same way, by actually exercising `/companies?include_market_data=true` against tickers with missing metadata, not just eyeballing the code.

## Explicitly deferred (not silently bundled in)

Docker, CI, linting/mypy enforcement, and pre-commit are real gaps (see the earlier audit) but weren't part of this phase's scope and weren't added implicitly. Also deferred: async repositories (a real Postgres repository can just as easily use a sync driver — the Protocol seam makes that swap small and localized whenever it happens), a Redis/task-queue layer (the TTL-fixed cache already caps yfinance load), and auth (add only if the API becomes reachable beyond localhost).

## Result

`pytest -q` — 142 tests pass (up from 65 before this phase: 77 new tests across repositories, services, API routes via `TestClient` with `dependency_overrides`, and the CLI). All four CLI phases and every API endpoint were also verified against **live data** — the CLI via direct runs (`python -m src.cli phase1` through `phase4`, confirmed identical output paths to the old scripts), the API via a real `uvicorn` process hit with `curl` (not just an in-process `TestClient`): `GET /api/health`, `GET /api/prices/NVDA`, `GET /api/anchors/NVDA/correlations` (8 satellites, full diagnostics attached), `GET /api/graph?anchors=NVDA,TSM` (16 nodes, 18 edges), and a genuine 404 for an unknown ticker with a structured JSON error body rather than a raw traceback.
