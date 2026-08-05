import { useEffect, useMemo, useRef, useState } from 'react'
import { useCompanySearch } from '../../api/hooks/useCompanySearch'

export interface AnchorMultiSelectProps {
  anchors: string[]
  onChange: (anchors: string[]) => void
}

const MAX_SUGGESTIONS = 10

/**
 * The anchors currently in the graph, as removable chips, plus an autocomplete
 * to add more. The dropdown suggests from the satellite universe (via
 * useCompanySearch) but the field still accepts any typed ticker, since the API
 * resolves tickers outside the universe too. Distinct from the header's
 * TickerSearch, which navigates to a single ticker's detail page.
 */
export function AnchorMultiSelect({ anchors, onChange }: AnchorMultiSelectProps) {
  const [draft, setDraft] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const { results } = useCompanySearch(draft)
  const suggestions = useMemo(
    () => results.filter((c) => !anchors.includes(c.ticker)).slice(0, MAX_SUGGESTIONS),
    [results, anchors],
  )

  // Close the dropdown when clicking outside the field/list.
  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  const addTicker = (ticker: string) => {
    const t = ticker.trim().toUpperCase()
    if (t && !anchors.includes(t)) onChange([...anchors, t])
    setDraft('')
    setHighlight(0)
    // Keep the list open so several anchors can be added in a row.
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
      if (isOpen && suggestions[highlight]) addTicker(suggestions[highlight].ticker)
      else if (draft.trim()) addTicker(draft)
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  const activeOptionId =
    isOpen && suggestions[highlight] ? `anchor-opt-${suggestions[highlight].ticker}` : undefined

  return (
    <div>
      <div className="mb-1.5 text-xs font-medium text-content-dim">Anchors</div>
      <div className="flex flex-wrap items-center gap-2">
        {anchors.map((anchor) => (
          <span
            key={anchor}
            className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-raised py-1 pl-3 pr-1.5 text-sm text-content"
          >
            {anchor}
            <button
              type="button"
              aria-label={`Remove ${anchor}`}
              onClick={() => onChange(anchors.filter((a) => a !== anchor))}
              className="flex h-4 w-4 items-center justify-center rounded-full text-content-dim transition-colors hover:bg-brand hover:text-white"
            >
              ×
            </button>
          </span>
        ))}

        <div ref={containerRef} className="relative">
          <input
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value)
              setIsOpen(true)
              setHighlight(0)
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={onKeyDown}
            placeholder="+ add ticker"
            role="combobox"
            aria-expanded={isOpen && suggestions.length > 0}
            aria-controls="anchor-suggestions"
            aria-autocomplete="list"
            aria-activedescendant={activeOptionId}
            aria-label="Add an anchor ticker"
            className="w-32 rounded-full border border-dashed border-hairline bg-transparent px-3 py-1 text-sm text-content placeholder:text-content-dim focus:border-brand focus:outline-none"
          />

          {isOpen && suggestions.length > 0 ? (
            <ul
              id="anchor-suggestions"
              role="listbox"
              className="absolute left-0 top-full z-30 mt-1.5 max-h-64 w-64 overflow-auto rounded-lg border border-hairline bg-raised py-1 shadow-lg"
            >
              {suggestions.map((company, i) => (
                <li
                  key={company.ticker}
                  id={`anchor-opt-${company.ticker}`}
                  role="option"
                  aria-selected={i === highlight}
                  onMouseEnter={() => setHighlight(i)}
                  onMouseDown={(e) => {
                    e.preventDefault() // keep focus in the input
                    addTicker(company.ticker)
                  }}
                  className={
                    'flex cursor-pointer items-baseline gap-2 px-3 py-1.5 text-sm ' +
                    (i === highlight
                      ? 'bg-[color-mix(in_srgb,var(--color-accent)_12%,transparent)]'
                      : '')
                  }
                >
                  <span className="font-semibold text-content">{company.ticker}</span>
                  <span className="truncate text-xs text-content-dim">{company.name}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  )
}
