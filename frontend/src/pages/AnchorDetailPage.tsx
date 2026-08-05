import { useParams } from 'react-router-dom'
import { useAnchorCorrelations } from '../api/hooks/useAnchorCorrelations'
import { errorKind } from '../api/client'
import { LoadingState } from '../components/shared/LoadingState'
import { ErrorState } from '../components/shared/ErrorState'
import { EmptyState } from '../components/shared/EmptyState'
import { SatelliteTable } from '../components/satellite-table/SatelliteTable'

/**
 * An anchor's ranked satellites as a sortable diagnostics table (Step 5).
 * Reached from the header search and from the detail panel's "view full
 * correlations". Row clicks open the shared detail panel (Step 6).
 */
export default function AnchorDetailPage() {
  const { ticker } = useParams<{ ticker: string }>()
  const query = useAnchorCorrelations(ticker, {})

  return (
    <div className="h-full overflow-auto px-6 py-6">
      <div className="mb-1 flex items-baseline gap-3">
        <h2 className="text-xl font-semibold text-content">{ticker}</h2>
        <span className="text-xs text-content-dim">satellite correlations</span>
      </div>
      <p className="mb-6 text-xs text-content-dim">
        Sort any column; click a ticker or row to inspect its price and profile.
      </p>

      {query.isPending ? (
        <LoadingState label={`Computing correlations for ${ticker}…`} />
      ) : query.isError ? (
        <ErrorState kind={errorKind(query.error)} onRetry={() => void query.refetch()} />
      ) : !query.data || query.data.satellites.length === 0 ? (
        <EmptyState
          title="No correlated satellites"
          message={`Nothing in the universe cleared the threshold against ${ticker}.`}
        />
      ) : (
        <SatelliteTable anchor={ticker ?? ''} satellites={query.data.satellites} />
      )}
    </div>
  )
}
