import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TickerSearch } from './TickerSearch'
import { DetailPanelContext, type DetailPanelValue } from '../ticker-detail/detail-panel-context'
import type { CompanyListResponse } from '../../types/domain'

const COMPANIES: CompanyListResponse = {
  companies: [{ ticker: 'SAT_HIGH', name: 'High Corr Co', sector: 'Semiconductors' }],
}

function renderWithProviders(openDetail: DetailPanelValue['openDetail']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const contextValue: DetailPanelValue = {
    ticker: null,
    relations: [],
    openDetail,
    closeDetail: vi.fn(),
  }
  return render(
    <QueryClientProvider client={queryClient}>
      <DetailPanelContext.Provider value={contextValue}>
        <TickerSearch />
      </DetailPanelContext.Provider>
    </QueryClientProvider>,
  )
}

describe('TickerSearch', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(COMPANIES), { status: 200 })),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('selecting a suggestion opens its detail panel', async () => {
    const user = userEvent.setup()
    const openDetail = vi.fn()
    renderWithProviders(openDetail)

    await user.type(screen.getByRole('combobox'), 'sat_h')
    const option = await screen.findByRole('option', { name: /SAT_HIGH/i })
    await user.click(option)

    expect(openDetail).toHaveBeenCalledWith('SAT_HIGH')
  })

  it('shows a hint, not an empty dropdown, for a ticker outside the universe', async () => {
    // AAPL is a real anchor ticker (config.yaml) that never appears in
    // /api/companies (the satellite universe) — this is exactly the gap
    // that made anchors look unsearchable before this hint existed.
    const user = userEvent.setup()
    renderWithProviders(vi.fn())

    await user.type(screen.getByRole('combobox'), 'AAPL')

    await waitFor(() => expect(screen.getByText(/not in the satellite list/i)).toBeInTheDocument())
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
    expect(screen.getByText('AAPL', { selector: 'span' })).toBeInTheDocument()
  })

  it('Enter still opens the detail panel for a ticker with no dropdown match', async () => {
    const user = userEvent.setup()
    const openDetail = vi.fn()
    renderWithProviders(openDetail)

    const input = screen.getByRole('combobox')
    await user.type(input, 'AAPL')
    await waitFor(() => expect(screen.getByText(/not in the satellite list/i)).toBeInTheDocument())
    await user.keyboard('{Enter}')

    expect(openDetail).toHaveBeenCalledWith('AAPL')
  })
})
