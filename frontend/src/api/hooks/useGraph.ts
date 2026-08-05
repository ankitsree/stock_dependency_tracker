import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../client'
import type { GraphResponse } from '../../types/domain'

export interface GraphParams {
  /** Omit to let the API fall back to config.yaml's default anchors. */
  anchors?: string[]
  topN?: number
  threshold?: number
}

/** Combined multi-anchor dependency graph: GET /api/graph. */
export function useGraph(
  { anchors, topN, threshold }: GraphParams = {},
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ['graph', anchors ?? null, topN ?? null, threshold ?? null],
    queryFn: ({ signal }) =>
      apiGet<GraphResponse>('/graph', { anchors, top_n: topN, threshold }, signal),
    enabled: options.enabled ?? true,
  })
}
