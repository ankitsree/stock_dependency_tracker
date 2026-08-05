import type { ErrorKind } from '../../api/client'

/**
 * Distinct, informative error states — never a single generic message.
 * `kind` is derived from the thrown error via `errorKind()` in api/client.ts:
 * 404 -> not-found, 422 -> insufficient-data, everything else -> generic.
 */
const COPY: Record<ErrorKind, { title: string; message: string }> = {
  'not-found': {
    title: 'Ticker not found',
    message: "We couldn't find that ticker. Check the symbol and try again.",
  },
  'insufficient-data': {
    title: 'Not enough price history',
    message:
      "This ticker doesn't have enough overlapping price history to compute a reliable correlation.",
  },
  generic: {
    title: 'Something went wrong',
    message: 'The request failed. This is usually temporary — try again.',
  },
}

export interface ErrorStateProps {
  kind?: ErrorKind
  /** Overrides the default copy when the API returned a specific message. */
  detail?: string
  /** When provided, renders a retry button (for user-triggered requests). */
  onRetry?: () => void
}

export function ErrorState({ kind = 'generic', detail, onRetry }: ErrorStateProps) {
  const { title, message } = COPY[kind]

  return (
    <div role="alert" className="flex flex-col items-center gap-3 p-8 text-center">
      <p className="text-sm font-semibold text-content">{title}</p>
      <p className="max-w-sm text-sm text-content-dim">{detail ?? message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-hairline bg-raised px-3 py-1.5 text-sm text-content transition-colors hover:border-brand hover:text-brand"
        >
          Try again
        </button>
      ) : null}
    </div>
  )
}
