# How correlation is computed

This walks through exactly what data goes in, what transformations happen, and what comes out — end to end, referencing the actual code.

## 1. The raw data point: daily adjusted close

[`fetch_price_history()`](../src/data/fetcher.py) calls `yfinance.download(..., auto_adjust=True)` and keeps only the `Close` column. With `auto_adjust=True`, that "Close" is already **split- and dividend-adjusted** — not the raw price a ticker tape would have shown that day, but the price adjusted so historical jumps from stock splits or dividend payouts don't masquerade as real price moves. This is the single data point pulled per ticker per day; nothing else (Open/High/Low/Volume) currently feeds into correlation.

- **Frequency:** daily (one adjusted-close value per trading day).
- **Window:** trailing `lookback_days` from `config.yaml` (365 by default) — i.e. roughly the last calendar year, though only actual trading days have prices.
- **Universe:** the anchor ticker(s) plus every ticker in [`load_universe()`](../src/data/universe.py) (~55 semiconductor/hardware satellites).

The result is a wide table: rows = trading dates, columns = tickers, values = adjusted close. Tickers that fail to download, or that have fewer than 30 trading days of data (`MIN_TRADING_DAYS` in `fetcher.py`), are dropped before anything else happens.

## 2. Prices → log-returns

Correlation is never computed on price *levels* — it's computed on **daily log-returns**, produced by [`compute_log_returns()`](../src/analysis/returns.py):

```
log_return[t] = ln(price[t] / price[t-1])
```

Why not raw prices? Two stocks priced at $500 and $5 aren't comparable in dollar terms, and price levels trend (they wander up or down over the whole window), which inflates correlation between *any* two stocks that both went up over the year regardless of whether they actually move together day-to-day. Returns strip out the price level and ask a narrower question: *on days when the anchor moved x%, did the satellite tend to move a proportional amount?* Log-returns specifically (vs. simple percentage returns) are used because they're additive across days and better behaved statistically (closer to symmetric/normal).

The very first day of the window has no prior day to compare to, so `compute_log_returns()` drops it — a 365-day price window yields 364 daily returns per ticker (fewer on both ends for tickers with gaps).

## 3. Pairwise alignment

Different tickers don't necessarily trade on the exact same set of days (listing dates, halts, and — relevant here — ASML/TSM as ADRs can have exchange-calendar quirks vs. US-listed satellites). So correlation is never computed against one shared global date index. Instead, [`compute_correlations()`](../src/analysis/correlation.py) does this **separately for every anchor/satellite pair**:

```python
pair = pd.concat([anchor_returns, satellite_returns[ticker]], axis=1).dropna()
```

This inner-joins the two return series on date and drops any day where either side is missing. If fewer than `MIN_OVERLAP_DAYS` (30) days survive, that satellite is skipped entirely for that anchor — there simply isn't enough overlapping history to say anything.

## 4. Pearson correlation

On the surviving aligned pair, `compute_correlations()` calls pandas' `.corr()`, which is the standard Pearson correlation coefficient:

```
r = cov(anchor_returns, satellite_returns) / (std(anchor_returns) * std(satellite_returns))
```

`r` ranges from **-1** (moves perfectly opposite) to **+1** (moves perfectly together), with **0** meaning no linear relationship. This is the `correlation` value that ends up in every report CSV and every graph edge weight. [`rank_top_n()`](../src/analysis/ranking.py) keeps satellites with `|r| ≥ correlation_threshold` (0.5 by default), ranked by `|r|` — so a strong inverse correlation (e.g. -0.75) ranks above a weak positive one (e.g. 0.55).

## 5. Rolling correlation → stability score

A single full-period `r` can hide a lot: a satellite could correlate at 0.85 for the first half of the year and -0.2 for the second half, and still average out to something that looks respectable. Phase 2 checks for that with [`compute_rolling_correlations()`](../src/analysis/correlation.py):

```python
pair.iloc[:, 0].rolling(window).corr(pair.iloc[:, 1])
```

This recomputes the same Pearson correlation on a sliding `window`-day sub-range (60 by default, `rolling_window` in `config.yaml`) instead of the whole period at once, producing a *series* of correlation values — one per day, each describing "the correlation over the trailing `window` days as of this date." Pairs with fewer than `window + MIN_OVERLAP_DAYS` total overlapping days can't fill even one window and are skipped.

That series is then collapsed into a single **stability score** by [`compute_stability_scores()`](../src/analysis/correlation.py):

```
stability = max(0, 1 - std(rolling_correlation_series))
```

