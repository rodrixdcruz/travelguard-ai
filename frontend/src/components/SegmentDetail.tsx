import type { Segment } from '../types'
import { formatDuration, scoreColor } from '../utils/format'
import { RiskBadge } from './RiskBadge'

interface Props {
  segment: Segment | null
  segments: Segment[]
  onSelect: (id: number) => void
}

const FACTOR_LABELS: Record<string, string> = {
  weather: 'Weather',
  accident: 'Accident',
  road: 'Road',
  disruption: 'Disruption',
  time: 'Time',
}

export default function SegmentDetail({ segment, segments, onSelect }: Props) {
  if (!segment) {
    return (
      <section className="glass p-5 h-full flex flex-col items-center justify-center text-center min-h-[280px]">
        <svg viewBox="0 0 24 24" className="w-10 h-10 text-slate-600 mb-3" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" />
        </svg>
        <p className="text-sm text-slate-400 font-medium">Select a route segment</p>
        <p className="text-xs text-slate-500 mt-1">Click any colored line on the map or pick from the list below.</p>
        <div className="mt-4 space-y-1.5 w-full">
          {segments.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s.id)}
              className="w-full flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-xs hover:border-cyan-400/30 hover:bg-cyan-400/5 transition-colors"
            >
              <span className="text-slate-300">{s.name}</span>
              <span className="font-bold" style={{ color: scoreColor(s.score) }}>
                {s.level}
              </span>
            </button>
          ))}
        </div>
      </section>
    )
  }

  const weather = segment.weather as { condition?: string; visibility_km?: number; precip_mm?: number }
  const road = segment.road_condition as { type?: string; surface?: string }

  return (
    <section className="glass p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-slate-300">
          {segment.name}
        </h2>
        <RiskBadge level={segment.level} />
      </div>

      <div className="flex items-baseline gap-2 mb-4">
        <span className="text-3xl font-display font-bold" style={{ color: scoreColor(segment.score) }}>
          {Math.round(segment.score)}
        </span>
        <span className="text-xs text-slate-500">/ 100 · {formatDuration(segment.duration_min)} stretch · {segment.distance_km.toFixed(1)} km</span>
      </div>

      <div className="space-y-2 mb-4">
        {segment.factors
          .slice()
          .sort((a, b) => b.score - a.score)
          .map((f) => (
            <div key={f.category} className="flex gap-2 text-xs">
              <span
                className="shrink-0 mt-0.5 w-14 text-center rounded px-1 py-0.5 font-semibold"
                style={{ color: scoreColor(f.score), background: `${scoreColor(f.score)}14` }}
              >
                {FACTOR_LABELS[f.category] ?? f.category}
              </span>
              <span className="text-slate-400 leading-relaxed">{f.reason}</span>
            </div>
          ))}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs mb-4">
        <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
          <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">Weather</div>
          <div className="text-slate-300">
            {weather.condition ?? '—'}
            {weather.precip_mm ? ` · ${weather.precip_mm} mm` : ''}
          </div>
          <div className="text-slate-500">
            visibility ~{weather.visibility_km ?? '?'} km
          </div>
        </div>
        <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2.5">
          <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">Road</div>
          <div className="text-slate-300 capitalize">{road.type ?? '—'} · {road.surface ?? '—'}</div>
        </div>
      </div>

      <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3 text-sm text-cyan-200/90 leading-relaxed">
        <span className="font-semibold">Action: </span>{segment.recommended_action}
      </div>

      <button
        onClick={() => onSelect(-1)}
        className="mt-3 text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        ← Back to segment list
      </button>
    </section>
  )
}
