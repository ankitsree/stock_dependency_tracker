/**
 * Persistent, always-visible note that relationships are price-correlation
 * based — a project-wide convention (CLAUDE.md), not optional fine print.
 * Rendered in the AppShell footer so it appears on every page.
 */
export function CorrelationDisclaimer() {
  return (
    <p className="text-xs leading-relaxed text-content-dim">
      Edges reflect <strong className="font-semibold text-content">price correlation</strong>,
      not verified supply-chain or business dependencies. Correlation is not causation —
      treat these as a discovery starting point, not investment advice.
    </p>
  )
}
