import { useMemo } from 'react'
import { useTheme } from '../../theme/theme-context'
import { PALETTES } from '../../theme/tokens'
import { relatednessColor } from '../graph/graphStyle'

export interface RelatednessHeatmapProps {
  anchors: string[]
  matrix: number[][]
}

/**
 * Anchor×anchor relatedness as a colored grid. Cell background is a sequential
 * ramp reusing the graph's positive-edge blue (see relatednessColor); the exact
 * value is always printed in-cell so magnitude is legible regardless of color
 * (and readable to screen readers via real table semantics).
 */
export function RelatednessHeatmap({ anchors, matrix }: RelatednessHeatmapProps) {
  const { theme } = useTheme()
  const palette = PALETTES[theme]

  const max = useMemo(() => {
    let m = 0
    for (let i = 0; i < matrix.length; i++) {
      for (let j = 0; j < matrix.length; j++) {
        if (i !== j) m = Math.max(m, matrix[i][j])
      }
    }
    return m
  }, [matrix])

  const cellText = (value: number): string => {
    // Dark theme cells read light throughout; light theme flips past mid-ramp.
    if (theme === 'dark') return palette.ink
    return max > 0 && value / max > 0.55 ? '#f7f2e9' : '#2a2420'
  }

  return (
    <div className="space-y-5">
      <div className="overflow-x-auto">
        <table className="border-collapse" aria-label="Anchor relatedness matrix">
          <thead>
            <tr>
              <th className="p-2" aria-hidden="true" />
              {anchors.map((anchor) => (
                <th
                  key={anchor}
                  scope="col"
                  className="px-2 pb-2 text-xs font-semibold text-content-dim"
                >
                  {anchor}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {anchors.map((rowAnchor, i) => (
              <tr key={rowAnchor}>
                <th
                  scope="row"
                  className="px-2 text-right text-xs font-semibold text-content-dim"
                >
                  {rowAnchor}
                </th>
                {anchors.map((colAnchor, j) => {
                  const isDiagonal = i === j
                  const value = matrix[i]?.[j] ?? 0
                  return (
                    <td
                      key={colAnchor}
                      title={
                        isDiagonal ? rowAnchor : `${rowAnchor} ↔ ${colAnchor}: ${value.toFixed(2)}`
                      }
                      style={{
                        backgroundColor: isDiagonal ? 'transparent' : relatednessColor(value, max, theme),
                        color: isDiagonal ? palette.inkMuted : cellText(value),
                      }}
                      className="h-16 w-16 border border-hairline text-center align-middle text-sm tabular-nums sm:h-20 sm:w-20"
                    >
                      {isDiagonal ? '—' : value.toFixed(2)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-xs text-content-dim">weaker</span>
        <div
          className="h-2.5 w-44 rounded-full border border-hairline"
          style={{
            background: `linear-gradient(to right, ${relatednessColor(0, max, theme)}, ${relatednessColor(max, max, theme)})`,
          }}
          aria-hidden="true"
        />
        <span className="text-xs text-content-dim">
          stronger{max > 0 ? ` (max ${max.toFixed(2)})` : ''}
        </span>
      </div>
    </div>
  )
}
