import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { CorrelationDisclaimer } from '../shared/CorrelationDisclaimer'
import { useDetailPanel } from '../ticker-detail/detail-panel-context'
import { TickerDetailPanel } from '../ticker-detail/TickerDetailPanel'

/**
 * Full-viewport layout: fixed header + footer, fillable content row. Using
 * h-screen gives the content row a concrete height so the graph canvas (which
 * fills flex-1) has real dimensions to size to — no magic pixel offsets.
 *
 * The detail panel renders here as a sibling of the page content so that, on
 * desktop, it's an in-flow right column (content reflows beside it) rather than
 * an overlay covering the header/footer. On mobile it's a fixed bottom sheet.
 */
export function AppShell() {
  const { ticker, relations, closeDetail } = useDetailPanel()

  return (
    <div className="flex h-screen flex-col bg-base text-content">
      <Header />
      <main className="flex flex-1 overflow-hidden">
        <div className="min-w-0 flex-1 overflow-hidden">
          <Outlet />
        </div>
        {ticker ? (
          <TickerDetailPanel ticker={ticker} relations={relations} onClose={closeDetail} />
        ) : null}
      </main>
      <footer className="shrink-0 border-t border-hairline px-6 py-3">
        <CorrelationDisclaimer />
      </footer>
    </div>
  )
}
