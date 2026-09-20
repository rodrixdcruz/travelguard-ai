import Panel from '../components/Panel'
import IntelligencePanel from '../components/IntelligencePanel'
import MLPipelineDemo from '../components/MLPipelineDemo'
import PlacesPanel from '../components/PlacesPanel'
import { useJourney } from '../context/JourneyContext'
import { useTouristLocation } from '../context/LocationContext'
import { scoreColor } from '../utils/format'
import { useEffect, useMemo, useState } from 'react'
import { chat, chatDiscovery, mlInfo } from '../services/api'
import type { RiskLevel, MlInfo } from '../types'

export function Alerts() {
  const { analysis } = useJourney()
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-slate-100 mb-1">Alerts</h1>
      <p className="text-sm text-slate-400 mb-6">Risk alerts from your latest analysis.</p>
      {analysis ? (
        <div className="space-y-3">
          {analysis.alerts.length === 0 && (
            <Panel><p className="text-sm text-slate-500">No alerts for the current journey. 👍</p></Panel>
          )}
          {analysis.alerts.map((a) => (
            <Panel key={a.id}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200 text-sm">{a.title}</span>
                <span className="text-xs font-bold px-2 py-1 rounded-lg border"
                  style={{ color: a.severity as RiskLevel ? scoreColorMap(a.severity) : '#999' }}>
                  {a.severity}
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-1">{a.detail}</p>
            </Panel>
          ))}
        </div>
      ) : (
        <Panel><p className="text-sm text-slate-500">Analyze a journey first — alerts will appear here.</p></Panel>
      )}
    </div>
  )
}

function scoreColorMap(level: string): string {
  return { LOW: '#2dd4bf', MODERATE: '#fbbf24', HIGH: '#fb923c', CRITICAL: '#f87171' }[level] ?? '#999'
}

