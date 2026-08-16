/**
 * Presence-gated Sentry init. Mirrors the backend's `if config.sentry_dsn`
 * pattern (src/api/main.py): if VITE_SENTRY_DSN is not set at build time the
 * SDK never boots and no network calls happen. Safe to leave the import in
 * every environment.
 *
 * VITE_SENTRY_DSN and VITE_SENTRY_ENVIRONMENT are inlined at build time by
 * Vite. Set them in the Vercel project's env vars (Production scope).
 */
import * as Sentry from '@sentry/react'

export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT ?? import.meta.env.MODE,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllText: false, blockAllMedia: false }),
    ],
    // 100% is fine at the current traffic scale; matches the backend.
    tracesSampleRate: 1.0,
    // Replay only on error keeps the payload cheap while still giving the
    // "what did the user do just before this" trail when something breaks.
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
  })
}
