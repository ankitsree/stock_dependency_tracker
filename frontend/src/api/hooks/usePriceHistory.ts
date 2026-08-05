import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../client'
import type { PriceHistoryResponse } from '../../types/domain'

/**
 * Adjusted-close price history for one ticker: GET /api/prices/{ticker}.
 * Feeds the detail-panel sparkline in Step 6. Disabled until a ticker is set.
 */
export function usePriceHistory(ticker: string | undefined, lookbackDays?: number) {
  return useQuery({
    queryKey: ['prices', ticker ?? null, lookbackDays ?? null],
    queryFn: ({ signal }) =>
      apiGet<PriceHistoryResponse>(
        `/prices/${encodeURIComponent(ticker as string)}`,
        { lookback_days: lookbackDays },
        signal,
      ),
    enabled: Boolean(ticker),
  })
}
