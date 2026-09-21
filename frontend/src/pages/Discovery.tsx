import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Panel from '../components/Panel'
import RiskMap from '../map/RiskMap'
import { DataBadge, OpeningChip } from '../components/DataStatusBadge'
import { fetchLocalSafety, fetchNearbyFood, fetchNearbyServices, planDay } from '../services/discovery'
import { useTouristLocation } from '../context/LocationContext'
import { DEMO_LOCATIONS, type DayPlan, type LocalSafety, type PlanItem } from '../types/discovery'

/* ═════════════════════════ AI DAY PLANNER ═════════════════════════ */

const INTERESTS = ['History', 'Food', 'Nature', 'Shopping', 'Culture', 'Photography', 'Family', 'Entertainment']
const DURATIONS = [
  { value: '2h', label: '2 hours' },
  { value: '4h', label: '4 hours' },
  { value: 'half_day', label: '5 hours' },
  { value: 'full_day', label: '8 hours' },
  { value: '6', label: '6 hours' },
]
const BUDGETS = [
  { value: 'budget', label: 'Budget (₹800)' },
  { value: 'moderate', label: 'Moderate (₹2,000)' },
  { value: 'premium', label: 'Premium (₹5,000)' },
]
const TRAVELERS = [
  { value: '1', label: '1 traveler' },
  { value: '2', label: '2 travelers' },
  { value: 'family', label: 'Family' },
  { value: 'group', label: 'Group' },
]

