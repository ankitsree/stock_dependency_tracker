import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../client'
import type { CorrelationResponse } from '../../types/domain'

export interface CorrelationParams {
  topN?: number
  threshold?: number
}

/**
 * Ranked satellites for one anchor with the full Phase 4 diagnostic stack:
 * GET /api/anchors/{ticker}/correlations. Disabled until a ticker is provided.
 */
export function useAnchorCorrelations(
  ticker: string | undefined,
  { topN, threshold }: CorrelationParams = {},
) {
  return useQuery({
    queryKey: ['correlations', ticker ?? null, topN ?? null, threshold ?? null],
    queryFn: ({ signal }) =>
      apiGet<CorrelationResponse>(
        `/anchors/${encodeURIComponent(ticker as string)}/correlations`,
        { top_n: topN, threshold },
        signal,
      ),
    enabled: Boolean(ticker),
  })
}
