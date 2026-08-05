import { Suspense, lazy } from 'react'
import { useGraph } from '../api/hooks/useGraph'
import { useGraphParams } from '../lib/useGraphParams'
import { errorKind } from '../api/client'
import { AnchorMultiSelect } from '../components/graph/AnchorMultiSelect'
import { GraphControls } from '../components/graph/GraphControls'
import { LoadingState } from '../components/shared/LoadingState'
import { ErrorState } from '../components/shared/ErrorState'
import { EmptyState } from '../components/shared/EmptyState'

// Code-split the graph library (the heaviest dependency) off the initial bundle.
const DependencyGraph = lazy(() => import('../components/graph/DependencyGraph'))

export default function DashboardPage() {
  const { anchors, topN, threshold, setAnchors, setTopN, setThreshold } = useGraphParams()
  const graph = useGraph({ anchors, topN, threshold })

  // Chips show the explicit URL anchors, or (on first load) the anchors the API
  // returned from its own defaults — so nothing is hardcoded on the frontend.
  const anchorChips =
    anchors ??
    (graph.data?.nodes.filter((n) => n.kind === 'anchor').map((n) => n.ticker) ?? [])

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 space-y-4 border-b border-hairline px-6 py-4">
        <AnchorMultiSelect anchors={anchorChips} onChange={setAnchors} />
        <GraphControls
          topN={topN}
          threshold={threshold}
          onTopN={setTopN}
          onThreshold={setThreshold}
        />
      </div>

      <div className="relative flex-1">
        {graph.isPending ? (
          <LoadingState label="Building the dependency graph — the first load pulls fresh prices and can take a minute…" />
        ) : graph.isError ? (
          <ErrorState kind={errorKind(graph.error)} onRetry={() => void graph.refetch()} />
        ) : !graph.data || graph.data.nodes.length === 0 ? (
          <EmptyState
            title="No graph to show"
            message="No satellites cleared the correlation threshold for these anchors. Try lowering the minimum correlation."
          />
        ) : (
          <Suspense fallback={<LoadingState label="Loading graph…" />}>
            <DependencyGraph data={graph.data} />
          </Suspense>
        )}
      </div>
    </div>
  )
}
