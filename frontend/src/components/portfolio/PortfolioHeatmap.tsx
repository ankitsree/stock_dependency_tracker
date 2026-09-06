import { useTheme } from '../../theme/theme-context'
import { correlationColor, correlationInk } from './portfolioStyle'
import type { HoldingExposure } from '../../types/domain'

export interface PortfolioHeatmapProps {
  holdings: HoldingExposure[]
  anchors: string[]
}

const pct = (value: number) => `${(value * 100).toFixed(0)}%`

/**
 * Holdings x anchors correlation grid, on a diverging blue↔red scale through a
 * neutral midpoint (correlation is signed — see portfolioStyle.ts).
 *
 * A real `<table>` with header scopes, and every value printed in-cell: this
 * doubles as the required table view for the whole analysis, so nothing on
 * this page is legible only through color.
 */
export function PortfolioHeatmap({ holdings, anchors }: PortfolioHeatmapProps) {
  const { theme } = useTheme()

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] border-collapse text-sm">
        <caption className="sr-only">
          Correlation of each holding to each anchor, with its portfolio weight and the share of
          its variance the anchors jointly explain.
        </caption>
        <thead>
          <tr>
            <th scope="col" className="px-2 pb-2 text-left text-xs font-semibold text-content-dim">
              Holding
            </th>
            <th scope="col" className="px-2 pb-2 text-right text-xs font-semibold text-content-dim">
              Weight
            </th>
            {anchors.map((anchor) => (
              <th key={anchor} scope="col" className="px-2 pb-2 text-center text-xs font-semibold text-content-dim">
                {anchor}
              </th>
            ))}
            <th scope="col" className="px-2 pb-2 text-right text-xs font-semibold text-content-dim">
              R²
            </th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => (
            <tr key={holding.ticker}>
              <th scope="row" className="whitespace-nowrap px-2 py-1 text-left font-medium text-content">
                {holding.ticker}
              </th>
              <td className="px-2 py-1 text-right tabular-nums text-content-dim">{pct(holding.weight)}</td>
              {anchors.map((anchor) => {
                const value = holding.correlations[anchor]
                return (
                  <td
                    key={anchor}
                    title={
                      value === null || value === undefined
                        ? `${holding.ticker} vs ${anchor}: not enough overlapping history`
                        : `${holding.ticker} vs ${anchor}: ${value.toFixed(2)}`
                    }
                    // 2px surface ring between adjacent fills, per the mark specs.
                    className="border-2 border-base px-2 py-1 text-center tabular-nums"
                    style={
                      value === null || value === undefined
                        ? undefined
                        : {
                            backgroundColor: correlationColor(value, theme),
                            color: correlationInk(value, theme),
                          }
                    }
                  >
                    {value === null || value === undefined ? (
                      <span className="text-content-dim">—</span>
                    ) : (
                      value.toFixed(2)
                    )}
                  </td>
                )
              })}
              <td className="px-2 py-1 text-right tabular-nums text-content-dim">
                {pct(holding.r_squared)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-3">
        <span className="text-xs text-content-dim">−1</span>
        <div
          aria-hidden="true"
          className="h-2.5 w-44 rounded-full border border-hairline"
          style={{
            background: `linear-gradient(to right, ${correlationColor(-1, theme)}, ${correlationColor(
              0,
              theme,
            )}, ${correlationColor(1, theme)})`,
          }}
        />
        <span className="text-xs text-content-dim">+1 correlation</span>
      </div>
    </div>
  )
}
