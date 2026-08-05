import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { DetailPanelContext, type AnchorRelation } from './detail-panel-context'

/**
 * Owns the detail-panel state shared by the graph (node click) and the
 * satellite table (row click) — one panel, two trigger points. Captures the
 * triggering element on open and restores focus to it on close (Step 6), and
 * closes the panel on route change. The panel itself is rendered by AppShell so
 * it can sit as an in-flow column beside the content (not overlapping the
 * header/footer).
 */
export function DetailPanelProvider({ children }: { children: ReactNode }) {
  const [ticker, setTicker] = useState<string | null>(null)
  const [relations, setRelations] = useState<AnchorRelation[]>([])
  const triggerRef = useRef<HTMLElement | null>(null)
  const location = useLocation()
  const lastPath = useRef(location.pathname)

  const openDetail = useCallback((next: string, nextRelations: AnchorRelation[] = []) => {
    triggerRef.current = document.activeElement as HTMLElement | null
    setTicker(next)
    setRelations(nextRelations)
  }, [])

  const closeDetail = useCallback(() => {
    setTicker(null)
    const trigger = triggerRef.current
    if (trigger && document.contains(trigger)) trigger.focus()
    triggerRef.current = null
  }, [])

  // Close on navigation (without focus restore — the trigger is likely gone).
  useEffect(() => {
    if (lastPath.current !== location.pathname) {
      lastPath.current = location.pathname
      setTicker(null)
      triggerRef.current = null
    }
  }, [location.pathname])

  return (
    <DetailPanelContext.Provider value={{ ticker, relations, openDetail, closeDetail }}>
      {children}
    </DetailPanelContext.Provider>
  )
}
