# Track A: Making This a Real Product — Complete Plan

**Purpose:** A detailed, architecture-first plan for executing Track A — the path that transforms the stock correlation app from an interesting prototype into a genuinely useful product.

**Scope:** Tier 0 → Precomputed correlations → Scheduled jobs → Portfolio analysis → Regime surfacing.

**Duration estimate:** 6–8 weeks for the full track at a sustainable pace.

---

## Executive Summary

The app today is **analytically rich but operationally thin.** Every graph request recomputes correlations from scratch, nothing runs on a schedule, and the product doesn't tell a user anything about *their* situation.

Track A fixes all three. A precomputed correlations table written by a scheduled job makes cold starts fast (unlocking the biggest performance lever); a portfolio concentration feature answers "so what?" — the question that converts an interesting visualisation into a tool someone actually uses; regime break surfacing gives the app **news value**, a reason to return.

The sequence is non-arbitrary: each phase builds on and unlocks the next. The architecture pattern (write-path separation, table-driven queries, domain-driven modeling) appears in every phase and makes future features cheap to add.

---

## 1. The Complete Roadmap

```
┌─────────────────────────────────────────────────────────────────┐
│ TIER 0: Finish what's in flight                                │
│ • Merge Sentry + frontend-tests PRs                            │
│ • Add frontend job to ci.yml                                   │
│ • Wire Sentry on the frontend                                  │
│ • Fix stale doc links in root README                           │
│ Timeline: 1–2 weeks (mostly review + merges)                   │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Precomputed Correlations (§3.1)                       │
│ Write path: Daily job computes & stores                        │
│ Read path: API serves stored rows (fast)                       │
│ User impact: Cold starts are now instant, not slow             │
│ Timeline: 2–3 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: Scheduled Jobs (§3.2)                                 │
│ • Daily: refresh prices, recompute correlations                │
│ • Weekly: rebuild universe (currently static)                  │
│ User impact: Data is never stale; the app has a heartbeat      │
│ Timeline: 1–2 weeks (building on Phase 1)                      │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Portfolio Concentration Analysis (§4.1)               │
│ NEW FEATURE: Paste holdings → learn about concentration         │
│ • Aggregate holdings against the correlation graph             │
│ • Visualise factor exposure (pie, scatter, heatmap)           │
│ • Persist? Client-side only for v1 (no auth needed)           │
│ User impact: The app tells you something about YOUR money      │
│ Timeline: 3–4 weeks (design + backend + frontend)             │
└─────────────────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: Regime Break Surfacing (§4.4)                         │
│ NEW FEATURE: Feed of "what changed" — regime breaks            │
│ • Surface correlations that weakened significantly             │
│ • Foundation for future alerts (Phase 5b)                      │
│ User impact: Weekly check-in habit forming                     │
│ Timeline: 2 weeks (mostly query + UI)                          │
└─────────────────────────────────────────────────────────────────┘

Total: ~10–12 weeks for the complete Track A.
```

---

## 2. The User's Journey — Before and After

### BEFORE (Current)

```
User visits the app
  → Sees the graph (loading… slow)
  → Picks different anchors to explore
  → Graphs become faster as caches warm
  → Closes the app; comes back next week with no reason to
```

**Friction:** Cold starts are slow. The app is a toy, not a tool.

### AFTER (Track A Complete)

```
User visits the app
  → Sees the graph instantly (served from correlations table)
  → Pastes their holdings: AAPL, MSFT, ASML
  → Discovers: "65% of your portfolio moves with NVDA"
  → Sees a "Regime Changes" feed: TSM ↔ ASML weakened 0.2 this week
  → Creates a mental model: supply-chain exposure
  → Comes back next week to watch the regime feed, check for portfolio shifts
```

**Transformation:** From exploration toy → decision-making tool.

---

## 3. Phase-by-Phase Detail

### Phase 1: Precomputed Correlations

#### Goal
Move correlations off the request path into a table written by a nightly job.

#### User workflows
- **No user-facing change yet.** Same graph, same interactions — just instant.
- The win is invisible: page loads in <500ms instead of 2–5s.

#### Technical approach

