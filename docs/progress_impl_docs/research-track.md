# Research Track — Portfolio Correlation Workspace

**What this is.** A design document for the feature that comes *after* Track A is complete
and auth exists: a **Research page** where a user can inspect the internal correlation
structure of their own portfolio over time, build a **draft portfolio**, and **compare** the
draft against what they actually hold.

**Where it sits.** This is the natural continuation of
[next-steps.md](next-steps.md) §4.2 (time-travel) and §4.3 (explain-this-edge), applied to a
portfolio rather than to a single anchor–satellite edge. It assumes
[track-a-product-plan.md](track-a-product-plan.md) has shipped in full.

**Status.** Proposal. Nothing here is built. §9 is a list of decisions I need from you
before this is implementable — several of them change the shape of the work substantially,
so please read that section even if you skim the rest.

---

## 0. Hard prerequisites

This feature is not buildable in isolation. It needs, in order:

| Prerequisite | From | Why it's load-bearing here |
|---|---|---|
| `correlations` table + write path | Track A Phase 1 | The read path must be a table lookup; live N×N computation per keystroke is not viable |
| Scheduled jobs | Track A Phase 2 | Draft analysis is only trustworthy if the underlying prices are current |
| Portfolio input + concentration analysis | Track A Phase 3 | This feature is the *deep* version of that shallow one; the parsing, ticker resolution, and exposure math get reused |
| **Auth + persisted portfolios** | Phase 5b | You cannot compare a draft to "your existing portfolio over time" without storing the existing portfolio. This is the prerequisite that Track A explicitly deferred |

The auth dependency is the important one. Track A Phase 3 takes a deliberate position —
holdings are client-side only, nothing persisted, "paste it, read it, refresh and it's gone."
That position is a genuine privacy feature, and this document **reverses it**. §7 covers what
that costs and what has to be true before it's acceptable.

---

## 1. The idea, restated precisely

Three capabilities, which are more different from each other than they first appear:

1. **Inspect** — for the portfolio I hold, show me the correlation structure *among my own
   holdings*, and how it has changed over time.
2. **Draft** — let me build a hypothetical portfolio (add, remove, reweight) and see the same
   analysis for it.
3. **Compare** — put the two side by side and tell me what actually changed.

### 1.1 What is genuinely new here

Everything the app currently computes is **anchor → satellite**: a star topology, one hub
against many spokes, `1 × N` correlations per anchor. `GET /api/graph/relatedness`
(`src/api/routers/graph.py:31`) is the one existing exception — it produces an anchor×anchor
matrix, and it is the closest existing precedent for what this feature needs.

A portfolio is **not** a star. The interesting question about a portfolio is the **complete
pairwise graph among its holdings** — `N × N`, no hub. "How correlated is AAPL with NVDA"
is a question the current schema can answer only if one of them happens to be an anchor.
For a user holding AAPL, MSFT, JPM, and XOM, the `correlations` table proposed in Track A
Phase 1 — keyed `(anchor, satellite)` — contains **zero** of the six pairs they care about.

> **This is the single most consequential finding in this document, and it has a deadline.**
> The Track A Phase 1 schema should be designed as a **symmetric pair table** keyed
> `(ticker_a, ticker_b)` with a canonical ordering (`ticker_a < ticker_b`), not as
> `(anchor, satellite)`. Anchor–satellite rows are then just the subset where one side is an
> anchor. Doing this now costs approximately nothing. Doing it later is a migration plus a
> rewrite of every query and every serializer that touches correlations.
> **Details in §4.1.**

### 1.2 Second thing that's new: time is now an axis, not a filter

"Correlations over time" for a portfolio is a materially harder problem than time-travel on
a single graph (§4.2 in next-steps). A 12-holding portfolio has 66 pairs. Over 250 trading
days that's 16,500 numbers. There is no chart that shows that. **The summarization question
is the design problem** — §2 is entirely about it, and it's where most of the intellectual
work of this feature lives.

---

## 2. The analytical core

### 2.1 The summarization problem

You cannot plot 66 rolling correlation lines. The options, in increasing order of how much I
think they're worth:

