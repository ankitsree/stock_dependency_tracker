import type { ReactNode } from 'react'

/** Neutral "there's nothing here" state — distinct from an error. */
export function EmptyState({
  title,
  message,
  action,
}: {
  title: string
  message?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 p-8 text-center">
      <p className="text-sm font-semibold text-content">{title}</p>
      {message ? <p className="max-w-sm text-sm text-content-dim">{message}</p> : null}
      {action}
    </div>
  )
}