**Backend:**
1. Add a `correlations` table to Postgres:
   ```sql
   CREATE TABLE correlations (
       anchor VARCHAR NOT NULL,
       satellite VARCHAR NOT NULL,
       lookback_days INT NOT NULL,
       computed_at TIMESTAMP NOT NULL,
       
       pearson_r FLOAT,
       partial_r FLOAT,
       stability_score FLOAT,
       best_lag INT,
       lag_correlation FLOAT,
       regime_break BOOLEAN,
       
       PRIMARY KEY (anchor, satellite, lookback_days, computed_at)
   );
   CREATE INDEX ON correlations (computed_at DESC);
   ```

2. Refactor `CorrelationService.rank_with_full_diagnostics()` to accept an optional `correlations_df` 
   parameter. When present, it returns cached results; when absent, it computes live (for `force_refresh`).

3. New `CorrelationRepository` method: `get_or_compute_latest(anchor, satellite)` — checks the 
   table first, falls back to live computation only if missing/stale.

4. New scheduled job (run nightly):
   ```python
   def compute_all_correlations():
       for anchor in config.anchors:
           result = correlation_service.rank_with_full_diagnostics(anchor)
           correlations_repo.upsert_batch(anchor, result.satellites)
   ```

**Frontend:**
- No change. The API response shape is identical; queries are just faster.

#### Performance & extensibility
- **Performance:** Graph loads in <500ms (Postgres query) vs. 5–30s (computation). Cold starts are 
  instant even on free-tier Render.
- **Extensibility:** The `correlations` table now holds a point-in-time snapshot. Phase 4 (regime 
  surfacing) and future features read from it. The table is the seam.
- **Modularity:** `CorrelationRepository` is new and isolated; the service layer (CorrelationService) 
  is unchanged in its public interface.

#### Milestones
1. Schema migration (1 day)
2. `CorrelationRepository` + upsert logic (2 days)
3. Scheduled job scaffolding (1 day)
4. Testing + backfill (2 days)
5. Deploy to Render (1 day)

**Total: ~1 week**

---

### Phase 2: Scheduled Jobs

#### Goal
Two independent scheduled jobs on different cadences: daily price refresh + correlation recompute, 
weekly universe rebuild.

#### User workflows
- **Still no user-facing change.** But data is never stale.
- A user's portfolio analysis is always against the latest prices and correlations.

#### Technical approach

**Backend:**
1. Render Cron Jobs are the platform. Two declarations in `render.yaml`:
   ```yaml
   jobs:
     - name: daily-correlation-recompute
       schedule: "0 16 * * *"  # 4 PM UTC (after market close)
       command: python -m src.cli daily-jobs
     
     - name: weekly-universe-rebuild
       schedule: "0 2 * * 1"    # Monday 2 AM UTC
       command: python -m src.cli weekly-jobs
   ```

2. New CLI entry points:
   ```python
   @cli.command("daily-jobs")
   def daily_jobs():
       """Refresh prices & recompute correlations."""
       correlation_service.prefetch_prices(
           config.anchors + universe, 
           force_refresh=True
       )
       for anchor in config.anchors:
           result = correlation_service.rank_with_full_diagnostics(anchor)
           correlations_repo.upsert_batch(anchor, result.satellites)
   
   @cli.command("weekly-jobs")
   def weekly_jobs():
       """Rebuild the satellite universe (Phase 7 prep)."""
       # Currently a no-op; Phase 7 wires a screener here
       pass
   ```

3. Logging & monitoring:
   - All jobs log to stdout; Render captures them in the service logs.
   - Sentry integration captures any exceptions automatically.

**Frontend:**
- No change. Queries serve fresher data, transparently.

#### Performance & extensibility
- **Performance:** Yahoo API is now throttled intelligently (once daily, off-peak). The `prefetch_prices` 
  pattern from Phase 4.8 ensures one pass over the price table instead of per-anchor fetches.
- **Extensibility:** New jobs are just new CLI commands. The pattern scales to weekly/monthly/on-demand 
  jobs without architectural change.
- **Modularity:** Jobs are stateless and can be paused/skipped without affecting the app. The table 
  is the state holder, not the job.

