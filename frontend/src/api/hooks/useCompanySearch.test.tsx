import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCompanySearch } from './useCompanySearch'
import type { CompanyListResponse } from '../../types/domain'

const COMPANIES: CompanyListResponse = {
  companies: [
    { ticker: 'SAT_HIGH', name: 'High Corr Co', sector: 'Semiconductors' },
    { ticker: 'SAT_LOW', name: 'Low Corr Co', sector: 'Semiconductors' },
    { ticker: 'ARKX', name: 'Space Exploration Fund', sector: 'Aerospace' },
  ],
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useCompanySearch', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify(COMPANIES), { status: 200 })),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns the full universe for an empty query', async () => {
    const { result } = renderHook(() => useCompanySearch(''), { wrapper })
    await waitFor(() => expect(result.current.results).toHaveLength(3))
  })

  it('matches by ticker substring, case-insensitively', async () => {
    const { result } = renderHook(() => useCompanySearch('sat_h'), { wrapper })
    await waitFor(() => expect(result.current.results).toHaveLength(1))
    expect(result.current.results[0].ticker).toBe('SAT_HIGH')
  })

  it('matches by company name substring', async () => {
    const { result } = renderHook(() => useCompanySearch('space'), { wrapper })
    await waitFor(() => expect(result.current.results).toHaveLength(1))
    expect(result.current.results[0].ticker).toBe('ARKX')
  })

  it('never returns anchors, since the universe endpoint excludes them by design', async () => {
    // NVDA is a real anchor ticker in config.yaml, deliberately absent from
    // the fixture above — this documents the root cause behind the search
    // hint added to TickerSearch/AnchorMultiSelect, not just a fixture gap.
    const { result } = renderHook(() => useCompanySearch('NVDA'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.results).toHaveLength(0)
  })
})
