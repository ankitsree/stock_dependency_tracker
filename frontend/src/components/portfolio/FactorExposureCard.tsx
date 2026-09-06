import type { ConcentrationMetrics } from '../../types/domain'

export interface FactorExposureCardProps {
  concentration: ConcentrationMetrics
  riskSummary: string[]
  weighting: string
  totalValue: number | null
  lookbackDays: number
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-base px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-content-dim">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-content">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-content-dim">{hint}</p> : null}
    </div>
  )
}

const money = (value: number) =>
  value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

/**
 * The "so what?" panel: three stat tiles (the headline numbers are numbers, not
 * charts — dataviz choosing-a-form) plus the server's plain-language read-out.
 */
export function FactorExposureCard({
  concentration,
  riskSummary,
  weighting,
  totalValue,
  lookbackDays,
}: FactorExposureCardProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat
          label="Top exposure"
          value={concentration.top_factor ?? '—'}
          hint={`${(concentration.top_factor_share * 100).toFixed(0)}% of variance`}
        />
        <Stat
          label="Top 3 factors"
          value={`${(concentration.top_three_share * 100).toFixed(0)}%`}
          hint="share of variance they jointly drive"
        />
        <Stat
          label="Effective factors"
          value={concentration.effective_factors.toFixed(1)}
          hint={`independent bets (HHI ${concentration.herfindahl_index.toFixed(2)})`}
        />
      </div>

      <ul className="space-y-1.5">
        {riskSummary.map((line) => (
          <li key={line} className="flex gap-2 text-sm text-content">
            <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-brand" />
            <span>{line}</span>
          </li>
        ))}
      </ul>

      <p className="text-xs text-content-dim">
        {weighting === 'market_value' && totalValue !== null
          ? `Weighted by market value (${money(totalValue)} total).`
          : 'Weighted equally across positions.'}{' '}
        Based on {lookbackDays} days of daily log-returns.
      </p>
    </div>
  )
}