#### Milestones
1. Render Cron Job declarations in `render.yaml` (1 day)
2. `daily-jobs` CLI command (1 day)
3. `weekly-jobs` scaffolding (1 day)
4. Monitoring + alerting (Sentry, logging) (1 day)
5. Deploy & validate (1 day)

**Total: ~1 week**

---

### Phase 3: Portfolio Concentration Analysis

#### Goal
User uploads holdings → app shows factor exposure and concentration risk.

#### User workflows

**New flow:**
1. User visits the app (graph loads instantly thanks to Phase 1).
2. User clicks a new "+ Analyze my portfolio" button in the graph view.
3. A modal opens: "Paste your holdings (one per line, e.g., AAPL, MSFT, TSM)".
4. User pastes:
   ```
   AAPL 100 shares
   MSFT 50 shares
   ASML 25 shares
   TSM 10 shares
   SAT_HIGH 100 shares
   ```
5. App computes:
   - Total portfolio value (stub: equal-weight for v1, or try to infer share prices)
   - Each holding's correlation to the anchors
   - Aggregate factor exposure: "65% of portfolio correlates with NVDA"
6. A new "Your Portfolio" view shows:
   - **Concentration pie chart** — what % of variance is driven by NVDA, AAPL, TSM, etc.
   - **Factor heatmap** — your holdings vs. anchors, colored by correlation strength
   - **Risk summary** — "Your top 3 exposures: [factor 1], [factor 2], [factor 3]"
7. User can export as CSV or take a screenshot.
8. **No persistence.** Holdings are client-side only. Refresh = data is gone. (Auth comes later in Phase 5b if they want to save.)

#### Technical approach

**Backend:**
1. New endpoint: `POST /api/portfolio/analyze`
   - Input: list of `{ticker: string, shares: number}` (or just tickers, assume equal weight)
   - Output: aggregated factor exposure + correlation matrix + summary stats
   ```python
   @router.post("/analyze")
   def analyze_portfolio(holdings: PortfolioInput) -> PortfolioAnalysisResponse:
       """
       Compute factor exposure for a user's holdings.
       
       - Fetch correlations for each holding vs. each anchor
       - Weight by position size
       - Aggregate into factor exposure vector
       - Compute variance attribution
       """
       # Get correlations from the correlations table (Phase 1)
       correlations = correlations_repo.get_latest_by_date()
       
       exposure = compute_factor_exposure(holdings, correlations)
       return PortfolioAnalysisResponse(
           concentration_by_factor=exposure,
           risk_summary=summarize_risks(exposure),
           correlation_matrix=build_matrix(holdings, correlations)
       )
   ```

2. New services:
   - `PortfolioService.compute_factor_exposure()` — aggregates holdings against correlation table
   - `PortfolioService.variance_attribution()` — Cholesky decomposition or PCA for factor rank

3. No database writes; no auth. The analysis is transient.

**Frontend:**
1. New components:
   - `<PortfolioModal>` — paste holdings, display summary
   - `<ConcentrationChart>` — pie chart of factor exposure
   - `<CorrelationHeatmap>` — holdings vs. anchors grid
   - `<FactorExposureCard>` — summary stats + risk summary

2. New route: `/portfolio` (or modal overlay on `/`).

3. UX flow:
   ```
   Graph view
     → "+ Analyze my portfolio" button (top-right, next to theme toggle)
     → Modal: paste holdings
     → Results panel: concentration pie + heatmap + summary
     → "Export as CSV" / "Take screenshot" buttons
     → Close to return to graph
   ```

#### Performance & extensibility
- **Performance:** Portfolio analysis is O(n_holdings × n_anchors), all from memory (the correlations 
  table is already loaded). Latency <100ms.
- **Extensibility:** The `PortfolioService` is independent. Future phases (Phase 5b: saved portfolios, 
  alerts on regime breaks) just add `portfolio_id` and persistence. The analysis logic is unchanged.
- **Modularity:** The portfolio feature doesn't touch the graph or correlation engine. It's a new 
  leaf-node view.

#### Milestones
1. Backend endpoint + PortfolioService (3 days)
2. Frontend components + modal UX (3 days)
3. Export (CSV, screenshot) (1 day)
4. Testing + edge cases (1 day)
5. Deploy (1 day)

