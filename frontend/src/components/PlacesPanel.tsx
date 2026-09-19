import { useState } from 'react'
import { apiConfig } from '../services/api'
import { DEMO_PLACES, INTEREST_OPTIONS } from '../services/places'
import Panel from './Panel'

interface RankedPlace {
  place_id: string
  name: string
  category: string
  distance_km: number
  estimated_cost: number
  recommendation_score: number
  reasons: string[]
  ranking_model: string
}

interface ItineraryStop {
  place_id: string
  name: string
  visit_duration_hours: number
  estimated_cost: number
  recommendation_score: number | null
}

interface ItineraryResponse {
  ranking_model: string
  model_version: string
  ranked_places: RankedPlace[]
  itinerary: {
    stops: ItineraryStop[]
    skipped: { name: string; why: string }[]
    summary: { total_stops: number; used_hours: number; available_hours: number; interest_matches: number; avg_safety: number }
    cost_breakdown: {
      tickets: number
      food_estimate: number
      transport_estimate: number
      transport_km: number
      total_estimate: number
      budget: number
      within_budget: boolean
    }
    optimizer: string
  }
}

export default function PlacesPanel() {
  const [interests, setInterests] = useState<string[]>(['history'])
  const [budget, setBudget] = useState(2000)
  const [hours, setHours] = useState(6)
  const [result, setResult] = useState<ItineraryResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleInterest(tag: string) {
    setInterests((cur) => (cur.includes(tag) ? cur.filter((t) => t !== tag) : [...cur, tag]))
  }

  async function run() {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`${apiConfig.API_BASE}/api/ml/itinerary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_preferences: { interests, budget, available_hours: hours },
          places: DEMO_PLACES,
        }),
      })
      if (!res.ok) throw new Error(`API error ${res.status}`)
      setResult((await res.json()) as ItineraryResponse)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const cb = result?.itinerary.cost_breakdown

  return (
    <Panel title="Recommended for you">
      <p className="text-[11px] text-slate-500 -mt-2 mb-4">
        Demo place catalog (synthetic) ranked by the ML recommendation engine for your context.
      </p>

      <div className="space-y-4">
        <div>
          <div className="label">Interests</div>
          <div className="flex flex-wrap gap-1.5">
            {INTEREST_OPTIONS.map((tag) => (
              <button
                key={tag}
                onClick={() => toggleInterest(tag)}
                className={`text-xs rounded-full px-3 py-1.5 border transition-colors ${
                  interests.includes(tag)
                    ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                    : 'border-white/10 text-slate-400 hover:text-slate-200'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="label">Budget (₹)</div>
            <input type="number" className="field" value={budget} min={0} step={100}
              onChange={(e) => setBudget(Number(e.target.value) || 0)} />
          </div>
          <div>
            <div className="label">Time available (h)</div>
            <input type="number" className="field" value={hours} min={1} max={14} step={0.5}
              onChange={(e) => setHours(Number(e.target.value) || 1)} />
          </div>
        </div>

        <button onClick={run} disabled={busy || interests.length === 0} className="btn-primary">
          {busy ? 'Ranking…' : '✦ Get recommendations'}
        </button>

        {error && (
          <p className="text-sm text-red-300 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</p>
        )}
      </div>

      {result && (
        <div className="mt-5 space-y-4">
          <div className="text-[10px] uppercase tracking-widest text-slate-500">
            Ranking model: {result.ranking_model} · v{result.model_version}
          </div>

          <ul className="space-y-2.5">
            {result.ranked_places.slice(0, 5).map((p) => (
              <li key={p.place_id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-200">
                    {p.name} <span className="text-[10px] uppercase tracking-wider text-slate-500">· {p.category}</span>
                  </div>
                  <div className="text-sm font-bold text-cyan-300">{Math.round(p.recommendation_score)}%</div>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-slate-400">
                  {p.reasons.map((r) => (
                    <span key={r}>✓ {r}</span>
                  ))}
                </div>
              </li>
            ))}
          </ul>

          {cb && (
            <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3.5 text-sm">
              <div className="font-semibold text-cyan-200 mb-2">
                Plan: {result.itinerary.summary.total_stops} stops · {result.itinerary.summary.used_hours}h of {result.itinerary.summary.available_hours}h
              </div>
              <ol className="space-y-1 text-xs text-slate-300 list-decimal list-inside">
                {result.itinerary.stops.map((s) => (
                  <li key={s.place_id}>
                    {s.name} <span className="text-slate-500">({s.visit_duration_hours}h · ₹{s.estimated_cost})</span>
                  </li>
                ))}
              </ol>
              <div className="mt-2.5 grid grid-cols-2 gap-1 text-xs text-slate-300">
                <span>Tickets: ₹{cb.tickets}</span>
                <span>Food: ~₹{cb.food_estimate}</span>
                <span>Transport: ~₹{cb.transport_estimate} ({cb.transport_km} km)</span>
                <span className={cb.within_budget ? 'text-emerald-300' : 'text-red-300'}>
                  Total: ₹{cb.total_estimate} {cb.within_budget ? '· within budget' : '· over budget'}
                </span>
              </div>
              {result.itinerary.skipped.length > 0 && (
                <div className="mt-2 text-[11px] text-slate-500">
                  Skipped: {result.itinerary.skipped.map((s) => `${s.name} (${s.why.toLowerCase()})`).join('; ')}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}
