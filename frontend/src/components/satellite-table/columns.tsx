import { createColumnHelper } from '@tanstack/react-table'
import type { ColumnDef } from '@tanstack/react-table'
import type { RankedSatellite } from '../../types/domain'

const num2 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
const lag = (v: number | null | undefined) =>
  v == null ? '—' : v === 0 ? '0d' : `${v > 0 ? '+' : ''}${v}d`

const helper = createColumnHelper<RankedSatellite>()

/**
 * Columns closed over `onSelect` (the ticker cell is the keyboard-accessible
 * trigger for the detail panel) — a factory rather than module augmentation of
 * TableMeta. Memoize the result on `onSelect` in the table component.
 */
export function makeSatelliteColumns(
  onSelect: (row: RankedSatellite) => void,
): ColumnDef<RankedSatellite, never>[] {
  return [
    helper.accessor('ticker', {
      header: 'Ticker',
      cell: (ctx) => (
        <button
          type="button"
          onClick={() => onSelect(ctx.row.original)}
          className="rounded-sm font-semibold text-content underline-offset-2 hover:text-brand hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
        >
          {ctx.getValue<string>()}
        </button>
      ),
    }),
    helper.accessor('name', {
      header: 'Company',
      cell: (ctx) => <span className="text-content-dim">{ctx.getValue<string>()}</span>,
    }),
    helper.accessor('sector', {
      header: 'Sector',
      cell: (ctx) => <span className="text-content-dim">{ctx.getValue<string>()}</span>,
    }),
    helper.accessor('correlation', {
      header: 'Corr',
      cell: (ctx) => <span className="text-content">{num2(ctx.getValue<number>())}</span>,
    }),
    helper.accessor('stability', { header: 'Stability', cell: (ctx) => num2(ctx.getValue<number>()) }),
    helper.accessor('partial_correlation', {
      header: 'Partial',
      cell: (ctx) => num2(ctx.getValue<number>()),
    }),
    helper.accessor('sector_relative_correlation', {
      header: 'Sector-rel',
      cell: (ctx) => num2(ctx.getValue<number>()),
    }),
    helper.accessor('best_lag', { header: 'Lag', cell: (ctx) => lag(ctx.getValue<number>()) }),
    helper.accessor('regime_break', {
      header: 'Regime',
      enableSorting: false,
      cell: (ctx) =>
        ctx.getValue<boolean>() ? (
          <span className="rounded bg-[color-mix(in_srgb,#eb6834_22%,transparent)] px-1.5 py-0.5 text-[11px] font-semibold text-[#eb6834] dark:text-[#f0a480]">
            break
          </span>
        ) : (
          <span className="text-content-dim">—</span>
        ),
    }),
  ] as ColumnDef<RankedSatellite, never>[]
}
