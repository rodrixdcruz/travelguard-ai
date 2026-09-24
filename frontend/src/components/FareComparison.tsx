import type { AnalyzeResponse } from '../types'
import Panel from './Panel'

const row = (label: string) =>
  /train|bus|metro/.test(label)
    ? 'border-emerald-400/25 bg-emerald-400/5'
    : /bike|auto|cab|taxi/i.test(label)
      ? 'border-cyan-400/25 bg-cyan-400/5'
      : 'border-slate-700 bg-slate-800/40'

/** Fare comparison — all 8 modes, cheapest first. Every fare is ESTIMATED. */
export default function FareComparison({ analysis }: { analysis: AnalyzeResponse }) {
  const fares = analysis.fare_comparison
  if (!fares?.length) return null

  const cheapest = fares[0]?.fare_inr

  return (
    <Panel>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-xs uppercase tracking-widest text-slate-400">Fare comparison · all modes</h3>
        <span className="text-[10px] uppercase tracking-widest text-amber-300/80 border border-amber-400/20 bg-amber-400/5 rounded-lg px-2 py-1">
          Estimated fares
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
        {fares.map((f) => (
          <div
            key={f.mode}
            className={`border rounded-xl px-3 py-2.5 ${f.fare_inr === cheapest ? 'border-emerald-400/60 bg-emerald-400/10' : row(f.label)}`}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="text-sm">{f.icon}</span>
              {f.fare_inr === cheapest && (
                <span className="text-[9px] uppercase tracking-wider text-emerald-300 font-semibold">cheapest</span>
              )}
              {f.fare_inr !== cheapest && (
                <span className="text-[9px] text-slate-500">+₹{Math.round(f.fare_inr - cheapest)}</span>
                )}
            </div>
            <div className="mt-1 text-sm font-display font-semibold text-slate-100">{f.label}</div>
            <div className="text-[11px] text-cyan-300">₹{Math.round(f.fare_inr)} · ~{Math.round(f.duration_min)} min</div>
            <div className="text-[10px] text-slate-500">{f.distance_km} km road est.</div>
          </div>
          ))}
      </div>
      <p className="mt-2 text-[10px] text-slate-500">
        Modeled rate cards × road-factor distance — not live fares. Fares shown per traveler.
      </p>
      <p className="sr-only">All {fares.length} transport modes compared, sorted cheapest first, estimated data</p>
    </Panel>
  )
}
