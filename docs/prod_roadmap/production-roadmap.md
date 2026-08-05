# Production Roadmap: Engineering Infra, Frontend & Deployment

**Scope:** everything between "Phases 1–4.5 done, 142 tests passing, no UI" and "a deployed, publicly usable dashboard." Covers linting/formatting/type-checking, Docker, Postgres, CI/CD, the frontend build, and hosting.

This picks up immediately after [phase4-5.md](phase4-5.md), which explicitly deferred all of this:

> Docker, CI, linting/mypy enforcement, and pre-commit are real gaps... weren't part of this phase's scope.

It also **supersedes the original roadmap's Phase 5** ([stock_correlation_graph_roadmap.md](../stock_correlation_graph_roadmap.md), "Dashboard & Productionisation"), which assumed a Streamlit app. Phase 4.5 already pivoted to a REST API + CORS config for `localhost:3000`/`5173` (see `config.yaml`), which only makes sense in front of a separately-hosted JS frontend. This doc treats that pivot as final and plans accordingly.

Numbering continues the existing convention (4.5 was inserted ahead of the roadmap's own Phase 5): **4.6–4.9 are new infra sub-phases, Phase 5 is the frontend, Phase 6 is deployment.**

---

## 1. Audit findings — what's actually missing today

Verified directly against the repo, not assumed:

| Gap | Evidence |
|---|---|
| **Zero commits.** Every file is untracked (`git status`); `git log` errors with "does not have any commits yet." | `git status`, `git log` |
| A remote already exists, so GitHub Actions is a natural CI choice with no new signup. | `origin → github.com/ankitsree/stock_dependency_tracker.git` |
| ~~No root `README.md`~~ — **resolved**: `docs/README.md` has since been relocated to the repo root. | `ls` at repo root |
| **No secrets handling.** `.gitignore` has no `.env` entry; `Config` ([src/config.py](../src/config.py)) only reads `config.yaml`, no environment-variable override. | `.gitignore`, `src/config.py` |
| **No lint/format/type-check config anywhere** — no ruff/black/flake8/mypy section in `pyproject.toml`, no `.pre-commit-config.yaml`. | `pyproject.toml` |
| **No Docker** — no Dockerfile, docker-compose.yml, or `.dockerignore`. | repo listing |
| **No CI** — no `.github/workflows/`. The 142 tests only run when someone remembers to run them locally. | repo listing |
| **Python version drift** — system `python3` is 3.8.8, the project's own `venv` is 3.9.6, `pyproject.toml` floors at `>=3.9`. Worth picking one target before containerizing. | `python3 --version` vs `venv/bin/python --version` |
| **Postgres: seam built, nothing behind it.** `src/repositories/base.py` defines `PriceRepository`/`CompanyRepository` as `Protocol`s specifically so a Postgres implementation is a drop-in — but no such implementation exists yet. | [src/repositories/base.py](../src/repositories/base.py) |
| **Frontend: zero code**, but `config.yaml`'s `cors_allowed_origins` already lists Vite's (`:5173`) and CRA/Next's (`:3000`) default dev ports — the intended stack was decided implicitly before this doc. | `config.yaml` |

None of this blocks anything you've already built — 142 tests pass cleanly right now. This is a punch list, not a rescue.

---

## 2. How the phases fit together

| Phase | Goal | Depends on | Rough effort |
|---|---|---|---|
| **Step 0** | Get the existing tree under version control | — | < 1 hour |
| **4.6** | Lint, format, type-check, pre-commit | Step 0 | half a day |
| **4.7** | Docker + docker-compose (API, Postgres, later frontend) | Step 0 | 1–2 days |
| **4.8** | Postgres-backed repositories + migrations | 4.7 (local DB via compose) | 3–5 days |
| **4.9** | CI/CD pipeline (GitHub Actions) | 4.6, 4.7 | 1–2 days |
| **5** | Frontend (React dashboard against the existing API) | *nothing above* | 2–4 weeks |
| **6** | Deployment & operations | 4.7, 4.8, 4.9, 5 | 1–2 days |

**Phase 5 has no hard dependency on 4.6–4.9.** It only needs the REST API, which is already stable and complete. If you have the bandwidth, run the frontend and the infra track in parallel — otherwise do infra first since it's shorter and de-risks deployment before you've built something to deploy.

```
Step 0 ──▶ 4.6 ──┐
       └─▶ 4.7 ──┼──▶ 4.9 ──┐
              └─▶ 4.8 ──────┼──▶ 6
                            │
        (parallel) Phase 5 ─┘
```

---

## 3. Step 0 — Get this repo under version control

Everything below assumes commits exist and `main` is pushed. Nothing else in this doc can start without it — GitHub Actions has nothing to trigger on, branch protection has no branch to protect.

1. Review `git status` for anything that shouldn't be committed (it currently looks clean — `data/cache/*`, `outputs/*` are already gitignored).
2. `git add`, initial commit, `git push -u origin main`.
3. ~~Add the root `README.md` this repo is missing~~ — **done**: it now lives at the repo root (relocated from `docs/README.md`). Worth a pass to add a project description/quickstart at the top if it still just reads as a docs index.

This is a real push to a shared remote — flagging it explicitly rather than doing it as a side effect of some other task.

---

## 4. Phase 4.6 — Engineering hygiene

**Goal:** one command lints, one command formats, one command type-checks — identically for a human and for CI.

**Tools:**

| Concern | Tool | Why |
|---|---|---|
| Lint + format | **Ruff** | Replaces flake8 + isort + black with one Rust-fast tool; single config block in `pyproject.toml`. |
| Type-check | **mypy** | The codebase already leans on modern hints (`from __future__ import annotations`, `X \| None`, pydantic v2 models) — a good mypy fit already, just unenforced. |
| Pre-commit hooks | **pre-commit** | Runs Ruff (+ optionally mypy) before a commit lands, not just in CI. |

`pyproject.toml` additions (illustrative):

```toml
[tool.ruff]
line-length = 120
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.9"
plugins = ["pydantic.mypy"]
check_untyped_defs = true
# yfinance / networkx / pyvis ship no type stubs
[[tool.mypy.overrides]]
module = ["yfinance.*", "networkx.*", "pyvis.*"]
ignore_missing_imports = true
```

**Key decisions:**
- **Gradual mypy, not `--strict` on day one.** Turning strict mode on across ~50 existing files at once produces a wall of errors with no proportional payoff. Start with `check_untyped_defs`, ratchet up (`disallow_untyped_defs`, then `disallow_any_generics`) module by module.
- **No docstring-coverage linter** (e.g. pydocstyle). CLAUDE.md's convention is deliberately comment-light ("default to writing no comments"); a docstring linter would fight house style.
- **The first Ruff-format run will touch every file.** Land it as its own commit, separate from any logic change, so it's trivially reviewable/revertable.

**Deliverable:** `.pre-commit-config.yaml` wired to Ruff (+ mypy if you want it pre-commit rather than CI-only — it's slower, so CI-only is a reasonable call too), plus `make lint` / `make format` / `make typecheck` targets (or a `justfile`, if you prefer `just` over `make`) so Phase 4.9's CI calls the exact same commands a human runs locally.

---

## 5. Phase 4.7 — Containerization

**Goal:** `docker compose up` brings up the API + Postgres (and later the frontend) locally with zero manual setup; a production Dockerfile builds a small, deployable image.

**Dockerfile (illustrative, multi-stage):**

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.12-slim
RUN useradd --create-home appuser
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY src/ src/
COPY config.yaml .
USER appuser
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key decisions:**
- **Bump the container to Python 3.12**, even though the local `venv` is 3.9.6 and `pyproject.toml` floors at `>=3.9`. Nothing in the dependency list requires <3.11; a fresh container is a clean place to run a current interpreter, and it likely lets you **drop `eval_type_backport`** (added in Phase 4.5 solely to work around a Python-3.9-specific pydantic/FastAPI annotation evaluation issue — see [phase4-5.md](phase4-5.md#key-decisions)). Verify the full dependency set installs cleanly on 3.12 before committing to this; keep `pyproject.toml`'s floor at 3.9 unless you want to bump that too.
- **Non-root user** (`appuser`) — cheap hardening, standard practice for any container that will eventually be internet-facing.
- **`.dockerignore`** excluding `venv/`, `data/cache/*`, `__pycache__/`, `tests/`, `docs/`, `.git/` — keeps the build context and image small.
- **Config via environment variables, not just `config.yaml`.** Right now `Config` ([src/config.py](../src/config.py)) only loads from a YAML file — fine for local dev, wrong for a container where secrets like `DATABASE_URL` shouldn't be baked into the image or committed. This phase should add `pydantic-settings`-style env-var overrides (env var wins if set, falls back to `config.yaml` otherwise) — a small, concrete code change, not just infra.

**docker-compose.yml (illustrative):**

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/stockdep
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./data/cache:/app/data/cache

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: stockdep
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 3s
      retries: 5

  # frontend service added once Phase 5 exists — vite dev server for
  # local dev, or an nginx-served static build for a compose-based prod-like run

volumes:
  pgdata:
```

`GET /api/health` (already implemented) is the natural Docker/Compose/eventual-orchestrator healthcheck target for the `api` service.

---

## 6. Phase 4.8 — Postgres migration

This is the phase [src/repositories/base.py](../src/repositories/base.py) was explicitly built for:

> a future Postgres-backed repository satisfies the same contract with zero changes to services/routes/schemas — only `src/api/deps.py`'s factory functions change.

**What goes in Postgres, and what doesn't:**

- `prices` and `companies` tables — replace the parquet cache and the hardcoded `SATELLITE_UNIVERSE` list ([src/data/universe.py](../src/data/universe.py)) with real, queryable, updatable-without-a-deploy storage. Note this `companies` table is also the storage substrate for **Phase 7** ([universe-roadmap.md](universe-roadmap.md)), which populates it dynamically from a screener instead of the 55-ticker list — that phase's real prerequisite is this one, which is why the `is_satellite_universe` flag below is designed for it.
- **Not** computed correlation results. `CorrelationService`'s in-memory TTL cache already serves that cheaply, and persisting derived/recomputable analytics adds staleness/migration burden with no clear win yet. Revisit only if you run multiple API replicas and the in-memory cache becomes inconsistent across them — a real trigger, just not one that exists today.
- **Schema sketch for a Phase 5b `watchlists` feature** (the original roadmap's Phase 5 wishlist) — worth designing now so it isn't a rework later, but not implemented in this phase; it needs light auth first (see §8).

**Schema (illustrative):**

```sql
CREATE TABLE companies (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    market_cap DOUBLE PRECISION,
    avg_volume DOUBLE PRECISION,
    is_satellite_universe BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE prices (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES companies(ticker),
    date DATE NOT NULL,
    adjusted_close DOUBLE PRECISION NOT NULL,
    volume BIGINT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ticker, date)
);
CREATE INDEX idx_prices_ticker_date ON prices (ticker, date);

-- Phase 5b sketch only — not built in 4.8
-- CREATE TABLE watchlists (id, user_id, name, created_at);
-- CREATE TABLE watchlist_items (watchlist_id, ticker);
```

`is_satellite_universe` is a boolean column, not "presence in the table," because [phase4-5.md](phase4-5.md) is explicit that `CompanyService.get_company_profile()` must resolve **any** ticker, including anchors like NVDA that were never in `universe.py`'s list. A Postgres `CompanyRepository.get_market_data()` needs to look up arbitrary tickers regardless of universe membership; `list_universe()` is the one query that filters on the flag.

**Key decisions:**
- **SQLAlchemy 2.0 + Alembic + `psycopg` (v3), synchronous.** Boring and well-supported. `SQLModel` (pydantic + SQLAlchemy fused) is tempting given how pydantic-heavy this codebase already is, but it would blur the separation this project has deliberately kept — `src/domain/models.py` is framework-agnostic on purpose, translated at the repository boundary. Keep DB models in a new `src/repositories/postgres/models.py`, separate from domain models, and translate between them in the repository — consistent with the existing architecture.
- **Stay synchronous.** [phase4-5.md](phase4-5.md) already decided this for the same reason: routes are plain `def` (FastAPI runs them in a threadpool), so an async driver buys nothing yet and would mean touching the `Protocol` signatures, every service, and every route. Revisit only if profiling shows the threadpool is the actual bottleneck.
- **Cutover via `DATABASE_URL` presence, not a hard swap.** In [src/api/deps.py](../src/api/deps.py), if `DATABASE_URL` is set, construct `PostgresPriceRepository`/`PostgresCompanyRepository`; otherwise fall back to the existing YFinance-backed ones. Keeps local hacking frictionless without requiring Postgres to be running, and matches the project's existing "cache aggressively, don't add friction" ethos.
- **yfinance stays the upstream source of truth.** Postgres is a durable, queryable cache/store, not a new data vendor. A refresh path (literally the existing `POST /anchors/{ticker}/refresh`, called on a schedule, or a new scheduled task) keeps rows from going stale, using the same `price_cache_ttl_seconds` config value against each row's `updated_at`/`fetched_at` instead of a file mtime.
- **Upsert, don't insert-and-fail.** Both tables need `ON CONFLICT ... DO UPDATE` (keyed on `ticker` for companies, `(ticker, date)` for prices) since refetch/refresh is expected, not exceptional.
- **Keep `data/cache/*.parquet`** as an offline/fallback path and for tests — don't delete the existing mechanism, just stop it being the only one.

**Step-by-step:**
1. Add `PostgresPriceRepository`/`PostgresCompanyRepository` implementing the two `Protocol`s exactly (`get_price_history`, `list_universe`, `get_market_data`) — no service or router changes needed, by design.
2. Add Alembic, first migration creates `companies`/`prices` with the indexes/constraints above.
3. Write a one-off backfill (`python -m src.cli backfill-postgres` or a standalone script) that reads today's parquet cache / re-fetches via yfinance and seeds Postgres.
4. Swap the two factory functions in `deps.py` behind the `DATABASE_URL` check.
5. Local dev DB comes from Phase 4.7's compose `db` service; document `alembic upgrade head` as a compose startup step or an explicit README instruction.
6. **Test against a real Postgres, not mocks** — mirror the existing `tests/repositories/test_yfinance_price_repository.py` pattern, but point it at an actual ephemeral database (Phase 4.9's CI spins one up natively via GitHub Actions `services:`). Exercising a real DB in CI catches migration/constraint bugs that a mock can't.

---

## 7. Phase 4.9 — CI/CD pipeline

**Goal:** every PR is automatically linted, type-checked, and tested against a real Postgres; every merge to `main` builds and deploys.

GitHub Actions is the natural choice — `origin` already points at `github.com/ankitsree/stock_dependency_tracker`, so there's no new tool or signup.

**Two workflow files, not one monolith** (keeps PR status checks legible and jobs parallelizable):

### `.github/workflows/ci.yml` — on every PR and push to `main`

| Job | What it does |
|---|---|
| `lint` | `ruff check`, `ruff format --check`, `mypy` — fails fast, no DB needed. |
| `test` | Spins up a `postgres:16` **service container** (native GitHub Actions feature — no docker-compose needed inside CI), runs `alembic upgrade head`, then `pytest` with `DATABASE_URL` pointed at it. Exercises the real Postgres repositories from §6, not just the yfinance-backed ones. |
| `build` | `docker build` only — confirms the image builds; doesn't push on PRs. |

```yaml
# illustrative excerpt — test job
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: stockdep_test
    ports: ["5432:5432"]
    options: >-
      --health-cmd pg_isready
      --health-interval 5s
      --health-timeout 3s
      --health-retries 5
```

### `.github/workflows/cd.yml` — on push/merge to `main`

1. Build the Docker image, tag with the git SHA + `latest`, push to **GitHub Container Registry (`ghcr.io`)** — free, no extra signup, authenticates with the automatic `GITHUB_TOKEN` (no separate registry secret to manage).
2. Run `alembic upgrade head` against production as a release step (exact mechanism depends on the host chosen in §8 — e.g. a Render "pre-deploy command" or `flyctl ssh console -C "..."`).
3. Trigger the deploy (host-specific — see §8).
4. **Frontend deploy is not a GitHub Actions step at all** — connect the repo directly in Vercel's dashboard. Its GitHub App auto-builds preview deployments per PR and production on merge to `main`, which is both less to maintain and gives you a live preview URL on every UI PR, genuinely useful for reviewing design changes.

**Secrets & environments:**
- Repo secrets (`Settings → Secrets and variables → Actions`): `DATABASE_URL` (prod), host-specific deploy token. `ghcr.io` needs no extra secret.
- Add `.env` to `.gitignore` (currently missing) and commit a `.env.example` template — a concrete, small fix that belongs in this phase.
- Use GitHub **Environments** to scope `production` secrets separately from CI-only ones, optionally requiring manual approval before a production deploy.
- Two environments is enough to start (`preview` for frontend PRs via Vercel, `production` for everything on `main`) — don't build a staging tier until the project's actual usage justifies the extra cost/complexity.

**Branch protection:** once `main` is pushed (Step 0), require the `lint` and `test` checks to pass before merging — a one-time manual setting in `Settings → Branches`, not a workflow file.

**Status badge:** once CI exists, add a badge to the root `README.md` this repo is currently missing (§1) — cheap, and it's the first thing anyone sees on the repo page.

---

## 8. Phase 5 — Frontend

Supersedes the original roadmap's Streamlit-based Phase 5. The backend already assumes a separately-hosted JS app (CORS origins for `:3000`/`:5173` are in `config.yaml` today).

For the step-by-step build sequence — the self-interview questions and follow-up prompts for each implementation step, from scaffolding through deployment handoff — see [frontend-roadmap.md](frontend-roadmap.md). This section covers the *what and why* (stack, functional spec, the base build prompt); that document covers the *in what order and with what specifics*.

### 8.1 Tech stack

| Concern | Choice | Why |
|---|---|---|
| Framework/build | **Vite + React + TypeScript** | Matches the `:5173` CORS origin already configured; fastest dev loop for a data-heavy SPA. |
| Styling | **Tailwind CSS + CSS custom properties for theme tokens** | Fast to build with; CSS variables keep colors/type centralized so the "avoid generic AI-slop" design mandate (CLAUDE.md) is enforced structurally, not left to Tailwind's defaults. |
| Data fetching/cache | **TanStack Query** | The dashboard is several independent async panels (graph, table, sparkline, heatmap) — Query's per-endpoint caching/loading/error states fit better than hand-rolled `useEffect` fetching. |
| Graph rendering | **`react-force-graph-2d`** | WebGL/canvas force-directed graph with built-in physics, zoom/pan, and hit-testing, but exposes `nodeCanvasObject`/`linkCanvasObject` callbacks so the exact styling rules from `.claude/skills/network-graph-style/SKILL.md` (sector color groups, log-scaled node size, edge width/opacity formulas) port over as custom draw calls instead of being reinvented. Alternative: hand-rolled D3 force simulation for maximum creative control, at real extra build cost — reasonable if the canned physics ever feel visually generic. |
| Tabular data | **TanStack Table** | Sortable/filterable satellite ranking table — the interactive successor to Phase 3's static companion HTML table. |
| Small charts | **Recharts** | Price-history sparklines only; overkill to pull in a heavier charting library for this. |
| Routing | **React Router** | Three real views (Dashboard, Anchor detail, Relatedness) justify actual routes over one giant page with modal state. |
| Local state | Plain `useState`/`useReducer`; **no Redux/Zustand** until prop-drilling actually hurts | Almost all state here is server state, which TanStack Query already owns. |
| Typed API client | **`openapi-typescript`** against FastAPI's auto-generated `/openapi.json` | Generates response types directly from `src/domain/models.py`/`src/api/schemas/*` instead of hand-duplicating them — one source of truth for the contract. |
| Testing | **Vitest + React Testing Library** (components), **Playwright** for 1–2 smoke tests | Matches the backend's existing philosophy: focused tests, not exhaustive ones. |

### 8.2 Functional requirements, grounded in the actual API

| API (already built) | UI feature |
|---|---|
| `GET /api/graph?anchors=` | Main force-directed graph: all configured anchors + satellites in one view. |
| `GET /api/anchors/{ticker}/correlations?top_n=&threshold=` | Sortable satellite table for a selected anchor — full Phase 4 diagnostics (Pearson, Spearman-blended correlation, stability, partial correlation, sector-relative correlation, best lag + lag correlation, regime break flag/drift). |
| `GET /api/prices/{ticker}` | Sparkline/mini price chart on hover or click — shows the actual price action behind a correlation number. |
| `GET /api/graph/relatedness?anchors=` | Anchor×anchor heatmap — a dataset not surfaced anywhere yet, even in the Python-rendered graphs. Good differentiator, not just "the graph, but web." |
| `GET /api/companies?include_market_data=` / `GET /api/companies/{ticker}` | Free-text ticker search — the API already resolves *any* real ticker, not just `config.anchors`, so don't limit the UI to a fixed dropdown. |
| `top_n` / `threshold` query params (already on `/graph` and `/correlations`) | Sliders — this is verbatim the original roadmap's Phase 5 wishlist ("adjust correlation thresholds... with sliders"), now buildable against a real API. |
| `TickerNotFoundError` → 404, `InsufficientDataError` → 422 (real, already-modeled error cases) | Distinct empty/error states — "AAPL isn't in the satellite universe and doesn't have enough history" reads differently from a generic network error toast. |

**Non-negotiable, sourced directly from CLAUDE.md's project conventions:**
- **Correlation ≠ causation must be visible in the UI**, not just in docs — CLAUDE.md: "don't claim a 'dependency' without noting it's price-correlation-based." A persistent footer note or an always-visible info affordance on the graph, not a buried tooltip.
- **Light/dark theme must match the existing Python-rendered graphs.** Port the exact hex values and formulas from `.claude/skills/network-graph-style/SKILL.md` (e.g. positive-edge blue `#2a78d6`/`#3987e5`, negative-edge red `#e34948`/`#e66767`, node size `12 + 6 * log10(market_cap / 1e8)` clamped `[12, 40]`) as CSS variables / canvas draw constants — visual continuity between the static/interactive HTML exports and the new web UI, not two competing color systems.
- **Accessibility fallback for the graph.** A canvas-rendered force graph is inherently unreadable to a screen reader. The sortable satellite table (already planned above) must work as a fully accessible standalone view, not merely a decorative sidebar — treat it as the accessible primary interface, the graph as the visual layer on top.

**Explicitly out of scope for v1 (don't silently assume they exist):**
- **Watchlists** — the original roadmap's Phase 5 wishlist item, but it needs a `watchlists`/`watchlist_items` schema (sketched in §6) and light auth, neither of which exists yet. Ship the read-only dashboard first; treat watchlists as Phase 5b once that backend slice is built.
- No auth, no multi-user state, no server-side rendering.

### 8.3 The build prompt

This is what to actually hand to a builder (human or AI) to build this frontend — self-contained, so it doesn't depend on this whole document being read first.

```
Build the Phase 5 frontend for the Stock Correlation Dependency Graph
project: a React + TypeScript single-page dashboard that lets everyday
investors explore which small/mid-cap "satellite" stocks are
statistically correlated with large-cap "anchor" stocks (NVDA, AAPL,
TSM, ASML). The backend is a stable, already-built FastAPI REST API
(base URL configurable, defaults to http://localhost:8000/api; OpenAPI
schema at /openapi.json) — this is a pure frontend build against a
fixed contract, not a full-stack task.

STACK: Vite + React + TypeScript, Tailwind CSS with CSS custom
properties for theme tokens, TanStack Query for data fetching,
TanStack Table for the ranking table, react-force-graph-2d for the
network graph, React Router, Recharts for sparklines. Generate typed
API response models from /openapi.json via openapi-typescript rather
than hand-writing them.

VIEWS REQUIRED:
1. Dashboard — the main force-directed graph (GET /api/graph),
   anchor selector (free-text ticker search, not just a fixed
   dropdown — the API resolves any real ticker), top_n/threshold
   sliders.
2. Anchor detail — sortable/filterable satellite table for the
   selected anchor (GET /api/anchors/{ticker}/correlations), showing
   correlation, stability, partial correlation, sector-relative
   correlation, best lag, and regime-break flag as columns.
3. Ticker panel — price sparkline (GET /api/prices/{ticker}) shown on
   node hover/click for both anchors and satellites.
4. Relatedness view — anchor×anchor heatmap (GET
   /api/graph/relatedness).

GRAPH STYLING — port these exact rules from this project's existing
Python renderers (do not invent new ones):
- Node color: satellites colored by sector color-group (7 fixed hues,
  see the project's network-graph-style skill for the palette and
  sector-to-group mapping); anchors are never sector-colored — fixed
  near-black (#0b0b0b light / near-white #ffffff dark) plus a
  distinct shape (star vs dot) instead.
- Edge color: positive correlation → blue (#2a78d6 light / #3987e5
  dark), negative → red (#e34948 light / #e66767 dark).
- Edge width: 1 + |correlation| * 6 px. Edge opacity: stability score
  clamped to [0.25, 1.0], full opacity if no stability score exists.
- Node size (satellites): 12 + 6 * log10(market_cap / 1e8), clamped
  [12, 40]; fixed 18 if market_cap is missing. Anchors: fixed 40.
- Support light and dark themes with these exact values — this must
  visually match the project's existing pyvis/matplotlib output, not
  introduce a third color system.

FUNCTIONAL REQUIREMENTS:
- Handle 404 (unknown ticker) and 422 (insufficient price history)
  from the API as distinct, informative empty states — not a generic
  error toast.
- A persistent, visible note that correlation is not causation and
  that relationships are price-correlation-based, not verified
  supply-chain data — this is a project-wide convention, not
  optional fine print.
- Fully responsive down to ~375px width: the satellite table should
  collapse below the graph (or into a bottom sheet) on small screens;
  the graph canvas must resize to its container, with touch
  pinch/pan support.
- The satellite table must work as a fully accessible, independent
  view — the force graph is canvas-rendered and inherently
  unreadable to screen readers, so the table is the accessible
  primary interface, not a decorative sidebar.

NON-GOALS FOR V1: no authentication, no persisted watchlists (needs a
backend slice that doesn't exist yet), no server-side rendering.

<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In
frontend design, this creates what users call the "AI slop"
aesthetic. Avoid this: make creative, distinctive frontends that
surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting.
Avoid generic fonts like Arial and Inter; opt instead for distinctive
choices that elevate the frontend's aesthetics.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for
consistency. Dominant colors with sharp accents outperform timid,
evenly-distributed palettes. Draw from IDE themes and cultural
aesthetics for inspiration. (Note: the graph's own node/edge colors
are fixed per the styling rules above — apply this freedom to
everything else: chrome, typography, layout, background.)

Motion: Use animations for effects and micro-interactions. Prioritize
CSS-only solutions for HTML. Use the Motion library for React where
available. Focus on high-impact moments: one well-orchestrated page
load with staggered reveals (animation-delay) creates more delight
than scattered micro-interactions.

Backgrounds: Create atmosphere and depth rather than defaulting to
solid colors. Layer CSS gradients, use geometric patterns, or add
contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics: overused font families (Inter,
Roboto, Arial, system fonts), clichéd color schemes (particularly
purple gradients on white backgrounds), predictable layouts, and
cookie-cutter component patterns. Interpret creatively — a financial
data tool doesn't have to look like a generic SaaS dashboard.
</frontend_aesthetics>

DEFINITION OF DONE: builds and runs against a local API instance, all
four views work end-to-end with real data, responsive down to 375px,
light/dark both implemented, satellite table is keyboard/screen-reader
accessible independent of the graph.
```

### 8.4 Build order & repo layout

1. Scaffold: `npm create vite@latest frontend -- --template react-ts`, installed as a new top-level `frontend/` directory (sibling to `src/`, not nested inside it) — add `frontend/node_modules/` and `frontend/dist/` to the root `.gitignore`.
2. Generate the typed API client from `/openapi.json`.
3. Build order: API client + query hooks → layout shell (header, ticker search, theme toggle) → graph view → satellite table → price sparkline → relatedness heatmap → responsive/accessibility pass.
4. Watchlists (Phase 5b) only after §6's schema exists and there's a real auth story.

---

## 9. Phase 6 — Deployment & operations

### 9.1 Hosting

| Component | Recommendation | Alternative |
|---|---|---|
| API | **Render** — "Web Service" auto-deploys from GitHub with no custom Action needed for the deploy step itself (Actions still gate lint/test); simplest path for a solo maintainer. Free-tier caveat: spins down when idle, cold-starts on the next request. | **Fly.io** — Docker-native, ties more naturally into the `ghcr.io` image built in §7 if you want the image build to genuinely matter; more config, less magic. |
| Postgres | The hosting platform's bundled Postgres (Render/Fly both offer one) to start. | **Neon** (serverless, branch-per-PR databases) — genuinely nice for preview environments; revisit if/when preview environments matter. |
| Frontend | **Vercel** — best-in-class React/Vite DX, automatic PR preview deploys (already assumed in §7). | Netlify, Cloudflare Pages — equivalent, fine alternatives. |

### 9.2 Config & secrets

Environment variables needed in production (values, not just names, live in each host's secret manager — never in git):

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string (§6). |
| `CORS_ALLOWED_ORIGINS` | Override `config.yaml`'s localhost defaults with the real Vercel production URL. |
| `PRICE_CACHE_TTL_SECONDS` | Optional override of the config.yaml default. |
| `LOG_LEVEL` | `INFO` in prod, `DEBUG` locally. |

### 9.3 Observability

- **Start with the host's built-in log viewer** (Render/Fly both have one, zero setup) — the API already uses `logging`, not `print()` (fixed in Phase 4.5), so this works immediately.
- **Add Sentry to the frontend early** — cheap to wire up, high value for a public-facing UI where you won't otherwise hear about a crash.
- Don't reach for a dedicated backend observability tool (Axiom, Better Stack) until there's real traffic to justify it.

### 9.4 Security basics before this is public

- **Rate-limit the API itself** (e.g. `slowapi`), independent of yfinance's own throttling — one heavy user shouldn't be able to hammer your server.
- Update `cors_allowed_origins` from localhost to the real deployed frontend origin (the config already has the right shape — just needs prod values via the env override from §4.7/9.2).
- `.env` gitignored, `.env.example` committed (§7).
- Consider whether `POST /anchors/{ticker}/refresh` needs its own throttle once public — it's a direct trigger for a yfinance round-trip through your server, and an easy abuse vector if left wide open.

### 9.5 Rough cost

Hobby-scale, order-of-magnitude only (verify current pricing before committing): Render free/hobby web service (~$0–14/mo) + bundled Postgres (~$0–7/mo), Vercel free tier for the frontend, `ghcr.io` free for a public image. Realistically $0–25/mo to start.

---

## 10. Open decisions — flag if you want something different

Every judgment call above, in one place, so you can redirect efficiently instead of re-reading each section:

- Ruff + mypy (vs. flake8/black/pyright)
- SQLAlchemy 2.0 + Alembic + `psycopg` v3, synchronous (vs. SQLModel, vs. async)
- Bumping the container to Python 3.12 while leaving `pyproject.toml`'s floor at 3.9 (vs. bumping the floor too, vs. staying on 3.9 everywhere)
- GitHub Actions + `ghcr.io` (vs. another CI/registry)
- Render for API + Postgres hosting (vs. Fly.io, Railway, raw AWS/GCP)
- `react-force-graph-2d` for the graph (vs. hand-rolled D3, vs. a `vis-network` React wrapper mirroring the Python pyvis output exactly)
- Tailwind + CSS variables for frontend styling (vs. a different CSS approach)
- Vercel for frontend hosting (vs. Netlify, Cloudflare Pages)
- Trunk-based deploy on every merge to `main` (vs. tag-based releases with deliberate version cuts)
- Not persisting correlation results in Postgres yet (vs. adding a `correlations` table now)

---

## 11. What to actually do first

1. **Step 0** — commit and push what already exists (needs your go-ahead; it's a push to a shared remote).
2. **Phase 4.6** — cheapest, immediately useful, and makes Phase 4.9's CI meaningful from day one.
3. From there, infra (4.7 → 4.8 → 4.9) and the frontend (Phase 5) can run in parallel if you have the bandwidth for both.