**Total: ~3 weeks**

---

### Phase 4: Regime Break Surfacing

#### Goal
A "What Changed" feed showing correlations that weakened significantly.

#### User workflows

**New feed view:**
1. User visits the app.
2. New "What's Changed" tab (or feed icon) appears in the top nav.
3. User clicks → sees a feed of regime breaks from the past week:
   ```
   📉 TSM ↔ ASML weakened
       Correlation dropped 0.23 (was 0.82, now 0.59)
       Supply-chain headwind?
       2026-08-14
   
   📈 NVDA ↔ MSFT strengthened
       Correlation rose 0.15 (was 0.65, now 0.80)
       AI adoption cycle?
       2026-08-13
   
   ⚠️  AAPL ↔ Energy sector decoupled
       Correlation fell below significance threshold
       2026-08-10
   ```
4. User reads the feed, updates their mental model of sector relationships.
5. Habituation: returns weekly to check for new regime breaks.

#### Technical approach

**Backend:**
1. New table: `correlation_changes` (or use the `correlations` table with temporal queries):
   ```sql
   -- Add to correlations table OR create new:
   CREATE TABLE correlation_changes (
       anchor VARCHAR,
       satellite VARCHAR,
       date DATE,
       correlation_now FLOAT,
       correlation_week_ago FLOAT,
       delta FLOAT,
       regime_break BOOLEAN,
       
       PRIMARY KEY (anchor, satellite, date)
   );
   ```

2. Nightly job computes regime breaks:
   ```python
   def detect_regime_breaks():
       """Compare this week's correlations to last week's."""
       current = correlations_repo.get_by_date(today)
       previous = correlations_repo.get_by_date(today - 7 days)
       
       breaks = []
       for anchor, satellite in current.items():
           r_now = current[anchor][satellite]
           r_prev = previous[anchor][satellite]
           delta = r_now - r_prev
           
           if abs(delta) > REGIME_BREAK_THRESHOLD:  # e.g., 0.15
               breaks.append({
                   'anchor': anchor,
                   'satellite': satellite,
                   'delta': delta,
                   'now': r_now,
                   'then': r_prev,
                   'date': today,
               })
       
       correlation_changes_repo.insert_batch(breaks)
   ```

3. New endpoint: `GET /api/regime-breaks?days=7`
   - Returns sorted list of recent breaks, strongest first
   - Include explanatory tags: "strengthened", "weakened", "decoupled"

**Frontend:**
1. New route: `/regime-breaks` (or tab in graph view).
2. New component: `<RegimeBreaksFeed>` — renders the list, color-codes by delta.
3. Optional: sentiment analysis or thematic tags ("supply-chain", "AI", "energy", etc.) for narrative.

#### Performance & extensibility
- **Performance:** Query is a simple date range scan over the changes table. <50ms.
- **Extensibility:** This is the foundation for:
  - Phase 5b: Email alerts on regime breaks ("Your holdings were affected")
  - Phase 5b: Watchlists (track specific anchor pairs)
  - Future: anomaly detection (machine learning on regime-break patterns)
- **Modularity:** The feed is read-only and independent. No cross-cutting concerns.

#### Milestones
1. `correlation_changes` table + nightly job (2 days)
2. Backend endpoint (1 day)
3. Frontend feed component (2 days)
4. Testing + narrative tags (1 day)
5. Deploy (1 day)

**Total: ~2 weeks**

---

## 4. Architecture Patterns & Principles

### The Write/Read Separation Pattern

Every phase follows this:

```
WRITE PATH (Scheduled, off-request)
  │
  ├─ Fetch fresh data (prices, universe, correlations)
  ├─ Compute analytically
  └─ Upsert into a durable table
       │
SHARED STATE TABLE (Postgres)
       │
       └─ Indexed on query key + timestamp
           │
READ PATH (On-request, fast)
  │
  ├─ Query the table
  ├─ Return instantly
  └─ Never compute on the request path
```

This pattern appears in every phase:
- **Phase 1:** correlations table written nightly, read on every graph request.
- **Phase 2:** Prices table kept warm by daily job.
- **Phase 3:** Same correlations table, now queried by portfolio analysis.
- **Phase 4:** Correlation changes table, written nightly, read by the regime-breaks feed.

