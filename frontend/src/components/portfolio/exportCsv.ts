/**
 * CSV export for a portfolio analysis (Track A Phase 3, milestone 3).
 *
 * One file, two sections separated by a blank line — holdings (with the full
 * correlation matrix as columns) and the factor decomposition. Spreadsheets
 * import that shape without complaint, and it keeps the export to a single
 * button rather than making the user choose between two downloads.
 */

import type { PortfolioAnalysis } from '../../types/domain'

function escapeCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function row(cells: (string | number | null | undefined)[]): string {
  return cells.map(escapeCell).join(',')
}

function round(value: number | null | undefined, places = 4): string | null {
  return value === null || value === undefined ? null : value.toFixed(places)
}

export function portfolioToCsv(analysis: PortfolioAnalysis): string {
  const anchors = analysis.anchors
  const lines: string[] = []

  lines.push(row(['Ticker', 'Shares', 'Last price', 'Market value', 'Weight', 'R-squared', ...anchors]))
  for (const holding of analysis.holdings) {
    lines.push(
      row([
        holding.ticker,
        holding.shares,
        round(holding.last_price, 2),
        round(holding.market_value, 2),
        round(holding.weight),
        round(holding.r_squared),
        ...anchors.map((anchor) => round(holding.correlations[anchor])),
      ]),
    )
  }

  lines.push('')
  lines.push(row(['Factor', 'Share of portfolio variance']))
  for (const factor of analysis.factor_exposure) {
    lines.push(row([factor.label, round(factor.share)]))
  }

  if (analysis.unresolved.length > 0) {
    lines.push('')
    lines.push(row(['Excluded ticker', 'Reason']))
    for (const entry of analysis.unresolved) {
      lines.push(row([entry.ticker, entry.reason]))
    }
  }

  return lines.join('\n')
}

export function downloadPortfolioCsv(analysis: PortfolioAnalysis): void {
  const stamp = analysis.generated_at.slice(0, 10)
  const url = URL.createObjectURL(new Blob([portfolioToCsv(analysis)], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `portfolio-exposure-${stamp}.csv`
  link.click()
  // Revoking immediately would race the click on some browsers; a tick is
  // enough for the download to have taken a reference to the blob.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
