import { useEffect, useState } from 'react'

/**
 * Reactive media-query match. Used to drive state-based responsive behavior
 * (e.g. which table columns render) rather than CSS `display:none`, so hidden
 * content isn't in the DOM/accessibility tree at all.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  )

  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (event: MediaQueryListEvent) => setMatches(event.matches)
    setMatches(mql.matches)
    mql.addEventListener('change', handler)
    return () => mql.removeEventListener('change', handler)
  }, [query])

  return matches
}
