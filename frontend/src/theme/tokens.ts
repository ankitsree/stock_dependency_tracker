/**
 * Plain-TypeScript mirror of the semantic design tokens in
 * src/styles/globals.css (docs/frontend-build-plan.md §2).
 *
 * Why this duplicates the CSS variables: canvas draw calls in later steps
 * (react-force-graph-2d's `nodeCanvasObject`, the relatedness heatmap) render
 * to a <canvas> and cannot read CSS custom properties — they need real JS
 * string values. This is the single place those values live for canvas use.
 * Keep in sync with globals.css by hand; the surface is intentionally small.
 *
 * NOTE: these are chrome tokens only. The graph's node/edge colors (sector
 * groups, positive/negative correlation) are a separate, fixed palette added
 * in Step 4 from .claude/skills/network-graph-style/SKILL.md — not here.
 */

export type ThemeName = 'light' | 'dark'

export interface ThemePalette {
  bg: string
  surface: string
  ink: string
  inkMuted: string
  border: string
  accent: string
  accentHover: string
}

export const PALETTES: Record<ThemeName, ThemePalette> = {
  light: {
    bg: '#f7f2e9',
    surface: '#fffaf0',
    ink: '#2a2420',
    inkMuted: '#6b6259',
    border: '#e3d9c6',
    accent: '#b5573a',
    accentHover: '#9c4830',
  },
  dark: {
    bg: '#1c1712',
    surface: '#241d16',
    ink: '#f0e9db',
    inkMuted: '#a89e90',
    border: '#352b20',
    accent: '#e08a63',
    accentHover: '#f0a480',
  },
}

export const palette = (theme: ThemeName): ThemePalette => PALETTES[theme]
