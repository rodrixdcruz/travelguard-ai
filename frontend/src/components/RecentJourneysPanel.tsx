import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Panel from './Panel'
import { analyzeJourney, fetchBriefing, fetchRecentJourneys, type RecentJourney } from '../services/api'
import { useJourney } from '../context/JourneyContext'
import { LOADING_STEPS } from './JourneyForm'

const LEVEL_COLOR: Record<string, string> = {
  LOW: '#2dd4bf',
  MODERATE: '#fbbf24',
  HIGH: '#fb923c',
  CRITICAL: '#f87171',
}

function relTime(iso: string | null): string {
  if (!iso) return ''
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

/**
 * RecentJourneysPanel — the last analyzed journeys from the backend
 * (GET /api/journeys/recent, backed by PostgreSQL). "Re-run" loads a stored
 * journey back into the analysis view: it re-analyzes live (fresh weather,
 * current ML inputs) rather than replaying stale numbers.
 */
export default function RecentJourneysPanel() {
  const [journeys, setJourneys] = useState<RecentJourney[] | null>(null)
  const [dbOn, setDbOn] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const { setAnalysis, setBriefing, setLoading, setError: setJourneyError } = useJourney()
  const navigate = useNavigate()

  const load = useCallback(() => {
    let alive = true
    setJourneys(null)
    setError(null)
    fetchRecentJourneys(8)
      .then((res) => {
        if (!alive) return
        setJourneys(res.journeys)
        setDbOn(res.database)
      })
      .catch(() => {
        if (alive) setError('Recent journeys unavailable right now.')
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => load(), [load])

  async function rerun(j: RecentJourney) {
    setBusyId(j.id)
    setJourneyError(null)
    setLoading(true, 0)

    let step = 0
    const advance = setInterval(() => {
      step = Math.min(step + 1, LOADING_STEPS.length - 1)
      setLoading(true, step)
    }, 420)

    try {
      // Re-analyze LIVE: fresh weather, current risk inputs — not a stale replay.
      const result = await analyzeJourney({
        origin: j.origin.name,
        destination: j.destination.name,
        date: j.date,
        time: j.time,
      })
      setAnalysis(result)
      try {
        const b = await fetchBriefing(result)
        setBriefing(b.briefing, b.source)
      } catch {
        setBriefing('Briefing unavailable — see segment details below.', 'fallback')
      }
      clearInterval(advance)
      setLoading(false, 0)
      navigate('/plan')
    } catch {
      clearInterval(advance)
      setLoading(false, 0)
      setJourneyError('Re-analysis failed — check the API connection and try again.')
    } finally {
      setBusyId(null)
    }
  }

  if (error) {
    return (
      <Panel title="Recent journeys">
        <p className="text-xs text-slate-500">{error}</p>
      </Panel>
    )
  }

  return (
    <Panel title="Recent journeys">
      {!dbOn && journeys !== null && (
        <p className="text-[11px] text-slate-500 mb-2">
          Persistence is off on this deployment — analyses aren't stored.
        </p>
      )}
      {journeys === null ? (
        <p className="text-sm text-slate-500 animate-pulse">Loading…</p>
      ) : journeys.length === 0 ? (
        <p className="text-xs text-slate-500">No journeys yet — analyze one above and it will appear here.</p>
      ) : (
        <ul className="space-y-2">
          {journeys.map((j) => (
            <li key={j.id} className="glass glass-hover rounded-xl px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-sm text-slate-200 truncate">
                    <span className="font-medium">{j.origin.name}</span>
                    <span className="text-slate-500"> → </span>
                    <span className="font-medium">{j.destination.name}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {j.date} · {j.time} · {j.distance_km.toFixed(0)} km
                    {j.created_at ? ` · ${relTime(j.created_at)}` : ''}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {j.risk_level && (
                    <span
                      className="text-[10px] font-bold tracking-widest px-1.5 py-0.5 rounded border"
                      style={{
                        color: LEVEL_COLOR[j.risk_level] ?? '#94a3b8',
                        borderColor: `${LEVEL_COLOR[j.risk_level] ?? '#94a3b8'}55`,
                      }}
                    >
                      {j.risk_level}
                    </span>
                  )}
                  <button
                    onClick={() => rerun(j)}
                    disabled={busyId !== null}
                    className="text-[11px] font-semibold text-cyan-300 hover:text-cyan-200 disabled:opacity-50"
                    title="Re-analyze this route with current live data"
                  >
                    {busyId === j.id ? '…' : 'Re-run'}
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
