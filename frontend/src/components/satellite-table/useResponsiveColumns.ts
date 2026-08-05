import { useMemo } from 'react'
import type { VisibilityState } from '@tanstack/react-table'
import { useMediaQuery } from '../../lib/useMediaQuery'

/**
 * Below `md` (768px) the diagnostic columns are hidden and surfaced via a
 * per-row expand instead. Driven by matchMedia state (not CSS) so the hidden
 * columns aren't rendered into the DOM / a11y tree on small screens at all.
 * `isNarrow` is also returned so the table knows whether to show expanders.
 */
export function useResponsiveColumns(): { columnVisibility: VisibilityState; isNarrow: boolean } {
  const isNarrow = useMediaQuery('(max-width: 767px)')

  const columnVisibility = useMemo<VisibilityState>(
    () =>
      isNarrow
        ? {
            sector: false,
            partial_correlation: false,
            sector_relative_correlation: false,
            best_lag: false,
            regime_break: false,
          }
        : {},
    [isNarrow],
  )

  return { columnVisibility, isNarrow }
}
