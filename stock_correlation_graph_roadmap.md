# Stock Correlation Dependency Graph — Project Roadmap

## The Idea

Build a Python tool that takes a set of large-cap "anchor" stocks (NVIDIA, Apple, Netflix, ASML, TSMC, etc.) and automatically discovers smaller, lesser-known companies whose stock prices are statistically correlated with each anchor. The output is a weighted dependency graph that everyday investors can explore to find new opportunities tied to macro themes they already understand.

---

## Why This Is Useful

When NVIDIA surges on AI demand, dozens of smaller companies in its supply chain, tooling ecosystem, and adjacent markets tend to move with it — but most retail investors never hear about them. This tool surfaces those hidden connections and quantifies the strength of each relationship, giving everyday investors a structured way to discover new names without needing a Bloomberg terminal.

---

## Key Concepts

**Anchor stocks** are the large, well-known companies that serve as the centre of each sub-graph (e.g. NVIDIA, Apple, TSMC).

**Satellite stocks** are smaller companies (filtered by market cap) whose price movements correlate with a given anchor over a defined time window.

**Correlation weight** is the strength of the statistical relationship between an anchor and a satellite, expressed as a value between -1 and +1. You'll likely want to focus on strong positive correlations (≥ 0.6) and possibly flag strong inverse correlations too.

**Dependency graph** is a network where each anchor is a hub node, connected by weighted edges to its top-N most correlated satellites. Satellites can appear under multiple anchors, revealing cross-cutting themes.

---

## Architecture Overview

The system breaks down into five layers that run in sequence:

```
┌─────────────────────────────────────────────────────────┐
│  1. DATA INGESTION          (fetch & store price data)  │
├─────────────────────────────────────────────────────────┤
│  2. UNIVERSE FILTERING      (define the satellite pool) │
├─────────────────────────────────────────────────────────┤
│  3. CORRELATION ENGINE      (compute & rank)            │
├─────────────────────────────────────────────────────────┤
│  4. GRAPH CONSTRUCTION      (build weighted network)    │
├─────────────────────────────────────────────────────────┤
│  5. VISUALISATION & OUTPUT  (interactive explorer)      │
└─────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Component 1 — Data Ingestion

**Purpose:** Fetch historical daily adjusted-close prices for both anchors and a broad universe of smaller stocks.

**Primary data source:** Yahoo Finance via the `yfinance` library (free, no API key, good for prototyping). For production scale, consider Alpha Vantage, Polygon.io, or Tiingo — all have free tiers with rate limits and paid tiers for serious use.

**What to store:**
- Ticker symbol
- Date
- Adjusted close price (accounts for splits and dividends)
- Volume (useful for liquidity filtering later)
- Market cap snapshot (for universe filtering)

**Storage:** Start with local Parquet files via pandas. They're columnar, fast to read, and compress well. If the dataset grows or you want to run scheduled updates, graduate to a local SQLite database or a lightweight PostgreSQL instance.

**Lookback window:** 1 year of daily data is a good starting point. You'll want to experiment with 6-month and 2-year windows to see how stable correlations are.

**Key decisions to make:**
- How often to refresh data (daily cron, manual trigger, or on-demand)?
- Whether to store raw OHLCV or only adjusted close.
- How to handle missing data days (holidays differ across exchanges for international stocks like ASML and TSMC).

**Rough file structure:**
```
data/
  raw/              # raw downloaded price CSVs or Parquet files
  processed/        # cleaned, aligned daily returns
  cache/            # cached API responses to avoid re-fetching
