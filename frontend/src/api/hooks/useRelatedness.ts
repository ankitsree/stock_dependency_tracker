import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../client'
import type { RelatednessResponse } from '../../types/domain'

export interface RelatednessParams {
  anchors?: string[]
  topN?: number
  threshold?: number
}

/** Anchor×anchor relatedness matrix: GET /api/graph/relatedness. */
export function useRelatedness({ anchors, topN, threshold }: RelatednessParams = {}) {
  return useQuery({
    queryKey: ['relatedness', anchors ?? null, topN ?? null, threshold ?? null],
    queryFn: ({ signal }) =>
      apiGet<RelatednessResponse>(
        '/graph/relatedness',
        { anchors, top_n: topN, threshold },
        signal,
      ),
  })
}