| Approach | What it shows | Verdict |
|---|---|---|
| 66 overlaid lines | Nothing. Spaghetti. | No |
| Mean pairwise correlation over time | One line: "is my portfolio moving as one thing?" | Yes — the baseline |
| Animated heatmap on a date scrubber | Structure changing, visually | Yes — reuses §4.2's slider |
| Top-K most-changed pairs, small multiples | The specific relationships that moved | Yes — this is the "so what" |
| **Absorption ratio over time** | Share of total variance in the first principal component | **Yes — this is the headline metric** |

### 2.2 The four metrics worth computing

These are the numbers I'd build the page around. All four are standard, all four are
computable from a returns matrix with no new data, and all four have a plain-English reading.

**1. Mean pairwise correlation** — the average of the off-diagonal upper triangle.

> *"The average pair in your portfolio moves together at r = 0.61."*

Simple, honest, easy to explain. Also the crudest: it hides whether that 0.61 is "everything
is moderately linked" or "three clusters that are internally tight and mutually independent."

**2. Absorption ratio** — the share of total portfolio variance explained by the first
principal component of the correlation matrix.

> *"78% of your portfolio's day-to-day movement is one single factor."*

This is the headline. It is the standard systemic-risk / concentration indicator, it collapses
to one number per date so it charts cleanly over time, and it directly answers the question a
user actually has. When it rises, the portfolio is becoming one bet. Track A Phase 3's
concentration pie is the static, single-date version of this; the research page is where it
becomes a time series.

**3. Effective number of bets (ENB)** — the entropy or Herfindahl equivalent of the
eigenvalue distribution.

> *"You hold 14 positions. You have 3.2 independent bets."*

This is the line I'd expect a user to screenshot and send to someone. It's also the single
best summary for the **comparison** view: `existing: 3.2 → draft: 5.1` is a complete answer
in eleven characters. Definition needs pinning down (§9, Q6) — entropy-based
`exp(-Σ pᵢ ln pᵢ)` and Herfindahl-based `1/Σ pᵢ²` over normalized eigenvalues both work and
give different numbers.

**4. Risk contribution per holding** — each position's share of total portfolio variance,
weight-aware.

> *"ASML is 6% of your money and 19% of your risk."*

This is where **weights finally matter**. Correlation itself is weight-independent; portfolio
risk is not. This metric is the bridge between "here is the correlation structure" and "here
is what it means for you specifically," and it's the reason the weights question in §9 Q1 is
not a detail.

### 2.3 The framing this must not slip into

The four metrics above are **descriptive statistics about historical co-movement.** They are
not risk forecasts, and a lower number is not "better."

Two specific ways this feature can quietly become dishonest:

- **Correlations converge in crises.** A portfolio that looks well-diversified over a calm
  250-day window can be perfectly correlated in the two weeks that actually hurt. Historical
  low correlation is *weak* evidence of future diversification, and this feature will produce
  a number that looks like a promise. The UI has to say this, not just the docs. A
  crisis-period comparison (§9, Q8) is one concrete mitigation.
- **Estimation error at realistic N.** A 30-holding portfolio over 252 days is a 30×30
  matrix from 252 observations — `T/N ≈ 8.4`. At that ratio, sample eigenvalues are
  materially biased upward (Marchenko–Pastur), so the absorption ratio and ENB are both
  *systematically optimistic in the wrong direction*. **Ledoit–Wolf shrinkage** is the standard
  fix and I'd treat it as non-optional for portfolios above ~15 holdings — the same way
  next-steps §5.1 treats FDR correction as non-optional above ~2,000 tickers. Same category
  of problem: naive statistics that break silently at scale.

Both belong in the product, not just in a footnote.

---

## 3. User workflows

### 3.1 Flow A — Inspect an existing portfolio

```
  Research page (/research)
    │
    ├─ Portfolio selector: [ My Portfolio ▾ ]     (from Phase 5b persistence)
    │
    ├─ HEADLINE STRIP
    │    Absorption ratio  78%  ▲ 6pts vs 90d ago
    │    Effective bets    3.2  (of 14 positions)
    │    Mean pairwise r   0.61
    │
    ├─ TIME SERIES  ─────────────────────────────────────
    │    absorption ratio, rolling, with the date scrubber
    │    from §4.2 time-travel driving the panel below
    │
    ├─ CORRELATION HEATMAP  (as of the scrubber date)
    │    N×N, clustered, reusing RelatednessHeatmap
    │    click a cell -> §4.3 explain-this-edge drawer
    │
    └─ WHAT MOVED
         top-K pairs by |Δr| over the selected window
```