```

---

### Component 2 — Universe Filtering

**Purpose:** Define which stocks are candidates to be "satellites." You don't want to compare anchors against the entire market indiscriminately — you need a sensible pool.

**Filtering criteria:**
- Market cap between £50M and £10B (small-cap to mid-cap range; adjustable).
- Minimum average daily volume threshold (e.g. 100,000 shares/day) to ensure the stock is actually tradeable.
- Listed on a major exchange (NYSE, NASDAQ, LSE, Euronext, etc.).
- Optionally filter by sector/industry to keep results thematically relevant (e.g. only tech-adjacent satellites for NVIDIA).

**Where to get the universe list:** The `yfinance` library doesn't provide a good stock screener. Options include downloading constituent lists from index providers (Russell 2000 for US small-caps, S&P 600, FTSE 250), scraping free screeners, or using the Financial Modeling Prep API which has a free tier with stock screening.

**A practical starting approach:**
1. Download the full Russell 2000 or S&P 1500 constituent list (widely available as CSVs).
2. Pull market cap and volume data for each ticker.
3. Filter down to your criteria.
4. Cache the filtered universe — this doesn't need to update daily.

---

### Component 3 — Correlation Engine

**Purpose:** The analytical core. Compute pairwise correlations between each anchor's returns and every satellite candidate's returns, then rank and filter.

**Method — step by step:**

1. **Compute daily log-returns** from adjusted close prices for every stock. Log-returns are preferred over simple percentage returns because they're additive over time and closer to normally distributed.

   ```
   log_return = ln(price_today / price_yesterday)
   ```

2. **Align time series.** Not all stocks trade every day (halts, different exchange calendars). Inner-join on dates so you're only comparing days where both stocks have a price.

3. **Compute Pearson correlation** between the anchor's return series and each satellite's return series. This gives you a single number between -1 and +1 for each pair.

4. **Compute rolling correlations** (e.g. 60-day rolling window) to check stability. A stock that correlates at 0.85 over the full year but swings between 0.3 and 0.95 in rolling windows is less reliable than one that stays consistently at 0.75.

5. **Rank satellites** by correlation strength. Take the top 10 (or top N, configurable) for each anchor.

6. **Statistical significance filter.** With ~250 trading days, a Pearson correlation of 0.13 is already statistically significant at p < 0.05, so most correlations will pass. More useful is to set a practical minimum threshold (e.g. 0.5 or 0.6) and only flag correlations that are both strong and stable.

**Advanced options to consider later:**
- Spearman rank correlation (more robust to outliers).
- Time-lagged cross-correlation (does the satellite move 1-2 days after the anchor? This is more predictive).
- Partial correlation controlling for the overall market (S&P 500). This separates "correlated because they both follow the market" from "genuinely correlated beyond the market factor."
- Sector-relative correlation (subtract sector ETF returns first).

**Output format:** A dataframe or dictionary structured as:
```
{
  "NVDA": [
    {"ticker": "ACME", "correlation": 0.87, "stability": 0.82, "market_cap": 2.1B, "sector": "Semiconductors"},
    {"ticker": "BETA", "correlation": 0.81, "stability": 0.78, "market_cap": 890M, "sector": "EDA Software"},
    ...
  ],
  "AAPL": [ ... ]
}
```

---

### Component 4 — Graph Construction

**Purpose:** Turn the correlation results into a proper graph data structure that can be queried, traversed, and visualised.

**Library:** NetworkX is the natural choice in Python. It handles weighted, directed or undirected graphs, has built-in layout algorithms, and exports to every common format.

**Graph structure:**
- Each anchor stock is a node (visually larger, colour-coded by sector).
- Each satellite stock is a node (sized by market cap or correlation strength).
- Each edge connects an anchor to a satellite, weighted by correlation strength.
- Satellites can connect to multiple anchors — this is where the graph gets interesting, because shared satellites reveal hidden links between anchors.

**Node metadata to attach:**
- Ticker, company name, sector, industry
- Market cap, average volume
- Current price (at time of last refresh)
- A short description or tag line (can be scraped or added manually)

**Edge metadata:**
- Pearson correlation value
- Stability score (from rolling correlation analysis)
- Time lag if applicable
- Whether the correlation is "market-adjusted" or raw

**Graph operations to support:**
- Query: "Show me the top 10 satellites for NVDA"
- Query: "Which satellites appear under both NVDA and TSMC?"
- Query: "What's the strongest cross-link between any two anchors?"
- Export to JSON, GraphML, or GEXF for use in external tools

---

### Component 5 — Visualisation & Output

**Purpose:** Make the graph explorable and useful. This is where everyday investors actually interact with the tool.

**Option A — Static visualisation (quick start):**
Use `matplotlib` with `NetworkX`'s drawing functions. Nodes sized by market cap, edges coloured by correlation strength (green = strong positive, red = inverse), labels on hover or on the graph. Good for generating PNG/PDF reports.

**Option B — Interactive web visualisation (recommended target):**
Use `Pyvis` (a Python wrapper around vis.js) or `Plotly` with network graph support. These produce self-contained HTML files where users can zoom, pan, hover over nodes for details, and click to drill down. Pyvis is the fastest path from a NetworkX graph to an interactive HTML file — it's literally one function call.

**Option C — Dashboard (stretch goal):**
Build a Streamlit or Dash app that lets users select anchors, adjust correlation thresholds and time windows with sliders, and see the graph update in real time. This is the most polished end product but requires the most work.

**What the visualisation should show at minimum:**
- Anchor nodes clearly distinguished from satellites (size, colour, border).
- Edge thickness proportional to correlation weight.
- Hover tooltip on each satellite showing: company name, ticker, market cap, correlation value, sector.
- A sidebar or table listing the top-N satellites for the currently selected anchor.
- Ability to toggle between different time windows.

---

## Suggested Tech Stack

| Layer | Library / Tool | Why |
|---|---|---|
| Price data | `yfinance` | Free, no key, sufficient for prototyping |
| Data wrangling | `pandas`, `numpy` | Industry standard for tabular data and numerical ops |
| Storage | Parquet files (start), SQLite (grow) | Fast, portable, no server needed |
| Correlation | `scipy.stats`, `pandas.DataFrame.corr()` | Built-in Pearson, Spearman, rolling windows |
| Graph | `networkx` | Full-featured graph library with export and layout |
| Visualisation | `pyvis` (interactive HTML), `matplotlib` (static) | Pyvis wraps vis.js; one call from NetworkX to browser |
| Dashboard (later) | `streamlit` | Fastest path to a shareable web UI in pure Python |
| Scheduling (later) | `cron` or `APScheduler` | For daily data refresh |
| Config | `pydantic` or YAML config file | Clean parameter management |

---

## Implementation Phases

### Phase 1 — Proof of Concept (1–2 weeks)

Goal: end-to-end pipeline for a single anchor (NVIDIA) producing a static graph image.

Tasks:
1. Set up project structure, virtual environment, and dependencies.
2. Write a data fetcher that pulls 1 year of daily adjusted close for NVDA and the Russell 2000 constituents (or a smaller subset of ~500 stocks to start).
3. Compute daily log-returns and Pearson correlations.
4. Filter to top 10 by correlation strength.
5. Build a NetworkX graph and render it with matplotlib.
6. Validate results manually — do the correlated companies make intuitive sense?

Deliverable: a Python script that outputs a graph image and a CSV of the top-10 list.

### Phase 2 — Multi-Anchor & Stability (1–2 weeks)

Goal: expand to all anchor stocks and add correlation stability analysis.

Tasks:
1. Parameterise the pipeline to accept a list of anchors.
2. Add rolling correlation calculation (60-day window).
3. Add a "stability score" metric.
4. Handle edge cases: missing data alignment, delisted stocks, stocks with short histories.
5. Add market-cap and volume metadata to nodes.
6. Generate a combined multi-anchor graph.

Deliverable: a multi-hub graph showing all anchors and their satellites, with stability scores on edges.

### Phase 3 — Interactive Visualisation (1–2 weeks)

Goal: move from static images to an explorable HTML graph.

Tasks:
1. Integrate Pyvis to generate interactive HTML from the NetworkX graph.
2. Add hover tooltips with company metadata.
3. Colour-code nodes by sector, size by market cap.
4. Add edge styling (thickness = correlation, opacity = stability).
5. Generate a companion summary table (exportable to CSV or displayed alongside).

Deliverable: a self-contained HTML file that opens in any browser and lets users explore the graph.

### Phase 4 — Advanced Analytics (2–3 weeks)

Goal: make the correlations smarter and more useful.

Tasks:
1. Add Spearman rank correlation alongside Pearson as the primary ranking/filtering metric. Small/mid-cap satellites are prone to sporadic outlier moves (M&A rumours, halts, earnings gaps) that can dominate a full-period Pearson r; Spearman's rank-based approach is robust to this. Compute both and store them on each edge — Spearman drives the top-N filter, Pearson stays as a secondary, more interpretable value for comparison against the existing ≥0.6 convention.
2. Implement market-adjusted (partial) correlation, removing S&P 500 as a confounding factor.
3. Add time-lagged cross-correlation analysis (does satellite X move 1-3 days after anchor Y?).
4. Add sector-relative correlation (subtract sector ETF returns).
5. Implement regime detection — flag when a previously strong correlation breaks down.
6. Add a "correlation of correlations" view showing how anchor-anchor relationships manifest through shared satellites.

Deliverable: richer edge metadata (Pearson + Spearman, partial correlation, time lag), a "leading indicators" list, and alerts for correlation regime changes.

### Phase 5 — Dashboard & Productionisation (2–4 weeks)

Goal: wrap everything in a Streamlit dashboard and automate data refreshes.

Tasks:
1. Build a Streamlit UI with controls for anchor selection, time window, correlation threshold, and market cap range.
2. Add daily data refresh via a scheduler.
3. Add a "watchlist" feature where users can save satellites they're interested in.
4. Add historical correlation charts (how has the NVDA ↔ ACME correlation changed over 2 years?).
5. Write documentation and a README.
6. Consider deploying to Streamlit Community Cloud for sharing.

Deliverable: a live dashboard accessible via browser, auto-updating daily.

---

## Project Structure

```
stock-correlation-graph/
│
├── README.md
├── requirements.txt
├── config.yaml                  # anchor tickers, thresholds, time windows
│
├── src/
│   ├── __init__.py
│   ├── config.py                # load and validate config
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetcher.py           # download price data from yfinance
│   │   ├── universe.py          # load and filter the satellite universe
│   │   └── storage.py           # save/load parquet files or SQLite
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── returns.py           # compute log-returns
│   │   ├── correlation.py       # pearson, rolling, partial, lagged
│   │   └── ranking.py           # rank and filter top-N satellites
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── builder.py           # construct NetworkX graph
│   │   └── queries.py           # graph traversal and query helpers
│   │
│   └── visualisation/
│       ├── __init__.py
│       ├── static_plot.py       # matplotlib rendering
│       ├── interactive.py       # pyvis HTML generation
│       └── dashboard.py         # streamlit app (Phase 5)
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── cache/
│
├── outputs/
│   ├── graphs/                  # generated graph images and HTML files
│   └── reports/                 # CSV exports, summary tables
│
├── notebooks/
│   └── exploration.ipynb        # Jupyter notebook for ad-hoc analysis
│
└── tests/
    ├── test_fetcher.py
    ├── test_correlation.py
    └── test_graph.py
