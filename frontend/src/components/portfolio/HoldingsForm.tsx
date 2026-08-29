import { useMemo, useState } from 'react'
import { parseHoldings } from '../../lib/parseHoldings'
import type { PortfolioHoldingInput } from '../../types/domain'

export interface HoldingsFormProps {
  onAnalyze: (holdings: PortfolioHoldingInput[]) => void
  isPending: boolean
}

const PLACEHOLDER = `AAPL 100 shares
MSFT 50
ASML 25
TSM 10`

const EXAMPLE = 'AAPL 100\nMSFT 50\nASML 25\nTSM 10\nAMKR 400'

/** Matches src/api/schemas/portfolio.py's MAX_HOLDINGS — the server rejects more. */
const MAX_HOLDINGS = 50

/**
 * Paste-a-portfolio input. Parsing happens as you type so the count, the
 * unparseable lines, and the disabled state are all visible before submitting
 * — a 422 from the server is a much worse way to learn a line was malformed.
 */
export function HoldingsForm({ onAnalyze, isPending }: HoldingsFormProps) {
  const [text, setText] = useState('')
  const { holdings, invalid } = useMemo(() => parseHoldings(text), [text])

  const tooMany = holdings.length > MAX_HOLDINGS
  const canSubmit = holdings.length > 0 && !tooMany && !isPending

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (canSubmit) onAnalyze(holdings)
      }}
      className="space-y-3"
    >
      <div>
        <label htmlFor="holdings" className="text-sm font-semibold text-content">
          Your holdings
        </label>
        <p id="holdings-help" className="mt-1 text-xs text-content-dim">
          One per line — ticker, then an optional share count. Nothing is saved or sent anywhere
          but this analysis.
        </p>
      </div>

      <textarea
        id="holdings"
        aria-describedby="holdings-help"
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={PLACEHOLDER}
        rows={8}
        spellCheck={false}
        className="w-full resize-y rounded-lg border border-hairline bg-base px-3 py-2 text-sm text-content placeholder:text-content-dim focus:border-brand focus:outline-none"
      />

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-base transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isPending ? 'Analyzing…' : 'Analyze portfolio'}
        </button>
        <button
          type="button"
          onClick={() => setText(EXAMPLE)}
          className="text-xs text-content-dim underline-offset-4 hover:text-brand hover:underline"
        >
          Use an example
        </button>
        <span aria-live="polite" className="text-xs text-content-dim">
          {holdings.length > 0
            ? `${holdings.length} holding${holdings.length === 1 ? '' : 's'} parsed`
            : 'No holdings yet'}
        </span>
      </div>

      {tooMany ? (
        <p role="alert" className="text-xs text-brand">
          {holdings.length} holdings — the limit is {MAX_HOLDINGS} per analysis.
        </p>
      ) : null}

      {invalid.length > 0 ? (
        <p className="text-xs text-content-dim">
          Couldn&apos;t read {invalid.length} line{invalid.length === 1 ? '' : 's'}:{' '}
          <span className="text-content">{invalid.slice(0, 3).join(' · ')}</span>
          {invalid.length > 3 ? ' …' : ''}
        </p>
      ) : null}
    </form>
  )
}