The date scrubber is the connective tissue: it drives the heatmap and the "what moved" list,
and it's the same control §4.2 introduces for the anchor graph. Building it once for both is
part of why this feature is cheaper than it looks.

### 3.2 Flow B — Build a draft

```
  [ + New draft ]  ──> starts from:  ( ) blank
                                     (•) copy of My Portfolio      <- default
    │
    ├─ EDITOR                          ├─ LIVE PREVIEW (debounced)
    │   AAPL   12%   [–]               │    Absorption  78% -> 71%
    │   MSFT   10%   [–]               │    Eff. bets   3.2 -> 3.9
    │   NVDA    8%   [–]               │    Mean r      0.61 -> 0.54
    │   + add ticker…                  │
    │   [normalize to 100%]            │    (metrics recompute ~300ms
    │                                  │     after typing stops)
    └─ [ Save draft ]  [ Compare → ]
```

Open design question: is a draft always *derived from* an existing portfolio (a diff you
apply) or an independent object (a blank slate)? I've drawn the derived version because the
comparison view is the point, but this is §9 Q3 and it changes the data model.

### 3.3 Flow C — Compare

```
  ┌── MY PORTFOLIO ──────────┐   ┌── DRAFT: "less semis" ───┐
  │ Absorption      78%      │   │ Absorption      71%  ▼7  │
  │ Effective bets  3.2      │   │ Effective bets  3.9  ▲   │
  │ Mean pairwise   0.61     │   │ Mean pairwise   0.54 ▼   │
  └──────────────────────────┘   └──────────────────────────┘

  DELTA HEATMAP        red = pair became more correlated
                       blue = pair became less correlated

  WHAT DRIVES THE DIFFERENCE
    – Removing AMAT and LRCX broke the 4-way semi-equipment cluster
      (those four averaged r = 0.83 with each other)
    + Adding XOM introduced the only holding with r < 0.2 to
      everything else you own

  BOTH PORTFOLIOS THROUGH TIME
    two absorption-ratio lines on one chart, 2019 -> today,
    with 2020-03 and 2022 shaded
```

The "what drives the difference" block is the hardest part to build and the most valuable.
It requires attributing a change in an aggregate metric to specific holdings — doable
(leave-one-out contribution to the absorption ratio is the straightforward version) but it is
real work, and it is the difference between a page that reports numbers and one that explains
them.

---

## 4. Architecture changes

### 4.1 Schema — the pair table (do this in Track A, not here)

**Instead of** the Track A Phase 1 sketch:

```
correlations(anchor, satellite, lookback_days, computed_at, ...)
```

**use:**

```
pair_correlations(
    ticker_a,          -- canonical: ticker_a < ticker_b, always
    ticker_b,
    as_of_date,        -- the date the window ENDS (point-in-time key)
    lookback_days,
    pearson_r,
    spearman_r,
    partial_r,         -- market-adjusted, vs ^GSPC
    stability_score,
    best_lag,
    lag_correlation,
    regime_break,
    computed_at,       -- provenance, distinct from as_of_date
    PRIMARY KEY (ticker_a, ticker_b, as_of_date, lookback_days)
)
```

Two changes from the Track A sketch, both load-bearing:

1. **Symmetric key.** `(ticker_a, ticker_b)` with enforced ordering rather than
   `(anchor, satellite)`. Anchor–satellite queries become
   `WHERE ticker_a = :anchor OR ticker_b = :anchor` — marginally more awkward, and worth it.
   Every pair the research page needs is now expressible in the same table.
2. **`as_of_date` separated from `computed_at`.** `as_of_date` is *what window this describes*;
   `computed_at` is *when we ran the job*. Conflating them makes backfills, recomputes, and
   point-in-time correctness ambiguous. Keeping them apart is what makes §4.2 time-travel and
   this feature's historical charts honest rather than approximate.

Everything else Track A Phase 1 does is unchanged. The write path, the job, the read path —
identical. This is a key-design decision, not a scope increase.

### 4.2 Schema — portfolios (Phase 5b territory)

```
users(id, email, created_at, ...)                    -- auth

portfolios(
    id, user_id, name, kind,                          -- kind: 'actual' | 'draft'
    parent_portfolio_id,                              -- drafts point at their source
    created_at, updated_at, deleted_at
)

holdings(
    portfolio_id, ticker, weight,                     -- see §9 Q1 on units
    PRIMARY KEY (portfolio_id, ticker)
)

portfolio_versions(                                   -- optional, see §9 Q4
    id, portfolio_id, snapshot_at, holdings_json
)
```

