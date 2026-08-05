import { useId } from 'react'
import type { PricePoint } from '../../types/domain'

/**
 * Lightweight hand-rolled SVG sparkline (no charting dependency — a single
 * polyline is all a sparkline needs). Line + soft area fill colored by the
 * period's direction: a warm sage for up, the graph's negative-red for down,
 * so it reads as part of the same visual system.
 */
export function PriceSparkline({ points, theme }: { points: PricePoint[]; theme: 'light' | 'dark' }) {
  const gradientId = useId()

  if (points.length < 2) {
    return <p className="text-sm text-content-dim">Not enough price history to chart.</p>
  }

  const values = points.map((p) => p.adjusted_close)
  const first = values[0]
  const last = values[values.length - 1]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  const W = 100
  const H = 34
  const coords = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W
    const y = H - ((v - min) / range) * H
    return [x, y] as const
  })
  const line = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  const area = `${line} L${W},${H} L0,${H} Z`

  const change = (last - first) / first
  const isUp = change >= 0
  const trend = isUp
    ? theme === 'dark'
      ? '#7bb894'
      : '#3f7a57'
    : theme === 'dark'
      ? '#e66767'
      : '#e34948'

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="h-16 w-full"
        role="img"
        aria-label={`Price trend, ${isUp ? 'up' : 'down'} ${(Math.abs(change) * 100).toFixed(1)} percent over the period`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={trend} stopOpacity="0.28" />
            <stop offset="100%" stopColor={trend} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill={`url(#${gradientId})`} />
        <path
          d={line}
          fill="none"
          stroke={trend}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="mt-2 flex items-baseline justify-between text-xs">
        <span className="text-content-dim">
          {points[0].date} → {points[points.length - 1].date}
        </span>
        <span className="font-semibold tabular-nums" style={{ color: trend }}>
          {isUp ? '↑' : '↓'} {(Math.abs(change) * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  )
}
