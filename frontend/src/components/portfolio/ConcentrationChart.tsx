import { useState } from 'react'
import { useTheme } from '../../theme/theme-context'
import { factorColor, residualColor } from './portfolioStyle'
import type { FactorExposure } from '../../types/domain'

export interface ConcentrationChartProps {
  factors: FactorExposure[]
}

const SIZE = 220
const RADIUS = 82
const THICKNESS = 26
/**
 * Angular gap between slices, in degrees — the dataviz rule's "2px surface gap
 * between adjacent fills", converted at this radius. Slices too small to
 * survive the gap are drawn without one rather than inverted.
 */
const GAP_DEGREES = (2 / RADIUS) * (180 / Math.PI)

function polar(cx: number, cy: number, r: number, degrees: number) {
  const radians = ((degrees - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(radians), y: cy + r * Math.sin(radians) }
}

function arcPath(cx: number, cy: number, r: number, start: number, end: number): string {
  // A full circle can't be expressed as a single arc (start === end), so nudge
  // the sweep just short of 360° — visually identical, geometrically valid.
  const sweep = Math.min(end - start, 359.99)
  const from = polar(cx, cy, r, start)
  const to = polar(cx, cy, r, start + sweep)
  return `M ${from.x} ${from.y} A ${r} ${r} 0 ${sweep > 180 ? 1 : 0} 1 ${to.x} ${to.y}`
}

const percent = (share: number) => `${(share * 100).toFixed(share < 0.1 ? 1 : 0)}%`

/**
 * Factor exposure as a donut plus a ranked bar list.
 *
 * The donut answers "what's the shape of this portfolio" at a glance; the bars
 * beside it answer "is NVDA bigger than TSM", which a donut genuinely cannot
 * (dataviz anti-patterns: never a pie for comparing close values). The bars
 * are also the legend and the direct labels, so identity is never carried by
 * color alone — see portfolioStyle.ts on why the ramp is sequential.
 */
export function ConcentrationChart({ factors }: ConcentrationChartProps) {
  const { theme } = useTheme()
  const [active, setActive] = useState<string | null>(null)

  const named = factors.filter((f) => !f.is_idiosyncratic)
  const colorFor = (factor: FactorExposure, index: number) =>
    factor.is_idiosyncratic ? residualColor(theme) : factorColor(index, named.length, theme)

  const focus = factors.find((f) => f.factor === active) ?? factors[0]

  let cursor = 0
  const slices = factors.map((factor, index) => {
    const start = cursor
    const sweep = factor.share * 360
    cursor += sweep
    return { factor, index, start, sweep }
  })

  return (
    <div className="flex flex-col items-center gap-8 sm:flex-row sm:items-center">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="h-52 w-52 shrink-0"
        role="img"
        aria-label={`Portfolio variance split across ${named.length} anchors; ${
          focus ? `${focus.label} is ${percent(focus.share)}` : 'no exposure'
        }`}
      >
        {slices.map(({ factor, index, start, sweep }) => {
          const gap = sweep > GAP_DEGREES * 3 ? GAP_DEGREES : 0
          const dimmed = active !== null && active !== factor.factor
          return (
            <path
              key={factor.factor}
              d={arcPath(SIZE / 2, SIZE / 2, RADIUS, start + gap / 2, start + sweep - gap / 2)}
              fill="none"
              stroke={colorFor(factor, index)}
              strokeWidth={THICKNESS}
              opacity={dimmed ? 0.35 : 1}
              className="transition-opacity duration-150"
              onMouseEnter={() => setActive(factor.factor)}
              onMouseLeave={() => setActive(null)}
            >
              <title>{`${factor.label}: ${percent(factor.share)} of portfolio variance`}</title>
            </path>
          )
        })}

        {/* Hero number in the hole: the value the whole view exists to deliver. */}
        <text
          x={SIZE / 2}
          y={SIZE / 2 - 4}
          textAnchor="middle"
          className="fill-content text-[26px] font-semibold tabular-nums"
        >
          {focus ? percent(focus.share) : '—'}
        </text>
        <text x={SIZE / 2} y={SIZE / 2 + 18} textAnchor="middle" className="fill-content-dim text-[11px]">
          {focus?.label ?? ''}
        </text>
      </svg>

      <ul className="w-full min-w-0 space-y-2.5">
        {factors.map((factor, index) => (
          <li
            key={factor.factor}
            onMouseEnter={() => setActive(factor.factor)}
            onMouseLeave={() => setActive(null)}
            className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3"
          >
            <span className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
                style={{ backgroundColor: colorFor(factor, index) }}
              />
              <span
                className={
                  'w-24 truncate text-xs ' +
                  (factor.is_idiosyncratic ? 'text-content-dim' : 'text-content')
                }
              >
                {factor.label}
              </span>
            </span>
            <span className="h-2 w-full overflow-hidden rounded-full bg-base">
              <span
                className="block h-full rounded-full transition-[width] duration-300"
                style={{
                  width: `${Math.max(factor.share * 100, factor.share > 0 ? 1.5 : 0)}%`,
                  backgroundColor: colorFor(factor, index),
                  opacity: active !== null && active !== factor.factor ? 0.35 : 1,
                }}
              />
            </span>
            <span className="w-10 text-right text-xs tabular-nums text-content-dim">
              {percent(factor.share)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
