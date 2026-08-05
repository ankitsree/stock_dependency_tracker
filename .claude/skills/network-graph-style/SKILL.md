---
name: network-graph-style
description: Use when styling any node/edge visualisation in this project (pyvis interactive HTML, matplotlib static plots, or a future Streamlit dashboard) — colors, sector groupings, sizing, and light/dark handling for the stock dependency graph. Concrete values derived from the dataviz skill; don't re-derive from scratch.
version: 0.1.0
---

# Network graph style guide (this project)

Concrete, validated color/encoding decisions for every graph rendering in this
repo (`static_plot.py`, `interactive.py`, and any future dashboard view). These
were derived once using the `dataviz` skill's method — reuse them rather than
re-deriving, and only re-run the validator (`scripts/validate_palette.js` in
the dataviz skill) if you change a hue or add a sector group.

## Why sectors are grouped, not colored 1:1

`src/data/universe.py` has ~15-16 distinct `sector` strings, but a categorical
palette tops out at 8 hues (a 9th+ series has to fold into "Other" — see the
dataviz skill's anti-patterns). Group the fine-grained sector into one of 7
coarser **color groups** for visual encoding only; keep the original `sector`
string as-is in node metadata/tooltips for anything that needs the precise
label.

| Color group | Sectors folded in |
|---|---|
| Semiconductor Equipment | Semiconductor Equipment |
| Semiconductors | Semiconductors |
| Chip IP, Materials & Memory | Semiconductor IP, Semiconductor Materials, Memory, Memory/Hardware |
| Photonics & Optical | Laser/Photonics, Optical Networking, Test & Measurement |
| Contract Manufacturing | Contract Manufacturing |
| Networking & Systems | Networking Hardware, Electronic Systems |
| Other Components | EDA Software, Electronic Components, Electronic Materials, Precision Components |

That's 7 groups, deliberately leaving one categorical slot (red) unused —
see below.

## Hex values (validated — `node scripts/validate_palette.js`, both PASS)

Assigned in the dataviz skill's fixed categorical order, **skipping slot 6
(red)** so red is reserved exclusively for negative-correlation edges and
never means "a sector" anywhere in this project:

| Slot | Group | Light | Dark |
|---|---|---|---|
| 1 (blue) | Semiconductor Equipment | `#2a78d6` | `#3987e5` |
| 2 (aqua) | Semiconductors | `#1baf7a` | `#199e70` |
| 3 (yellow) | Chip IP, Materials & Memory | `#eda100` | `#c98500` |
| 4 (green) | Photonics & Optical | `#008300` | `#008300` |
| 5 (violet) | Contract Manufacturing | `#4a3aa7` | `#9085e9` |
| 7 (magenta) | Networking & Systems | `#e87ba4` | `#d55181` |
| 8 (orange) | Other Components | `#eb6834` | `#d95926` |

Validated: light mode all PASS except a contrast WARN on aqua/yellow/magenta
(sub-3:1) — mitigated because node tickers are always shown as direct labels
on the graph, and a companion HTML table ships alongside every interactive
graph (both count as the required "relief"). Dark mode all PASS except a
CVD WARN (worst adjacent ΔE 10.3, floor band) — also mitigated by direct
labels being always-on.

## Anchor nodes: never colored by sector

Anchors (NVDA, TSM, ASML, ...) don't get a categorical slot — there are only
3-4 of them and each is uniquely labeled, so color isn't needed for their
identity. Instead they get a **different shape** (`star` in pyvis/vis.js vs
`dot` for satellites) and a fixed neutral fill that's the theme's primary-ink
token — max contrast on either surface, and unambiguously "not a sector
color":

- Light mode: `#0b0b0b` (near-black on the `#fcfcfb` light surface)
- Dark mode: `#ffffff` (white on the `#1a1a19` dark surface)

## Edges: diverging pair, not the categorical palette

Edge color encodes correlation **sign** (polarity — a diverging job, per the
dataviz skill, not categorical identity):

- Positive correlation → blue: `#2a78d6` light / `#3987e5` dark (slot 1 — same
  hue as the sequential default, reused deliberately since it's the same
  "this is the positive/primary direction" idea)
- Negative correlation → red: `#e34948` light / `#e66767` dark (the dataviz
  skill's diverging red pole)

Other edge encodings:
- **Width** = magnitude: `1 + |correlation| * 6` (px), same formula in both
  the static and interactive renderers, so switching between them doesn't
  change what "thick" means.
- **Opacity** = stability score, clamped to `[0.25, 1.0]` — never fully
  transparent even at zero stability, so the edge stays clickable/visible;
  full opacity (1.0) when no stability score exists (e.g. Phase 1 output,
  which predates the stability metric).

## Node size: market cap, log-scaled

Satellite node size scales with `market_cap` on a **log scale** (market caps
span orders of magnitude — linear scaling would make everything except the
largest one or two nodes invisible): `size = 12 + 6 * log10(market_cap / 1e8)`,
clamped to `[12, 40]`. Falls back to a fixed `18` when `market_cap` metadata
isn't available (Phase 1 graphs, or any ticker `fetch_metadata()` couldn't
resolve). Anchor nodes are a fixed `40` regardless of their own market cap —
size is reserved for distinguishing satellites from each other, not for
outranking the anchor (that's already handled by shape).

## pyvis-specific gotchas

- `Network(bgcolor=...)` is a **CSS `background-color` on the `#mynetwork`
  div**, not a canvas fill — so light/dark theme switching is just a CSS
  `@media (prefers-color-scheme: dark)` override injected after
  `net.generate_html()`, no JS canvas redraw needed.
- Use `cdn_resources="in_line"` (not the default `"local"`, which — despite
  the name — still pulls vis-network's JS/CSS from a CDN). `"in_line"` embeds
  vis-network directly in the file, which is what actually makes the output
  openable offline. Note pyvis's own template still hardcodes a Bootstrap CDN
  `<link>`/`<script>` regardless of this setting — a real self-containment
  gap in the library itself, not something worth working around for an
  internal tool.
- `net.from_nx(graph)` copies node/edge attributes through as extra dict keys,
  but doesn't map them to vis.js visual properties automatically — you still
  have to walk `net.nodes` / `net.edges` afterward and set `color`, `size`,
  `shape`, `title` (tooltip), and `width` yourself from those attributes.
- **`net.from_nx(graph)` mutates the graph you pass it** — it renames the
  `weight` edge attribute to `width` *in place* on the same attribute dicts
  (not a copy). If you read `graph[u][v]["weight"]` again after calling
  `from_nx`, it's gone. Always call `net.from_nx(graph.copy())` and keep using
  the original `graph` object for your own attribute lookups.