`kind` + `parent_portfolio_id` is what makes a draft a first-class object that knows what it
was derived from, which is what the comparison view needs. `portfolio_versions` is the
"did my portfolio's absorption ratio change because the market changed, or because I traded?"
question — genuinely interesting, and genuinely optional for v1.

### 4.3 Compute tiering — the coverage problem

A portfolio contains arbitrary tickers. The precomputed pair table covers `universe × universe`
plus anchors. A user holding JPM, XOM, and UNH gets **zero** cache hits.

Three tiers, in the order the service should try them:

```
  request: pairs for {AAPL, MSFT, NVDA, JPM, XOM}   (10 pairs)
     │
     ├─ TIER 1  pair_correlations lookup              -> 3 pairs hit
     │          fast (single indexed query)
     │
     ├─ TIER 2  compute live from cached prices       -> 5 pairs
     │          prices already in the prices table
     │          cost: one df.corr() call — trivial
     │
     └─ TIER 3  fetch prices from Yahoo, then compute -> 2 pairs
                THE ONLY EXPENSIVE TIER
                rate-limited, needs a budget (§9 Q9)
```

**The key insight: compute is cheap here, data acquisition is not.** A 30-holding portfolio
is 435 pairs, which is a single vectorized `DataFrame.corr()` — milliseconds. Even a rolling
absorption ratio (eigendecomposition of a 30×30 matrix at 250 dates) is trivial numerically.
What is *not* cheap is Yahoo Finance calls for tickers we've never seen.

This is the opposite of Track A Phase 1, where the *diagnostic stack itself* was the cost.
So the architecture here should be **price-cache-centric**, not correlation-cache-centric:
the thing worth precomputing and persisting aggressively is the price history for every
ticker that appears in any saved portfolio, not the correlations derived from it.

Which suggests a genuinely nice pattern:

> **The write path learns from user data.** A nightly job reads the distinct set of tickers
> across all saved portfolios and adds them to the price-refresh set. Tier 3 (the expensive
> path) is then only ever hit the *first* time anyone adds a given ticker; from the next day
> on it's Tier 2. The scheduled job's workload is shaped by what users actually hold.

This also cleanly bounds the Yahoo pressure that next-steps §6 correctly identifies as the
real scarce resource.

### 4.4 New backend modules

Following the existing layering (`analysis/` → `services/` → `api/routers/`) with no
structural change:

```
src/analysis/portfolio.py          NEW — pure math, no I/O
    correlation_matrix(returns_df)
    mean_pairwise_correlation(corr)
    absorption_ratio(corr)                     -- PCA, first eigenvalue share
    effective_number_of_bets(corr)             -- entropy or Herfindahl
    risk_contributions(corr, weights, vols)
    shrink_covariance(returns_df)              -- Ledoit-Wolf, see §2.3
    rolling_portfolio_metrics(returns_df, window)

src/services/portfolio_analytics_service.py    NEW — orchestration
    analyze(holdings, as_of, lookback) -> PortfolioAnalysis
    compare(a, b, as_of, lookback)     -> PortfolioComparison
    timeseries(holdings, start, end)   -> list[PortfolioMetricPoint]

src/services/portfolio_service.py              NEW — CRUD, auth-scoped
    (drafts, versions, ownership checks)

src/repositories/base.py                       EXTEND
    PortfolioRepository  (Protocol — same pattern as PriceRepository)
    PairCorrelationRepository

src/domain/models.py                           EXTEND
    Holding, Portfolio, PortfolioAnalysis,
    PortfolioComparison, PortfolioMetricPoint
```

`src/analysis/portfolio.py` staying pure (DataFrames in, numbers out, no repositories, no
config) matches how `src/analysis/correlation.py` is written today and is what makes it
testable without fixtures.

New endpoints:

```
POST   /api/research/analyze        holdings + as_of + lookback -> metrics + matrix
POST   /api/research/compare        two holdings sets           -> deltas + attribution
POST   /api/research/timeseries     holdings + range            -> metric time series
GET    /api/portfolios              auth-scoped list
POST   /api/portfolios              create (actual or draft)
PATCH  /api/portfolios/{id}         rename, reweight
DELETE /api/portfolios/{id}         soft delete
```

