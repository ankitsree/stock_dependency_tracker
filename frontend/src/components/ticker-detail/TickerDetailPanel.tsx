import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTheme } from '../../theme/theme-context'
import { useMediaQuery } from '../../lib/useMediaQuery'
import { useCompanyProfile } from '../../api/hooks/useCompanyProfile'
import { useGraph } from '../../api/hooks/useGraph'
import { usePriceHistory } from '../../api/hooks/usePriceHistory'
import { errorKind } from '../../api/client'
import { LoadingState } from '../shared/LoadingState'
import { ErrorState } from '../shared/ErrorState'
import { PriceSparkline } from './PriceSparkline'
import type { AnchorRelation } from './detail-panel-context'

function formatMoney(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(value)
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`
  return `${sign}$${abs.toFixed(0)}`
}

function formatVolume(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

function formatRatio(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

function formatYield(value: number | null | undefined): string {
  // The pinned yfinance returns dividendYield already as a percentage number
  // (verified: TSM → 0.94 for a ~0.9% yield), so it's shown as-is, not ×100.
  return value == null ? '—' : `${value.toFixed(2)}%`
}

function formatMargin(value: number | null | undefined): string {
  // profitMargins / returnOnEquity are fractions (e.g. 0.29 = 29%).
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

/**
 * A preview of the business summary that ends at a full sentence where possible
 * (so it doesn't read as cut off mid-sentence), falling back to a word boundary
 * with an ellipsis. `truncated` drives whether the "Read more" affordance shows.
 */
function summaryPreview(text: string, max = 240): { preview: string; truncated: boolean } {
  if (text.length <= max) return { preview: text, truncated: false }
  const slice = text.slice(0, max)
  const lastSentenceEnd = slice.lastIndexOf('. ')
  if (lastSentenceEnd > max * 0.5) {
    return { preview: slice.slice(0, lastSentenceEnd + 1), truncated: true }
  }
  return { preview: slice.replace(/\s+\S*$/, '') + '…', truncated: true }
}

function stabilityWord(stability: number | null): string {
  if (stability == null) return ''
  if (stability >= 0.75) return ', stable'
  if (stability >= 0.5) return ', fairly stable'
  return ', unstable'
}

export function TickerDetailPanel({
  ticker,
  relations,
  onClose,
}: {
  ticker: string
  relations: AnchorRelation[]
  onClose: () => void
}) {
  const { theme } = useTheme()
  const navigate = useNavigate()
  const isDesktop = useMediaQuery('(min-width: 768px)')
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const moreButtonRef = useRef<HTMLButtonElement>(null)
  const summaryCloseRef = useRef<HTMLButtonElement>(null)
  const [showFullSummary, setShowFullSummary] = useState(false)

  const profile = useCompanyProfile(ticker)
  const prices = usePriceHistory(ticker)

  // When opened without relations (e.g. from the header search), derive the
  // anchors this ticker correlates with from the default graph. Only fetches in
  // that case — graph/table clicks already supply relations.
  const graphForRelations = useGraph({}, { enabled: relations.length === 0 })
  const effectiveRelations = useMemo<AnchorRelation[]>(() => {
    if (relations.length > 0) return relations
    return (graphForRelations.data?.edges ?? [])
      .filter((edge) => edge.satellite === ticker)
      .map((edge) => ({
        anchor: edge.anchor,
        correlation: edge.weight,
        stability: edge.stability ?? null,
      }))
  }, [relations, graphForRelations.data, ticker])

  const closeSummary = useCallback(() => {
    setShowFullSummary(false)
    moreButtonRef.current?.focus()
  }, [])

  useEffect(() => {
    closeButtonRef.current?.focus()
  }, [])
  useEffect(() => {
    // Escape closes the summary modal first (if open), otherwise the panel.
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (showFullSummary) closeSummary()
      else onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, showFullSummary, closeSummary])
  useEffect(() => {
    if (showFullSummary) summaryCloseRef.current?.focus()
  }, [showFullSummary])

  const ratios = profile.data
    ? [
        { label: 'P/E (TTM)', value: formatRatio(profile.data.trailing_pe) },
        { label: 'P/E (fwd)', value: formatRatio(profile.data.forward_pe) },
        { label: 'PEG', value: formatRatio(profile.data.peg_ratio) },
        { label: 'P/B', value: formatRatio(profile.data.price_to_book) },
        { label: 'Beta', value: formatRatio(profile.data.beta) },
        { label: 'Div yield', value: formatYield(profile.data.dividend_yield) },
      ]
    : []

  const summary = profile.data?.business_summary
    ? summaryPreview(profile.data.business_summary)
    : null

  const content = (
    <>
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-hairline px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-content">{ticker}</h2>
          {profile.data ? (
            <p className="truncate text-sm text-content-dim">
              {profile.data.name} · {profile.data.sector}
            </p>
          ) : null}
        </div>
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-hairline text-content-dim transition-colors hover:border-brand hover:text-brand"
        >
          ✕
        </button>
      </header>

      <div className="flex-1 space-y-6 overflow-auto px-5 py-5">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-dim">
            Price · last 12 months
          </h3>
          {prices.isPending ? (
            <LoadingState label="Loading prices…" />
          ) : prices.isError ? (
            <ErrorState kind={errorKind(prices.error)} onRetry={() => void prices.refetch()} />
          ) : prices.data ? (
            <PriceSparkline points={prices.data.points} theme={theme} />
          ) : null}
        </section>

        {effectiveRelations.length > 0 || profile.data?.business_summary ? (
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-dim">
              About
            </h3>
            {effectiveRelations.length > 0 ? (
              <p className="text-sm text-content">
                Price-correlated with{' '}
                {effectiveRelations.map((r, i) => (
                  <span key={r.anchor}>
                    {i > 0 ? ', ' : ''}
                    <strong className="font-semibold">{r.anchor}</strong> (
                    {r.correlation.toFixed(2)}
                    {stabilityWord(r.stability)})
                  </span>
                ))}
                .{' '}
                <span className="text-content-dim">
                  A price relationship, not a confirmed business link.
                </span>
              </p>
            ) : null}
            {summary ? (
              <p className="mt-2 text-sm leading-relaxed text-content-dim">
                {summary.preview}
                {summary.truncated ? (
                  <>
                    {' '}
                    <button
                      ref={moreButtonRef}
                      type="button"
                      onClick={() => setShowFullSummary(true)}
                      className="font-medium text-brand underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
                    >
                      Read more
                    </button>
                  </>
                ) : null}
              </p>
            ) : null}
          </section>
        ) : null}

        {profile.isPending ? (
          <LoadingState label="Loading company…" />
        ) : profile.isError ? (
          <ErrorState kind={errorKind(profile.error)} onRetry={() => void profile.refetch()} />
        ) : profile.data ? (
          <>
            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-dim">
                Company
              </h3>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div>
                  <dt className="text-xs text-content-dim">Market cap</dt>
                  <dd className="tabular-nums text-content">
                    {formatMoney(profile.data.market_cap)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-content-dim">Avg volume</dt>
                  <dd className="tabular-nums text-content">
                    {formatVolume(profile.data.avg_volume)}
                  </dd>
                </div>
              </dl>
            </section>

            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-dim">
                Valuation
              </h3>
              <dl className="grid grid-cols-3 gap-x-4 gap-y-3 text-sm">
                {ratios.map((r) => (
                  <div key={r.label}>
                    <dt className="text-xs text-content-dim">{r.label}</dt>
                    <dd className="tabular-nums text-content">{r.value}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-content-dim">
                Profitability
              </h3>
              <dl className="grid grid-cols-3 gap-x-4 gap-y-3 text-sm">
                <div>
                  <dt className="text-xs text-content-dim">EBIT</dt>
                  <dd className="tabular-nums text-content">{formatMoney(profile.data.ebit)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-content-dim">Profit margin</dt>
                  <dd className="tabular-nums text-content">
                    {formatMargin(profile.data.profit_margin)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-content-dim">ROE</dt>
                  <dd className="tabular-nums text-content">
                    {formatMargin(profile.data.return_on_equity)}
                  </dd>
                </div>
              </dl>
            </section>
          </>
        ) : null}
      </div>

      <footer className="shrink-0 border-t border-hairline px-5 py-4">
        <button
          type="button"
          onClick={() => navigate(`/anchor/${encodeURIComponent(ticker)}`)}
          className="w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-hover"
        >
          View full correlations →
        </button>
      </footer>
    </>
  )

  const summaryModal =
    showFullSummary && profile.data?.business_summary ? (
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div
          className="absolute inset-0 bg-black/50 animate-[fadeIn_150ms_ease-out]"
          onClick={closeSummary}
          aria-hidden="true"
        />
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`${ticker} — company overview`}
          className="relative z-10 flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-hairline bg-raised shadow-xl"
        >
          <div className="flex items-start justify-between gap-3 border-b border-hairline px-5 py-4">
            <h3 className="text-base font-semibold text-content">
              {ticker}
              {profile.data.name ? <span className="text-content-dim"> · {profile.data.name}</span> : null}
            </h3>
            <button
              ref={summaryCloseRef}
              type="button"
              onClick={closeSummary}
              aria-label="Close overview"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-hairline text-content-dim transition-colors hover:border-brand hover:text-brand"
            >
              ✕
            </button>
          </div>
          <p className="overflow-auto px-5 py-4 text-sm leading-relaxed text-content-dim">
            {profile.data.business_summary}
          </p>
        </div>
      </div>
    ) : null

  if (isDesktop) {
    return (
      <>
        <aside
          role="complementary"
          aria-label={`${ticker} details`}
          className="relative flex h-full w-[380px] shrink-0 flex-col overflow-hidden border-l border-hairline bg-raised animate-[slideInRight_180ms_ease-out]"
        >
          {content}
        </aside>
        {summaryModal}
      </>
    )
  }

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40 animate-[fadeIn_180ms_ease-out]"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`${ticker} details`}
        className="fixed inset-x-0 bottom-0 z-50 flex max-h-[78vh] flex-col overflow-hidden rounded-t-2xl border-t border-hairline bg-raised shadow-xl animate-[slideUp_200ms_ease-out]"
      >
        {content}
      </aside>
      {summaryModal}
    </>
  )
}