**Benefits:**
- Decouples freshness cadence from request path (can update on different schedules).
- Makes read queries predictable and fast (always from a table, never computed live).
- Enables time-travel queries (Phase 2 bonus: historical regime breaks).
- Scales to multiple replicas (Phase 7+: write once, read everywhere).

### Modularity Through Domain-Driven Layers

```
┌─────────────────────────┐
│ Views / Pages           │  (Graph, Portfolio, Regime Breaks)
├─────────────────────────┤
│ API Routers             │  (graph, portfolio, regime_breaks)
├─────────────────────────┤
│ Services                │  (CorrelationService, PortfolioService,
│ (business logic)        │   RegimeSurfaceService)
├─────────────────────────┤
│ Repositories            │  (CorrelationRepository,
│ (data access)           │   CorrelationChangesRepository)
├─────────────────────────┤
│ Postgres Tables         │  (correlations, correlation_changes,
│ (durable state)         │   prices, companies)
└─────────────────────────┘
```

Each layer has **one responsibility** and talks to the layer below via a well-defined interface:
- **Services** don't know about HTTP; they know about domain concepts (factor exposure, regime breaks).
- **Repositories** are data-access abstractions; they swap yfinance → Postgres without changing services.
- **Routers** are marshalling layers; they translate HTTP request/response to/from service signatures.

**This makes the codebase:**
- **Testable:** Mock a service to test a router; mock a repo to test a service.
- **Extensible:** A new feature (e.g., alerts) adds a new service, reusing existing repos.
- **Maintainable:** A bug in portfolio math is isolated to `PortfolioService`, not scattered across views and routers.

### Extensibility Anchors (Planned)

As each phase lands, it creates **extension points** for future work:

| Phase | Table | Extension | Example (Future) |
|---|---|---|---|
| 1 | `correlations` | Time-travel | "View the graph as it stood on 2026-01-01" (Phase 2 bonus) |
| 2 | (prices, correlations) | Alerts | "Email me when NVDA ↔ ASML decouples" (Phase 5b) |
| 3 | (none — client-side v1) | Persistence | Save portfolios to a `user_portfolios` table (Phase 5b auth) |
| 4 | `correlation_changes` | Scoring | ML model on regime-break patterns (post-launch) |

None of these require rearchitecting; they just populate new tables or add new routers.

---

## 5. Performance Targets & Budgets

### Request-Path Performance (Frontend)

| View | Current | Phase 1 | Phase 3 | Phase 4 |
|---|---|---|---|---|
| Graph load | 2–5s | <500ms | — | — |
| Portfolio analysis | N/A | N/A | <100ms | — |
| Regime-breaks feed | N/A | N/A | N/A | <200ms |

**How to hit these:**
- Graph: Postgres index on `correlations (computed_at DESC)` → one index scan.
- Portfolio: Correlation matrix already in memory (from graph query) → matrix multiply only.
- Regime breaks: Index on `correlation_changes (date DESC)` → range scan + sort.

### Write-Path Performance (Jobs)

| Job | Frequency | Target duration | Trigger |
|---|---|---|---|
| Daily correlation recompute | 1x/day, 4 PM UTC | <5 min | Render Cron |
| Weekly universe rebuild | 1x/week, 2 AM UTC | <10 min | Render Cron |

**How to hit these:**
- Phase 1 job: Compute 4 anchors × 55 satellites = 220 correlations in parallel (one per thread pool task) + batch upsert (1 SQL statement). Duration: ~2–3 min (yfinance bound).
- Phase 2 universe rebuild: Currently a no-op (static list). Phase 7 will screener-fetch ~2000 tickers; with batching and rate limiting, still <10 min.

### Postgres Capacity

| Table | Rows after 1 year | Index size | Query impact |
|---|---|---|---|
| `correlations` | ~250k (4 anchors × 55 satellites × 365 days) | ~50 MB | No impact; `basic-256mb` Postgres easily handles this. |
| `correlation_changes` | ~10k (major breaks only) | ~2 MB | Negligible. |
| `prices` | ~3M (55 + 4 anchors × 365 days) | ~100 MB | Already live and tested. |