```

---

## Risks & Pitfalls to Watch For

**Spurious correlations.** With hundreds of stocks and one anchor, some will correlate by pure chance. Mitigations: use a high threshold (≥ 0.6), check stability over rolling windows, and sanity-check that correlated companies have a plausible fundamental link.

**Market beta contamination.** In a bull market, most stocks go up together. If you don't adjust for the overall market, your "correlated" satellites might just be stocks that follow the S&P 500 — not the specific anchor. Phase 4's partial correlation addresses this.

**Survivorship bias.** If your universe list only includes stocks that exist today, you'll miss companies that went bankrupt or were acquired during your lookback window. This overstates the reliability of correlations. Not critical for a v1 but worth noting.

**Data quality.** Yahoo Finance occasionally has gaps, incorrect splits, or stale data. Always sanity-check a few tickers manually. Consider adding automated data quality checks (e.g. flag any stock with more than 5 consecutive missing days).

**Rate limits.** yfinance pulls from Yahoo's unofficial API. Aggressive bulk downloading can get your IP throttled. Add delays between batch requests and cache aggressively.

**International stocks.** ASML trades on Euronext and TSMC on TWSE, but both have US ADRs (ASML, TSM). Use the ADR tickers for simpler alignment with US satellite stocks. Be aware that ADR prices can diverge slightly from the home listing.

**Note on SpaceX.** SpaceX is a private company — there's no public stock price data available for it. You'll need to either remove it from the anchor list or substitute a publicly traded space-sector proxy (e.g. Rocket Lab — RKLB, or the ARKX Space ETF).

---

## Future Enhancements (Beyond v1)

- **Fundamental overlay:** Enrich satellite nodes with revenue data, earnings dates, and analyst ratings to give context beyond just price correlation.
- **News sentiment correlation:** Use a news API to check whether correlated stocks also respond to the same news themes.
- **Supply chain mapping:** Cross-reference correlation results with known supply chain data (e.g. from Bloomberg or FactSet) to distinguish "price correlation" from "actual business dependency."
- **Alert system:** Notify users when a new stock enters the top-10 for an anchor, or when a previously strong correlation breaks.
- **Multi-timeframe view:** Show how the graph differs across 3-month, 1-year, and 3-year windows side by side.
- **Community features:** Let users suggest anchors or flag interesting satellites, building a curated database over time.

---

## Getting Started — First Session Checklist

1. Create a virtual environment: `python -m venv venv && source venv/bin/activate`
2. Install core deps: `pip install yfinance pandas numpy scipy networkx pyvis matplotlib`
3. Pick one anchor (NVDA) and a small satellite pool (~100 tickers from a downloaded index list).
4. Write `fetcher.py` — pull 1 year of adjusted close for all tickers.
5. Write `returns.py` — compute log-returns.
6. Write `correlation.py` — compute Pearson r for NVDA vs each satellite.
7. Sort, take top 10, print results. Do they make sense?
8. If yes, you have your proof of concept. Move to Phase 2.
