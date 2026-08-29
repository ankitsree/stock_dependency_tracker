import { describe, expect, it } from 'vitest'
import { portfolioToCsv } from './exportCsv'
import type { PortfolioAnalysis } from '../../types/domain'

const ANALYSIS: PortfolioAnalysis = {
  anchors: ['NVDA', 'TSM'],
  holdings: [
    {
      ticker: 'SAT_HIGH',
      shares: 100,
      last_price: 12.3456,
      market_value: 1234.56,
      weight: 0.75,
      correlations: { NVDA: 0.912345, TSM: null },
      r_squared: 0.83,
    },
  ],
  unresolved: [{ ticker: 'NOPE', reason: 'No price history available' }],
  weighting: 'market_value',
  total_value: 1234.56,
  factor_exposure: [
    { factor: 'NVDA', label: 'NVDA', share: 0.6, is_idiosyncratic: false },
    { factor: 'idiosyncratic', label: 'Unexplained', share: 0.4, is_idiosyncratic: true },
  ],
  concentration: {
    herfindahl_index: 0.52,
    effective_factors: 1.92,
    top_factor: 'NVDA',
    top_factor_share: 0.6,
    top_three_share: 0.6,
  },
  risk_summary: ['NVDA is your largest single exposure at 60% of portfolio variance.'],
  lookback_days: 365,
  generated_at: '2026-08-29T10:00:00Z',
}

describe('portfolioToCsv', () => {
  it('writes one column per anchor in the holdings header', () => {
    const [header] = portfolioToCsv(ANALYSIS).split('\n')

    expect(header).toBe('Ticker,Shares,Last price,Market value,Weight,R-squared,NVDA,TSM')
  })

  it('writes a holding row with rounded values and blanks for missing correlations', () => {
    const row = portfolioToCsv(ANALYSIS).split('\n')[1]

    expect(row).toBe('SAT_HIGH,100,12.35,1234.56,0.7500,0.8300,0.9123,')
  })

  it('appends the factor decomposition as its own section', () => {
    const csv = portfolioToCsv(ANALYSIS)

    expect(csv).toContain('\n\nFactor,Share of portfolio variance\nNVDA,0.6000\nUnexplained,0.4000')
  })

  it('appends excluded tickers with their reason', () => {
    expect(portfolioToCsv(ANALYSIS)).toContain('Excluded ticker,Reason\nNOPE,No price history available')
  })

  it('omits the excluded section when nothing was excluded', () => {
    expect(portfolioToCsv({ ...ANALYSIS, unresolved: [] })).not.toContain('Excluded ticker')
  })

  it('quotes cells containing a comma', () => {
    const csv = portfolioToCsv({
      ...ANALYSIS,
      unresolved: [{ ticker: 'X', reason: 'Fewer than 30 days, so it was skipped' }],
    })

    expect(csv).toContain('X,"Fewer than 30 days, so it was skipped"')
  })
})
