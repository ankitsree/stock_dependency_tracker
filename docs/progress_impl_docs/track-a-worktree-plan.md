# Track A — Parallel Execution with Worktrees

**Question this answers:** should Track A be built using git worktrees with Claude CLI agents
working in parallel, and if so, how should the work be split so the merges stay trivial?

**Short answer:** yes, but **not along the axis [track-a-product-plan.md](track-a-product-plan.md)
is written in.** Phases are a dependency chain, not parallel tracks. The axis that actually
parallelises is *backend vs frontend within a phase*, plus Tier 0's independent chores. Split
that way, and land a **seam commit** before each fan-out, and conflicts drop to near zero.

---

## 1. Verdict

| | |
|---|---|
| **Use worktrees?** | Yes — for Tier 0, Phase 3, and Phase 4 |
| **Don't use them for** | Phase 1 and Phase 2 — single worktree, sequential |
| **Realistic time saved** | ~2 weeks off a 10–12 week track. Real, not transformative |
| **Biggest risk** | Not merge conflicts. It's **two worktrees sharing one local Postgres** (§6.1) |
| **Prerequisite for every fan-out** | A seam commit on `main` first (§4). Skip it and you get conflicts in every shared file |
| **Recommended shape** | Phase 1 solo → Phase 2 ∥ Phase 3 (3 worktrees) → Phase 4 — see **§5A** |

The honest framing: worktrees don't create parallelism, they only *exploit* parallelism that
already exists in the dependency graph. Most of Track A's graph is serial. Where it isn't,
worktrees are excellent.

---

## 2. Why "one worktree per phase" is the wrong split

Track A's phases form a star out of Phase 1, not a chain of independent work:

```
                    ┌─────────────────────────┐
                    │  PHASE 1                │
                    │  correlations table     │
                    │  + CorrelationRepository│
                    └───────────┬─────────────┘
                                │  everything below reads this
              ┌─────────────────┼──────────────────┐
              │                 │                  │
      ┌───────▼──────┐  ┌───────▼───────┐  ┌───────▼────────┐
      │  PHASE 2     │  │  PHASE 3      │  │  PHASE 4       │
      │  jobs call   │  │  portfolio    │  │  regime breaks │
      │  the repo    │  │  reads table  │  │  diffs table   │
      └──────────────┘  └───────────────┘  └────────────────┘
```

Run Phase 1 and Phase 3 in parallel worktrees and the Phase 3 agent is writing code against a
table that doesn't exist and a repository whose method signatures are still being invented.
What you get back isn't a merge conflict — it's code that merges cleanly and doesn't work.
**That is strictly worse than a conflict**, because git won't warn you.

The rule: **parallelise across the layer boundary, never across a data-dependency.**

---

## 3. What is actually parallel

| Work | Parallel with | Why it's safe |
|---|---|---|
| Tier 0: frontend CI job | everything | touches `.github/workflows/ci.yml` only |
| Tier 0: frontend Sentry | everything | touches `frontend/src/main.tsx` + deps |
| Tier 0: README doc links | everything | markdown only |
| Phase 3 backend | Phase 3 frontend | disjoint trees, once the API contract is fixed |
| Phase 4 backend | Phase 4 frontend | same |
| Phase 4 backend | Phase 3 frontend | different tables, different pages |

| Work | **Not** parallel with | Why |
|---|---|---|
| Phase 1 | anything downstream | it defines the schema + repository everything else calls |
| Phase 2 | Phase 1 | jobs call Phase 1's repository directly |
| Any two migrations | each other | Alembic's revision chain forks — §6.2 |

---

## 4. The core technique: seam commit, then fan out

**Before** any parallel wave, land one small PR on `main` that contains *only* the shared-surface
edits. Every file that two agents would both need to append to, gets touched exactly once —
by you, before anyone forks.

A seam commit for Phase 3 would be:

```
  migrations/versions/xxxx_portfolio.py       (if the phase needs schema — authored ONCE)
  src/domain/models.py                        + PortfolioInput, PortfolioAnalysis (stubs)
  src/repositories/base.py                    + PortfolioRepository Protocol (methods, no impl)
  src/api/routers/portfolio.py                NEW — every route returns 501 Not Implemented
  src/api/main.py                             + portfolio.router in the include tuple (line ~91)
  src/api/deps.py                             + get_portfolio_repository()
  frontend/src/types/domain.ts                + the response types, hand-written to match
  frontend/src/pages/PortfolioPage.tsx        NEW — renders "coming soon"
  frontend/src/routes.tsx                     + <Route path="portfolio" .../>
```