export function History() {
  const { history } = useJourney()
  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-slate-100 mb-1">History</h1>
      <p className="text-sm text-slate-400 mb-6">Journeys analyzed in this session.</p>
      <Panel>
        {history.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing yet. Analyses from this session are listed here.</p>
        ) : (
          <ul className="divide-y divide-white/5">
            {history.map((h) => (
              <li key={h.id} className="py-3 flex items-center justify-between">
                <div>
                  <div className="text-sm text-slate-200 font-medium">{h.origin} → {h.destination}</div>
                  <div className="text-xs text-slate-500">{h.date} · {h.time}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold" style={{ color: scoreColor(h.score) }}>{h.level}</div>
                  <div className="text-xs text-slate-500">{Math.round(h.score)}/100</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  )
}

export function AiAssistant() {
  const { analysis } = useJourney()
  const { location } = useTouristLocation()
  const [messages, setMessages] = useState<{ role: 'you' | 'guard'; text: string; source?: string }[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  // Latest generated day plan — the assistant answers from this real data.
  const discovery: Record<string, unknown> | null = useMemo(() => {
    try {
      const raw = localStorage.getItem('tg_last_plan_v1')
      if (!raw) return null
      const plan = JSON.parse(raw) as import('../types/discovery').DayPlan
      return {
        places: [],
        itinerary: plan.itinerary,
        cost_breakdown: plan.cost_breakdown,
        safety: plan.safety,
        travelers: plan.cost_breakdown.travelers,
      }
    } catch {
      return null
    }
  }, [messages.length])

  async function send(q: string) {
    const question = q.trim()
    if (!question || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'you', text: question }])
    setBusy(true)
    try {
      const res = discovery
        ? await chatDiscovery(discovery, question)
        : await chat(analysis, question)
      setMessages((m) => [...m, { role: 'guard', text: res.answer, source: res.source }])
    } catch {
      setMessages((m) => [
        ...m,
        { role: 'guard', text: 'Travel data is temporarily unavailable — the backend may be offline. Please retry.' },
      ])
    } finally {
      setBusy(false)
    }
  }

  const suggestions = discovery
    ? [
        'What is the plan for the day?',
        'What can I do nearby for ₹1,000?',
        'Where do we go first?',
        'How safe is the area?',
        'Where can I eat?',
        'Why these places?',
      ]
    : [
        'Why is this route risky?',
        'What is the biggest risk?',
        'Which segment should I be careful about?',
        'What should I do?',
      ]

  return (
    <div className="max-w-3xl">
      <h1 className="font-display text-2xl font-bold text-slate-100 mb-1">AI Assistant</h1>
      <p className="text-sm text-slate-400 mb-2">
        {discovery
          ? `Asking about your latest day plan (${location.name}). Answers come only from that real data — never invented.`
          : 'Ask about your analyzed journey. Answers come from the calculated risk data — never invented.'}
      </p>
      {!discovery && (
        <p className="text-xs text-slate-500 mb-4">
          Tip: generate a day plan on <a href="/plan-day" className="text-cyan-400/90 hover:text-cyan-300">Plan My Day</a> and the
          assistant can answer questions about your itinerary, budget, food and safety.
        </p>
      )}
      <Panel className="min-h-[420px] flex flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto max-h-[420px] pr-1">
          {messages.length === 0 && (
            <div className="text-center py-10">
              <p className="text-sm text-slate-400">
                {analysis ? 'Try one of these:' : 'Analyze a journey first, then ask questions about it.'}
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => send(s)}
                    className="text-xs border border-white/10 rounded-full px-3.5 py-1.5 text-slate-300 hover:border-cyan-400/40 hover:text-cyan-300 transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'you' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                m.role === 'you'
                  ? 'bg-cyan-500/15 border border-cyan-400/20 text-cyan-100'
                  : 'bg-white/[0.04] border border-white/10 text-slate-300'
              }`}>
                {m.text}
                {m.source && (
                  <div className="mt-1.5 text-[10px] uppercase tracking-widest text-slate-500">
                    {m.source === 'ai' ? 'AI generated' : 'Deterministic engine'}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && <div className="text-xs text-slate-500 animate-pulse">TravelGuard is thinking…</div>}
        </div>
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => { e.preventDefault(); send(input) }}
        >
          <input
            className="field flex-1" placeholder="Ask about risks, segments, actions…"
            value={input} onChange={(e) => setInput(e.target.value)}
          />
          <button className="btn-primary !w-auto px-5" disabled={busy || !input.trim()}>Send</button>
        </form>
      </Panel>
    </div>
  )
}

/** Data Mode setting — Live (default) vs Demo, persisted in LocationContext. */
function DataModePanel() {
  const { mode, setMode } = useTouristLocation()
  return (
    <Panel title="Data Mode">
      <div className="space-y-2">
        <label className="flex items-start gap-2.5 cursor-pointer">
          <input
            type="radio"
            name="data-mode"
            checked={mode === 'live'}
            onChange={() => setMode('live')}
            className="mt-1 accent-emerald-400"
          />
          <span>
            <span className="text-sm font-semibold text-emerald-300">Live</span>{' '}
            <span className="text-xs text-slate-500 block">
              Default. Your actual location (browser GPS) or a place you select;
              real OpenStreetMap places/food/services and Open-Meteo weather when
              reachable. Anything that falls back stays clearly labeled.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2.5 cursor-pointer">
          <input
            type="radio"
            name="data-mode"
            checked={mode === 'demo'}
            onChange={() => setMode('demo')}
            className="mt-1 accent-sky-400"
          />
          <span>
            <span className="text-sm font-semibold text-sky-300">Demo</span>{' '}
            <span className="text-xs text-slate-500 block">
              Explore the labeled Mumbai demonstration dataset. For testing only —
              every item is shown with a DEMO badge.
            </span>
          </span>
        </label>
      </div>
    </Panel>
  )
}

function SystemStatusPanel() {
  const [info, setInfo] = useState<MlInfo | null>(null)
  useEffect(() => {
    let alive = true
    mlInfo().then((i) => alive && setInfo(i)).catch(() => {})
    return () => {
      alive = false
    }
  }, [])

  const rows: { name: string; status: string; badge: string; kind: 'active' | 'estimated' }[] = [
    { name: 'ML Safety Model', status: info ? `ACTIVE — ${info.safety_model.model_used} v${info.safety_model.model_version}` : 'ACTIVE', badge: 'ACTIVE', kind: 'active' },
    { name: 'Recommendation Model', status: info ? `ACTIVE — ${info.recommendation_model.model_used} v${info.recommendation_model.model_version}` : 'ACTIVE', badge: 'ACTIVE', kind: 'active' },
    { name: 'Places / Food / Services', status: 'LIVE — OpenStreetMap Overpass (key-less) · DEMO fallback labeled', badge: 'ACTIVE', kind: 'active' },
    { name: 'Weather (discovery + routes)', status: 'LIVE — Open-Meteo (key-less) · visibility ESTIMATED · DEMO fallback labeled', badge: 'ACTIVE', kind: 'active' },
    { name: 'Transport / Tickets / Meals', status: 'ESTIMATED — modeled rates, not live fares', badge: 'ESTIMATED', kind: 'estimated' },
    { name: 'Risk Engine (route rules)', status: 'ACTIVE — cross-check & fallback', badge: 'ACTIVE', kind: 'active' },
    { name: 'SOS', status: 'ACTIVE — verified ERSS 112', badge: 'ACTIVE', kind: 'active' },
  ]
  return (
    <Panel title="System status">
      <ul>
        {rows.map((r) => (
          <li key={r.name} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
            <div>
              <div className="text-sm text-slate-200 font-medium">{r.name}</div>
              <div className="text-[11px] text-slate-500">{r.status}</div>
            </div>
            <span
              className={`inline-flex items-center gap-1.5 text-[10px] uppercase tracking-widest ${
                r.kind === 'active' ? 'text-emerald-300' : 'text-sky-300'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${r.kind === 'active' ? 'bg-emerald-400' : 'bg-sky-400'}`} />
              {r.badge}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}

export function Settings() {
  return (
    <div className="max-w-3xl">
      <h1 className="font-display text-2xl font-bold text-slate-100 mb-1">Settings & Intelligence</h1>
      <p className="text-sm text-slate-400 mb-6">
        System status, the live ML pipeline demo, and the recommendation playground.
      </p>
      <div className="space-y-6">
        <DataModePanel />
        <SystemStatusPanel />
        <IntelligencePanel />
        <MLPipelineDemo />
        <PlacesPanel />
        <Panel title="Application">
          <ul className="text-sm text-slate-400 space-y-2 list-disc list-inside">
            <li>Default route preferences (avoid tolls, prefer highways) — coming in a later milestone</li>
            <li>Notification thresholds for risk levels</li>
            <li>Provider keys are configured on the backend via environment variables only</li>
          </ul>
        </Panel>
      </div>
    </div>
  )
}
