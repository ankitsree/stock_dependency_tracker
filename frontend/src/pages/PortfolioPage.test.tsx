import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PortfolioPage from './PortfolioPage'
import { ThemeProvider } from '../theme/ThemeProvider'
import type { PortfolioAnalysis } from '../types/domain'

const ANALYSIS: PortfolioAnalysis = {
  anchors: ['NVDA', 'TSM'],
  holdings: [
    {
      ticker: 'AAPL',
      shares: 100,
      last_price: 200,
      market_value: 20000,
      weight: 0.8,
      correlations: { NVDA: 0.61, TSM: null },
      r_squared: 0.4,
    },
    {
      ticker: 'MSFT',
      shares: 50,
      last_price: 100,
      market_value: 5000,
      weight: 0.2,
      correlations: { NVDA: 0.3, TSM: 0.25 },
      r_squared: 0.12,
    },
  ],
  unresolved: [{ ticker: 'NOPE', reason: 'No price history available' }],
  weighting: 'market_value',
  total_value: 25000,
  factor_exposure: [
    { factor: 'NVDA', label: 'NVDA', share: 0.55, is_idiosyncratic: false },
    { factor: 'TSM', label: 'TSM', share: 0.1, is_idiosyncratic: false },
    { factor: 'idiosyncratic', label: 'Unexplained', share: 0.35, is_idiosyncratic: true },
  ],
  concentration: {
    herfindahl_index: 0.44,
    effective_factors: 2.3,
    top_factor: 'NVDA',
    top_factor_share: 0.55,
    top_three_share: 0.65,
  },
  risk_summary: ['NVDA is your largest single exposure at 55% of portfolio variance.'],
  lookback_days: 365,
  generated_at: '2026-08-29T10:00:00Z',
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  )
  return render(<PortfolioPage />, { wrapper })
}

function stubFetch(response: Response) {
  // Typed as the real fetch signature so `mock.calls` carries [input, init]
  // rather than the zero-arg tuple an `async () => …` stub would infer.
  const fetchMock = vi.fn(async (_input: string, _init?: RequestInit) => response.clone())
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('PortfolioPage', () => {
  beforeEach(() => {
    stubFetch(new Response(JSON.stringify(ANALYSIS), { status: 200 }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('starts empty with the analyze button disabled', () => {
    renderPage()

    expect(screen.getByText('Nothing analysed yet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyze portfolio' })).toBeDisabled()
  })

  it('enables analysis once a holding parses', async () => {
    renderPage()

    await userEvent.type(screen.getByLabelText('Your holdings'), 'AAPL 100')

    expect(screen.getByText('1 holding parsed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analyze portfolio' })).toBeEnabled()
  })

  it('posts the parsed holdings to the analyze endpoint', async () => {
    const fetchMock = stubFetch(new Response(JSON.stringify(ANALYSIS), { status: 200 }))
    renderPage()

    await userEvent.type(screen.getByLabelText('Your holdings'), 'AAPL 100{enter}MSFT 50')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze portfolio' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/portfolio/analyze')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string).holdings).toEqual([
      { ticker: 'AAPL', shares: 100 },
      { ticker: 'MSFT', shares: 50 },
    ])
  })

  it('renders the decomposition, summary, and holdings grid on success', async () => {
    renderPage()

    await userEvent.type(screen.getByLabelText('Your holdings'), 'AAPL 100')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze portfolio' }))

    await screen.findByText('Where your risk comes from')
    // Every factor is direct-labelled, so identity never rests on color alone.
    expect(screen.getAllByText('NVDA').length).toBeGreaterThan(0)
    expect(screen.getByText('Unexplained')).toBeInTheDocument()
    expect(
      screen.getByText('NVDA is your largest single exposure at 55% of portfolio variance.'),
    ).toBeInTheDocument()
    expect(screen.getByText('2.3')).toBeInTheDocument()
    // A correlation the API couldn't compute renders as a dash, not as zero.
    expect(screen.getByTitle('AAPL vs TSM: not enough overlapping history')).toBeInTheDocument()
  })

  it('surfaces excluded tickers with their reason', async () => {
    renderPage()

    await userEvent.type(screen.getByLabelText('Your holdings'), 'AAPL 100')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze portfolio' }))

    expect(await screen.findByText(/excluded/)).toHaveTextContent(
      'NOPE excluded — no price history available',
    )
  })

  it('shows the insufficient-data error state when nothing could be analysed', async () => {
    stubFetch(new Response(JSON.stringify({ detail: 'nope' }), { status: 422 }))
    renderPage()

    await userEvent.type(screen.getByLabelText('Your holdings'), 'ZZZZ 100')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze portfolio' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/enough price history/i)
  })

  it('reports lines it could not parse', async () => {
    renderPage()

    await userEvent.type(screen.getByLabelText('Your holdings'), 'AAPL 100{enter}12345')

    expect(screen.getByText(/Couldn't read 1 line/)).toBeInTheDocument()
  })
})