`POST` for the analysis endpoints rather than `GET` is deliberate: the holdings list is the
request body, it can be long, and **it should not end up in server access logs or browser
history**, which a query string would guarantee. That's a privacy decision disguised as a
REST style choice.

### 4.5 Frontend

```
frontend/src/pages/ResearchPage.tsx                NEW  — route /research
frontend/src/components/research/
    PortfolioEditor.tsx           add/remove/reweight, debounced
    MetricStrip.tsx               the headline numbers + deltas
    AbsorptionChart.tsx           metric over time, with scrubber
    ComparisonPanes.tsx           side-by-side A/B
    DeltaHeatmap.tsx              red/blue pair-level diff
    AttributionList.tsx           "what drives the difference"
frontend/src/api/hooks/
    usePortfolioAnalysis.ts       useMutation (POST)
    usePortfolioComparison.ts
    usePortfolios.ts              CRUD, auth-scoped
```

Reuse, not rebuild:

- `RelatednessHeatmap.tsx` already renders a symmetric ticker×ticker matrix. Generalizing it
  from "anchors" to "an arbitrary ticker set" is the single highest-value refactor for this
  feature and should happen before anything else is built.
- The `§4.3 explain-this-edge` drawer, if built in Track C, is exactly what a heatmap cell
  click should open. Same component, different entry point.
- `DetailPanelProvider` / `detail-panel-context` already models "something is selected, show
  the panel" and should absorb pair selection rather than growing a parallel mechanism.

**State model for the editor** — worth being explicit, because this is where these UIs usually
rot:

```
   saved ──edit──> dirty ──debounce 300ms──> computing ──> preview
     ↑                                                        │
     └──────────────── save ──────────────────────────────────┘
```

Every recompute is cancellable (`AbortSignal`, which `apiGet` already threads through), the
last-write-wins, and the preview is always labelled with which holdings it reflects. Without
that last part users will read a stale number as a live one.

---

## 5. Performance

| Operation | N=10 | N=30 | Where the time goes |
|---|---|---|---|
| Correlation matrix, cached prices | <10ms | <30ms | one `df.corr()` |
| Absorption ratio, single date | <5ms | <10ms | one eigendecomposition |
| Rolling metrics, 250 dates | ~150ms | ~600ms | 250 eigendecompositions — the one place to watch |
| Full analysis, all prices cached | **<300ms** | **<800ms** | dominated by rolling |
| Full analysis, 3 tickers uncached | 2–5s | 2–5s | **Yahoo, entirely** |

Targets: **<500ms for the common case** (all holdings already in the price cache), and an
explicit loading state for the cold case, because a first-time ticker is a network call and no
amount of engineering hides that.

Two levers if rolling metrics get slow: compute at weekly rather than daily resolution for
multi-year ranges (nobody scrubs a 5-year chart day by day), and cache the rolling series per
`(holdings-set-hash, lookback, resolution)` since drafts get re-analyzed repeatedly with
identical holdings.

---

## 6. Phasing

| Phase | Deliverable | Depends on | Rough effort |
|---|---|---|---|
| **R0** | `pair_correlations` schema decision folded into Track A Phase 1 | — | hours, if done *now* |
| **R1** | `src/analysis/portfolio.py` + tests. Pure math, no API, no UI | R0 | ~1 week |
| **R2** | `/api/research/analyze` + generalized heatmap. Flow A, single date only | R1, Phase 5b auth | ~1.5 weeks |
| **R3** | Time series + scrubber. Flow A complete | R2, §4.2 time-travel | ~1.5 weeks |
| **R4** | Draft editor + persistence. Flow B | R3, portfolios schema | ~2 weeks |
| **R5** | Comparison + attribution. Flow C | R4 | ~2 weeks |
| **R6** | Ledoit–Wolf shrinkage, crisis-period comparison | R5 | ~1 week |

**~9 weeks**, and that assumes auth already exists. R0 is the one with a real deadline —
it costs hours today and a migration later.

R1 is deliberately first and deliberately standalone: the metrics are pure functions over a
returns matrix, so they can be written, tested, and validated against known cases (a
perfectly correlated portfolio has ENB = 1; an orthogonal one has ENB = N) with no
dependency on auth, UI, or the API. If this feature ever gets shelved mid-build, R1 is still
useful on its own — it's what Track A Phase 3's concentration analysis should be using anyway.

