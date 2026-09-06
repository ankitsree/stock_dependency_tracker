import type { Page } from '@playwright/test'

// Kept deliberately small — this is fixture data for two smoke tests, not a
// realistic universe. NVDA/AAPL match config.yaml's real anchors so the
// scenario ("search for an anchor, open its detail panel") mirrors the
// actual root cause behind the search-hint fix in TickerSearch.tsx.
const GRAPH = {
  nodes: [
    { ticker: 'NVDA', kind: 'anchor', name: 'NVIDIA Corp', sector: 'Semiconductors' },
    { ticker: 'AAPL', kind: 'anchor', name: 'Apple Inc', sector: 'Technology' },
    { ticker: 'SAT_HIGH', kind: 'satellite', name: 'High Corr Co', sector: 'Semiconductors' },
  ],
  edges: [{ anchor: 'NVDA', satellite: 'SAT_HIGH', weight: 0.82, stability: 0.7 }],
}

const COMPANIES = {
  companies: [{ ticker: 'SAT_HIGH', name: 'High Corr Co', sector: 'Semiconductors' }],
}

function companyProfile(ticker: string) {
  return { ticker, name: `${ticker} Inc`, sector: 'Technology' }
}

function priceHistory(ticker: string) {
  return {
    ticker,
    lookback_days: 30,
    points: [{ date: '2026-08-01', adjusted_close: 100.0 }],
    generated_at: new Date().toISOString(),
  }
}

const PORTFOLIO_ANALYSIS = {
  anchors: ['NVDA', 'AAPL'],
  holdings: [
    {
      ticker: 'AMKR',
      shares: 100,
      last_price: 12.5,
      market_value: 1250,
      weight: 1,
      correlations: { NVDA: 0.82, AAPL: 0.11 },
      r_squared: 0.68,
    },
  ],
  unresolved: [],
  weighting: 'market_value',
  total_value: 1250,
  factor_exposure: [
    { factor: 'NVDA', label: 'NVDA', share: 0.65, is_idiosyncratic: false },
    { factor: 'AAPL', label: 'AAPL', share: 0.03, is_idiosyncratic: false },
    { factor: 'idiosyncratic', label: 'Unexplained', share: 0.32, is_idiosyncratic: true },
  ],
  concentration: {
    herfindahl_index: 0.53,
    effective_factors: 1.9,
    top_factor: 'NVDA',
    top_factor_share: 0.65,
    top_three_share: 0.68,
  },
  risk_summary: ['NVDA is your largest single exposure at 65% of portfolio variance.'],
  lookback_days: 365,
  generated_at: new Date().toISOString(),
}

/** Stubs every /api/* call the dashboard + detail panel + portfolio view make,
 * so these smoke tests never depend on a real backend, Yahoo Finance, or
 * network access. */
export async function mockApi(page: Page) {
  await page.route('**/api/graph*', (route) => route.fulfill({ json: GRAPH }))
  await page.route('**/api/companies', (route) => route.fulfill({ json: COMPANIES }))
  await page.route('**/api/companies/*', (route) => {
    const ticker = new URL(route.request().url()).pathname.split('/').pop() ?? ''
    return route.fulfill({ json: companyProfile(ticker) })
  })
  await page.route('**/api/prices/*', (route) => {
    const ticker = new URL(route.request().url()).pathname.split('/').pop() ?? ''
    return route.fulfill({ json: priceHistory(ticker) })
  })
  await page.route('**/api/portfolio/analyze', (route) => route.fulfill({ json: PORTFOLIO_ANALYSIS }))
  await page.route('**/api/anchors/*/correlations*', (route) =>
    route.fulfill({ json: { anchor: 'NVDA', satellites: [], generated_at: new Date().toISOString(), cache_hit: true } }),
  )
}
