import { useEffect, useMemo, useRef, useState } from 'react'
import { useCompanySearch } from '../../api/hooks/useCompanySearch'
import { useDetailPanel } from '../ticker-detail/detail-panel-context'

const MAX_SUGGESTIONS = 8

/**
 * Header quick-jump: type/pick a ticker to open its detail panel (price,
 * profile, business summary, and the anchors it correlates with). A custom
 * combobox rather than a native <datalist> so clicking a suggestion actually
 * does something. Accepts any typed ticker, since the API resolves symbols
 * outside the universe too.
 */
export function TickerSearch() {
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const { openDetail } = useDetailPanel()
  const { results } = useCompanySearch(query)
  const suggestions = useMemo(() => results.slice(0, MAX_SUGGESTIONS), [results])

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  const select = (ticker: string) => {
    const t = ticker.trim().toUpperCase()
    if (!t) return
    // No relations passed — the panel derives the correlated anchors from the graph.
    openDetail(t)
    setQuery('')
    setIsOpen(false)
    setHighlight(0)
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIsOpen(true)
      setHighlight((h) => Math.min(h + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (isOpen && suggestions[highlight]) select(suggestions[highlight].ticker)
      else if (query.trim()) select(query)
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  const activeOptionId =
    isOpen && suggestions[highlight] ? `ticker-opt-${suggestions[highlight].ticker}` : undefined
  // The dropdown only ever suggests from the satellite universe, which
  // structurally excludes anchors (NVDA, AAPL, ...) — so a real ticker with
  // no suggestions looks identical to a typo. This hint is the only signal
  // that Enter still works; without it, "no matches" reads as "invalid".
  const trimmedQuery = query.trim()
  const showNoMatchHint = isOpen && trimmedQuery.length > 0 && suggestions.length === 0

  return (
    <div ref={containerRef} className="relative" role="search">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setIsOpen(true)
          setHighlight(0)
        }}
        onFocus={() => setIsOpen(true)}
        onKeyDown={onKeyDown}
        placeholder="Search ticker…"
        role="combobox"
        aria-expanded={isOpen && (suggestions.length > 0 || showNoMatchHint)}
        aria-controls="ticker-search-listbox"
        aria-autocomplete="list"
        aria-activedescendant={activeOptionId}
        aria-label="Search for a ticker"
        className="h-9 w-40 rounded-md border border-hairline bg-raised px-3 text-sm text-content placeholder:text-content-dim focus:border-brand focus:outline-none sm:w-52"
      />
      {showNoMatchHint ? (
        <div
          id="ticker-search-listbox"
          className="absolute right-0 top-full z-50 mt-1.5 w-64 rounded-lg border border-hairline bg-raised px-3 py-2 text-xs text-content-dim shadow-lg"
        >
          Not in the satellite list — press <kbd className="font-semibold text-content">Enter</kbd> to
          look up <span className="font-semibold text-content">{trimmedQuery.toUpperCase()}</span> anyway.
        </div>
      ) : isOpen && suggestions.length > 0 ? (
        <ul
          id="ticker-search-listbox"
          role="listbox"
          className="absolute right-0 top-full z-50 mt-1.5 max-h-72 w-64 overflow-auto rounded-lg border border-hairline bg-raised py-1 shadow-lg"
        >
          {suggestions.map((company, i) => (
            <li
              key={company.ticker}
              id={`ticker-opt-${company.ticker}`}
              role="option"
              aria-selected={i === highlight}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={(e) => {
                e.preventDefault()
                select(company.ticker)
              }}
              className={
                'flex cursor-pointer items-baseline gap-2 px-3 py-1.5 text-sm ' +
                (i === highlight ? 'bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)]' : '')
              }
            >
              <span className="font-semibold text-content">{company.ticker}</span>
              <span className="truncate text-xs text-content-dim">{company.name}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
