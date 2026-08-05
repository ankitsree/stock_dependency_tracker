/**
 * Graph visual encoding — ported verbatim from the project's
 * .claude/skills/network-graph-style/SKILL.md so the web graph matches the
 * existing Python (pyvis/matplotlib) renderers exactly. Do NOT invent new
 * values here; these are the validated ones. This is the single source shared
 * by the force graph and (later) the relatedness heatmap's diverging scale.
 */

import { PALETTES, type ThemeName } from '../../theme/tokens'
import type { GraphNode, GraphResponse } from '../../types/domain'

type ColorGroup =
  | 'equipment'
  | 'semiconductors'
  | 'ipMaterialsMemory'
  | 'photonics'
  | 'contractMfg'
  | 'networking'
  | 'other'

// Fine-grained sector string -> coarse color group (7 groups; skill's table).
const SECTOR_TO_GROUP: Record<string, ColorGroup> = {
  'Semiconductor Equipment': 'equipment',
  Semiconductors: 'semiconductors',
  'Semiconductor IP': 'ipMaterialsMemory',
  'Semiconductor Materials': 'ipMaterialsMemory',
  Memory: 'ipMaterialsMemory',
  'Memory/Hardware': 'ipMaterialsMemory',
  'Laser/Photonics': 'photonics',
  'Optical Networking': 'photonics',
  'Test & Measurement': 'photonics',
  'Contract Manufacturing': 'contractMfg',
  'Networking Hardware': 'networking',
  'Electronic Systems': 'networking',
  'EDA Software': 'other',
  'Electronic Components': 'other',
  'Electronic Materials': 'other',
  'Precision Components': 'other',
}

// Categorical palette, skipping slot 6 (red) — red is reserved for negative edges.
const GROUP_COLORS: Record<ColorGroup, { light: string; dark: string }> = {
  equipment: { light: '#2a78d6', dark: '#3987e5' },
  semiconductors: { light: '#1baf7a', dark: '#199e70' },
  ipMaterialsMemory: { light: '#eda100', dark: '#c98500' },
  photonics: { light: '#008300', dark: '#008300' },
  contractMfg: { light: '#4a3aa7', dark: '#9085e9' },
  networking: { light: '#e87ba4', dark: '#d55181' },
  other: { light: '#eb6834', dark: '#d95926' },
}

const SECTOR_GROUP_LABELS: Record<ColorGroup, string> = {
  equipment: 'Semiconductor Equipment',
  semiconductors: 'Semiconductors',
  ipMaterialsMemory: 'Chip IP, Materials & Memory',
  photonics: 'Photonics & Optical',
  contractMfg: 'Contract Manufacturing',
  networking: 'Networking & Systems',
  other: 'Other Components',
}

// Anchors are never sector-colored: fixed neutral primary-ink fill + star shape.
const ANCHOR_FILL: Record<ThemeName, string> = { light: '#0b0b0b', dark: '#ffffff' }

// Edge color encodes correlation sign (diverging), not category.
const EDGE_POSITIVE: Record<ThemeName, string> = { light: '#2a78d6', dark: '#3987e5' }
const EDGE_NEGATIVE: Record<ThemeName, string> = { light: '#e34948', dark: '#e66767' }

export function sectorColor(sector: string, theme: ThemeName): string {
  const group = SECTOR_TO_GROUP[sector] ?? 'other'
  return GROUP_COLORS[group][theme]
}

export function nodeFill(node: { kind: string; sector: string }, theme: ThemeName): string {
  return node.kind === 'anchor' ? ANCHOR_FILL[theme] : sectorColor(node.sector, theme)
}

/** Anchor: fixed 40. Satellite: log-scaled by market cap, clamped [12, 40]. */
export function nodeSize(node: { kind: string; marketCap: number | null }): number {
  if (node.kind === 'anchor') return 40
  const mc = node.marketCap
  if (mc == null || mc <= 0) return 18
  return Math.min(40, Math.max(12, 12 + 6 * Math.log10(mc / 1e8)))
}

export function edgeWidth(weight: number): number {
  return 1 + Math.abs(weight) * 6
}

