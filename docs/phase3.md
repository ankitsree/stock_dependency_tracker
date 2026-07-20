# Phase 3 — Interactive Visualisation

**Goal (from the roadmap):** move from static images to an explorable HTML graph.

*Run via `python -m src.cli phase3` — the standalone `run_phase3.py` script described below was superseded by a shared CLI in the Phase 4.5 refactor; see [phase4-5.md](phase4-5.md).*

## What it does, in plain terms

Same multi-anchor pipeline as Phase 2 (fetch → correlate → rank → stability → combined graph), but instead of a matplotlib PNG, the graph is rendered as a **self-contained, interactive HTML file** using pyvis/vis.js. Open it in any browser: drag nodes around, zoom/pan, and hover over anything for details. A summary table sits below the graph so the same data is also readable as plain rows, not just visually.

Concretely, on top of the graph itself:

1. **Nodes are colored by sector**, sized by market cap (log scale, since market caps span orders of magnitude).
2. **Anchors are visually distinct** from satellites — a white/black star shape at a fixed large size, rather than competing for a color slot.
3. **Edges encode two things at once**: color = correlation sign (blue = positive, red = negative), width = correlation strength, and opacity = the stability score from Phase 2 (a shaky correlation literally looks faded).
4. **Hovering** over a node shows company name, sector, market cap, average volume; hovering an edge shows the anchor/satellite pair, correlation, and stability.
5. The whole page **adapts to the browser's light/dark preference** automatically (`prefers-color-scheme`), including the graph's node/edge colors and the summary table — not just the page background.

## Code map (new/changed since Phase 2)

| File | What's new |
|---|---|
| [src/visualisation/style.py](../src/visualisation/style.py) *(new)* | Pure functions for every visual encoding decision: `sector_color()`, `anchor_color()`, `edge_color()`, `edge_width()`, `edge_opacity()`, `satellite_size()`. No pyvis/matplotlib imports, so these are unit-testable without rendering anything. |
| [src/visualisation/interactive.py](../src/visualisation/interactive.py) *(new)* | `build_interactive_graph()` — builds a pyvis `Network` from the NetworkX graph, applies `style.py`'s encoding to every node/edge, generates the HTML, then post-processes it to inject a light/dark theme-switch script and the companion summary table. |
| [src/cli.py](../src/cli.py) (`phase3` subcommand) | Same orchestration as `phase2`, but calls `build_interactive_graph()` instead of `plot_graph()` and writes a `.html` instead of a `.png`. Originally a standalone `run_phase3.py` script — see [phase4-5.md](phase4-5.md). |
| [.claude/skills/network-graph-style/SKILL.md](../.claude/skills/network-graph-style/SKILL.md) *(new)* | The concrete color/size/encoding decisions below, written up once as a reusable project skill so Phase 5 (dashboard) doesn't have to re-derive them. |
| [src/graph/builder.py](../src/graph/builder.py) | Correlation, stability, market cap, and avg volume are now cast to native Python `float` when attached to the graph (`float(row["correlation"])`, etc.) — pandas/numpy scalar types aren't JSON-serializable, which the interactive renderer needs and the static one happened not to care about. |

## Key decisions

- **Color, not just position, needed a real palette.** ~15 fine-grained sector labels don't fit an 8-hue categorical palette, so they're grouped into 7 coarser color groups for visual encoding only (`style.sector_group()`) — the original precise `sector` string is untouched in tooltips and the summary table. One categorical slot (red) is deliberately left unused so red can mean "negative correlation" on edges without ever also meaning a sector. Anchors skip the categorical channel entirely — shape (star) and a fixed neutral ink color do that job instead, since there are only 3-4 anchors and each is already uniquely labeled.
- **Both light and dark mode, not just one.** Since this is a standalone file someone opens directly in their browser (no in-app theme toggle), it needed to look right in whatever mode the browser/OS is already in. `Network(bgcolor=...)` turned out to just be a CSS `background-color` on a div (not a canvas fill), but node/edge fills are vis.js DataSet items set once at generation time — those need an actual small JS snippet that detects `prefers-color-scheme` and calls `nodes.update()`/`edges.update()` with the alternate color set. Verified by extracting and running that snippet under Node with a stubbed DOM rather than trusting a browser screenshot (Chrome's `--force-color-scheme` flag didn't reliably force light mode in this environment).
- **Two real pyvis bugs surfaced and were worked around, not ignored:**
  - `Network.from_nx(graph)` **mutates the graph you pass it** — it renames the `weight` edge attribute to `width` in place, on the same dict object. Reading `graph[u][v]["weight"]` afterward silently breaks. Fixed by always passing `graph.copy()` to `from_nx()` and keeping the original `graph` for all subsequent lookups.
  - pyvis's own HTML template renders `{{heading}}` **twice**. Worked around by passing an empty heading to `Network()` and injecting exactly one `<h1>` during post-processing instead.
- **`cdn_resources="in_line"`**, not the (confusingly-named) default `"local"` — only `"in_line"` actually embeds vis-network's JS/CSS in the file rather than pulling it from a CDN, which is what makes the output genuinely openable offline. (pyvis's template still hardcodes a Bootstrap CDN link regardless of this setting — a real gap in the library, not worth working around for an internal tool.)
- **A project-level skill, not just a doc.** The color/sizing rules were derived once (using the `dataviz` skill's method: pick the job each color does, validate the categorical palette with its script, don't eyeball it) and then written into `.claude/skills/network-graph-style/SKILL.md` so future work — the Phase 5 dashboard, or a revisit of the static plot — reuses the same validated values instead of re-deriving them.

## Result

`python run_phase3.py` against live data produces `outputs/graphs/multi_anchor_dependency_graph.html`: NVDA/TSM/ASML's shared semiconductor-equipment satellites (MKSI, NVMI, AEIS, ONTO, ...) render as blue dots sized by market cap, densely connected to all three anchor stars; AAPL sits off to the side with its one weak link (QRVO). Hovering any node surfaces its sector and market cap; hovering an edge shows the exact correlation and stability figures. The page verified correctly in both light and dark rendering (screenshot-checked for dark; the light-mode JS branch verified directly under Node since forcing a real browser into light mode via CLI flags proved unreliable in this environment).
