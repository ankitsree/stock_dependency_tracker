import { Fragment, useCallback, useMemo, useState } from 'react'
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import type { SortingState } from '@tanstack/react-table'
import type { RankedSatellite } from '../../types/domain'
import { useDetailPanel } from '../ticker-detail/detail-panel-context'
import { useResponsiveColumns } from './useResponsiveColumns'
import { makeSatelliteColumns } from './columns'

/** Column ids rendered left-aligned; everything else is a right-aligned number. */
const LEFT_ALIGNED = new Set(['ticker', 'name', 'sector'])

function ariaSort(dir: false | 'asc' | 'desc'): 'none' | 'ascending' | 'descending' {
  if (dir === 'asc') return 'ascending'
  if (dir === 'desc') return 'descending'
  return 'none'
}

/** Diagnostics hidden on narrow screens, shown in the per-row expander instead. */
const NARROW_HIDDEN: { key: keyof RankedSatellite; label: string }[] = [
  { key: 'sector', label: 'Sector' },
  { key: 'partial_correlation', label: 'Partial' },
  { key: 'sector_relative_correlation', label: 'Sector-rel' },
  { key: 'best_lag', label: 'Best lag' },
  { key: 'regime_break', label: 'Regime break' },
]

export function SatelliteTable({
  anchor,
  satellites,
}: {
  anchor: string
  satellites: RankedSatellite[]
}) {
  const { openDetail } = useDetailPanel()
  const { columnVisibility, isNarrow } = useResponsiveColumns()
  const [sorting, setSorting] = useState<SortingState>([{ id: 'correlation', desc: true }])
  const [expanded, setExpanded] = useState<string | null>(null)

  // Opening from the table carries this anchor as the relation context.
  const select = useCallback(
    (row: RankedSatellite) =>
      openDetail(row.ticker, [
        { anchor, correlation: row.correlation, stability: row.stability ?? null },
      ]),
    [openDetail, anchor],
  )

  const columns = useMemo(() => makeSatelliteColumns(select), [select])

  const table = useReactTable({
    data: satellites,
    columns,
    state: { sorting, columnVisibility },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="overflow-x-auto rounded-lg border border-hairline">
      <table className="w-full border-collapse text-sm" aria-label="Correlated satellites, sortable">
        <thead>
          <tr className="border-b border-hairline">
            {isNarrow ? <th className="w-8" aria-label="Expand row" /> : null}
            {table.getHeaderGroups()[0]?.headers.map((header) => {
              const sortable = header.column.getCanSort()
              const dir = header.column.getIsSorted()
              const left = LEFT_ALIGNED.has(header.column.id)
              return (
                <th
                  key={header.id}
                  scope="col"
                  aria-sort={sortable ? ariaSort(dir) : undefined}
                  className={
                    'bg-raised px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-content-dim ' +
                    (left ? 'text-left' : 'text-right')
                  }
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={header.column.getToggleSortingHandler()}
                      className={
                        'inline-flex items-center gap-1 rounded-sm hover:text-content focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand ' +
                        (left ? '' : 'flex-row-reverse')
                      }
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      <span aria-hidden="true" className="text-content">
                        {dir === 'asc' ? '↑' : dir === 'desc' ? '↓' : ''}
                      </span>
                    </button>
                  ) : (
                    flexRender(header.column.columnDef.header, header.getContext())
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isBreak = row.original.regime_break === true
            const isOpen = expanded === row.original.ticker
            return (
              <Fragment key={row.id}>
                <tr
                  onClick={() => select(row.original)}
                  className={
                    'cursor-pointer border-b border-hairline transition-colors hover:bg-[color-mix(in_srgb,var(--color-accent)_8%,transparent)] ' +
                    (isBreak ? 'bg-[color-mix(in_srgb,#eb6834_7%,transparent)]' : '')
                  }
                >
                  {isNarrow ? (
                    <td className="px-1">
                      <button
                        type="button"
                        aria-expanded={isOpen}
                        aria-label={isOpen ? 'Collapse details' : 'Expand details'}
                        onClick={(e) => {
                          e.stopPropagation()
                          setExpanded(isOpen ? null : row.original.ticker)
                        }}
                        className="flex h-6 w-6 items-center justify-center rounded text-content-dim hover:text-content"
                      >
                        {isOpen ? '▾' : '▸'}
                      </button>
                    </td>
                  ) : null}
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={
                        'px-3 py-2.5 ' +
                        (LEFT_ALIGNED.has(cell.column.id) ? 'text-left' : 'text-right tabular-nums')
                      }
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {isNarrow && isOpen ? (
                  <tr className="border-b border-hairline bg-raised/50">
                    <td colSpan={row.getVisibleCells().length + 1} className="px-4 py-3">
                      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                        {NARROW_HIDDEN.map(({ key, label }) => {
                          const value = row.original[key]
                          return (
                            <div key={key} className="flex justify-between gap-2">
                              <dt className="text-content-dim">{label}</dt>
                              <dd className="tabular-nums text-content">
                                {value == null
                                  ? '—'
                                  : typeof value === 'boolean'
                                    ? value
                                      ? 'yes'
                                      : 'no'
                                    : typeof value === 'number'
                                      ? value.toFixed(2)
                                      : String(value)}
                              </dd>
                            </div>
                          )
                        })}
                      </dl>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
