import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../client'
import type { CompanyProfile } from '../../types/domain'

/**
 * One company's profile: GET /api/companies/{ticker}. Works for any real
 * ticker (anchors included), so the detail panel fetches its own data by ticker
 * and renders identical content whether opened from the graph or the table.
 */
export function useCompanyProfile(ticker: string | undefined) {
  return useQuery({
    queryKey: ['company', ticker ?? null],
    queryFn: ({ signal }) =>
      apiGet<CompanyProfile>(`/companies/${encodeURIComponent(ticker as string)}`, undefined, signal),
    enabled: Boolean(ticker),
    staleTime: 30 * 60 * 1000,
  })
}
