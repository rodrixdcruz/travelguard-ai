import type { OverallRisk } from '../types'
import { levelColor, scoreColor } from '../utils/format'

const LABELS: Record<string, string> = {
  weather: 'Weather',
  accident: 'Accident Risk',
  road: 'Road Conditions',
  disruption: 'Disruptions',
  time: 'Time of Travel',
}

export default function RiskBreakdown({ breakdown }: { breakdown: OverallRisk['breakdown'] }) {
  const entries = Object.entries(breakdown)
  const max = Math.max(...entries.map(([, v]) => v), 10)

  return (
    <section className="glass p-5">
      <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-slate-300 mb-4">
        Risk Breakdown
      </h2>
      <div className="space-y-3.5">
        {entries.map(([cat, value]) => (
          <div key={cat}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-slate-300">{LABELS[cat] ?? cat}</span>
              <span className="font-semibold" style={{ color: scoreColor(value) }}>
                {Math.round(value)}
              </span>
            </div>
            <div className="h-2 rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${(value / max) * 100}%`,
                  background: `linear-gradient(90deg, ${scoreColor(value)}55, ${scoreColor(value)})`,
                  boxShadow: `0 0 8px ${scoreColor(value)}44`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
