import { useMutation } from '@tanstack/react-query'
import { apiPost } from '../client'
import type { PortfolioAnalysis, PortfolioAnalyzeRequest } from '../../types/domain'

/**
 * POST /api/portfolio/analyze.
 *
 * A mutation, not a query, even though the endpoint only reads: the analysis
 * is user-triggered, the input is a form the user is still editing, and the
 * result must never be refetched or cached against a stale holdings list.
 * Holdings are never persisted anywhere — they live in this hook's variables
 * and nowhere else (Track A Phase 3: "No persistence").
 */
export function usePortfolioAnalysis() {
  return useMutation({
    mutationFn: (body: PortfolioAnalyzeRequest) =>
      apiPost<PortfolioAnalysis>('/portfolio/analyze', body),
  })
}
