/**
 * Visual encoding for the portfolio views.
 *
 * Two deliberate decisions, both following the project's dataviz method
 * (.claude/skills/dataviz, and network-graph-style/SKILL.md for the values):
 *
 * 1. **Factor exposure uses a SEQUENTIAL ramp, not the categorical palette.**
 *    The categorical slots in this project are spoken for — they mean *sector*
 *    everywhere else in the app (graphStyle.ts), so painting NVDA blue here
 *    would make blue mean "Semiconductor Equipment" on one screen and "NVDA"
 *    on the next. The ramp is ordered by share (darkest = largest), which is
 *    also the order the legend and the ranked bars use, so the mapping is
 *    learnable at a glance. Identity is never carried by color alone: every
 *    slice is direct-labelled in the ranked bar list beside it.
 *
 * 2. **The heatmap uses the DIVERGING pair, reusing the graph's exact poles.**
 *    Correlation is signed — a polarity job, not a magnitude one — so it gets
 *    blue↔red through a neutral midpoint rather than a one-hue ramp. Same
 *    hexes as the graph's positive/negative edges so the two views read as one
 *    system.
 */

import { PALETTES, type ThemeName } from '../../theme/tokens'

// The sequential hue, same blue pole the graph's positive edges use.
const SEQUENTIAL_POLE: Record<ThemeName, string> = { light: '#2a78d6', dark: '#3987e5' }

// Diverging poles, verbatim from graphStyle.ts's edge colors.
const DIVERGING_POSITIVE: Record<ThemeName, string> = { light: '#2a78d6', dark: '#3987e5' }
const DIVERGING_NEGATIVE: Record<ThemeName, string> = { light: '#e34948', dark: '#e66767' }

// The residual slice is not a factor and must not look like one. A warm
// neutral drawn from the theme's own border token keeps it visually recessive.
const RESIDUAL: Record<ThemeName, string> = { light: '#c9bda6', dark: '#4a3d2e' }

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '')
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  }
}

function toHexPair(value: number): string {
  return Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, '0')
}

function mixHex(a: string, b: string, t: number): string {
  const ca = hexToRgb(a)
  const cb = hexToRgb(b)
  return `#${toHexPair(ca.r + (cb.r - ca.r) * t)}${toHexPair(ca.g + (cb.g - ca.g) * t)}${toHexPair(
    ca.b + (cb.b - ca.b) * t,
  )}`
}

/**
 * Sequential step for the factor at position `index` of `count`, ranked
 * largest-first. Stops at 0.62 of the way to the surface so even the last
 * step stays clearly a mark rather than fading into the background.
 */
export function factorColor(index: number, count: number, theme: ThemeName): string {
  const steps = Math.max(1, count - 1)
  const t = count <= 1 ? 0 : (index / steps) * 0.62
  return mixHex(SEQUENTIAL_POLE[theme], PALETTES[theme].surface, t)
}

export function residualColor(theme: ThemeName): string {
  return RESIDUAL[theme]
}

/**
 * Diverging cell color for a correlation in [-1, 1]: red pole at -1, the
 * theme surface at 0, blue pole at +1. A neutral (not a hue) midpoint is the
 * rule for diverging scales — a third hue at zero would read as a category.
 */
export function correlationColor(value: number, theme: ThemeName): string {
  const clamped = Math.max(-1, Math.min(1, value))
  const pole = clamped < 0 ? DIVERGING_NEGATIVE[theme] : DIVERGING_POSITIVE[theme]
  return mixHex(PALETTES[theme].surface, pole, Math.abs(clamped))
}

/**
 * Ink for text sitting on top of a correlation cell. Cells only get dark
 * enough to need light text near the poles; everywhere else the theme's own
 * ink wins.
 */
export function correlationInk(value: number, theme: ThemeName): string {
  const strong = Math.abs(value) > 0.62
  if (theme === 'dark') return PALETTES.dark.ink
  return strong ? '#f7f2e9' : PALETTES.light.ink
}
