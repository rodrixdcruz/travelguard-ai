import { useState } from 'react'
import { mlSafetyPredict } from '../services/api'
import Panel from './Panel'
import type { MlSafetyResponse } from '../types'

const FEATURE_LABELS: Record<string, string> = {
  weather_severity: 'Weather severity',
  rain_intensity: 'Rain intensity',
  visibility: 'Visibility (km)',
  wind_severity: 'Wind severity',
  night_indicator: 'Night travel',
  road_disruption: 'Road disruption',
  historical_incident_density: 'Incident density (/km-yr)',
  distance_to_emergency_service: 'Emergency-service distance (km)',
  nearby_service_density: 'Service density',
  tourist_area_indicator: 'Tourist area',
  area_activity_level: 'Activity level',
  route_condition: 'Route condition',
  time_of_day: 'Time-of-day exposure',
}

const PRESETS = {
  calm: {
    label: 'Calm afternoon',
    payload: {
      weather: { condition: 'Clear', precip_mm: 0, visibility_km: 10, wind_kph: 6 },
      context: { hour: 15, tourist_area: true, activity_level: 7 },
      location: { incident_density: 0.3, nearest_hospital_km: 2.5, service_density: 8 },
      road: { type: 'expressway', surface: 'good' },
    },
  },
  monsoon: {
    label: 'Monsoon night, ghat road',
    payload: {
      weather: { condition: 'Heavy Rain', precip_mm: 42, visibility_km: 1.2, wind_kph: 38 },
      context: { hour: 2, tourist_area: false, activity_level: 2 },
      location: { incident_density: 2.6, nearest_hospital_km: 26, service_density: 2 },
      road: { type: 'ghat', surface: 'poor' },
    },
  },
  fog: {
    label: 'Winter fog, highway',
    payload: {
      weather: { condition: 'Fog', precip_mm: 0, visibility_km: 0.8, wind_kph: 5 },
      context: { hour: 5, tourist_area: false, activity_level: 3 },
      location: { incident_density: 1.2, nearest_hospital_km: 9, service_density: 4 },
      road: { type: 'highway', surface: 'fair' },
    },
  },
} as const

type PresetKey = keyof typeof PRESETS

export default function MLPipelineDemo() {
  const [preset, setPreset] = useState<PresetKey>('monsoon')
  const [result, setResult] = useState<MlSafetyResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setResult(await mlSafetyPredict(PRESETS[preset].payload))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const features = result?.model_features ?? {}

  return (
    <Panel title="ML Pipeline Demo">
      <p className="text-[11px] text-slate-500 -mt-2 mb-4">
        Live view of the actual pipeline: structured context → feature engineering → RandomForest → risk score.
      </p>

      <div className="flex flex-wrap gap-1.5 mb-4">
        {(Object.keys(PRESETS) as PresetKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setPreset(k)}
            className={`text-xs rounded-full px-3 py-1.5 border transition-colors ${
              preset === k
                ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                : 'border-white/10 text-slate-400 hover:text-slate-200'
            }`}
          >
            {PRESETS[k].label}
          </button>
        ))}
      </div>

      <button onClick={run} disabled={busy} className="btn-primary">
        {busy ? 'Running pipeline…' : '▶ Run pipeline'}
      </button>

      {error && (
        <p className="mt-3 text-sm text-red-300 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</p>
      )}

      {result && (
        <div className="mt-5 space-y-3">
          <Stage n="1" title="INPUT FEATURES" />
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {Object.entries(result.model_features).map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-white/5 py-0.5">
                <span className="text-slate-400">{FEATURE_LABELS[k] ?? k}</span>
                <span className="text-slate-200 font-medium">{v}</span>
              </div>
            ))}
          </div>

          <div className="text-center text-slate-500 text-xs py-1">↓ feature engineering · {Object.keys(features).length} features ↓</div>

          <Stage n="2" title="RANDOM FOREST REGRESSOR" />
          <div className="text-xs text-slate-400 text-center">
            {result.model_used === 'random_forest'
              ? `TravelGuard ML v${result.model_version} · trained on synthetic demonstration data`
              : 'ML artifact not loaded — rule-based fallback active'}
          </div>

          <div className="text-center text-slate-500 text-xs py-1">↓ prediction ↓</div>

          <Stage n="3" title="RISK SCORE" />
          <div className="flex items-center justify-center gap-3 py-1">
            <span className="text-3xl font-display font-bold text-cyan-300">{result.risk_score.toFixed(1)}</span>
            <span className="rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-bold text-cyan-300">
              {result.risk_level}
            </span>
          </div>

          <Stage n="4" title="EXPLANATION" />
          {result.feature_importance.length > 0 ? (
            <>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">Model feature importance (top 5)</div>
              <div className="space-y-1.5">
                {result.feature_importance.map((f) => (
                  <div key={f.feature} className="flex items-center gap-2 text-xs">
                    <span className="w-52 shrink-0 text-slate-400">{FEATURE_LABELS[f.feature] ?? f.feature}</span>
                    <div className="flex-1 h-1.5 rounded bg-white/5 overflow-hidden">
                      <div
                        className="h-full rounded bg-gradient-to-r from-cyan-500/50 to-cyan-400"
                        style={{ width: `${Math.min(f.importance * 100 * 2.5, 100)}%` }}
                      />
                    </div>
                    <span className="w-10 text-right text-slate-300">{f.importance.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="text-[10px] uppercase tracking-widest text-slate-500">Contextual risk factors</div>
          )}
          <ul className="space-y-1">
            {result.factors.slice(0, 4).map((f) => (
              <li key={f.label} className="text-xs text-slate-300">
                <span className="text-amber-300 mr-1.5">▲</span>
                {f.label} <span className="text-slate-500">— {f.detail}</span>
              </li>
            ))}
          </ul>

          <p className="text-[11px] text-slate-500 leading-relaxed border-t border-white/5 pt-3">
            This score is a contextual travel-risk indicator, not a probability of an accident.
          </p>
        </div>
      )}
    </Panel>
  )
}

function Stage({ n, title }: { n: string; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-5 h-5 rounded-md bg-cyan-400/10 border border-cyan-400/20 text-cyan-300 text-[10px] font-bold flex items-center justify-center">
        {n}
      </span>
      <span className="text-[10px] uppercase tracking-widest text-slate-400">{title}</span>
      <div className="flex-1 h-px bg-white/5" />
    </div>
  )
}
