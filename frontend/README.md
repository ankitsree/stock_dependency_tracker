# Stock Dependency Tracker — Frontend

Phase 5 React frontend for the stock correlation dependency graph. Built against
the existing FastAPI backend (see [../docs/frontend-roadmap.md](../docs/frontend-roadmap.md)
and [../docs/frontend-build-plan.md](../docs/frontend-build-plan.md)).

**Status:** Steps 1–2 complete — scaffold, design tokens + theming, and the
typed API data layer. The four views (graph, table, detail panel, heatmap) are
Steps 3–7 and not built yet.

## Locked design decisions (frontend-roadmap.md Step 0)

- **Flexible** = handles variable data gracefully + stays extensible. No
  resizable/draggable panels in v1.
- **Consumer-approachable**, not terminal-dense — generous whitespace,
  progressive disclosure.
- **Typography:** Martian Mono (variable) for everything, with approachable
  spacing/hierarchy rather than terminal density.
- **Accent:** muted clay/terracotta (`#b5573a` light / `#e08a63` dark).
- **Default theme:** light cream/beige. Dark mode required, not default.
- **Primary device:** desk/laptop research sessions; mobile still supported.
- **Data scale:** many anchors, `top_n` 10–15; universe ≤ 55 today.
- **Perf targets:** LCP < 3.1s, INP < 250ms, CLS < 0.12, bundle < 310 KB gz.

## Stack

Vite 8 · React 19 · TypeScript 5.9 · Tailwind CSS v4 (CSS-first `@theme`) ·
TanStack Query v5 · openapi-typescript (typed client).

> Note: Tailwind v4 is CSS-first — theme tokens live in
> [src/styles/globals.css](src/styles/globals.css), not a `tailwind.config.ts`,
> and there is no `postcss.config.js`. This deviates from the file structure
> sketched in frontend-build-plan.md §3 (written before pinning a version); v4's
> `@theme` model is a closer fit for "CSS variables as the source of truth."

## Local development

Two servers run concurrently:

```bash
# terminal 1 — backend (from the repo root, not here)
venv/bin/uvicorn src.api.main:app --reload --port 8000

# terminal 2 — frontend
cd frontend
npm install
npm run dev            # http://localhost:5173
```

`config.yaml`'s `cors_allowed_origins` already allows `http://localhost:5173`,
so no CORS setup is needed. The API base URL is read from `VITE_API_BASE_URL`
([.env.development](.env.development) / [.env.production](.env.production)).

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR. |
| `npm run build` | Type-check (`tsc -b`) then production build. |
| `npm run typecheck` | Type-check only. |
| `npm run lint` | Oxlint. |
| `npm run generate:api` | Regenerate `src/api/generated/schema.d.ts` from the running API's `/openapi.json`. Backend must be up. |

## Layout

```
src/
  api/            client.ts (fetch wrapper + ApiError/errorKind), hooks/, generated/ (typed schema)
  components/     layout/ (ThemeToggle), shared/ (Loading/Error/Empty states)
  theme/          ThemeProvider (data-theme switch), tokens.ts (palette for canvas draws)
  styles/         globals.css (Tailwind + design tokens), fonts.css (self-hosted Martian Mono)
  types/          domain.ts (friendly re-exports of the generated schema)
```

The `data-theme` attribute is set pre-paint by an inline script in
[index.html](index.html) (no flash of the wrong theme), then owned by
`ThemeProvider`.