type ChipProps = { active: boolean; onClick: () => void; children: React.ReactNode }
function Chip({ active, onClick, children }: ChipProps) {
  return (
    <button
      onClick={onClick}
      className={`text-xs rounded-full border px-3 py-1.5 transition-colors ${
        active
          ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
          : 'border-white/10 text-slate-400 hover:border-cyan-400/30 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}

function StepLabel({ n, title }: { n: number; title: string }) {
  return (
    <p className="text-[10px] font-bold tracking-widest text-slate-500 mt-4 mb-2 first:mt-0">
      <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-cyan-400/15 text-cyan-300 mr-1.5 text-[9px]">
        {n}
      </span>
      {title}
    </p>
  )
}

function ItemGlyph({ type }: { type: PlanItem['type'] }) {
  const g = type === 'travel' ? '🚕' : type === 'meal' ? '🍽' : '🏛'
  return (
    <div
      className={`w-9 h-9 shrink-0 rounded-full flex items-center justify-center text-base border ${
        type === 'travel'
          ? 'border-white/10 bg-white/5'
          : type === 'meal'
            ? 'border-amber-400/30 bg-amber-400/10'
            : 'border-cyan-400/30 bg-cyan-400/10'
      }`}
    >
      {g}
    </div>
  )
}

function ItineraryItem({ item }: { item: PlanItem }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = item.type === 'attraction'
  return (
    <li className="flex gap-3">
      <div className="flex flex-col items-center">
        <span className="font-mono text-xs text-cyan-300/90">{item.time}</span>
        <div className="mt-1 mb-1 w-px flex-1 bg-white/10" />
      </div>
      <div className="pb-5 flex-1 min-w-0">
        <ItemGlyph type={item.type} />
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <span className={`text-sm font-medium ${item.type === 'attraction' ? 'text-slate-100' : 'text-slate-300'}`}>
            {item.name}
          </span>
          {item.type === 'attraction' && item.category && (
            <span className="text-[10px] uppercase tracking-wider text-slate-500 border border-white/10 rounded px-1.5 py-0.5">
              {item.category}
            </span>
          )}
          <DataBadge status={item.data_status} />
          {item.safety && (
            <span
              className={`text-[9px] font-bold tracking-widest rounded px-1.5 py-0.5 border ${
                item.safety === 'LOW'
                  ? 'text-emerald-300 border-emerald-400/30'
                  : item.safety === 'MODERATE'
                    ? 'text-amber-300 border-amber-400/30'
                    : 'text-red-300 border-red-400/30'
              }`}
            >
              Safety: {item.safety}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{item.detail}</p>
        <p className="text-[11px] text-slate-400 mt-1">
          {item.duration_min} min
          {item.type === 'attraction' && item.travel_time_min != null && (
            <> · travel {item.travel_time_min} min</>
          )}
          {' '}· ₹{item.cost_inr.toLocaleString('en-IN')}
          {item.type === 'attraction' && item.ticket_required != null && (
            <> · Ticket: {item.ticket_required ? 'Required' : item.ticket_required === false ? 'No' : 'Unknown'}</>
          )}
        </p>
        {hasDetails && (item.reasons?.length || item.recommendation_score != null) && (
          <>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="mt-1.5 text-[11px] text-cyan-400/90 hover:text-cyan-300"
            >
              {expanded ? '▾ Hide why' : '▸ Why this place?'}
            </button>
            {expanded && (
              <div className="mt-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                {item.recommendation_score != null && (
                  <p className="text-[11px] text-slate-400 mb-1">
                    Recommendation score: <span className="text-cyan-300 font-semibold">{item.recommendation_score}/100</span>
                    <span className="text-slate-600"> · model feature-derived</span>
                  </p>
                )}
                <ul className="space-y-0.5">
                  {(item.reasons ?? []).map((r) => (
                    <li key={r} className="text-[11px] text-slate-300">✓ {r}</li>
                  ))}
                  {!item.reasons?.length && (
                    <li className="text-[11px] text-slate-500">Ranked by the recommendation model for your context.</li>
                  )}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </li>
  )
}

export function DayPlanner() {
  const { location, setLocation, needsLocation, mode } = useTouristLocation()
  const [params, setParams] = useSearchParams()
  const interestParam = params.get('interest')
  const [interests, setInterests] = useState<string[]>(
    interestParam ? [interestParam] : ['History', 'Food'],
  )
  const [duration, setDuration] = useState('half_day')
  const [budget, setBudget] = useState('moderate')
  const [travelers, setTravelers] = useState('2')
  const [startTime, setStartTime] = useState('09:00')
  const [plan, setPlan] = useState<DayPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function generate() {
    if (needsLocation) {
      setError('Set your location first — use GPS or pick a place.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await planDay({
        latitude: location.latitude,
        longitude: location.longitude,
        location_name: location.name,
        duration,
        budget,
        interests,
        travelers,
        start_time: startTime,
      })
      setPlan(result)
      // Persist for the AI Assistant's discovery context (real app data, never invented).
      try {
        localStorage.setItem('tg_last_plan_v1', JSON.stringify(result))
      } catch {
        /* storage unavailable — assistant just won't have plan context */
      }
      requestAnimationFrame(() => {
        document.getElementById('plan-summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Planning failed — is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  // Route polyline through the tourist's location + attraction stops (in visit order).
  const itineraryPath = useMemo(() => {
    if (!plan) return []
    const pts: { lat: number; lon: number; name: string }[] = [
      { lat: plan.location.latitude, lon: plan.location.longitude, name: 'Start' },
    ]
    for (const item of plan.itinerary.items) {
      if (item.type === 'attraction' && item.latitude != null && item.longitude != null) {
        pts.push({ lat: item.latitude, lon: item.longitude, name: item.name })
      }
    }
    return pts
  }, [plan])

  const segments = useMemo(
    () =>
      itineraryPath.slice(0, -1).map((p, i) => ({
        id: 9000 + i,
        name: `${p.name} → ${itineraryPath[i + 1].name}`,
        start: { lat: p.lat, lon: p.lon },
        end: { lat: itineraryPath[i + 1].lat, lon: itineraryPath[i + 1].lon },
        path: [p, itineraryPath[i + 1]].map((q) => ({ lat: q.lat, lon: q.lon })),
        distance_km: 0,
        duration_min: 0,
        score: 30,
        level: 'LOW' as const,
        factors: [],
        weather: {},
        road_condition: {},
        recommended_action: '',
      })),
    [itineraryPath],
  )

  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-slate-100">Plan My Day</h1>
      <p className="text-sm text-slate-400 mb-6">
        ML ranks what fits you; the optimizer builds a feasible schedule. Your location:{' '}
        <span className="text-slate-200">{location.name}</span>{' '}
        <span className="text-[9px] font-bold tracking-widest text-slate-500 border border-white/10 rounded px-1 py-0.5 align-middle">
          {location.source === 'browser' ? 'GPS' : location.source === 'demo' ? 'DEMO LOCATION' : location.source === 'unset' ? 'NOT SET' : 'SELECTED'}
        </span>
      </p>

      <div className="grid lg:grid-cols-3 gap-6 items-start">
        <Panel title="Your day">
          <StepLabel n={1} title="WHERE ARE YOU?" />
          <div className="text-xs text-slate-300 mb-1">{location.name}</div>
          {mode === 'demo' && (
            <select
              className="field !py-2 !text-xs"
              title="Labeled demo places (Demo Mode dataset)"
              value={DEMO_LOCATIONS.some((d) => d.name === location.name) ? location.name : ''}
              onChange={(e) => {
                const found = DEMO_LOCATIONS.find((d) => d.name === e.target.value)
                if (found) setLocation(found)
              }}
            >
              <option value="" disabled>Switch place…</option>
              {DEMO_LOCATIONS.map((d) => (
                <option key={d.name} value={d.name}>{d.name}</option>
              ))}
            </select>
          )}
          <p className="text-[10px] text-slate-600 mt-1">Change your location from the homepage or Near Me.</p>

          <StepLabel n={2} title="HOW MUCH TIME?" />
          <div className="flex flex-wrap gap-1.5">
            {DURATIONS.map((d) => (
              <Chip key={d.value} active={duration === d.value} onClick={() => setDuration(d.value)}>
                {d.label}
              </Chip>
            ))}
          </div>

          <StepLabel n={3} title="WHAT'S YOUR BUDGET?" />
          <div className="flex flex-wrap gap-1.5">
            {BUDGETS.map((b) => (
              <Chip key={b.value} active={budget === b.value} onClick={() => setBudget(b.value)}>
                {b.label}
              </Chip>
            ))}
          </div>

          <StepLabel n={4} title="WHAT DO YOU ENJOY?" />
          <div className="flex flex-wrap gap-1.5">
            {INTERESTS.map((i) => (
              <Chip
                key={i}
                active={interests.includes(i)}
                onClick={() => {
                  setInterests((cur) => (cur.includes(i) ? cur.filter((x) => x !== i) : [...cur, i]))
                  if (interestParam) setParams({}, { replace: true })
                }}
              >
                {i}
              </Chip>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 mt-4">
            <label className="block">
              <span className="text-[10px] font-bold tracking-widest text-slate-500">TRAVELERS</span>
              <select value={travelers} onChange={(e) => setTravelers(e.target.value)} className="field mt-1 !py-2 text-xs">
                {TRAVELERS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[10px] font-bold tracking-widest text-slate-500">START</span>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="field mt-1 !py-2 text-xs"
              />
            </label>
          </div>

          <button onClick={generate} disabled={loading} className="btn-primary w-full mt-5">
            {loading ? 'Planning…' : '✨ Plan My Day'}
          </button>
          {error && <p className="mt-3 text-xs text-red-300">{error}</p>}
        </Panel>

        <div className="lg:col-span-2 space-y-6">
          {plan && (
            <div id="plan-summary" className="grid grid-cols-3 gap-3">
              {[
                { label: 'YOUR DAY — PLACES', value: String(plan.itinerary.totals.places) },
                {
                  label: 'YOUR DAY — HOURS',
                  value: `${Math.floor(plan.itinerary.totals.total_time_min / 60)}h ${plan.itinerary.totals.total_time_min % 60}m`,
                },
                {
                  label: 'YOUR DAY — ESTIMATED',
                  value: `₹${plan.cost_breakdown.total_estimate.toLocaleString('en-IN')}`,
                },
              ].map((s) => (
                <div key={s.label} className="glass p-3.5 text-center">
                  <div className="text-[10px] font-bold tracking-widest text-slate-500">{s.label}</div>
                  <div className="text-xl font-bold text-slate-100 mt-1">{s.value}</div>
                </div>
              ))}
            </div>
          )}

          {plan && (
            <div className="grid md:grid-cols-2 gap-6">
              <Panel title="Timeline">
                <ul>
                  {plan.itinerary.items.map((item, i) => (
                    <ItineraryItem key={i} item={item} />
                  ))}
                </ul>
                <div className="mt-2 pt-3 border-t border-white/5 space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Within budget?</span>
                    <span className={plan.itinerary.totals.within_budget ? 'text-emerald-300' : 'text-amber-300'}>
                      {plan.itinerary.totals.within_budget ? 'Yes ✓' : 'Over budget'}
                    </span>
                  </div>
                  {plan.skipped.length > 0 && (
                    <p className="text-[11px] text-slate-500">
                      Skipped: {plan.skipped.map((s) => s.name).join(', ')} (time/budget)
                    </p>
                  )}
                </div>
              </Panel>

              <div className="space-y-6">
                <Panel title="Your route on the map">
                  <div className="h-[280px]">
                    <RiskMap segments={segments} heightClass="h-[280px] w-full" />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-2 flex items-center gap-1.5">
                    <DataBadge status="ESTIMATED" /> straight-line travel legs (no live routing yet)
                  </p>
                </Panel>

                <Panel title="Cost summary">
                  <p className="text-[10px] font-bold tracking-widest text-slate-500 mb-2">ESTIMATED TOTAL — NOT EXACT PRICING</p>
                  <ul className="space-y-1.5 text-sm">
                    {(
                      [
                        ['Attraction tickets', plan.cost_breakdown.tickets, plan.cost_breakdown.line_status['tickets']],
                        ['Food', plan.cost_breakdown.food_estimate, plan.cost_breakdown.line_status['food_estimate']],
                        ['Transport', plan.cost_breakdown.transport_estimate, plan.cost_breakdown.line_status['transport_estimate']],
                      ] as [string, number, string][]
                    ).map(([label, v, status]) => (
                      <li key={label} className="flex justify-between items-center">
                        <span className="text-slate-400">{label}</span>
                        <span className="text-slate-200 flex items-center gap-2">
                          ₹{v.toLocaleString('en-IN')} <DataBadge status={status as PlanItem['data_status']} />
                        </span>
                      </li>
                    ))}
                    <li className="flex justify-between items-center pt-2 border-t border-white/5">
                      <span className="text-slate-300 font-medium">Estimated total</span>
                      <span className="text-cyan-300 font-bold">₹{plan.cost_breakdown.total_estimate.toLocaleString('en-IN')}</span>
                    </li>
                    <li className="flex justify-between text-xs text-slate-500">
                      <span>Budget ({plan.cost_breakdown.travelers} travelers)</span>
                      <span>₹{plan.cost_breakdown.budget_total.toLocaleString('en-IN')}</span>
                    </li>
                  </ul>
                </Panel>

                <Panel title="Local safety context">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-2xl font-bold" style={{ color: plan.safety.risk_level === 'LOW' ? '#2dd4bf' : plan.safety.risk_level === 'MODERATE' ? '#fbbf24' : '#fb923c' }}>
                        {plan.safety.risk_level}
                      </div>
                      <div className="text-xs text-slate-500">Contextual risk {plan.safety.risk_score.toFixed(1)}/100</div>
                    </div>
                    <DataBadge status={plan.safety.data_status ?? 'DEMO'} />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-2">
                    Model: TravelGuard ML {plan.safety.model_version} · {plan.safety.disclaimer}
                  </p>
                </Panel>
              </div>
            </div>
          )}

          {loading && (
            <Panel className="min-h-[280px] flex items-center justify-center text-center">
              <p className="text-slate-400 text-sm animate-pulse">
                Ranking places with ML, then fitting them into a feasible day…
              </p>
            </Panel>
          )}

          {!plan && !loading && (
            <Panel className="min-h-[280px] flex items-center justify-center text-center">
              <div>
                <p className="text-slate-400 text-sm">Pick your time, budget and interests — then Plan My Day.</p>
                <p className="text-slate-500 text-xs mt-1">
                  The ML recommender ranks places; the optimizer fits them into a feasible schedule.
                </p>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}

/* ═════════════════════════ FOOD NEAR YOU ═════════════════════════ */

const FOOD_FILTERS = ['ALL', 'VEG', 'NON-VEG', 'LOCAL', 'STREET FOOD', 'CAFE', 'BUDGET'] as const
type FoodFilter = (typeof FOOD_FILTERS)[number]

export function FoodNearYou() {
  const { location, needsLocation } = useTouristLocation()
  const [food, setFood] = useState<import('../types/discovery').FoodPlace[] | null>(null)
  const [filter, setFilter] = useState<FoodFilter>('ALL')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    if (needsLocation) {
      setFood([])
      return
    }
    setFood(null)
    setError(null)
    fetchNearbyFood({ latitude: location.latitude, longitude: location.longitude, radius_km: 15, limit: 30 })
      .then((res) => {
        if (alive) setFood(res.food)
      })
      .catch(() => {
        if (alive) setError('Food data is temporarily unavailable. Choose a place to continue or retry shortly.')
      })
    return () => {
      alive = false
    }
  }, [location.latitude, location.longitude, needsLocation])

  const filtered = useMemo(() => {
    if (!food) return []
    switch (filter) {
      case 'VEG': return food.filter((f) => f.vegetarian)
      case 'NON-VEG': return food.filter((f) => f.non_vegetarian)
      case 'STREET FOOD': return food.filter((f) => f.cuisine.toLowerCase().includes('street'))
      case 'CAFE': return food.filter((f) => f.cuisine.toLowerCase().includes('cafe'))
      case 'BUDGET': return food.filter((f) => f.price_range === '₹' || f.price_range === '₹₹')
      default: return food
    }
  }, [food, filter])

  const markers = useMemo(
    () =>
      filtered.map((f) => ({
        id: f.id,
        name: f.name,
        kind: 'food' as const,
        category: f.cuisine,
        latitude: f.latitude,
        longitude: f.longitude,
        distance_km: f.distance_km,
        detail: `${f.cuisine} · ${f.price_range}${f.rating ? ` · ★${f.rating}` : ''}`,
        data_status: f.data_status,
      })),
    [filtered],
  )

  return (
    <div>
      <h1 className="font-display text-2xl font-bold text-slate-100">Food Near You</h1>
      <p className="text-sm text-slate-400 mb-6">
        Eateries around {location.name}{' '}
        <span className="text-[9px] font-bold tracking-widest text-slate-500 border border-white/10 rounded px-1 py-0.5 align-middle">
          {location.source === 'browser' ? 'GPS' : location.source === 'demo' ? 'DEMO LOCATION' : location.source === 'unset' ? 'NOT SET' : 'SELECTED'}
        </span>
      </p>

      <div className="flex flex-wrap gap-1.5 mb-5">
        {FOOD_FILTERS.map((f) => (
          <Chip key={f} active={filter === f} onClick={() => setFilter(f)}>{f}</Chip>
        ))}
      </div>

      {error && <Panel><p className="text-sm text-red-300">{error}</p></Panel>}

      {!error && food === null && <p className="text-sm text-slate-500 animate-pulse">Finding food nearby…</p>}

      {food !== null && (
        <div className="grid lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2 grid sm:grid-cols-2 gap-4">
            {filtered.map((f) => (
              <Panel key={f.id}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-slate-100">{f.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{f.cuisine}</div>
                  </div>
                  <OpeningChip status={f.opening_status} />
                </div>
                <div className="mt-3 flex items-center justify-between text-xs">
                  <span className="text-slate-400">
                    {f.price_range}
                    {f.rating ? ` · ★${f.rating}` : ''} · {f.distance_km.toFixed(1)} km
                  </span>
                  <div className="flex items-center gap-1.5">
                    {f.vegetarian && <span className="text-[9px] font-bold tracking-widest text-emerald-300 border border-emerald-400/30 rounded px-1.5 py-0.5">VEG</span>}
                    {f.non_vegetarian && !f.vegetarian && <span className="text-[9px] font-bold tracking-widest text-rose-300 border border-rose-400/30 rounded px-1.5 py-0.5">NON-VEG</span>}
                    <DataBadge status={f.data_status} />
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 mt-2">{f.address}</p>
                <a
                  href={`https://www.openstreetmap.org/?mlat=${f.latitude}&mlon=${f.longitude}#map=17/${f.latitude}/${f.longitude}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block mt-2 text-[11px] text-cyan-400/90 hover:text-cyan-300"
                >
                  View on map →
                </a>
              </Panel>
            ))}
            {filtered.length === 0 && (
              <Panel><p className="text-sm text-slate-500">No food places match this filter nearby.</p></Panel>
            )}
          </div>

          <div className="lg:col-span-1">
            <div className="sticky top-20 h-[420px]">
              <RiskMap markers={markers} fitToMarkers heightClass="h-[420px] w-full" />
            </div>
            <p className="text-[11px] text-slate-500 mt-2">Food shown as 🍽 markers on the map.</p>
          </div>
        </div>
      )}
    </div>
  )
}

