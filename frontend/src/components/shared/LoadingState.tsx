/**
 * Neutral loading indicator used by every async view. A layout-shaped skeleton
 * is a Step 9 (motion & polish) refinement; a labelled spinner is enough now.
 */
export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 p-6 text-content-dim"
    >
      <span
        aria-hidden="true"
        className="h-4 w-4 animate-spin rounded-full border-2 border-hairline border-t-brand"
      />
      <span className="text-sm">{label}</span>
    </div>
  )
}
