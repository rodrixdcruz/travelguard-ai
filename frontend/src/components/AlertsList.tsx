import type { Alert } from '../types'
import { RiskBadge } from './RiskBadge'

export default function AlertsList({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="glass p-5">
      <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-slate-300 mb-4">
        Critical Alerts
      </h2>
      {alerts.length === 0 ? (
        <p className="text-sm text-slate-500">No active alerts for this journey. 👍</p>
      ) : (
        <ul className="space-y-3 max-h-64 overflow-y-auto pr-1">
          {alerts.map((a) => (
            <li key={a.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-sm font-semibold text-slate-200">{a.title}</span>
                <RiskBadge level={a.severity} />
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{a.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
