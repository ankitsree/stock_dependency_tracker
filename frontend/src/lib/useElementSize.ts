import { useLayoutEffect, useRef, useState } from 'react'

/**
 * Measures a container so the canvas graph can size to it (not to the window).
 * Returns a ref to attach and the current { width, height } in CSS pixels.
 * Satisfies the "graph canvas resizes to its container" requirement (Step 8).
 */
export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        const { width, height } = entry.contentRect
        setSize({ width, height })
      }
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return [ref, size] as const
}
