import { useRelatedness } from '../api/hooks/useRelatedness'
import { errorKind } from '../api/client'
import { LoadingState } from '../components/shared/LoadingState'
import { ErrorState } from '../components/shared/ErrorState'
import { EmptyState } from '../components/shared/EmptyState'
import { RelatednessHeatmap } from '../components/relatedness/RelatednessHeatmap'

/**
 * Relatedness view (Step 7), on its own /relatedness route. Shows how strongly
 * each pair of anchors relates through the small-cap satellites they share —
 * a derived signal, not a direct anchor-to-anchor price correlation.
 */
export default function RelatednessPage() {
  const query = useRelatedness()

  return (
    <div className="mx-auto h-full max-w-3xl overflow-auto px-6 py-8">
      <header className="mb-6">
        <h2 className="text-xl font-semibold text-content">Anchor relatedness</h2>
        <p className="mt-1 max-w-prose text-sm text-content-dim">
          How strongly each pair of anchors relates through the satellites they{' '}
          <em>share</em> — averaged over every shared satellite, using the weaker of the
          two correlation links each time. It is inferred from shared satellites, not a
          direct anchor-to-anchor correlation.
        </p>
      </header>

      {query.isPending ? (
        <LoadingState label="Computing anchor relatedness…" />
      ) : query.isError ? (
        <ErrorState kind={errorKind(query.error)} onRetry={() => void query.refetch()} />
      ) : !query.data || query.data.anchors.length < 2 ? (
        <EmptyState
          title="Need at least two anchors"
          message="Relatedness compares anchors against each other, so it needs two or more."
        />
      ) : (
        <RelatednessHeatmap anchors={query.data.anchors} matrix={query.data.matrix} />
      )}
    </div>
  )
}