---

## 7. What could go wrong

**It becomes an optimizer by accident.** The moment the page says "adding X would lower your
absorption ratio," this is a portfolio optimizer making recommendations, with all the framing
and liability that implies. The line I'd hold: **the app describes, the user drafts.** Report
what a draft does; never propose one. §9 Q7.

**False comfort.** Covered in §2.3 and worth repeating because it's the most likely real-world
harm: a user reads "effective bets: 5.1" as a safety margin, and in the next drawdown all five
bets move together. The mitigation isn't a disclaimer nobody reads — it's showing the
crisis-period number next to the full-period one, so the failure mode is visible in the
product itself.

**Estimation noise presented as signal.** At T/N ≈ 8, the difference between ENB 3.2 and 3.4
is not meaningful, but the UI will render it as a change. Either shrink the estimator, show
confidence bands, or round hard enough that noise doesn't display as movement. Probably all
three.

**Privacy escalation.** Track A's client-side-only position was a real feature. Storing
holdings makes this app a target it currently isn't. Non-negotiables if this ships: holdings
encrypted at rest, hard delete that actually deletes (including versions), export before
delete, no third-party analytics on the research page, and holdings never in a URL, a log
line, or a Sentry breadcrumb. That last one needs an explicit Sentry scrubbing rule
(`before_send`) — the current config in `src/api/main.py` sends everything.