Since correlation is bounded to [-1, 1], a rolling series that barely moves has a small standard deviation → stability near 1 (reliable). A series that swings across a wide range (e.g. from 0.9 to -0.3) has a large standard deviation → stability near 0 (the full-period number was likely a fluke, or the relationship broke down partway through the window). This score is attached to ranked satellites via `attach_stability()` and shown alongside `correlation` in every Phase 2 report and graph edge — `correlation` says *how strong*, `stability` says *how much to trust that number*.

## 6. Spearman rank correlation — the primary ranking metric (Phase 4)

Everything above describes Pearson correlation, which is still computed — but as of Phase 4, [`compute_correlations()`](../src/analysis/correlation.py) takes a `method` argument (`"pearson"` or `"spearman"`, passed straight to pandas' `Series.corr`), and [`rank_top_n()`](../src/analysis/ranking.py) is now called with the **Spearman** result, not Pearson.

Spearman correlates *ranks* rather than raw return values: convert each day's anchor return and each day's satellite return to their rank within their own series, then compute Pearson correlation on those ranks. The practical effect: a single extreme day (a small-cap satellite gapping 30%+ on an M&A rumour, a halt, or an earnings surprise) still counts as "a big up day," but its *magnitude* can no longer dominate the year's covariance the way it can with Pearson. This matters more here than it would for large-caps — the satellite universe is small/mid-cap and thin, exactly where sporadic outlier days are common.

Pearson is still computed and attached to every ranked satellite as `pearson_correlation`, so the two are directly comparable — a satellite where Spearman and Pearson roughly agree is a cleaner signal than one where they diverge sharply (a sign an outlier day is doing a lot of the work in the Pearson number).

## 7. Partial correlation — removing the market as a confound (Phase 4)

A raw anchor-satellite correlation can't distinguish "these two are actually linked" from "both of these just went up because the whole market went up." [`compute_partial_correlations()`](../src/analysis/correlation.py) addresses this with the standard first-order partial correlation formula, controlling for the S&P 500 (`market_proxy_ticker: "^GSPC"` in `config.yaml`):

```
r(anchor, satellite | market) = (r_as - r_am · r_sm) / sqrt((1 - r_am²)(1 - r_sm²))
```

where `r_as`, `r_am`, `r_sm` are ordinary Pearson correlations between anchor/satellite, anchor/market, and satellite/market, all computed on the same three-way inner-joined date range (anchor, satellite, and `^GSPC` log-returns must all have a price that day). The result isolates co-movement specific to the anchor-satellite pair — the part of `r_as` *not* explained by both legs independently tracking the market.

This is the roadmap's **market-beta contamination** risk, addressed directly: in the live Phase 4 run, top satellites' raw correlation to TSM/ASML/NVDA regularly dropped by roughly half once market-adjusted (e.g. ONTO ↔ TSM: 0.63 raw → 0.35 partial) — meaningful evidence that a large share of "correlation" in this universe is just shared market beta, not an anchor-specific relationship.

## 8. Time-lagged cross-correlation — same relationship, but predictive (Phase 4)

[`compute_lagged_correlations()`](../src/analysis/correlation.py) asks a different question from same-day correlation: does the satellite tend to move `lag` days *after* the anchor, for `lag` in `1..lag_max_days` (3 by default)? For each candidate lag, the anchor's return on day `t` is correlated against the satellite's return on day `t + lag` (implemented as `satellite_returns.shift(-lag)` before the usual inner-join-and-correlate). The lag with the largest `|r|` is kept as `best_lag`/`best_lag_correlation`.

A same-day correlation, however strong, isn't actionable — by the time you see the anchor move, the satellite has already moved too. A satellite whose strongest correlation shows up at `lag > 0` is a genuine "leading indicator" candidate: the anchor's move today is informative about that satellite's move a few days out. `run_phase4.py` collects every satellite (across all anchors) whose best-lag correlation clears `correlation_threshold` into a printed/saved "leading indicators" list.

## 9. Sector-relative correlation — removing the sector as a confound (Phase 4)

The same market-beta problem exists one level down: two chip-equipment stocks can correlate simply because the whole semiconductor-equipment sub-sector moves together, independent of any anchor-specific relationship. [`compute_sector_relative_correlations()`](../src/analysis/correlation.py) applies the same subtraction idea as partial correlation, but at sector granularity — it subtracts a representative sector ETF's return from *both* the anchor's and the satellite's returns, then correlates the residuals.

The sector ETF is chosen per satellite via `sector_etf_for()`, which reuses the graph's existing 7-group sector taxonomy (`visualisation.style.sector_group()`) rather than inventing a new one: the three chip-related groups (Semiconductor Equipment, Semiconductors, Chip IP/Materials/Memory) map to `SOXX` (iShares Semiconductor ETF); everything else maps to `XLK` (Technology Select Sector SPDR). **This is a deliberate simplification, not a precise mapping** — there's no sufficiently liquid ETF for finer distinctions like "semiconductor equipment specifically" vs. "semiconductors broadly," so `SOXX` stands in for both. Treat `sector_relative_correlation` as directionally useful, not exact.

## 10. Regime-break detection — is the correlation still true *today*? (Phase 4)

Phase 2's stability score asks "was this correlation consistent over the whole lookback window?" [`detect_regime_breaks()`](../src/analysis/correlation.py) asks the more time-sensitive question: "is it still true *right now*, or has it recently broken down?" For each satellite, it averages the trailing `regime_recent_days` (30 by default) of the Phase 2 rolling-correlation series and compares that to the full-period correlation:

```
drift = full_period_correlation − mean(rolling_correlation[-recent_days:])
regime_break = |drift| ≥ regime_break_threshold   (0.35 by default)
```

A satellite can have a high full-period correlation *and* a high stability score (consistent all year) and still be mid-breakdown right now if the relationship only recently shifted — stability alone wouldn't catch this, since 11 stable months and 1 broken one still average to a low standard deviation. This is a heuristic threshold, not a formal change-point test — consistent with the stability score also being a heuristic (`1 - std`) rather than a statistical test.

## 11. Anchor relatedness — "correlation of correlations" (Phase 4)

[`anchor_relatedness_matrix()`](../src/graph/queries.py) extends Phase 2/3's `shared_satellites()`/`strongest_cross_link()` (which surface only the *single* strongest cross-anchor link) into a full anchor × anchor matrix. No anchor-anchor price correlation is computed directly — instead, for every satellite shared by two or more anchors, each anchor pair gets one "link strength" sample (the weaker of their two edge weights to that satellite, same weakest-link logic as `strongest_cross_link`), and a pair's final score is the mean of all such samples across every satellite they share. Two anchors linked through many shared satellites score higher than two linked through one coincidental overlap.

This is explicitly an *inferred* relatedness, not a measured one — worth restating the correlation-vs-causation caveat here specifically, since "NVDA and TSM are 0.52-related" sounds like a direct measurement but is actually several steps removed from one.

## Worked example

Anchor NVDA, satellite X, over a 100-day window:

1. Pull adjusted close for both, 100 days each → align to, say, 97 common trading days.
2. Compute log-returns for both → 96 return values each.
3. Pearson `corr()` on those 96 pairs → e.g. `r = 0.62`. That clears the 0.5 threshold, so X shows up in NVDA's ranked satellite list with `correlation = 0.62`.
4. Rolling 60-day correlation gives 96 - 60 + 1 = 37 overlapping-window values, e.g. ranging narrowly between 0.55 and 0.68 → `std ≈ 0.03` → `stability = 1 - 0.03 = 0.97`. High confidence that 0.62 reflects a real, consistent relationship rather than a one-off alignment of two noisy series.

## Summary of every input to the correlation math

| Input | Source | Used for |
|---|---|---|
| Adjusted close price | `yfinance.download(..., auto_adjust=True)["Close"]` | Base data point; nothing else (volume, open/high/low) currently feeds into correlation. |
| Daily log-return | `ln(price[t] / price[t-1])` | What's actually correlated — not price levels. |
| Trailing lookback window | `config.yaml: lookback_days` (365) | How much price history is pulled per ticker. |
| Per-pair overlapping dates | Inner join, dropna | Ensures each anchor/satellite pair is compared only on days both actually traded. |
| Rolling window length | `config.yaml: rolling_window` (60) | Sub-window size for the stability check. |
| Correlation threshold | `config.yaml: correlation_threshold` (0.5) | Minimum `|r|` to keep a satellite in the ranked output (applied to Spearman as of Phase 4). |
| S&P 500 (`^GSPC`) adjusted close → log-return | `yfinance`, same fetch path as any other ticker | Market factor removed by partial correlation (Phase 4). Configurable via `config.yaml: market_proxy_ticker`. |
| Sector ETF (`SOXX` or `XLK`) adjusted close → log-return | `yfinance`; ETF chosen per satellite via `sector_etf_for()` | Sector factor removed by sector-relative correlation (Phase 4). |
| Satellite's fine-grained sector label | `src/data/universe.py` metadata, grouped via `visualisation.style.sector_group()` | Selects which sector ETF applies to a given satellite (Phase 4). |
| Max lag | `config.yaml: lag_max_days` (3) | How many days ahead of the anchor a satellite's move is checked (Phase 4). |
| Regime-detection window / threshold | `config.yaml: regime_recent_days` (30) / `regime_break_threshold` (0.35) | Defines "recent" for regime-break detection and how much drift counts as a break (Phase 4). |

## How Phase 4 maximises the accuracy of the results

Every Phase 4 addition targets a specific way the Phase 1-3 numbers could mislead someone:

| Failure mode (see roadmap "Risks & Pitfalls") | Phase 4 mitigation |
|---|---|
| **Spurious correlation from outlier days** — a thinly-traded satellite's single 30% gap day inflates its full-period Pearson `r` | Spearman rank correlation drives ranking; outlier days shift a rank by at most one position, not by their full magnitude |
| **Market-beta contamination** — "correlated" satellites are really just tracking the S&P 500 like everything else in a bull market | Partial correlation nets out the market factor; a satellite's edge weight now reflects anchor-specific co-movement |
| **Sector-wide comovement mistaken for an anchor-specific link** — two chip-equipment names correlate because the whole sub-sector moves together | Sector-relative correlation nets out a representative sector ETF before correlating |
| **Stale relationships** — a full-period correlation can look strong while the underlying relationship has already broken down in the last few weeks | Regime-break detection compares the trailing 30 days against the full-period value and flags large drift |
| **No forward-looking signal** — same-day correlation, however strong, isn't actionable | Lagged cross-correlation surfaces satellites whose strongest relationship to the anchor shows up 1-3 days later |
| **Single-anchor tunnel vision** — the graph only ever showed the *one* strongest cross-anchor link | Anchor relatedness matrix scores every anchor pair using *all* their shared satellites, not just the strongest one |

None of this eliminates the roadmap's fundamental correlation-vs-causation caveat — a satellite that survives Spearman ranking, a partial-correlation check, a sector-relative check, and shows no regime break is still a **statistically robust price correlation**, not a verified supply-chain dependency. Phase 4 makes the number harder to fool yourself with; it doesn't make it a different kind of claim. See the roadmap's "Future Enhancements" section (and the V2 data ideas below) for what an actual dependency signal would require.

## Data used today vs. potential V2 additions

**What feeds the correlation math today**, in full: adjusted close price (one series per ticker) → daily log-return → Pearson and Spearman correlation on inner-joined dates → rolling-window stability → partial correlation against `^GSPC` → sector-relative correlation against `SOXX`/`XLK` → lagged correlation → regime-break comparison. That's it — no volume, no fundamentals, no news, no order-book data. Every anchor-satellite "relationship" in this project is currently a statement about **daily closing-price co-movement only**.

That's a real limitation, and the roadmap's own "Future Enhancements" section already gestures at it. Concretely, a V2 correlation engine could incorporate:

- **Volume / liquidity data** (already fetched for node sizing via `fetch_metadata()`, but unused in the correlation math itself) — e.g. weighting or filtering correlations by whether both legs had comparable liquidity that day, so a thin satellite's noisy prints don't get the same statistical weight as a liquid one's.
- **Intraday / higher-frequency prices** — daily closes can't distinguish "the satellite reacted within the hour" from "the satellite reacted the next morning"; hourly or minute bars would sharpen the lagged-correlation analysis (#8 above) considerably.
- **Fundamental data** (revenue, margins, guidance, earnings calendar) — lets you check whether a correlated satellite is fundamentally exposed to the anchor's business (e.g. % of revenue from the anchor's industry) rather than only price-exposed. This is the most direct way to start closing the correlation-vs-causation gap.
- **News/event sentiment** — flagging days where anchor and satellite both had *news* (not just price moves) would help separate "these move together because of shared catalysts" from "these move together because of shared beta that happens to net out the same."
- **Actual supply-chain data** (Bloomberg/FactSet supplier-customer relationships, 10-K "major customer" disclosures) — the roadmap's explicit answer to the correlation-vs-causation gap: cross-referencing a statistically-surviving correlation against a *known* business relationship would let the tool distinguish "priced like a supplier" from "verified as a supplier."
- **Options-implied volatility / skew** — a market-derived signal of forward-looking risk perception that log-returns (backward-looking) can't capture; could add a volatility-regime dimension alongside the existing price-regime one.
- **Short interest / institutional ownership changes** — a proxy for how "crowded" a correlated trade already is, relevant for anyone acting on a discovered satellite rather than just observing it.
- **Multiple concurrent lookback windows** (the roadmap's "multi-timeframe view") — running the whole Phase 4 stack at 3-month, 1-year, and 3-year windows side by side, rather than the single `lookback_days` window used today, to see whether a relationship is a recent development or a multi-year pattern.

None of these are implemented; they're listed here because the user's natural next question after "what data goes into this" is "what data is missing," and the honest answer is: everything except price.
