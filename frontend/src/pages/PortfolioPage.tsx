import { usePortfolioAnalysis } from '../api/hooks/usePortfolioAnalysis'
import { errorKind } from '../api/client'
import { HoldingsForm } from '../components/portfolio/HoldingsForm'
import { ConcentrationChart } from '../components/portfolio/ConcentrationChart'
import { FactorExposureCard } from '../components/portfolio/FactorExposureCard'
import { PortfolioHeatmap } from '../components/portfolio/PortfolioHeatmap'
import { downloadPortfolioCsv } from '../components/portfolio/exportCsv'
import { LoadingState } from '../components/shared/LoadingState'
import { ErrorState } from '../components/shared/ErrorState'
import { EmptyState } from '../components/shared/EmptyState'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-hairline bg-raised p-5">
      <h3 className="mb-4 text-sm font-semibold text-content">{title}</h3>
      {children}
    </section>
  )
}

/**
 * Portfolio concentration view (Track A Phase 3).
 *
 * Its own route rather than a modal over the graph: the results are three
 * stacked panels' worth of reading, and a route means the view can be
 * navigated back to. Holdings live in component state and are never persisted
 * — a refresh clears them, by design.
 */
export default function PortfolioPage() {
  const analysis = usePortfolioAnalysis()
  const result = analysis.data

  return (
    <div className="mx-auto h-full max-w-5xl overflow-auto px-6 py-8">
      <header className="mb-6">
        <h2 className="text-xl font-semibold text-content">Your portfolio</h2>
        <p className="mt-1 max-w-prose text-sm text-content-dim">
          Paste your holdings to see which anchors actually drive their variance. Exposures are
          split so that correlated anchors don&apos;t each claim the same risk, and everything left
          over is reported as unexplained rather than forced onto a factor.
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[20rem_minmax(0,1fr)] lg:items-start">
        <div className="rounded-xl border border-hairline bg-raised p-5">
          <HoldingsForm
            onAnalyze={(holdings) => analysis.mutate({ holdings, anchors: null })}
            isPending={analysis.isPending}
          />
        </div>

        <div className="space-y-5">
          {analysis.isPending ? (
            <LoadingState label="Correlating your holdings against the anchors…" />
          ) : analysis.isError ? (
            <ErrorState
              kind={errorKind(analysis.error)}
              detail={
                errorKind(analysis.error) === 'insufficient-data'
                  ? "None of those tickers had enough price history to analyse. Check the symbols and try again."
                  : undefined
              }
              onRetry={() => analysis.reset()}
            />
          ) : !result ? (
            <EmptyState
              title="Nothing analysed yet"
              message="Paste a few tickers on the left — share counts are optional, and without them every position is weighted equally."
            />
          ) : (
            <>
              <Section title="Where your risk comes from">
                <ConcentrationChart factors={result.factor_exposure} />
              </Section>

              <Section title="Summary">
                <FactorExposureCard
                  concentration={result.concentration}
                  riskSummary={result.risk_summary}
                  weighting={result.weighting}
                  totalValue={result.total_value ?? null}
                  lookbackDays={result.lookback_days}
                />
              </Section>

              <Section title="Holdings vs. anchors">
                <PortfolioHeatmap holdings={result.holdings} anchors={result.anchors} />
                {result.unresolved.length > 0 ? (
                  <ul className="mt-4 space-y-1 border-t border-hairline pt-3">
                    {result.unresolved.map((entry) => (
                      <li key={entry.ticker} className="text-xs text-content-dim">
                        <span className="font-medium text-content">{entry.ticker}</span> excluded —{' '}
                        {entry.reason.toLowerCase()}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </Section>

              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => downloadPortfolioCsv(result)}
                  className="rounded-md border border-hairline bg-raised px-3 py-1.5 text-sm text-content transition-colors hover:border-brand hover:text-brand"
                >
                  Export as CSV
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
