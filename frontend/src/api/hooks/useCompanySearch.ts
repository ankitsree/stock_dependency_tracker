import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../client'
import type { CompanyListResponse, CompanyProfile } from '../../types/domain'

/**
 * The satellite universe list: GET /api/companies. Cached with a long
 * staleTime — the universe changes rarely (and only when the backend's list
 * does), so there's no reason to refetch it while the app is open.
 */
export function useCompanies(includeMarketData = false) {
  return useQuery({
    queryKey: ['companies', includeMarketData],
    queryFn: ({ signal }) =>
      apiGet<CompanyListResponse>('/companies', { include_market_data: includeMarketData }, signal),
    staleTime: 30 * 60 * 1000,
  })
}

/**
 * Free-text search over the universe. The API has no server-side search
 * endpoint, so this filters the cached companies list client-side (matching
 * ticker or name). Case-insensitive; an empty query returns the full list.
 * Shares the ['companies'] cache entry with useCompanies — no extra request.
 */
export function useCompanySearch(query: string) {
  const companiesQuery = useCompanies()

  const results = useMemo<CompanyProfile[]>(() => {
    const all = companiesQuery.data?.companies ?? []
    const q = query.trim().toLowerCase()
    if (!q) return all
    return all.filter(
      (c) => c.ticker.toLowerCase().includes(q) || c.name.toLowerCase().includes(q),
    )
  }, [companiesQuery.data, query])

  return { ...companiesQuery, results }
}