**Scaling to Phase 7 (2000 tickers):** 
- `correlations` becomes ~250M rows (2000 × 2000 × 365), which needs **vertical scaling** (Render → production plan) or **horizontal archival** (move old dates offline). Not blocking Phase 3 or 4; design this when Phase 7 lands.

---

## 6. Implementation Sequence & Dependencies

```
Week 1–2: Tier 0 (merge & setup)
│
├→ Week 3–4: Phase 1 (precomputed correlations)
│  └─ Phase 2 (scheduled jobs) depends on Phase 1 ✓
│
├→ Week 5–7: Phase 3 (portfolio analysis)
│  └─ Depends on Phase 1 (correlations table readable)
│  └─ Independent of Phase 2 (jobs run; analysis works either way)
│
└→ Week 8–9: Phase 4 (regime breaks)
   └─ Depends on Phase 2 (historical correlations available)
   └─ Independent of Phase 3
```

**Critical path:** Tier 0 → Phase 1 → (Phase 2 parallel with Phase 3) → Phase 4.

**Non-blocking work (can parallelize):**
- While Phase 1 backend is being built (days 1–3 of week 3), do Phase 3 frontend design & UX flow.
- While Phase 2 jobs are being wired (days 1–2 of week 5), start Phase 4 table schema.

---

## 7. Key Technical Decisions

| Decision | Choice | Why |
|---|---|---|
| Precomputation storage | Postgres `correlations` table, not Redis | Durable, queryable, time-indexed; survives cold starts; Phase 7-ready. |
| Job scheduler | Render Cron Jobs, not external (Temporal, Dagster) | Simplest; runs in the same container, same env, same Sentry. Scales to Phase 7 (weekly jobs). |
| Portfolio persistence | Client-side (v1), database + auth (Phase 5b) | Reduces auth/design scope now; table schema already designed (just not wired). |
| Regime-break detection | Threshold on weekly delta, not statistical | Transparent; no ML black box; easy to tune; extensible later. |

---

## 8. Success Criteria & Rollout Plan

### Phase 1 (Precomputed correlations)

**Success:** Graph loads <500ms cold start, even on a spun-down free-tier instance.

**Rollout:**
1. Deploy to a `dev` branch on Render (separate service, same code).
2. Smoke test: hit `/api/graph`, confirm Sentry latency is <500ms.
3. Merge to `main`, trigger `cd.yml`, watch the deploy.
4. Monitor: Sentry performance dashboard for 48 hours. Alert if >1s p99.

### Phase 3 (Portfolio analysis)

**Success:** Users can paste 5–10 holdings and see concentration breakdown in <100ms.

**Rollout:**
1. Deploy to dev branch.
2. Manual testing: paste various portfolios (single holding, equal-weight, skewed weight), verify math correctness (concentration percentages sum to 100%, heatmap correlations match API).
3. Load test: 100 concurrent portfolio analyses, confirm <200ms p99.
4. Merge to `main`.
5. Monitor: Sentry error rate for portfolio endpoint, feature adoption (via page views on `/portfolio`).

### Phase 4 (Regime breaks)

**Success:** Feed displays 1–3 regime breaks per week with correct delta calculations.

**Rollout:**
1. Deploy to dev. Run nightly job, inspect `correlation_changes` table for correctness (deltas are reasonable, no duplicates).
2. Frontend smoke test: open `/regime-breaks`, confirm feed renders, deltas are non-zero and sensible.
3. Merge to `main`.
4. Monitor: Feed page views (adoption signal), error rate on the endpoint.

---

## 9. Coherence & Long-term Scalability

### Why this design "holds together"

1. **One source of truth per fact:**
   - Correlations: `correlations` table (single point of update).
   - Regime breaks: derived table (correlations diff), computed once nightly.
   - Portfolios: client-side v1, then user-persisted (Phase 5b), never both.

2. **Interfaces don't leak implementation:**
   - `CorrelationService.rank_with_full_diagnostics()` works the same whether backed by live computation or precomputed table.
   - `PortfolioService` doesn't care if correlations came from yesterday or live; it reads from one endpoint.
   - New features add new routers/services; they don't rewrite existing ones.