That commit is maybe 150 lines, takes an hour, and **is the entire conflict surface of the
phase.** After it lands:

```
  BEFORE seam commit          AFTER seam commit
  ─────────────────           ──────────────────
  BE agent  ──┐               BE agent  ──> fills routers/portfolio.py
              ├─> both edit                  + services/portfolio_service.py
  FE agent  ──┘   main.py                    + repositories/postgres/portfolio_*.py
                  routes.tsx
                  models.py     FE agent  ──> fills pages/PortfolioPage.tsx
                  domain.ts                   + components/portfolio/*
                  ↓                           (touches nothing the BE agent touches)
              CONFLICTS                       ↓
                                          CLEAN MERGE
```

Two further benefits worth naming:

- **The API contract is fixed in writing before either side starts.** The `domain.ts` types and
  the pydantic models are written together, in one commit, by one person. That's where
  frontend/backend integration usually goes wrong, and this eliminates it structurally.
- **Each worktree stays runnable.** The 501 stubs mean the FE agent can build against a live
  route from minute one, and the BE agent's tests can assert against a registered router.

---

## 5. The wave plan

### Wave 0 — Tier 0 (genuinely parallel, 3 worktrees)

No seam commit needed; these barely overlap.

| Worktree | Branch | Owns | Conflict risk |
|---|---|---|---|
| `wt-ci` | `tier0/frontend-ci` | `.github/workflows/ci.yml` | none |
| `wt-sentry-fe` | `tier0/frontend-sentry` | `frontend/src/main.tsx`, `frontend/package.json` | lockfile only |
| `wt-docs` | `tier0/doc-links` | `README.md`, `docs/**` | none |

The Sentry worktree is the only one adding an npm dependency, so it owns `package-lock.json`
for this wave. See §6.4.

### Wave 1 — Phase 1 (single worktree)

**Do not split this.** It's ~1 week, it defines the schema and the repository Protocol that
three later phases depend on, and every part of it is coupled to every other part. One
worktree, one agent, one branch. Merge to `main` before Wave 2 starts.

Also fold in the [research-track.md](research-track.md) §1.1 recommendation here — key the
table as symmetric `(ticker_a, ticker_b)` rather than `(anchor, satellite)`. It's hours now
and a migration later, and doing it inside this already-solo wave costs nothing.

### Wave 2 — Phase 2 (single worktree)

~1 week, mostly `render.yaml` + two CLI commands. Not worth splitting. Can run **concurrently
with Wave 3's frontend worktree** if you want, since it touches no frontend file at all.

### Wave 3 — Phase 3 (seam commit + 2 worktrees)

```
  main:  ──● seam commit (routes, types, stubs, migration) ──────●─── merge
            │                                                  ↗↗
            ├─ wt-p3-api ──── services + repos + router body ──┘
            │                                                 ↗
            └─ wt-p3-ui ───── page + components + hooks ──────┘
```

| Worktree | Branch | Owns exclusively |
|---|---|---|
| `wt-p3-api` | `phase3/portfolio-api` | `src/services/portfolio_service.py`, `src/analysis/portfolio.py`, `src/repositories/postgres/portfolio_*.py`, `src/api/routers/portfolio.py` (body only), `tests/**` for those |
| `wt-p3-ui` | `phase3/portfolio-ui` | `frontend/src/pages/PortfolioPage.tsx`, `frontend/src/components/portfolio/**`, `frontend/src/api/hooks/usePortfolio*.ts`, their tests |

Neither may edit: `main.py`, `deps.py`, `routes.tsx`, `domain.ts`, `models.py`, `migrations/`.
Those were finished in the seam commit. If one of them *needs* a change there, that's a signal
the contract was wrong — stop, fix it on `main`, rebase both. Don't let one worktree edit it
unilaterally.

### Wave 4 — Phase 4 (seam commit + 2 worktrees)

