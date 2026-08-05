/**
 * Thin typed fetch wrapper. The base URL comes from VITE_API_BASE_URL
 * (.env.development / .env.production) so the same build points at localhost in
 * dev and the deployed API in prod. See docs/frontend-build-plan.md §4.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

/** Error carrying the HTTP status so callers can branch 404 vs 422 vs other. */
export class ApiError extends Error {
  readonly status: number
  readonly detail?: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export type ErrorKind = 'not-found' | 'insufficient-data' | 'generic'

/**
 * Maps any thrown error to the kind of empty/error state to show. The API's
 * exception handlers return 404 for an unknown ticker and 422 for insufficient
 * price history (src/api/errors.py) — these read very differently to a user
 * than a generic network failure, so they get distinct states.
 */
export function errorKind(error: unknown): ErrorKind {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'not-found'
    if (error.status === 422) return 'insufficient-data'
  }
  return 'generic'
}

type QueryValue = string | number | boolean | string[] | undefined | null

function buildQuery(params?: Record<string, QueryValue>): string {
  if (!params) return ''
  const usp = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      // Repeated key per value (?anchors=NVDA&anchors=TSM) — the shape FastAPI
      // expects for a list query param.
      for (const item of value) usp.append(key, String(item))
    } else {
      usp.append(key, String(value))
    }
  }
  const qs = usp.toString()
  return qs ? `?${qs}` : ''
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, QueryValue>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}${buildQuery(params)}`, {
    signal,
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let detail: unknown
    try {
      const body = await response.json()
      detail = body
      // The API's error bodies are { detail: string, ticker?: string }.
      if (typeof body?.detail === 'string') message = body.detail
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new ApiError(response.status, message, detail)
  }

  return (await response.json()) as T
}
