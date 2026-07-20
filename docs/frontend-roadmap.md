# Frontend Implementation Roadmap

A step-by-step build sequence for the Phase 5 React frontend, structured around two things at every step: **questions you answer for yourself first**, and **the prompt that follows from those answers**. The goal is that by the time you hand a step to a coding agent, the instructions are specific enough to produce something performant, responsive, flexible, and sleek — not a generic first draft you then have to fight into shape.

This assumes the decisions already made in [production-roadmap.md §8](production-roadmap.md#8-phase-5--frontend) — stack (Vite + React + TS, Tailwind, TanStack Query/Table, `react-force-graph-2d`, Recharts, React Router), the API contract, and the graph styling rules ported from `.claude/skills/network-graph-style/SKILL.md`. Don't re-derive those here; this document is about **execution order**, not architecture. The big project-level brief in production-roadmap.md §8.3 is the base context for every prompt below — each one is a scoped follow-up, not a replacement.

## How to use this

Work top to bottom. Steps 4–7 (the four core views) are logically independent once Step 3's shell exists — reorder or parallelize them if you have the bandwidth, but doing them sequentially keeps each coding-agent session's context small and focused, which tends to produce better output than one enormous session.

| Step | Goal | Pillars |
|---|---|---|
| [0](#step-0--define-the-direction-no-code) | Define the direction — no code | all four, set here once |
| [1](#step-1--scaffold--design-tokens) | Scaffold + design tokens | Sleek |
| [2](#step-2--api-client--data-layer) | API client & data layer | Performant |
| [3](#step-3--app-shell--navigation) | App shell & navigation | Flexible, Responsive |
| [4](#step-4--graph-view-core-performance-critical) | Graph view (core) | Performant, Sleek |
| [5](#step-5--satellite-ranking-table) | Satellite ranking table | Responsive, Flexible |
| [6](#step-6--ticker-detail-panel--sparkline) | Ticker detail panel & sparkline | Flexible |
| [7](#step-7--relatedness-heatmap) | Relatedness heatmap | Sleek |
| [8](#step-8--responsive-pass) | Responsive pass | Responsive |
| [9](#step-9--motion--visual-polish) | Motion & visual polish | Sleek |
| [10](#step-10--performance-audit--optimization) | Performance audit & optimization | Performant |
| [11](#step-11--accessibility-audit) | Accessibility audit | Responsive, Flexible |
| [12](#step-12--testing) | Testing | Performant (regression safety) |
| [13](#step-13--deployment-readiness-handoff) | Deployment readiness handoff | — |

*Pillars = performant / responsive / flexible / sleek-and-modern, tagged where each step's decisions most directly serve one.*

---

## Step 0 — Define the direction (no code)

The most expensive mistake at this stage isn't a wrong technical choice — it's an unanswered aesthetic or scope question that a coding agent silently answers *for* you, generically. Answer these before Step 1.

**1. What does "flexible" mean to you here?** It's doing three different jobs and they have very different costs:
   - *Handles variable data gracefully* (4 anchors today, maybe 20 later; 10 satellites per anchor today, maybe hundreds later) — build this in by default, it's not optional.
   - *Codebase stays extensible* (watchlists, auth, multi-timeframe compare slot in later without a rewrite) — also a default engineering practice below, not a UI decision.
   - *Layout is user-rearrangeable* (resizable/collapsible/draggable panels) — this is a real, separate feature with real cost (persisted layout state, resize handles, more QA surface). Decide explicitly: **in v1, or deferred?** Recommend deferring — nothing in the functional spec needs it yet.

**2. Terminal-dense or approachable-consumer?** Worth naming because the project's own roadmap sets up a tension: it exists so people *don't* need "a Bloomberg terminal" to find these connections, but the subject matter (correlation coefficients, regime breaks, partial correlation) is inherently data-dense. Both are legitimate, distinct design directions:
   - Lean **consumer-approachable** — generous whitespace, plain-language labels alongside the stats, the diagnostic columns progressively disclosed rather than all shown at once.
   - Lean **terminal-aesthetic, deliberately** — dense tables, monospace-forward, dark-by-default, wears the "quant tool" identity on purpose as a style choice, while still being usable by a non-expert.
   
   Pick one — it drives density, type scale, and motion decisions in every step below.

**3. Typography pairing.** The project's own style mandate (CLAUDE.md) explicitly warns against defaulting to Inter/Roboto/Arial *and* Space Grotesk specifically ("you still tend to converge on common choices \[like Space Grotesk\]"). Three concrete, distinct options — pick one or bring your own:
   - **A — Editorial/terminal hybrid:** [Instrument Serif](https://fonts.google.com/specimen/Instrument+Serif) for headings + [Berkeley Mono](https://berkeleygraphics.com/typefaces/berkeley-mono/) or [JetBrains Mono](https://www.jetbrains.com/lp/mono/) for tickers/numbers/data.
   - **B — Warm/technical:** [Fraunces](https://fonts.google.com/specimen/Fraunces) (variable weight, has real personality) for headings + [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) for data.
   - **C — All-in on the terminal identity:** [Martian Mono](https://fonts.google.com/specimen/Martian+Mono) or [Departure Mono](https://departuremono.com/) for *everything*, headings included — the most thematically on-the-nose choice for a stock/quant tool, pairs naturally with option 2's "terminal-aesthetic" direction if you pick that one.

**4. Accent color for UI chrome.** The graph's node/edge colors are fixed (positive/negative correlation, sector groups) and must not be reused for buttons/links/focus rings — that would make "is this a sector color or a button?" ambiguous. Pick a distinct accent identity for chrome; it should hold its own next to the graph's blue/red without competing with them.

**5. Default theme** — light or dark first? (Both are required per production-roadmap.md §8.2; this just decides which one a first-time visitor sees.)

**6. Device priority.** Checked on a phone during a commute, or used at a desk for research sessions? Both must work (mobile is not optional — it was in the original ask), but this decides where extra polish time goes first.

**7. Realistic data scale.** `config.yaml` has 4 anchors × `top_n: 10` today — roughly 40–50 nodes in the full graph. If the roadmap's "Russell 2000 screener" universe ever lands, that could jump by 10–100x. **This is the single most consequential answer for Steps 4, 5, and 10** — it decides whether plain canvas rendering is sufficient forever or whether you'll eventually need clustering/level-of-detail simplification. Answer for "today" and "the ceiling you actually expect within a year."

**8. Performance targets.** Recommended defaults (standard "good" Core Web Vitals thresholds) — confirm or adjust:
   - LCP (Largest Contentful Paint) < 2.5s on a throttled mid-tier mobile profile
   - INP (Interaction to Next Paint) < 200ms — matters most for graph drag/zoom and table sort/filter
   - CLS (Cumulative Layout Shift) < 0.1
   - Initial JS bundle (gzipped) < 250KB, with the graph library explicitly code-split since it's the heaviest dependency

**9. Breakpoints.** Recommend Tailwind's defaults (`sm` 640px / `md` 768px / `lg` 1024px / `xl` 1280px / `2xl` 1536px) unless a specific device you use falls awkwardly between them.

Write your answers down somewhere durable (a comment at the top of `frontend/README.md` is a reasonable place) — Steps 1, 4, 5, 8, and 10 all reference them directly.

---

## Step 1 — Scaffold + design tokens

**Answer first:**
- Confirmed font pairing and accent color from Step 0?
- Base spacing/radius/shadow scale — a sharp-cornered, high-contrast "data tool" feel or a softer, rounded one? (Follows from Step 0's Q2 answer.)

**Then prompt:**
> Scaffold a Vite + React + TypeScript project in `frontend/`. Configure Tailwind with CSS custom properties for all theme tokens (color, spacing, radius, shadow, font family) rather than hardcoded Tailwind defaults. Self-host the chosen font pairing \[fonts from Step 0\] via `@fontsource` or local font files — not a render-blocking third-party CDN `<link>`. Implement a light/dark theme toggle using React context + a `data-theme` attribute on `<html>`, respecting `prefers-color-scheme` as the initial default \[per Step 0's chosen default\]. Do not touch the graph's node/edge colors here — those are fixed values defined later in Step 4; this step is chrome only: background, surface, text, border, and the accent color \[from Step 0\].

**Done when:** project boots, theme toggle flips every token, fonts load without a flash of unstyled text. Run Lighthouse once against this bare shell — that number is your "before" baseline for Step 10.

---

## Step 2 — API client & data layer

**Answer first:**
- Developing against `localhost:8000` only for now, or does a deployed API instance exist to point at? (Decides whether an env-based API base URL split is needed now or can wait for production-roadmap.md §6.)
- Client-side cache staleness — recommend a short TanStack Query `staleTime` (a few minutes) independent of the backend's own 6-hour TTL; the two caches solve different problems (server: avoid hammering yfinance; client: avoid re-fetching while a human is actively looking at the same screen).
- Failed requests: silent auto-retry-once for background refetches, but a visible retry action (not silent) for anything the user directly triggered (a ticker search) — so failure is never invisible.

**Then prompt:**
> Generate a typed API client from the running API's `/openapi.json` using `openapi-typescript`. Wrap each endpoint in a TanStack Query hook: `useGraph(anchors, topN, threshold)`, `useAnchorCorrelations(ticker, topN, threshold)`, `usePriceHistory(ticker)`, `useRelatedness(anchors)`, `useCompanySearch(query)`. Build three shared components used by every view from here on: `<LoadingState>`, `<ErrorState kind="not-found" | "insufficient-data" | "generic">`, `<EmptyState>` — mapping the API's 404 (unknown ticker) and 422 (insufficient price history) to distinct, informative `ErrorState` variants, not a single generic error message.

**Done when:** hooks return real data against a running local API instance; requesting a deliberately invalid ticker renders the 404 `ErrorState`, not a crash or a blank screen.

---

## Step 3 — App shell & navigation

**Answer first:**
- Nav pattern — recommend a top bar with an inline, search-as-you-type ticker switcher (not a fixed dropdown, since the API resolves any real ticker) over a sidebar; reserve a sidebar for if/when a watchlist view gets added.
- Real routes or panels within one page? Recommend real routes (`/`, `/anchor/:ticker`, `/relatedness`) — a URL you can send someone should reproduce the exact view they're looking at.
- Should selection/filter state (selected anchor, `top_n`, `threshold`) live in the URL as query params? Strongly recommend yes — nearly free with React Router's `useSearchParams`, and it makes every view state shareable and bookmarkable.

**Then prompt:**
> Build the route structure \[routes from above\] with React Router. Header contains: the ticker search/switcher, the theme toggle from Step 1, and a persistent, always-visible note that correlations are price-based, not verified supply-chain data (per production-roadmap.md §8.2 — this is a project-wide convention, not optional fine print). Wire anchor selection and the `top_n`/`threshold` filters to URL search params so every view is a shareable link.

**Done when:** switching anchors updates the URL; reloading the page on a deep link reproduces the same view.

---

## Step 4 — Graph view (core, performance-critical)

**Answer first:**
- Confirmed node-count ceiling from Step 0 Q7? This decides everything else in this step.
- Interaction model — recommend: click a node to focus it (dims the rest, opens the detail panel from Step 6), drag temporarily repositions it (physics resumes on release, no permanent pin in v1), no other gestures. The simplest model that still feels alive; add more later if it feels lacking.
- Touch behavior, since hover tooltips don't exist on a touchscreen — recommend a bottom sheet on tap rather than a fragile tap-once-for-tooltip/tap-again-to-navigate convention.

**Then prompt:**
> Integrate `react-force-graph-2d` fed by `useGraph`. Implement `nodeCanvasObject`/`linkCanvasObject` draw callbacks using these exact values (do not invent new ones — they must match the project's existing Python-rendered graphs): satellite node color by sector color-group per `.claude/skills/network-graph-style/SKILL.md`'s palette; anchor nodes fixed near-black `#0b0b0b` (light) / near-white `#ffffff` (dark) with a star shape vs. satellites' dot shape; edge color blue `#2a78d6`/`#3987e5` for positive correlation, red `#e34948`/`#e66767` for negative; edge width `1 + |correlation| * 6` px; edge opacity = stability clamped `[0.25, 1.0]`, full opacity if stability is absent; satellite node size `12 + 6 * log10(market_cap / 1e8)` clamped `[12, 40]`, fixed `18` if `market_cap` is missing, anchors fixed `40`. Debounce re-layout on filter/slider changes rather than snapping instantly. On touch devices, tapping a node opens a bottom sheet instead of a hover tooltip.

**Done when:** renders real data, stays interactive (pan/zoom/click/drag) without dropped frames at the node count confirmed in Step 0, mobile tap opens the sheet instead of doing nothing.

---

## Step 5 — Satellite ranking table

**Answer first:**
- Default visible columns on desktop vs. mobile — recommend desktop shows every diagnostic column (correlation, stability, partial correlation, sector-relative correlation, best lag, regime-break flag), mobile shows ticker/name/correlation/stability with the rest behind a tap-to-expand row.
- Pagination vs. plain scroll vs. virtualization — at today's scale (`top_n` defaults to 10) plain scroll is enough; only add virtualization if Step 0's data-scale answer says this will grow substantially.

**Then prompt:**
> Build the satellite table with TanStack Table, sortable on every numeric column, fed by `useAnchorCorrelations`. Responsive column visibility driven by a `useMediaQuery` hook (state-driven, not just CSS `display:none` — hidden-but-rendered cells still cost layout and accessibility-tree weight). Visually flag `regime_break: true` rows distinctly. This is the accessibility-primary view for the whole app (per production-roadmap.md §8.2, since the canvas graph is not screen-reader-accessible) — full keyboard navigation (arrow keys or tab order through sortable headers and rows) is required, not optional here specifically.

**Done when:** fully sortable and operable with keyboard only, no mouse; passes an automated a11y scan (axe) on its own, independent of the rest of the app.

---

## Step 6 — Ticker detail panel & sparkline

**Answer first:**
- Does clicking a graph node and clicking a table row open the same panel? Strongly recommend yes — one shared component, two trigger points, rather than two divergent "detail view" implementations that drift apart over time.
- Placement — recommend a persistent side panel on desktop (keeps the graph visible while inspecting a satellite; a modal would block it) collapsing to a bottom sheet on mobile (consistent with Step 4's mobile tap behavior — same sheet, reused).

**Then prompt:**
> Build one `<TickerDetailPanel>` fed by `usePriceHistory`, rendering a Recharts sparkline plus the company profile fields (name, sector, market cap, avg volume). Wire both the graph's node-click handler (Step 4) and the table's row-click handler (Step 5) to open this same component with the clicked ticker — no second implementation.

**Done when:** opening from the graph and opening from the table produce identical content; closing the panel returns keyboard focus to whichever element triggered it.

---

## Step 7 — Relatedness heatmap

**Answer first:**
- Own route, or a collapsible panel on the dashboard? This is a secondary/exploratory feature (a real differentiator, per production-roadmap.md §8.2, but not core to the everyday workflow) — recommend a collapsible panel or a low-traffic dedicated route, not prime dashboard real estate.

**Then prompt:**
> Build a small anchor×anchor heatmap fed by `useRelatedness`. Reuse the graph's exact diverging blue/red edge-color scale (Step 4) for cell color, so it reads as part of the same visual system rather than a bolted-on chart with its own color logic.

**Done when:** renders correctly for the full configured anchor set; color scale visually matches the graph's edges.

---

## Step 8 — Responsive pass

**Answer first:**
- Revisit Step 0 Q6 (device priority) and Q9 (breakpoints) — confirmed, or adjusting based on what building Steps 1–7 revealed?

**Then prompt:**
> Audit every component built so far at 375px, 768px, 1024px, and 1440px widths. Fix overflow/truncation. Confirm the graph canvas resizes to its container (not a fixed pixel size) and that the table's mobile column-collapse (Step 5) actually engages at the right breakpoint. Verify all touch targets are ≥44px. Test with real device emulation (not just a resized desktop browser window — emulation exercises touch event paths a resized mouse-driven window doesn't).

**Done when:** no horizontal scroll at any breakpoint except inside deliberately scrollable containers (the table); a real mobile-device or device-emulation pass is done, not just responsive-resize-in-devtools.

---

## Step 9 — Motion & visual polish

**Answer first:**
- Respect `prefers-reduced-motion`? Recommend yes, unconditionally — correct default, low cost, doubles as an accessibility requirement.
- Where does the "one well-orchestrated staggered reveal" (per the aesthetics brief in production-roadmap.md §8.3) happen — first load only, or every route change? Recommend first load only; re-animating on every navigation reads as noisy rather than delightful after the second time you see it.

**Then prompt:**
> Implement a staggered entrance animation (CSS `animation-delay`, not a JS animation library, for the initial render) on first load only — route transitions after that should feel instant. Add hover/focus micro-interactions to interactive elements (buttons, table rows, graph nodes). Replace generic spinners with loading skeletons shaped like the final layout. Wrap all of the above in a `prefers-reduced-motion: reduce` check that disables the non-essential motion cleanly.

**Done when:** first load feels considered, repeat navigation doesn't re-animate, and toggling reduced-motion at the OS level actually changes behavior.

---

## Step 10 — Performance audit & optimization

**Answer first:**
- Confirm or adjust the Step 0 targets (LCP/INP/CLS/bundle size) before auditing against them.

**Then prompt:**
> Run Lighthouse (or WebPageTest) against a production build under mobile throttling, not against the unthrottled localhost dev server. Code-split `react-force-graph-2d` and any route not needed on first paint. Check the gzipped initial bundle against the Step 0 budget. Use React Query Devtools to confirm no redundant refetching is happening across the views built in Steps 4–7. Confirm fonts/images aren't blocking LCP.

**Done when:** meets the Step 0 targets under throttling — a passing score on unthrottled localhost is not sufficient evidence, it's the single most common false-positive in frontend perf work.

---

## Step 11 — Accessibility audit

**Answer first:**
- Nothing new to decide — this step verifies what Steps 1–9 already committed to (keyboard nav in Step 5, reduced-motion in Step 9, focus return in Step 6).

**Then prompt:**
> Do a full keyboard-only pass through every view — no mouse. Run an automated axe scan across the app. Do a screen-reader spot-check specifically on the satellite table (Step 5), since it's the designated accessible primary interface for a canvas-rendered graph that a screen reader cannot otherwise interpret.

**Done when:** axe reports zero critical/serious issues; every interactive element is reachable and operable by keyboard alone.

---

## Step 12 — Testing

**Answer first:**
- Which flows actually matter enough for an end-to-end test? Recommend exactly three, matching the backend's existing philosophy of focused tests over exhaustive ones: (1) dashboard loads and the graph renders, (2) searching a valid ticker opens the detail panel with real data, (3) searching an invalid ticker shows the 404 empty state rather than crashing.

**Then prompt:**
> Write Vitest + React Testing Library unit tests for the shared query hooks (Step 2) and the detail panel's dual-trigger logic (Step 6). Write one Playwright spec covering the three flows above. Wire both into CI — either a new `frontend-ci.yml` or an additional job in the existing `.github/workflows/ci.yml` from production-roadmap.md §7.

**Done when:** `npm test` and the Playwright spec both pass locally and in CI.

---

## Step 13 — Deployment readiness handoff

**Answer first:**
- Nothing new — this step confirms production-roadmap.md §6/§9 assumptions actually hold once real code exists.

**Then prompt:**
> Confirm the API base URL switches correctly between a local dev build and a production build via environment variables. Confirm the Vite build output matches what Vercel expects (zero-config for a standard Vite project). Open a PR and confirm Vercel's automatic preview deployment actually renders and functions end-to-end against whatever API instance it's configured to hit.

**Done when:** a real Vercel preview URL loads and works — graph renders, search works, detail panel opens — not just "the build succeeded."

---

## After this

Watchlists and any auth-gated feature are explicitly out of scope here (production-roadmap.md §8.2) — they need the `watchlists` schema and a real auth story from §6 of that document first. Treat everything above as the complete v1 scope; revisit only once that backend slice exists.