Identical shape. `wt-p4-api` owns `correlation_changes` repo + the detection job + the endpoint
body; `wt-p4-ui` owns `RegimeBreaksFeed` and its page.

Phase 4's backend can start during Wave 3 if its seam commit lands early — it reads Phase 1's
table and writes a new one, so it collides with Phase 3 nowhere.

---

## 5A. Recommended variant: Phase 1 solo → Phase 2 ∥ Phase 3 → Phase 4

This is a better shape than the generic wave plan above, and it's the one to use.

**Verdict: yes, and Phase 2 ∥ Phase 3 is the cleanest pairing in the whole track.** Their file
footprints are almost perfectly disjoint:

| | Phase 2 (jobs) | Phase 3 (portfolio) |
|---|---|---|
| Touches | `render.yaml`, `src/cli.py`, job tests | `src/analysis/`, `src/services/`, `src/api/routers/`, all of `frontend/` |
| Doesn't touch | anything under `frontend/`, any router | `src/cli.py`, `render.yaml` |
| Shared files | **`src/config.py` only** (both may add settings) — and `pyproject.toml` if either adds a dep | |

`src/cli.py` is the one file with real conflict potential, since `main()` builds every
subcommand in a single `add_parser` block (`src/cli.py:35-41`) — but only Phase 2 goes near it,
so it has one owner by construction.

### Three refinements

**1. Make it three worktrees, not two.** Phase 2 is ~1 week; Phase 3 is ~3. Splitting Phase 3
into backend and frontend is where the actual wall-clock saving is — Phase 2 vs Phase 3 saves
one week, Phase 3's own BE/UI split saves more.

```
  main ──● Phase 1 merged ──●  Phase 3 seam commit ──────────────●── merge
          │                  │                                  ↗↗↗
          ├─ wt-jobs ────────┼─ Phase 2, whole thing ───────────┘↗↗
          │  (starts here —  │                                   ↗↗
          │   needs no seam) ├─ wt-p3-api ─── services + router ┘↗
          │                  │                                   ↗
          │                  └─ wt-p3-ui ──── page + components ─┘
```

Note that **`wt-jobs` needs no seam commit** — it shares no append-point with Phase 3. So Phase
2 can start the moment Phase 1 merges, in parallel with you *authoring* Phase 3's seam commit.
That's a free head start.

**2. Ship Phase 2 to production early — Phase 4 is gated on wall-clock, not code.** Phase 4
diffs this week's correlations against last week's. Until the daily job has actually been
running for a week or two, the regime-breaks feed has nothing to display, and you can't tell a
working feed from a broken one.

Two ways to handle it, and you want at least one:
- **Merge and deploy Phase 2 as soon as it's green**, well before Phase 3 finishes, so history
  accumulates while you build. This is the reason to run these in parallel rather than
  sequentially — not the week saved, but the week of *data* gained.
- **Give Phase 1's job an `--as-of DATE` backfill mode** so correlation rows can be generated
  retroactively from the `prices` table, which already holds the history. Then Phase 4 isn't
  wall-clock gated at all. Worth folding into Phase 1's solo wave if you want the option.

**3. ⚠️ Watch the Yahoo rate limit — this pairing is the one that provokes it.** Phase 2's whole
purpose is bulk-fetching the universe, and its agent will run the daily job repeatedly to test
it. Phase 3's agent triggers fetches too. Both from one IP. `CLAUDE.md` flags this explicitly:
yfinance hits Yahoo's unofficial API and **can get an IP rate-limited** — which then breaks
*both* worktrees and looks like unrelated bugs in each.

Mitigations, cheapest first:
- Warm one price cache and share it. `data/cache/` is gitignored, so just copy it into each
  worktree after the first full fetch.
- Point both worktrees' `DATABASE_URL` at databases seeded from one backfill
  (`python -m src.cli backfill-postgres`), so the TTL logic finds warm rows and never calls out.
- Have the Phase 2 agent test against a 3–5 ticker subset rather than the full universe. Job
  *correctness* doesn't need 59 tickers; job *timing* does, and that's a production measurement
  anyway.

### Phase 4 last