**Scope.** Three flows, a new math module, auth, and a new page. R4 and R5 are where this
quietly turns into two months. Shipping R1–R3 and stopping is a legitimate outcome — Flow A
alone (inspect your own portfolio's structure over time) is a complete, useful feature.

---

## 8. Why this is worth building anyway

It converts the app's central asset — a correlation engine with real analytical depth — from
something that describes *the market* into something that describes *the user's own position
in the market*. Track A Phase 3 takes the first step (static concentration); this is the
version with time and counterfactuals in it, which is the version someone would actually
return to.

It also reuses more than it adds: the price cache, the pair table, the heatmap, the scrubber,
the explain-edge drawer, and the ticker resolution all already exist or are already planned.
The genuinely new code is one pure-math module and one page.

---

## 9. Open questions — please review

These are ordered by how much your answer changes the work. The first four are blocking; I'd
want them settled before R1.

### Q1 — Weights: what unit, and do they even enter the analysis? ⚠️ *blocking*

Correlation is weight-independent. Portfolio *risk* is not. Three options:

- **(a) Tickers only, equal-weight.** Simplest. Answers "is what I own structurally
  diversified?" Ignores that a 40% position is not the same as a 2% one.
- **(b) Percentages.** User enters weights summing to 100. Enables risk contribution (§2.2
  metric 4), no price lookups needed, no dollar amounts stored.
- **(c) Share counts.** Most natural to enter, requires live prices to convert to weights,
  and means we're storing something very close to net worth.

**My recommendation: (b).** It unlocks the metric that makes the feature personal, and it
deliberately stops short of storing anything that looks like an account balance. But (a) is a
legitimate v1 if you want to defer the whole weights question.

### Q2 — Is this correlation analysis or risk analysis? ⚠️ *blocking*

Related to Q1 but distinct. "Show me how my holdings co-move" and "show me where my risk
comes from" are different products with different metrics, and trying to be both produces a
page that's cluttered and vague.

I've written §2 assuming **co-movement first, with risk contribution as the one bridge metric**.
Confirm or redirect — this determines whether volatility, drawdown, and beta belong on the
page at all (I've assumed not).

### Q3 — Is a draft derived from a portfolio, or independent? ⚠️ *blocking*

- **Derived:** a draft is a diff against a real portfolio. Comparison is the default action.
  Data model has `parent_portfolio_id`. Cannot draft without holding something first.
- **Independent:** a draft is any ticker set. Compare anything to anything, including two
  drafts. More flexible, weaker default workflow, more UI.

I've drawn derived in §3.2 because the comparison view is the point of the feature, but this
is genuinely your call about who the user is.

### Q4 — What counts as "over time"? ⚠️ *blocking*

Three readings of "correlations between my portfolio over time," and they are different
features:

- **(a)** Fixed holdings, rolling window. "How has the correlation structure of *these*
  holdings evolved?" One portfolio, many windows.
- **(b)** Actual holdings as they changed. Requires `portfolio_versions` and trade history.
  "Did my portfolio get more concentrated because I traded, or because the market did?"
  Much richer, much more input required from the user.
- **(c)** Both, on one chart.

I've assumed **(a)** throughout — it needs no new user input and answers the more common
question. (b) is a strong follow-up but is really a portfolio-tracking feature wearing a
research-page hat.

### Q5 — Point-in-time correctness: how strict?

If a user drafts a portfolio and views it "as of March 2020," do we use only data available
in March 2020, or today's full history? The strict version is more correct and is the
interesting technical claim (next-steps §4.2 makes exactly this argument). The loose version
is simpler and, for a *descriptive* co-movement statistic, arguably fine.

I lean strict — mostly because the loose version invites users to read the page as a backtest,
and a backtest with lookahead is worse than no backtest.

### Q6 — Which ENB definition?

Entropy-based `exp(-Σ pᵢ ln pᵢ)` vs Herfindahl `1/Σ pᵢ²` over normalized eigenvalues. Both
standard, both defensible, different numbers for the same portfolio. Needs to be picked once,
documented in the UI, and never quietly changed — a metric that shifts because we changed the
formula is worse than no metric.

### Q7 — Does the app ever suggest changes?

"Adding a holding with r < 0.3 to your existing positions would raise your effective bets to
4.1" is enormously useful and is unambiguously a recommendation. My strong recommendation is
**no suggestions, ever** — describe drafts, don't propose them. Flagging it because it's the
most tempting feature to add later and the hardest to walk back.

### Q8 — Benchmarks and crisis periods?

Two additions I think are high-value:

- Compare against a reference (SPY, equal-weight S&P, equal-weight version of the user's own
  holdings). "Your absorption ratio is 78%; the S&P 500's is 61%" makes an abstract number
  legible.
- A **crisis-period toggle** — recompute over Mar 2020, 2022, Aug 2024 — as the concrete
  mitigation for the false-comfort problem in §7.

Both are cheap. Worth doing?

### Q9 — Compute budget for unknown tickers?

A user can paste 50 tickers we've never seen, each a Yahoo fetch. Options: cap portfolio size
(what number?), rate-limit per user (`slowapi` is already wired), queue it as a background job
with a "we're fetching, check back" state, or restrict drafts to tickers already in the price
table. I'd cap at ~50 holdings and rate-limit; the queue is over-engineering until it isn't.

### Q10 — Non-equity holdings?

Cash, bonds, ETFs, crypto, options. ETFs work fine (they're tickers with prices). Cash is a
zero-variance holding that mechanically dilutes every metric and needs explicit handling.
Options don't work at all. Simplest defensible v1: **equities and ETFs only, cash entered as
a weight but excluded from the correlation math with a visible note.**

### Q11 — Short-history tickers?

A holding that IPO'd four months ago cannot participate in a 250-day correlation. Drop it from
the matrix with a visible warning, shorten the window for everyone (contaminating the whole
analysis), or block it? I'd drop-with-warning — `MIN_OVERLAP_DAYS = 30` in
`src/analysis/correlation.py:3` already establishes this pattern.

### Q12 — Sharing?

Shareable permalinks are listed as a cheap win in next-steps §4.6, but a URL that encodes a
portfolio is a URL that leaks holdings — into chat logs, browser history, and referrer
headers. If sharing matters here, it needs opaque server-side share tokens with explicit
expiry, not URL-encoded state. Or skip it.

---

## 10. Recommendation

**Do R0 now** — the symmetric `pair_correlations` key costs hours today and a migration later.
It is the only thing in this document with a real deadline, and it's worth folding into the
Track A Phase 1 PR regardless of whether this feature is ever built.

**Then build R1 opportunistically.** `src/analysis/portfolio.py` is pure math with no
dependency on auth or UI, and Track A Phase 3's concentration analysis should be calling it
anyway. It's useful whether or not the research page happens.

**Then stop and re-read Q1–Q4.** Those four answers determine whether R2–R5 is a six-week
feature or a twelve-week one.

**And consider shipping Flow A alone.** "Inspect your own portfolio's correlation structure
over time" is a complete product. Flows B and C are the better demo, but Flow A is the thing
someone would use on a Tuesday.
