const TOP_N_OPTIONS = [10, 11, 12, 13, 14, 15]

export interface GraphControlsProps {
  topN: number | undefined
  threshold: number | undefined
  onTopN: (n: number) => void
  onThreshold: (t: number) => void
}

/**
 * top_n is a narrow 10–15 range, so a segmented stepper communicates the
 * discrete choice better than a slider. threshold is continuous → a slider.
 * Undefined values fall back to the API's config defaults (10 / 0.5) for display.
 */
export function GraphControls({ topN, threshold, onTopN, onThreshold }: GraphControlsProps) {
  const activeTopN = topN ?? 10
  const activeThreshold = threshold ?? 0.5

  return (
    <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
      <div>
        <div className="mb-1.5 text-xs font-medium text-content-dim">Connections per anchor</div>
        <div className="inline-flex overflow-hidden rounded-md border border-hairline">
          {TOP_N_OPTIONS.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={n === activeTopN}
              onClick={() => onTopN(n)}
              className={
                'px-3 py-1.5 text-sm transition-colors ' +
                (n === activeTopN
                  ? 'bg-brand text-white'
                  : 'bg-raised text-content-dim hover:text-content')
              }
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <div className="min-w-[200px]">
        <label htmlFor="threshold" className="mb-1.5 block text-xs font-medium text-content-dim">
          Min correlation ·{' '}
          <span className="text-content">{activeThreshold.toFixed(2)}</span>
        </label>
        <input
          id="threshold"
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={activeThreshold}
          onChange={(e) => onThreshold(Number(e.target.value))}
          className="w-full"
          style={{ accentColor: 'var(--color-accent)' }}
        />
      </div>
    </div>
  )
}
