# Dynamic Universe Roadmap (Phase 7)

The plan to replace the hardcoded 55-ticker satellite list with a dynamically-sourced, filterable universe. Sequenced **after** the Phase 5 frontend per your call — see the dependency note in §2, which is honest about what this actually depends on (it isn't the frontend).

This is not new scope invented here — [src/data/universe.py](../src/data/universe.py)'s own docstring already flags the hardcoded list as a Phase 1 shortcut ("For the Phase 1 proof of concept we skip the screener step and use a curated, hand-picked list"), and the original roadmap's Component 2 (Universe Filtering) describes the intended real approach. This document is about doing it, grounded in what the code actually looks like today.

---

## 1. What's hardcoded today — audited, not assumed

| Fact | Evidence |
|---|---|
| The satellite universe is **exactly 55 tickers**, hand-picked, all semiconductor/hardware/datacenter-adjacent (i.e. implicitly NVDA-thematic). | Counted directly in [src/data/universe.py](../src/data/universe.py) |
| Each entry is a `(ticker, name, sector)` tuple. The **company name and the fine-grained sector both come from this list and nowhere else.** | `SATELLITE_UNIVERSE` structure |
| **yfinance supplies only `market_cap` and `avg_volume`** — `fetch_metadata()` reads `marketCap` and `threeMonthAverageVolume` from yfinance's `info` and nothing else. It does **not** pull sector, name, industry, or exchange, even though yfinance's `info` dict exposes them. | [src/data/fetcher.py:101-113](../src/data/fetcher.py#L101-L113) |
| The fine-grained sector strings ("Semiconductor Equipment", "Laser/Photonics", "Optical Networking", …) are **the input to the graph's entire color system** — `.claude/skills/network-graph-style/SKILL.md` folds them into 7 color groups. Lose the fine-grained labels and the graph's sector coloring degrades. | network-graph-style skill |
| For any ticker not in the list (e.g. anchors like NVDA), `CompanyService` falls back to `name = ticker`, `sector = "Unknown"`. | [src/services/company_service.py:31-34](../src/services/company_service.py#L31-L34) |
| **No universe-filter parameters exist in config** — no market-cap range, no volume floor, no exchange whitelist. The roadmap's Component 2 describes them (£50M–£10B, ≥100k shares/day, major exchanges) but they were never added to `config.yaml`/`Config`. | `grep` of `config.yaml` + `src/config.py` — zero hits |

**The one insight that reframes this whole phase:** the hardcoded list is doing *three* jobs, not one. It's the ticker source, the name source, and the sector-taxonomy source. De-hardcoding the tickers is the easy 20%; replacing the hand-curated names and fine-grained sectors without wrecking the graph's visual identity is the hard 80%. §3 is about that.

---

## 2. The dependency reality (read before sequencing anything)

You asked for this **after** the frontend, and that's a perfectly good *priority* call — the frontend is the visible payoff; this is backend data engineering with no user-facing surface of its own. But be clear on the actual technical dependency graph, because it isn't the frontend:

- **This phase's real prerequisite is Phase 4.8 (Postgres)**, not Phase 5 (frontend). A universe of hundreds-to-thousands of screened tickers with market caps that drift and index membership that changes quarterly does not belong in a Python list *or* in the parquet cache — it wants the queryable `companies` table with the `is_satellite_universe` flag already sketched in [production-roadmap.md §6](production-roadmap.md#6-phase-48--postgres-migration). That table was designed with this phase in mind.
- **The frontend does not block this and this does not block the frontend.** They're independent. If you build the frontend first (against the current 55-ticker universe) and *haven't* done Postgres yet, then starting this phase pulls Phase 4.8 in as its prerequisite at that point.
- **Downstream, this phase changes nothing above the repository seam** — see §5. Services, API routes, schemas, and the frontend are all untouched, by the same architectural design that makes the Postgres swap non-invasive.

So the honest sequencing is: **Phase 4.8 (Postgres) → \[frontend and everything else in whatever order you like\] → Phase 7 (this).** Calling it "Phase 7 / after the frontend" is fine shorthand; just don't let it hide that Postgres is the true gate.

---

## 3. The central tension: curation quality vs. scale

This is the intellectual core of the phase. The current system gets three things *for free* from hand-curation that a dynamic universe has to actively re-earn:

**a. Company names.** yfinance's `info["longName"]`/`shortName` exists but isn't currently pulled. A dynamic universe must start pulling it (coarse, occasionally ugly — "Advanced Energy Industries, Inc." vs. the clean "Advanced Energy Industries" in the list today), or source names elsewhere.

**b. The fine-grained sector taxonomy — the hard one.** yfinance/screener `sector` is GICS-coarse: "Technology", "Industrials". That is dramatically less specific than "Semiconductor Equipment" vs. "Laser/Photonics" vs. "Optical Networking", and it's exactly that granularity the graph's 7 color groups encode. **The likely answer: use the `industry` field, not `sector`.** yfinance/FMP `industry` (e.g. "Semiconductor Equipment & Materials") is far closer to the hand-curated labels than `sector` is. Plan to map `industry → color group`, keep GICS `sector` only as a coarse fallback for the long tail, and consider a small curated override table for tickers where the automated industry label is wrong or too coarse. Whatever the choice, the network-graph-style skill's color-group mapping must be re-derived against the new label vocabulary — its current table is keyed to the 15-16 hand-written strings, which won't exist anymore.

**c. Thematic relevance.** All 55 current tickers are plausible NVDA satellites *by construction* — a human pre-filtered to semis/hardware/datacenter. Pull the raw Russell 2000 and you have ~2000 stocks, most thematically irrelevant to any given anchor. **De-hardcoding without a thematic filter is a behavior change, not just a scale change** — you'd be correlating NVDA against random biotechs and REITs. §4's biggest decision is how to preserve thematic relevance at scale.

The through-line: **you are trading curation quality for breadth and freshness.** That's the right trade for a product that shouldn't require a human to edit a Python file to add a stock — but it's a real trade, and the graph's current visual/thematic coherence is the thing at risk. Every decision below is really about how much of that coherence you spend.

---

## 4. Self-interview — decisions only you can make

Same format as [frontend-roadmap.md](frontend-roadmap.md)'s Step 0: answer these before any code, because a coding agent will otherwise silently pick generically.

**1. Breadth — how wide does the universe go?** The consequential one.
   - *Curated-but-dynamic:* keep a thematic candidate pool (tech/semiconductor supply chain), but source it from a screener + light rules instead of a hand-typed list. Modest scale (low hundreds), preserves relevance and most of the graph's coherence, low spurious-correlation risk. **Recommended starting point** — it's the smallest step away from today's behavior that still removes the hand-editing.
   - *Broad with per-anchor thematic pre-filter:* full small/mid-cap universe (Russell 2000-ish), but each anchor only draws candidates from sectors/industries affine to it (NVDA → semis/hardware only). More discovery, more infra, needs the affinity mapping in (2).
   - *Broad, no pre-filter:* everything correlates against everything; rely purely on correlation + stability + significance to surface links. Maximum discovery, maximum spurious-correlation and compute cost. Only viable with the §7 statistical safeguards firmly in place.

**2. If broad — how is thematic relevance preserved?** Anchor→sector affinity map in config (explicit, predictable), or purely statistical (let correlation decide, accept the noise)? Recommend explicit affinity if you go broad — it's the cheap insurance against the spurious-correlation explosion.

**3. Sector taxonomy — how much granularity do you fight to keep?** Accept coarse GICS `sector` and re-map the graph colors to it (loses the supply-chain granularity that makes the current graph interesting), or invest in `industry`-based mapping + curated overrides (per §3b) to preserve most of it? Recommend the latter — the granularity *is* the product's visual identity.

**4. Source — free-and-fiddly or paid-and-clean?** See §6's table. Free ETF-holdings/exchange-listing files (more assembly, no sector/fundamentals) vs. a screener API like Financial Modeling Prep (one call returns tickers filtered by cap/volume/sector, but a signup and rate limits, and possibly cost past the free tier). Recommend FMP's free tier to start — the roadmap already named it, and it collapses steps 1-3 of the pipeline into one filtered call.

**5. Survivorship bias — solve it or note it?** Point-in-time constituent data (what the Russell 2000 *was* a year ago, including since-delisted names) is a paid, heavyweight data problem (CRSP-grade). Recommend **note and defer** — same stance as the original roadmap. Live-constituents-only overstates correlation reliability, but it's not a v1 blocker.

**6. Refresh cadence.** The universe changes on index rebalances (quarterly) and market-cap drift, not daily. Recommend a **separate, slower universe-rebuild job** (weekly or monthly) distinct from the daily price refresh — rebuilding the whole screened universe every day is wasted API budget.

**7. Compute ceiling.** At N=55 the full Phase 4 diagnostic stack per satellite is cheap. At N=2000 it is not (partial + lagged + sector-relative + regime, per anchor). Are you comfortable with a **two-stage funnel** — cheap raw-Pearson pre-filter to a shortlist, full diagnostics only on the shortlist? Recommend yes if you pick a broad universe; it's the difference between tractable and not.

---

## 5. Where it plugs in — the seam is already built

This is the same architectural payoff as the Postgres migration, and it's not aspirational — the seam exists and is documented in the code:

> `list_universe()` is the seam a future Postgres `companies` table would replace — today it's `src.data.universe.load_universe()` … but callers only ever see the CompanyRepository interface.
> — [src/repositories/yfinance_company_repository.py:14-17](../src/repositories/yfinance_company_repository.py#L14-L17)

`CompanyRepository` ([src/repositories/base.py](../src/repositories/base.py)) is a `Protocol` with two methods: `list_universe()` and `get_market_data()`. Everything above it — `CompanyService`, the `/api/companies` routes, the frontend — depends only on that interface. So this phase's surface area is deliberately tiny:

- **`list_universe()`** stops returning a static 55-row DataFrame and instead returns the screened universe (queried from Postgres `companies WHERE is_satellite_universe`, once Phase 4.8 exists). Same `ticker/name/sector` columns, more rows, sourced dynamically.
- **`get_market_data()`** is largely unaffected — it already fetches per-ticker market cap/volume; it just gets called with more tickers.
- **Nothing else changes.** No service, router, schema, or frontend edit is required for the swap itself, by construction. (New *config* and a new *ingestion module* are additive — §8/§9 — not changes to the read path.)

One real code consequence to plan for: `CompanyService.get_company_profile`'s `name=ticker`/`sector="Unknown"` fallback ([company_service.py:31-34](../src/services/company_service.py#L31-L34)) becomes *less* load-bearing once the universe carries real names/sectors for far more tickers — but it must stay, because anchors still won't be in the satellite universe table.

---

## 6. Universe source options

| Source | Gives you | Cost / friction | Verdict |
|---|---|---|---|
| **Financial Modeling Prep** (screener API) | Tickers filtered by market cap, volume, sector, exchange in one call — plus sector/industry/name | Free tier (rate-limited), signup; paid past it | **Recommended start.** Collapses source+filter+enrich into one call; the roadmap already named it. |
| **iShares/Vanguard ETF holdings CSV** (e.g. IWM = Russell 2000) | The constituent ticker list, free, official | CSV parsing; no fundamentals/sector — must enrich separately via yfinance | Good free ticker source; pair with yfinance `info` enrichment. Watch ToS. |
| **nasdaqtrader.com listing files** (`nasdaqlisted.txt`, `otherlisted.txt`) | All listed US securities + exchange, official, free | No market cap/sector/volume; huge and unfiltered | Useful as an exchange/validity check, not as a primary universe. |
| **yfinance `info` (enrichment only)** | `sector`, `industry`, `longName`, `exchange` per ticker (not currently pulled) | Slow + rate-limited at hundreds of tickers; no bulk screen | Enrichment layer on top of a ticker list, never the list source itself. |
| **Polygon / Tiingo / Finnhub** | Tickers + fundamentals, free tiers | Signup, rate limits | Fine alternatives to FMP; pick on free-tier limits. |

Whatever the source, **yfinance stays the price source of truth** (unchanged) — this phase changes where the *ticker list and its metadata* come from, not where prices come from.

---

## 7. New risks at scale (that don't exist at N=55)

The original roadmap's risk section already names these; the point here is they get **materially worse** the moment N grows, and this phase is where they stop being theoretical:

- **Spurious correlations (multiple-comparisons explosion).** The roadmap notes that with ~250 trading days, r≈0.13 is already p<0.05 — so at N=2000 you will get *dozens* of r≥0.6 satellites by pure chance per anchor. At N=55 this is a nuisance; at N=2000 it's a correctness problem. Mitigations become mandatory, not optional: a higher practical threshold, **stability gating as a hard filter** (not just a displayed score), and a real multiple-comparisons correction (Benjamini-Hochberg FDR is the sane default over Bonferroni at this N). This is the single most important non-obvious consequence of going broad.
- **Compute cost.** Full Phase 4 diagnostics (partial, lagged, sector-relative, regime) × thousands of satellites × N anchors. The §4.7 two-stage funnel (cheap Pearson pre-filter → full diagnostics on the shortlist only) is the mitigation. `CorrelationService`'s existing TTL cache helps with *repeat* requests but does nothing for the first cold computation.
- **Survivorship bias** (§4.5) — worse with a bigger live-only universe, still deferred.
- **Data quality at volume.** Hand-checking 55 tickers is feasible; 2000 is not. Need automated quality gates (the roadmap's "flag >5 consecutive missing days", plus drop tickers with too-short history for the lookback window) as a pipeline stage, since a human won't eyeball them.
- **yfinance rate-limiting.** Enriching/pricing thousands of tickers hammers Yahoo's unofficial API far harder than 55+4 does. The existing TTL parquet cache and threaded metadata fetch help, but a broad universe likely forces real throttling/batching discipline — the exact risk CLAUDE.md warns about ("can get an IP rate-limited").

---

## 8. Step-by-step build

Assumes Phase 4.8 (Postgres) exists per §2.

1. **Add universe-filter config** (§9) — market-cap range, volume floor, exchange whitelist, source selection, refresh cadence, optional anchor→sector affinity.
2. **Build `src/data/screener.py`** — the ingestion module: hit the chosen source (§6), apply the filters, enrich sector/industry/name, map `industry → color group`, and produce a `ticker/name/sector` DataFrame in the exact shape `load_universe()` returns today (so the seam contract is preserved).
3. **Reconcile the sector taxonomy** (§3b) — re-derive the network-graph-style color-group mapping against the new `industry`/`sector` vocabulary; add curated overrides where the automated label is wrong.
4. **Write to Postgres** — populate `companies` with `is_satellite_universe = true` for tickers that pass; upsert on `ticker`.
5. **Swap the repository read path** — either a Postgres-backed `CompanyRepository.list_universe()` querying the flag, or a `ScreenerCompanyRepository`. Zero downstream changes (§5).
6. **Add the two-stage correlation funnel** (§7) *if* you chose a broad universe — cheap Pearson pre-filter before the full diagnostic stack.
7. **Tighten statistical filtering** (§7) — FDR correction + hard stability gate, scaled to the new N.
8. **Add a scheduled universe-rebuild job** (§4.6) — weekly/monthly, separate from the daily price refresh; reuses the existing refresh plumbing.
9. **Data-quality gates** (§7) — automated history-length and missing-day checks as a pipeline stage.
10. **Backfill + verify** — run the screener, confirm the graph still renders coherently with real sector colors, spot-check that thematic relevance survived.

---

## 9. Config additions (illustrative)

None of these exist today (§1). Additive to `config.yaml` + `Config`:

```yaml
universe:
  source: "fmp"                      # fmp | etf_holdings | manual
  market_cap_min: 50_000_000         # roadmap Component 2: ~£50M floor
  market_cap_max: 10_000_000_000     # ~£10B ceiling (small/mid-cap band)
  min_avg_volume: 100_000            # tradeable-liquidity floor
  allowed_exchanges: ["NMS", "NYQ"]  # NASDAQ / NYSE
  refresh_days: 7                    # rebuild cadence, distinct from daily prices
  # only if you chose a broad universe (§4.1/4.2):
  anchor_sector_affinity:
    NVDA: ["Semiconductors", "Semiconductor Equipment", "Networking Hardware"]
    # ...
```

The current `market_proxy_ticker`/`lag_max_days`/etc. sit flat at the top level; whether to nest universe params under a `universe:` key or keep them flat is a style call — nesting reads better as this group grows.

---

## 10. Frontend implications

Mostly forward-compatible *because* [frontend-build-plan.md](frontend-build-plan.md) explicitly said not to hardcode anchor/satellite counts — this phase is exactly the "universe grows past 55" scenario that warning was written for. What becomes newly worth building once the universe is large and dynamic:

- **A sector/industry filter** in the UI — near-useless at 55 curated tickers, genuinely useful across a broad screened universe.
- **A universe-size / candidate-pool indicator** — "showing top 15 of 340 candidates for NVDA" — so users understand the graph is a filtered view, not the whole pool.
- **Candidate-pool transparency** — surfacing *why* a ticker is a candidate (passed which filters, which anchor affinity) matters more when a human didn't hand-pick it.
- **Reinforce the correlation≠causation note** — even more load-bearing when the satellite was surfaced statistically from thousands of options rather than chosen by a human who saw a plausible supply-chain link.

None of these are required for the swap; they're the UI catching up to a bigger universe, and they slot in after this phase, not during it.

---

## 11. What to do first

1. **Confirm Phase 4.8 (Postgres) is done** — it's the real gate (§2). If not, this phase starts there.
2. **Answer §4** — especially Q1 (breadth) and Q3 (sector granularity); everything else follows from those two.
3. **Prototype the screener against 2-3x today's size before going wide** — pull, say, ~150 tech-adjacent tickers via FMP, run them end-to-end, and confirm the graph still looks coherent with automated sectors *before* committing to a 2000-stock universe and the §7 statistical machinery it demands. Validate the curation-vs-scale trade (§3) on a small step before paying for the big one.