/* ═════════════════════════ LOCAL SAFETY ═════════════════════════ */

export function LocalSafetyPage() {
  const { location, needsLocation } = useTouristLocation()
  const [safety, setSafety] = useState<LocalSafety | null>(null)
  const [services, setServices] = useState<import('../types/discovery').LocalService[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    if (needsLocation) {
      setSafety(null)
      setServices([])
      return
    }
    setSafety(null)
    setServices(null)
    setError(null)
    Promise.all([
      fetchLocalSafety(location.latitude, location.longitude),
      fetchNearbyServices({ latitude: location.latitude, longitude: location.longitude, radius_km: 6, limit: 50 }),
    ])
      .then(([s, svc]) => {
        if (!alive) return
        setSafety(s)
        setServices(svc.services)
      })
      .catch(() => {
        if (alive) setError('Travel data is temporarily unavailable. Choose a place to continue.')
      })
    return () => {
      alive = false
    }
  }, [location.latitude, location.longitude])

  const levelColor = (lvl: string) => (lvl === 'LOW' ? '#2dd4bf' : lvl === 'MODERATE' ? '#fbbf24' : '#fb923c')

  const helpRows = useMemo(() => {
    if (!services) return []
    const byType = (t: string) => services.find((s) => s.service_type === t)
    return [
      { label: '🏥 Hospital', svc: byType('hospital') },
      { label: '🛡 Police', svc: byType('police') },
      { label: '℞ Pharmacy', svc: byType('pharmacy') },
      { label: 'ℹ Tourist help', svc: byType('tourist_help') },
    ]
  }, [services])

  return (
    <div className="max-w-2xl">
      <h1 className="font-display text-2xl font-bold text-slate-100">Local Safety</h1>
      <p className="text-sm text-slate-400 mb-6">
        Contextual conditions where you are — {location.name}{' '}
        <span className="text-[9px] font-bold tracking-widest text-slate-500 border border-white/10 rounded px-1 py-0.5 align-middle">
          {location.source === 'browser' ? 'GPS' : location.source === 'demo' ? 'DEMO LOCATION' : location.source === 'unset' ? 'NOT SET' : 'SELECTED'}
        </span>
      </p>

      {error && <Panel><p className="text-sm text-red-300">{error}</p></Panel>}
      {!safety && !error && <p className="text-sm text-slate-500 animate-pulse">Checking local conditions…</p>}

      {safety && (
        <div className="space-y-6">
          <Panel>
            <p className="text-[10px] font-bold tracking-widest text-slate-500">CONTEXTUAL TRAVEL RISK</p>
            <div className="mt-2 flex items-end gap-3">
              <span className="text-4xl font-bold" style={{ color: levelColor(safety.risk_level) }}>{safety.risk_level}</span>
              <span className="text-sm text-slate-400 mb-1">{safety.risk_score.toFixed(1)} / 100</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span>Model: TravelGuard ML {safety.model_version}</span>
              <DataBadge status={safety.data_status} />
            </div>
            <p className="mt-3 text-[11px] text-slate-500 border border-white/10 bg-white/5 rounded-lg px-3 py-2">
              ℹ {safety.disclaimer}
            </p>
          </Panel>

          <Panel title="Current context">
            <p className="text-xs text-slate-400">
              Risk factors in this area: the score combines weather conditions, time of day, area
              activity, road context and emergency-service proximity. Open{' '}
              <a href="/settings" className="text-cyan-400/90 hover:text-cyan-300">Settings → ML Pipeline Demo</a>{' '}
              to see the exact feature values and model importances behind a score.
            </p>
            <p className="text-[11px] text-slate-500 mt-2">
              Higher contextual risk areas call for normal big-city precautions — shared below.
            </p>
          </Panel>

          <Panel title="Nearby help">
            <ul className="space-y-2">
              {helpRows.map((row) =>
                row.svc ? (
                  <li key={row.label} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2">
                    <div className="min-w-0">
                      <div className="text-sm text-slate-200">{row.label} — {row.svc.name}</div>
                      <div className="text-[11px] text-slate-500">{row.svc.address} · {row.svc.distance_km.toFixed(1)} km</div>
                    </div>
                    <DataBadge status={row.svc.data_status} />
                  </li>
                ) : (
                  <li key={row.label} className="rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-500">
                    {row.label}: unavailable in current data.
                  </li>
                ),
              )}
            </ul>
          </Panel>

          <Panel title="What to do">
            <ul className="space-y-1.5 text-sm text-slate-300">
              <li>• Keep valuables secure and stay aware in crowded areas.</li>
              <li>• Save the emergency number (112) in your phone before heading out.</li>
              <li>• Use licensed taxis or ride apps for longer hops after dark.</li>
              <li>• Share your itinerary with a trusted contact.</li>
            </ul>
            <p className="text-[10px] text-slate-600 mt-2">General precautions, not area-specific claims.</p>
          </Panel>
        </div>
      )}
    </div>
  )
}