3. **The data model is future-proof:**
   - `correlations(anchor, satellite, computed_at)` can be queried as-of-date without schema change.
   - `correlation_changes` can have arbitrary metadata columns (sentiment tags, explanatory text) without breaking existing queries.
   - Portfolio table (when Phase 5b adds it) is just `(user_id, ticker, shares, created_at)` — orthogonal to existing tables.

### Scaling to Phase 7 (dynamic universe)

Once the universe grows to 2000+ tickers:
1. Correlations table goes 250M rows → archive old dates to S3 / cold storage.
2. Daily job becomes **two-stage funnel:** cheap Pearson pre-filter → full diagnostics only on shortlist.
3. FDR correction activates automatically (spurious-correlation explosion needs it).
4. Portfolio analysis still <100ms (matrix multiply is O(anchors²), not O(universe²)).
5. Regime breaks still fast (index scan + threshold filter, size-independent).

**No feature needs rearchitecting.** The patterns from Track A scale.

---

## 10. Effort & Timeline Summary

| Phase | Duration | Team | Effort/person |
|---|---|---|---|
| Tier 0 | 1–2 weeks | 1 | Low (review/merge) |
| Phase 1 | 2–3 weeks | 1–2 | Med (schema/job/test) |
| Phase 2 | 1–2 weeks | 1 | Low (Cron wiring) |
| Phase 3 | 3–4 weeks | 1 BE, 1 FE (parallel) | Med (design/build/test) |
| Phase 4 | 2 weeks | 1 BE, 1 FE (parallel) | Low-Med (query/feed) |
| **Total** | **10–12 weeks** | Solo OK | **Doable as solo dev** |

**Parallelization:** Phases 2 & 3 can overlap (independent features, same correlations table). Phase 4 can start week 7 while Phase 3 is finishing. Realistic solo timeline: 10–12 weeks at sustainable pace (20–25 hrs/week).

---

## 11. Open Questions for the Product

1. **Portfolio persistence:** Release v1 client-side only, or invest in user accounts + saved portfolios from day 1?
   - Recommendation: v1 client-side. Revisit Phase 5b if adoption warrants.

2. **Regime-break notifications:** Email alerts from day 1, or just the feed?
   - Recommendation: Feed first (proves the feature is valuable). Alerts (Phase 5b) once users are checking the feed weekly.

3. **Factor exposure metrics:** Concentration pie only, or also variance decomposition / PCA?
   - Recommendation: Pie chart only for v1. PCA as an opt-in "advanced mode" post-launch if demand appears.

4. **Historical regime breaks:** Go back 1 month, 1 year, or all-time?
   - Recommendation: 1 month for v1 (fresh, not overwhelming). Archive & searchable past (Phase 7).

---

## 12. Appendix: Deployment & Monitoring Checklist

Before each phase ships:

- [ ] `make check` passes (lint, format, types, tests).
- [ ] New tables have migrations (Alembic) + indexes.
- [ ] New jobs have Sentry integration + error alerting.
- [ ] New endpoints have request/response documentation.
- [ ] New frontend pages load <2s on a 3G connection (Lighthouse audit).
- [ ] Postgres query plans reviewed (no sequential scans, index hits confirmed).
- [ ] Load test passed (concurrent requests, sustained for 5 min).
- [ ] Render deploy runs without manual shell steps (everything in `cd.yml`).
- [ ] Monitoring is in place: Sentry performance, endpoint error rate, job success rate.

---

## Conclusion

Track A is **not a list of features; it's a coherent architecture** that builds on itself. Phase 1 makes the app fast; Phase 2 keeps it fresh; Phase 3 makes it useful; Phase 4 makes it sticky.

The design **scales**: the same write/read separation pattern holds at 55 tickers and 2000. The same layer architecture (domain services → data repositories → Postgres) absorbs Phase 5b (user accounts), Phase 7 (dynamic universe), and whatever comes after.

**Start with Tier 0 + Phase 1. Ship by week 4. Then reassess** — is the market moving? Are users coming back? Use that signal to prioritize Phase 3 (portfolio) vs. other post-launch ideas.
