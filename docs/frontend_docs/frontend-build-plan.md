# Frontend Build Plan

The concretized output of [frontend-roadmap.md](frontend-roadmap.md)'s Step 0: your answers, locked in and reconciled where two of them pulled in different directions, plus the rough file structure and the local dev/iteration workflow for actually building it. Read Step 0 there for the original questions and reasoning; this document is the answer key plus what to do with it.

## 1. Step 0 answers, locked in

| # | Question | Your answer | Notes |
|---|---|---|---|
| 1 | What does "flexible" mean | Handles variable data gracefully + codebase stays extensible | Resizable/rearrangeable panels confirmed **out of scope** for v1, as recommended. |
| 2 | Terminal-dense or consumer-approachable | Consumer-approachable | Generous whitespace, plain-language labels alongside stats, diagnostic columns progressively disclosed rather than all-shown-always. |
| 3 | Typography | Option C — all-monospace | See reconciliation below — this needs to coexist with #2. |
| 4 | Accent color | *(not answered)* | Filled in below with a reasoned default — flag if you want something else. |
| 5 | Default theme | Light, cream/beige | Concrete tokens proposed below. Dark mode is still required (per production-roadmap.md §8.2's non-negotiable list), just not the default. |
| 6 | Device priority | Desk/laptop research sessions | Re-weights, doesn't eliminate, the mobile requirement — see below. |
| 7 | Data scale | Many anchors, `top_n` user-defined 10–15 | Grounded against the real universe size below — the actual ceiling is smaller than "many anchors" might suggest. |
| 8 | Performance targets | ~20–25% more relaxed than my defaults | Recomputed below. |
| 9 | Breakpoints | Tailwind defaults | Confirmed, with `lg`/`xl` as the primary-effort breakpoints given #6. |

### Reconciling #2 and #3

Option C (all-monospace — Martian Mono or Departure Mono, for *everything*) was framed in frontend-roadmap.md as pairing naturally with the terminal-dense direction, not the consumer-approachable one. They're not actually incompatible, but it takes a deliberate choice to make them work together: **use the monospace typeface, but apply consumer-approachable spacing and hierarchy rules, not terminal density.** Concretely:
- **Martian Mono over Departure Mono** — it's a variable font (weight range ~100–800), so it can carry both headings and body/data through weight and size contrast alone, without needing a second typeface or feeling like a cramped single-weight terminal dump. Departure Mono is gorgeous but single-weight and more overtly "hacker terminal" — harder to make feel approachable. Easy to swap later if you decide you want that edgier feel after all.
- Generous line-height (1.5–1.6 for body text, tighter for headings), real whitespace between sections, and numbers/tickers given breathing room rather than packed into dense grid cells.
- The result should read as "a well-typeset modern data tool that happens to use monospace" (closer to how some modern fintech/dev-tool dashboards use mono for numerals) — not a Bloomberg terminal.

### Filling in #4 — accent color

Left unanswered, and it's a genuinely constrained choice: the graph's own palette (`.claude/skills/network-graph-style/SKILL.md`) already claims blue, aqua, yellow, green, violet, magenta, and orange across its 7 sector groups, plus blue and red as the fixed positive/negative edge colors. That's essentially the whole standard categorical wheel spoken for. Picking a UI chrome accent from that same set risks reading as "is this a sector color or a button?" even outside the graph itself.

**Recommendation: a muted clay/terracotta**, kept low-saturation enough to read as "warm ink" rather than competing with the graph's brighter, more saturated hues, and a natural pairing with a cream/beige base:
- Light: `#b5573a` (accent), `#9c4830` (hover/active)
- Dark: `#e08a63` (accent), `#f0a480` (hover/active)

Used sparingly — primary buttons, links, focus rings, selected states — not as a background wash. Flag it if you'd rather go a different direction; this is the one answer here that's genuinely my guess filling a gap, not your call.

### #6 device priority — what actually changes

"Responsive" doesn't get dropped, but the effort allocation shifts: **design and polish for a 13–16" laptop viewport first** (roughly the `lg`–`xl` Tailwind range), verify it holds up on a tablet, and treat phone-width as best-effort graceful degradation rather than a launch blocker. This changes emphasis in frontend-roadmap.md Step 8, not its requirement to exist.

### #7 — the real data ceiling

"Many anchors" sounds like it implies a big graph, but worth grounding in what the backend actually holds today: `src/data/universe.py`'s satellite pool is a **hardcoded list of exactly 55 tickers** (confirmed by counting it directly). Every anchor draws its satellites from that same shared pool — so no matter how many anchors a user selects, total *unique* satellite nodes cannot exceed 55 today (with heavy overlap expected and, per the original roadmap, actually the interesting part — shared satellites are "where the graph gets interesting").

Concretely, worst case today: ~10–20 anchors selected × `top_n` up to 15 → up to a few hundred edges, but never more than 55 + (number of anchors) unique nodes — realistically well under 100 nodes total. That's comfortably within `react-force-graph-2d`'s canvas rendering without needing clustering or level-of-detail simplification.

Two things follow from this:
- **Don't build clustering/LOD complexity now** — there's no data volume that justifies it yet.
- **Don't hardcode assumptions about anchor/satellite counts anywhere** (styling, layout, "top N anchors fit on one row" type logic) — the moment production-roadmap.md §6's Postgres/screener work lands, the universe could grow well past 55, and the whole point of "flexible" (#1) is that this shouldn't require a rewrite when it does.

This also simplifies the anchor-selection UI: since `GET /api/graph?anchors=` already accepts a list of any tickers (not just `config.yaml`'s 4), "choose from many anchors" is purely a frontend multi-select build — no backend change needed.

### #7 continued — the `top_n` control

10–15 is a narrow range (6 discrete values), not a continuous one. A **stepper or segmented control** (`10 · 11 · 12 · 13 · 14 · 15`) communicates that better than a slider, which implies a large continuous range. Recommend building it as a stepper. Note this is a purely frontend-imposed constraint — the API's `top_n` param accepts any positive integer server-side, so widening the range later is a UI-only change.

### #8 — recomputed performance targets

20–25% looser than frontend-roadmap.md Step 0's proposed defaults:

| Metric | Original | Relaxed (×1.20–1.25) | Target going forward |
|---|---|---|---|
| LCP | < 2.5s | 3.0–3.1s | **< 3.1s** |
| INP | < 200ms | 240–250ms | **< 250ms** |
| CLS | < 0.1 | 0.12–0.125 | **< 0.12** |
| Initial JS bundle (gzipped) | < 250KB | 300–312KB | **< 310KB** |

These are the numbers frontend-roadmap.md Step 10's audit checks against.

---

## 2. Design tokens (concrete starting values)

CSS custom properties, defined once in `styles/globals.css`, switched via a `data-theme` attribute — same mechanism described in frontend-roadmap.md Step 1.

| Token | Light (cream/beige, default) | Dark |
|---|---|---|
| `--color-bg` | `#f7f2e9` | `#1c1712` |
| `--color-surface` | `#fffaf0` | `#241d16` |
| `--color-ink` (primary text) | `#2a2420` | `#f0e9db` |
| `--color-ink-muted` (secondary text) | `#6b6259` | `#a89e90` |
| `--color-border` | `#e3d9c6` | `#352b20` |
| `--color-accent` | `#b5573a` | `#e08a63` |
| `--color-accent-hover` | `#9c4830` | `#f0a480` |

Both themes stay in the same warm/editorial family deliberately — cream-and-ink in light mode, espresso-and-cream in dark mode — rather than switching to a generic dark slate that would abandon the identity the moment someone toggles the theme.

**Why tokens also need a plain TypeScript export, not just CSS variables:** `react-force-graph-2d`'s canvas draw calls (`nodeCanvasObject`/`linkCanvasObject`) can't read CSS custom properties — canvas needs actual JS string/number values. Mirror the palette in `theme/tokens.ts` as plain exported constants, consumed by the graph and heatmap draw calls, kept in sync with `globals.css` by hand (small enough surface that a build-time codegen step isn't worth it yet).

Font: **Martian Mono** (variable, weights 300/400/500/700 pulled in), self-hosted via `@fontsource/martian-mono` or local font files — not a render-blocking third-party CDN link (ties into the LCP budget above).

---

## 3. Rough file structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── .env.development              # VITE_API_BASE_URL=http://localhost:8000/api
├── .env.production
├── public/
│   └── favicon.svg
├── src/
│   ├── main.tsx
│   ├── App.tsx                   # router + providers root
│   ├── styles/
│   │   ├── globals.css           # Tailwind directives + §2's CSS variables (light/dark)
│   │   └── fonts.css             # @font-face, self-hosted Martian Mono
│   ├── theme/
│   │   ├── ThemeProvider.tsx      # data-theme switch, prefers-color-scheme default
│   │   └── tokens.ts              # §2's palette mirrored as plain TS constants for canvas use
│   ├── api/
│   │   ├── client.ts              # thin fetch wrapper, base URL from env
│   │   ├── generated/             # openapi-typescript output — regenerate via `npm run generate:api`, never hand-edit
│   │   │   └── schema.d.ts
│   │   └── hooks/
│   │       ├── useGraph.ts
│   │       ├── useAnchorCorrelations.ts
│   │       ├── usePriceHistory.ts
│   │       ├── useRelatedness.ts
│   │       └── useCompanySearch.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── TickerSearch.tsx        # header quick-jump: type any ticker → /anchor/:ticker
│   │   │   └── ThemeToggle.tsx
│   │   ├── graph/
│   │   │   ├── DependencyGraph.tsx     # react-force-graph-2d wrapper
│   │   │   ├── graphStyle.ts            # ported color/size/width/opacity formulas — single source, shared with the heatmap
│   │   │   ├── AnchorMultiSelect.tsx     # dashboard-scoped: which anchors are in the current graph (chips, not a single dropdown)
│   │   │   └── GraphControls.tsx         # top_n stepper (10–15) + threshold slider, feeds useGraph
│   │   ├── satellite-table/
│   │   │   ├── SatelliteTable.tsx
│   │   │   ├── columns.tsx
│   │   │   └── useResponsiveColumns.ts
│   │   ├── ticker-detail/
│   │   │   ├── TickerDetailPanel.tsx
│   │   │   └── PriceSparkline.tsx
│   │   ├── relatedness/
│   │   │   └── RelatednessHeatmap.tsx
│   │   └── shared/
│   │       ├── LoadingState.tsx
│   │       ├── ErrorState.tsx            # maps 404 / 422 / generic, per production-roadmap.md §8.2
│   │       ├── EmptyState.tsx
│   │       └── CorrelationDisclaimer.tsx  # persistent "correlation ≠ causation" note
│   ├── pages/
│   │   ├── DashboardPage.tsx
│   │   ├── AnchorDetailPage.tsx
│   │   └── RelatednessPage.tsx
│   ├── routes.tsx
│   ├── lib/
│   │   └── useMediaQuery.ts
│   └── types/
│       └── domain.ts                     # narrowed/re-exported types from api/generated
├── tests/
│   ├── setup.ts
│   ├── components/
│   │   └── TickerDetailPanel.test.tsx
│   └── e2e/
│       └── smoke.spec.ts                 # Playwright — the 3 flows from frontend-roadmap.md Step 12
└── README.md                             # dev quickstart, mirrors §4 below
```

`AnchorMultiSelect` (dashboard, "which anchors are active") and `TickerSearch` (header, "jump to any single ticker's detail page") are deliberately two different components — one is a multi-select filter feeding the combined graph, the other is a single-target quick-navigation search. Conflating them would make both worse at their actual job.

---

## 4. Local dev & iteration workflow

**Prerequisites:** Node 20 LTS, the backend's existing venv.

**Two servers, running concurrently:**

```bash
# terminal 1 — backend, from repo root
venv/bin/uvicorn src.api.main:app --reload --port 8000
# confirm: curl http://localhost:8000/api/health

# terminal 2 — frontend
cd frontend && npm install && npm run dev
# serves at http://localhost:5173
```

`config.yaml`'s `cors_allowed_origins` already includes `http://localhost:5173` — zero CORS setup needed to talk to the real local API from day one.

**What "iterative" looks like turn by turn:**
1. Agree on the next small slice — a whole frontend-roadmap.md step, or something smaller (e.g. "just the header").
2. I write or edit the files for that slice.
3. Vite's dev server hot-reloads automatically. Most edits (markup, styles, most component logic) appear in your already-open browser tab within about a second, without losing component state. A few kinds of change (editing `vite.config.ts`, adding a new env var, sometimes a new dependency) force a full page reload instead of hot-reloading — expected, not a bug.
4. You look at `http://localhost:5173` in your own browser and tell me what's off — or screenshot it and share the image directly in chat, or save it to a file and give me the path. I can read images directly and react to what's actually rendered, not just to what the code claims it renders.
5. I adjust, HMR updates again, repeat.

**An honest caveat:** I don't have a browser-automation or screenshot tool in this environment, so I can't independently open the page and look at it — the visual "does this look right" check has to go through you, either directly or via a screenshot you share. What I *can* do without you looking at anything: start/stop both dev servers, watch their terminal output for build or runtime errors, run lint/typecheck/tests, and verify API responses look correct. If you want me to be able to see the rendered page myself, a Playwright-based MCP tool would give me that — happy to help wire one up if you want it, but it's not required to iterate effectively at the pace above.

**Batching the heavier checkpoints:** don't run the full performance/accessibility audits (frontend-roadmap.md Steps 10–11) after every small tweak — those are checkpoint steps, meant to run once a meaningful chunk of views is functionally done, not continuously during day-to-day iteration.

---

## 5. Where to actually start

Frontend-roadmap.md Step 1 (scaffold + design tokens) is the literal next action — everything in §2 and §3 above is its concrete input. Say the word and I'll scaffold `frontend/` for real against this structure.
