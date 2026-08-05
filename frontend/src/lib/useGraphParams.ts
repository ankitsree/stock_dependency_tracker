import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * The dashboard's filter state (selected anchors, top_n, threshold) lives in
 * the URL so every view is a shareable, bookmarkable link (Step 3). Anchors are
 * a comma-separated list; omitting a param lets the API fall back to its
 * config.yaml defaults.
 */
export function useGraphParams() {
  const [searchParams, setSearchParams] = useSearchParams()

  const rawAnchors = searchParams.get('anchors')
  const anchors = rawAnchors
    ? rawAnchors.split(',').map((a) => a.trim().toUpperCase()).filter(Boolean)
    : undefined

  const topNParam = searchParams.get('top_n')
  const topN = topNParam ? Number(topNParam) : undefined

  const thresholdParam = searchParams.get('threshold')
  const threshold = thresholdParam ? Number(thresholdParam) : undefined

  const update = useCallback(
    (key: string, value: string | undefined) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (value === undefined || value === '') next.delete(key)
          else next.set(key, value)
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const setAnchors = useCallback(
    (list: string[]) => update('anchors', list.length ? list.join(',') : undefined),
    [update],
  )
  const setTopN = useCallback((n: number | undefined) => update('top_n', n?.toString()), [update])
  const setThreshold = useCallback(
    (t: number | undefined) => update('threshold', t?.toString()),
    [update],
  )

  return { anchors, topN, threshold, setAnchors, setTopN, setThreshold }
}