/** Opacity = stability, clamped [0.25, 1]; full opacity when stability absent. */
export function edgeOpacity(stability: number | null): number {
  if (stability == null) return 1
  return Math.min(1, Math.max(0.25, stability))
}

export function edgeColor(weight: number, stability: number | null, theme: ThemeName): string {
  const hex = weight < 0 ? EDGE_NEGATIVE[theme] : EDGE_POSITIVE[theme]
  return hexToRgba(hex, edgeOpacity(stability))
}

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

/** Linear blend of two hex colors. t=0 → a, t=1 → b. */
function mixHex(a: string, b: string, t: number): string {
  const ca = hexToRgb(a)
  const cb = hexToRgb(b)
  return `#${toHexPair(ca.r + (cb.r - ca.r) * t)}${toHexPair(ca.g + (cb.g - ca.g) * t)}${toHexPair(
    ca.b + (cb.b - ca.b) * t,
  )}`
}

function hexToRgba(hex: string, alpha: number): string {
  const { r, g, b } = hexToRgb(hex)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function lighten(hex: string, amount: number): string {
  return mixHex(hex, '#ffffff', amount)
}

export function darken(hex: string, amount: number): string {
  return mixHex(hex, '#000000', amount)
}

// --- Web-tuned node treatment ------------------------------------------------
// The dashboard mutes/warms the (bright, validated) skill palette so nodes sit
// inside the cream/espresso UI instead of reading as out-of-place web colors.
// A deliberate, aesthetic-driven deviation from the Python renderers: the
// sector-to-hue MAPPING is preserved, only the tone is softened. Nodes are also
// drawn smaller than the skill's sizes (WEB_SIZE_SCALE) for a less crowded feel.

const WARM_NEUTRAL: Record<ThemeName, string> = { light: '#8c7d6b', dark: '#9a8a76' }

/** Multiplier applied to skill node sizes when rendering in the web graph. */
export const WEB_SIZE_SCALE = 0.62

/** Anchor fill: fixed white (dark) / near-black (light). */
export function anchorFill(theme: ThemeName): string {
  return ANCHOR_FILL[theme]
}

/** Sector color, desaturated toward a warm neutral to harmonize with the UI. */
export function webSectorColor(sector: string, theme: ThemeName): string {
  return mixHex(sectorColor(sector, theme), WARM_NEUTRAL[theme], 0.32)
}

/**
 * Relatedness heatmap cell color: a SEQUENTIAL ramp from the theme surface (0)
 * to the graph's positive-edge blue (max), reusing the exact same blue pole as
 * the graph edges so the two views read as one system. Sequential (not the full
 * diverging blue↔red) because relatedness is a non-negative strength score —
 * there are no negative values for red to encode.
 */
export function relatednessColor(value: number, maxValue: number, theme: ThemeName): string {
  const t = maxValue > 0 ? Math.min(1, Math.max(0, value / maxValue)) : 0
  return mixHex(PALETTES[theme].surface, EDGE_POSITIVE[theme], t)
}

/** Legend rows for the sector color groups, in the active theme. */
export function sectorLegend(theme: ThemeName): { label: string; color: string }[] {
  return (Object.keys(GROUP_COLORS) as ColorGroup[]).map((group) => ({
    label: SECTOR_GROUP_LABELS[group],
    color: GROUP_COLORS[group][theme],
  }))
}

// --- Transform the API response into react-force-graph's {nodes, links} shape.

export interface ForceNodeData {
  id: string
  kind: string
  name: string
  sector: string
  marketCap: number | null
}

export interface ForceLinkData {
  source: string
  target: string
  weight: number
  stability: number | null
}

export function toForceGraph(data: GraphResponse): {
  nodes: ForceNodeData[]
  links: ForceLinkData[]
} {
  const nodes = data.nodes.map((n: GraphNode) => ({
    id: n.ticker,
    kind: n.kind,
    name: n.name,
    sector: n.sector,
    marketCap: n.market_cap ?? null,
  }))
  const links = data.edges.map((e) => ({
    source: e.anchor,
    target: e.satellite,
    weight: e.weight,
    stability: e.stability ?? null,
  }))
  return { nodes, links }
}
