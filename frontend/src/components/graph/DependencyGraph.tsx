import { useCallback, useEffect, useMemo, useRef } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import type { ForceGraphMethods, NodeObject } from 'react-force-graph-2d'
import { useTheme } from '../../theme/theme-context'
import { useDetailPanel } from '../ticker-detail/detail-panel-context'
import { PALETTES } from '../../theme/tokens'
import { useElementSize } from '../../lib/useElementSize'
import type { GraphResponse } from '../../types/domain'
import {
  anchorFill,
  darken,
  edgeColor,
  edgeWidth,
  lighten,
  nodeSize,
  toForceGraph,
  webSectorColor,
  WEB_SIZE_SCALE,
  type ForceLinkData,
  type ForceNodeData,
} from './graphStyle'

// react-force-graph adds x/y at runtime; our data fields need a cast off NodeObject.
type GNode = NodeObject & ForceNodeData

// Spacing: charge repulsion + link distance are dialed up from the library
// defaults (~-30 / ~30) so nodes sit further apart; zoomToFit then frames them.
const CHARGE_STRENGTH = -240
const LINK_DISTANCE = 90

function drawStar(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  outerR: number,
  innerR: number,
) {
  const spikes = 5
  const step = Math.PI / spikes
  let rot = -Math.PI / 2
  ctx.beginPath()
  ctx.moveTo(cx + Math.cos(rot) * outerR, cy + Math.sin(rot) * outerR)
  for (let i = 0; i < spikes; i++) {
    rot += step
    ctx.lineTo(cx + Math.cos(rot) * innerR, cy + Math.sin(rot) * innerR)
    rot += step
    ctx.lineTo(cx + Math.cos(rot) * outerR, cy + Math.sin(rot) * outerR)
  }
  ctx.closePath()
}

export default function DependencyGraph({ data }: { data: GraphResponse }) {
  const { theme } = useTheme()
  const { openDetail } = useDetailPanel()
  const [containerRef, { width, height }] = useElementSize<HTMLDivElement>()
  const palette = PALETTES[theme]

  const fgRef = useRef<ForceGraphMethods | undefined>(undefined)
  const didFit = useRef(false)

  const graphData = useMemo(() => toForceGraph(data), [data])

  // Widen the layout, then re-frame it once it settles. Re-applied whenever the
  // data changes (react-force-graph resets its forces on new graphData).
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    const charge = fg.d3Force('charge') as unknown as
      | { strength: (n: number) => unknown }
      | undefined
    charge?.strength(CHARGE_STRENGTH)
    const link = fg.d3Force('link') as unknown as
      | { distance: (n: number) => unknown }
      | undefined
    link?.distance(LINK_DISTANCE)
    didFit.current = false
    fg.d3ReheatSimulation()
  }, [graphData])

  const handleEngineStop = useCallback(() => {
    if (didFit.current) return
    fgRef.current?.zoomToFit(500, 70)
    didFit.current = true
  }, [])

  // New callback identity on theme change forces a repaint with the new palette.
  const paintNode = useCallback(
    (node: NodeObject, ctx: CanvasRenderingContext2D, scale: number) => {
      const n = node as GNode
      const x = n.x ?? 0
      const y = n.y ?? 0
      const radius = (nodeSize(n) * WEB_SIZE_SCALE) / 2

      if (n.kind === 'anchor') {
        drawStar(ctx, x, y, radius, radius * 0.5)
        ctx.fillStyle = anchorFill(theme)
        ctx.fill()
        ctx.lineWidth = Math.max(0.4, radius * 0.06)
        ctx.strokeStyle = theme === 'dark' ? darken('#ffffff', 0.22) : lighten('#0b0b0b', 0.25)
        ctx.stroke()
      } else {
        const base = webSectorColor(n.sector, theme)
        // Soft top-left light source → sphere shading, plus a darker rim = "finish".
        const gradient = ctx.createRadialGradient(
          x - radius * 0.35,
          y - radius * 0.35,
          radius * 0.15,
          x,
          y,
          radius,
        )
        gradient.addColorStop(0, lighten(base, 0.16))
        gradient.addColorStop(0.65, base)
        gradient.addColorStop(1, darken(base, 0.14))
        ctx.beginPath()
        ctx.arc(x, y, radius, 0, 2 * Math.PI)
        ctx.fillStyle = gradient
        ctx.fill()
        ctx.lineWidth = Math.max(0.4, radius * 0.07)
        ctx.strokeStyle = darken(base, 0.3)
        ctx.stroke()
      }

      // Always-on ticker label — the accessibility relief the skill relies on.
      const fontSize = 9.5 / scale
      ctx.font = `600 ${fontSize}px "Martian Mono Variable", ui-monospace, monospace`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillStyle = palette.inkMuted
      ctx.fillText(n.id, x, y + radius + 3 / scale)
    },
    [theme, palette.inkMuted],
  )

  const paintPointerArea = useCallback(
    (node: NodeObject, color: string, ctx: CanvasRenderingContext2D) => {
      const n = node as GNode
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.arc(n.x ?? 0, n.y ?? 0, (nodeSize(n) * WEB_SIZE_SCALE) / 2, 0, 2 * Math.PI)
      ctx.fill()
    },
    [],
  )

  const linkColor = useCallback(
    (link: ForceLinkData) => edgeColor(link.weight, link.stability, theme),
    [theme],
  )
  const linkWidth = useCallback((link: ForceLinkData) => edgeWidth(link.weight), [])

  const nodeLabel = useCallback(
    (node: NodeObject) => {
      const n = node as GNode
      const cap = n.marketCap ? `$${(n.marketCap / 1e9).toFixed(2)}B` : '—'
      const kind = n.kind === 'anchor' ? 'Anchor' : n.sector
      return `<div style="font:12px 'Martian Mono Variable',monospace;padding:6px 8px;border-radius:6px;background:${palette.surface};color:${palette.ink};border:1px solid ${palette.border}"><strong>${n.id}</strong> · ${n.name}<br/>${kind} · ${cap}</div>`
    },
    [palette],
  )

  const handleNodeClick = useCallback(
    (node: NodeObject) => {
      const n = node as GNode
      // This satellite's price-correlation links to its anchor(s), from the
      // original (unmutated) edge data. Empty when an anchor node is clicked.
      const relations = data.edges
        .filter((e) => e.satellite === n.id)
        .map((e) => ({ anchor: e.anchor, correlation: e.weight, stability: e.stability ?? null }))
      openDetail(n.id, relations)
    },
    [openDetail, data.edges],
  )

  return (
    <div ref={containerRef} className="absolute inset-0">
      {width > 0 && height > 0 ? (
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          width={width}
          height={height}
          backgroundColor={palette.bg}
          nodeCanvasObjectMode={() => 'replace'}
          nodeCanvasObject={paintNode}
          nodePointerAreaPaint={paintPointerArea}
          nodeLabel={nodeLabel}
          linkColor={linkColor as (link: object) => string}
          linkWidth={linkWidth as (link: object) => number}
          onNodeClick={handleNodeClick}
          onEngineStop={handleEngineStop}
        />
      ) : null}
    </div>
  )
}
