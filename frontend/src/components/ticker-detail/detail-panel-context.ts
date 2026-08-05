import { createContext, useContext } from 'react'

/** A price-correlation link from the opened ticker to one anchor. */
export interface AnchorRelation {
  anchor: string
  correlation: number
  stability: number | null
}

export interface DetailPanelValue {
  /** The ticker whose detail panel is open, or null when closed. */
  ticker: string | null
  /** Anchor(s) the open ticker price-correlates with (empty for an anchor). */
  relations: AnchorRelation[]
  /** Open the panel for a ticker. Both the graph and the table call this. */
  openDetail: (ticker: string, relations?: AnchorRelation[]) => void
  /** Close the panel and restore focus to whatever opened it. */
  closeDetail: () => void
}

export const DetailPanelContext = createContext<DetailPanelValue | null>(null)

export function useDetailPanel(): DetailPanelValue {
  const ctx = useContext(DetailPanelContext)
  if (!ctx) throw new Error('useDetailPanel must be used within <DetailPanelProvider>')
  return ctx
}