Correct call. It depends on Phase 2's output and shares nothing with Phase 3, so there's no
parallelism left to exploit by then — and by that point you want the daily job's real output in
front of you before writing the detection thresholds. Split it BE/UI with its own seam commit
if you want the two-worktree pattern again; it's a ~2 week phase, so the benefit is modest but
real.

### Net effect

```
  Phase 1  ██████                     1 wk   solo
  Phase 2      ████                   1 wk   ┐ parallel
  Phase 3      ████████████           3 wk   ┘ (BE ∥ UI inside)
  Phase 4                  ████████   2 wk   solo-ish
                                      ─────
                                      ~7 wk  vs ~9 sequential
```

Plus Phase 4 starts with two months of accumulated correlation history instead of an empty
table, which is worth more than the two weeks.

---

## 6. The real hazards (repo-specific, verified)

These are the things that will actually bite, ordered by how much damage they do. Only one of
them is a git conflict.

### 6.1 ⚠️ Two worktrees, one Postgres — the worst one

`tests/repositories/postgres/conftest.py:32-37` calls `Base.metadata.drop_all(engine)` on both
setup *and* teardown, against `DATABASE_URL` defaulting to
`postgresql://app:app@localhost:5432/stockdep`.

Two worktrees running `make test` at the same time **drop each other's tables mid-run.** You
get bizarre, non-reproducible failures that look like flaky tests and aren't.

**Fix — one database per worktree, same container:**

```bash
docker compose up -d db
docker compose exec db psql -U app -c "CREATE DATABASE stockdep_p3api;"
docker compose exec db psql -U app -c "CREATE DATABASE stockdep_p3ui;"
```

Then in each worktree's own `.env` (already gitignored, so it never conflicts):

```
DATABASE_URL=postgresql://app:app@localhost:5432/stockdep_p3api
```

The conftest reads `DATABASE_URL` from the environment, so this needs no code change. **Do this
before the first parallel wave, not after the first mystery failure.**

### 6.2 ⚠️ Alembic revision forking

`alembic.ini:2` → `script_location = migrations`, currently one revision
(`ecf9be0d7993_initial_schema_companies_prices.py`). Two worktrees each running
`alembic revision --autogenerate` both set `down_revision = 'ecf9be0d7993'` → two heads →
`alembic upgrade head` fails in CI *and* in `cd.yml`'s migrate step, which gates production
deploys.

Git merges both files cleanly. Nothing warns you until deploy.

**Fix — exactly one migration author per wave.** The seam commit writes the migration; no
worktree runs `alembic revision` afterwards. If two heads happen anyway,
`alembic merge -m "merge heads" <rev1> <rev2>` resolves it, but treat that as a process failure,
not a routine step.

### 6.3 ⚠️ Port collisions

Both hardcoded, both will fail:
- `frontend/playwright.config.ts:16` — `npm run dev -- --port 4321 --strictPort`. `--strictPort`
  means the second worktree hard-errors rather than silently drifting. (Good — visible failure.)
- `docker-compose.yml` — API on `8000`, Postgres on `5432`.

**Fix:** only one worktree runs Playwright or `make up` at a time, or override ports per
worktree. Simplest is to designate the frontend worktree as the only one that runs e2e.

### 6.4 Lockfiles

`frontend/package-lock.json` (and `pyproject.toml`) conflict badly and resolve tediously.

**Fix:** one worktree per wave is the designated dependency-adder. If a second worktree needs a
package, it goes in the seam commit or waits. On conflict, don't hand-merge — take one side and
re-run `npm install`.

### 6.5 The small append-only files

Genuine conflicts, but trivial ones — and the seam commit eliminates all of them:

| File | Why every phase touches it |
|---|---|
| `src/api/main.py` (~line 91) | the router include tuple — one line, every new router |
| `src/api/deps.py` | one provider function per new repository |
| `src/cli.py` | one command per new job |
| `src/repositories/base.py` | one Protocol per new repository |
| `src/domain/models.py` | new pydantic models |
| `frontend/src/routes.tsx` | 17 lines total; every new page adds an import + a `<Route>` |
| `frontend/src/types/domain.ts` | the shared API contract |

### 6.6 Per-worktree environment setup

Not a conflict, just cost — worth knowing before you commit to five worktrees:

```bash
git worktree add ../stockdep-p3api -b phase3/portfolio-api
cd ../stockdep-p3api
python -m venv venv && source venv/bin/activate
make dev-install                    # ~2-3 min; editable install is path-specific,
                                    # so venvs CANNOT be shared between worktrees
cd frontend && npm ci               # ~1 min
cp ../stock_dependency_tracker/.env .env   # then edit DATABASE_URL per §6.1
```

`venv/` and `frontend/node_modules/` are both gitignored, so each worktree starts empty.
Budget ~5 minutes of setup per worktree. Across five worktrees that's real, but it's a one-time
cost against weeks of work.

---

## 7. Scoping the agents

Each worktree gets its own long-running `claude` session. The scoping rule that matters most:

> **Give the agent an explicit do-not-touch list.** Models are helpful by default and will
> happily "fix" the router registration or add the missing type — which is exactly the edit
> that creates the conflict.

A workable prompt shape for `wt-p3-api`:

```
You are working in a git worktree on branch phase3/portfolio-api.
Scope: the BACKEND half of Phase 3 in docs/progress_impl_docs/track-a-product-plan.md.

Build:
  src/analysis/portfolio.py          pure math, no I/O
  src/services/portfolio_service.py  orchestration
  src/api/routers/portfolio.py       replace the 501 stubs with real handlers
  tests/ for all of the above

DO NOT EDIT — these were finalised in the seam commit and another
worktree depends on them being stable:
  src/api/main.py, src/api/deps.py, src/domain/models.py,
  src/repositories/base.py, migrations/**, anything under frontend/

If you believe one of those files must change, STOP and tell me why
instead of editing it.

Gate: `make check` must pass before you report done.
```

Two more rules:

- **`make check` is the contract.** It's what CI runs (`.github/workflows/ci.yml` calls the same
  targets), so an agent that passes it locally will pass CI. Make every agent run it before
  reporting done.
- **One agent per worktree, not several.** Two agents in one worktree race on the working tree
  and produce interleaved half-edits. The worktree *is* the isolation unit.

---

## 8. Merge order

Merge **backend before frontend**, always. The frontend branch was built against 501 stubs; if
the backend lands first, the frontend PR's CI runs against real endpoints and catches contract
drift. The other order tests nothing.

Per wave:

```
1. seam commit                → main   (before any fan-out)
2. wt-*-api                   → main   (backend first)
3. rebase wt-*-ui on main, re-run `make check` + `npm run test`
4. wt-*-ui                    → main
5. git worktree remove ../stockdep-*   (cleanup — stale worktrees drift badly)
```

Step 3 is where contract drift surfaces. Do it deliberately rather than discovering it in the
merge.

---

## 9. When to skip worktrees entirely

Worth stating plainly, because the setup cost is real:

- **Phase 1 and Phase 2** — single worktree. Splitting a one-week, tightly-coupled phase costs
  more in coordination than it saves in wall-clock.
- **Any phase you're building solo and sequentially anyway.** Worktrees pay off when work
  genuinely happens at the same time. If you're reviewing one agent's output at a time, plain
  branches are simpler and you lose nothing.
- **Anything needing a schema change mid-flight.** If the migration isn't settled, one worktree
  until it is.

The pattern that gives most of the benefit for a fraction of the cost: **seam commit + two
worktrees (BE/UI), only on Phases 3 and 4.** That's four worktrees total across Track A, and
it captures nearly all the available parallelism.

---

## 10. Summary

1. **Don't** split by phase. The dependency graph is a star out of Phase 1, and parallel work
   across a data-dependency produces code that merges cleanly and doesn't work.
2. **Do** split by layer — backend vs frontend — inside Phases 3 and 4, plus Tier 0's three
   independent chores.
3. **Always** land a seam commit first: migration, models, Protocol, router registration, route,
   types. It's ~150 lines and it *is* the phase's entire conflict surface.
4. **Fix §6.1 before the first parallel wave.** One Postgres database per worktree. The test
   fixture drops tables on setup and teardown, and two worktrees sharing a database will
   destroy each other's runs in a way that looks like flaky tests.
5. **One migration author per wave.** Alembic head-forking merges cleanly in git and fails at
   deploy time, which is the worst combination.
6. Merge backend → rebase frontend → merge frontend. Then remove the worktree.
