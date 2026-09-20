import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Panel from '../components/Panel'
import RiskMap from '../map/RiskMap'
import { DataBadge, OpeningChip } from '../components/DataStatusBadge'
import { fetchNearbyPlaces, fetchNearbyServices, fetchLocalSafety } from '../services/discovery'
import { browserLocation } from '../services/discovery'
import LocationSearch from '../components/LocationSearch'
import { mlInfo } from '../services/api'
import { DEMO_LOCATIONS, type Place } from '../types/discovery'
import { useTouristLocation } from '../context/LocationContext'
import { markersFromDiscovery, type MapMarker } from '../utils/markers'
import type { LocalService } from '../types/discovery'
import type { LocalSafety } from '../types/discovery'
import type { MlInfo } from '../types'

const WANT_TO_DO = [
  { key: 'History', icon: '🏛' },
  { key: 'Food', icon: '🍽' },
  { key: 'Nature', icon: '🌿' },
  { key: 'Shopping', icon: '🛍' },
  { key: 'Culture', icon: '🎭' },
  { key: 'Photography', icon: '📷' },
  { key: 'Family', icon: '👨‍👩‍👧' },
  { key: 'Entertainment', icon: '🎪' },
]

export default function Dashboard() {
  const { location, setLocation, setSosOpen, needsLocation } = useTouristLocation()
  const [places, setPlaces] = useState<Place[] | null>(null)
  const [services, setServices] = useState<LocalService[] | null>(null)
  const [safety, setSafety] = useState<LocalSafety | null>(null)
  const [locating, setLocating] = useState(false)
  const [locMsg, setLocMsg] = useState<string | null>(null)
  const [ml, setMl] = useState<MlInfo | null>(null)

  useEffect(() => {
    let alive = true
    mlInfo().then((i) => alive && setMl(i)).catch(() => {}) // strip is optional decoration
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    // Live mode with no location yet: show the explicit "set your location"
    // state instead of fetching demo data for a coordinate the user never
    // chose (never silently Mumbai).
    if (needsLocation) {
      setPlaces([])
      setServices([])
      setSafety(null)
      return
    }
    let alive = true
    setPlaces(null)
    setServices(null)
    Promise.all([
      fetchNearbyPlaces({ latitude: location.latitude, longitude: location.longitude, radius_km: 8, limit: 12 }),
      fetchNearbyServices({ latitude: location.latitude, longitude: location.longitude, radius_km: 8, limit: 15 }),
      fetchLocalSafety(location.latitude, location.longitude),
    ])
    .then(([p, s, sf]) => {
      if (!alive) return
      setPlaces(p.places)
      setServices(s.services)
      setSafety(sf)
    })
    .catch(() => {
      if (alive) setPlaces([])
    })
    return () => {
      alive = false
    }
  }, [location.latitude, location.longitude, needsLocation])

  const markers: MapMarker[] = useMemo(
    () => markersFromDiscovery(places ?? [], [], services ?? []),
    [places, services],
  )

  async function useMyLocation() {
    setLocating(true)
    setLocMsg(null)
    try {
      const loc = await browserLocation()
      setLocation(loc)
    } catch {
      setLocMsg('Location unavailable. Choose a place to continue.')
    } finally {
      setLocating(false)
    }
  }

  const topPlaces = (places ?? []).slice(0, 4)

  const locationLabel =
    location.source === 'browser'
      ? 'GPS — your actual position'
      : location.source === 'unset'
        ? 'Location not set — use GPS or pick a place below'
        : location.source === 'search'
          ? 'Selected location'
          : 'DEMO LOCATION — not your real position'

  return (
    <div>
      {/* ── Hero: tourist companion ── */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 text-[11px] uppercase tracking-[0.25em] text-cyan-300/80 border border-cyan-400/20 bg-cyan-400/5 rounded-full px-4 py-1.5 mb-5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
          Your intelligent local travel companion
        </div>
        <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight text-slate-100">
          TravelGuard <span className="bg-gradient-to-r from-cyan-300 to-blue-500 bg-clip-text text-transparent">AI</span>
        </h1>
        <p className="mt-3 text-slate-400 max-w-xl mx-auto">
          Explore smarter. Know the place. Travel with confidence.
        </p>

        {/* Where are you? */}
        <div className="mt-6 max-w-md mx-auto">
          <p className="text-xs uppercase tracking-widest text-slate-500 mb-2">Where are you?</p>
          <div className="space-y-2">
            <LocationSearch />
            <div className="flex gap-2">
              <button onClick={useMyLocation} disabled={locating} className="btn-primary flex-1 !py-2.5 !text-xs">
                {locating ? 'Locating…' : '📍 Use My Location'}
              </button>
              <select
                className="field !py-2.5 !text-xs flex-1"
                title="Labeled demo places (Demo Mode dataset)"
                value={DEMO_LOCATIONS.some((d) => d.name === location.name) ? location.name : ''}
                onChange={(e) => {
                  const found = DEMO_LOCATIONS.find((d) => d.name === e.target.value)
                  if (found) setLocation(found)
                }}
              >
                <option value="" disabled>Demo places…</option>
                {DEMO_LOCATIONS.map((d) => (
                  <option key={d.name} value={d.name}>{d.name}</option>
                ))}
              </select>
            </div>
          </div>
          {locMsg && (
            <p className="mt-2 text-[11px] text-amber-300 bg-amber-400/10 border border-amber-400/20 rounded-lg px-2.5 py-1.5">
              {locMsg}
            </p>
          )}
        </div>

        {/* TravelGuard Intelligence — compact, honest, expandable in Settings */}
        <div className="mt-6 inline-flex items-center gap-4 text-[11px] text-slate-400 border border-white/10 rounded-full px-4 py-1.5">
          <span className="font-semibold text-slate-300">TravelGuard Intelligence</span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Safety Model
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Recommendations
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> AI Assistant
          </span>
          <Link to="/settings" className="text-cyan-400/90 hover:text-cyan-300">details</Link>
        </div>

        {/* Primary actions */}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link to="/near-me" className="btn-primary !w-auto px-5 !py-2.5 !text-xs">Explore Near Me</Link>
          <Link to="/plan-day" className="btn-primary !w-auto px-5 !py-2.5 !text-xs">Plan My Day</Link>
          <Link to="/food" className="btn-primary !w-auto px-5 !py-2.5 !text-xs">Find Food</Link>
          <Link to="/safety" className="btn-primary !w-auto px-5 !py-2.5 !text-xs">Check Safety</Link>
          <button
            onClick={() => setSosOpen(true)}
            className="px-5 py-2.5 rounded-xl text-xs font-bold tracking-wide bg-red-500/15 border border-red-400/40 text-red-300 hover:bg-red-500/25 transition-colors"
          >
            🚨 SOS
          </button>
        </div>

        {/* What do you want to do? */}
        <p className="mt-8 mb-2 text-xs uppercase tracking-widest text-slate-500">What are you interested in?</p>
        <div className="flex flex-wrap justify-center gap-1.5 max-w-2xl mx-auto">
          {WANT_TO_DO.map((w) => (
            <Link
              key={w.key}
              to={`/plan-day?interest=${encodeURIComponent(w.key)}`}
              className="text-xs rounded-full border border-white/10 px-3 py-1.5 text-slate-300 hover:border-cyan-400/40 hover:text-cyan-300 transition-colors"
            >
              {w.icon} {w.key}
            </Link>
            ))}
        </div>
      </div>

      {/* ── Below hero: where you are + local safety ── */}
      <div className="grid lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2 space-y-6">
          <Panel title="Where you are">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-slate-100">{location.name}</div>
                <div className="text-xs text-slate-500">{locationLabel}</div>
              </div>
              <Link to="/near-me" className="text-xs text-cyan-300 hover:text-cyan-200">Explore nearby →</Link>
            </div>
          </Panel>

          <Panel title="Nearby">
            {needsLocation ? (
              <p className="text-sm text-amber-300 bg-amber-400/10 border border-amber-400/20 rounded-lg px-3 py-2">
                Set your location above (GPS or pick a place) to see what's nearby.
              </p>
            ) : places === null ? (
              <p className="text-sm text-slate-500 animate-pulse">Discovering nearby…</p>
            ) : (
              <ul className="grid sm:grid-cols-2 gap-3">
                {topPlaces.map((p) => (
                  <li key={p.id}>
                    <Link
                      to={`/near-me?focus=${p.id}`}
                      className="block glass glass-hover p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-slate-200 truncate">{p.name}</span>
                        <span className="text-xs text-cyan-300 shrink-0">{p.distance_km.toFixed(1)} km</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1.5">
                        <span className="capitalize">{p.category}</span> · <OpeningChip status={p.opening_status} />
                      </div>
                    </Link>
                  </li>
                ))}
                {topPlaces.length === 0 && <li className="text-sm text-slate-500">No nearby places in the current dataset.</li>}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Local safety">
            {needsLocation ? (
              <p className="text-sm text-slate-500">Location needed — set it above.</p>
            ) : safety ? (
              <div>
                <div className="flex items-end justify-between">
                  <div>
                    <div
                      className="text-3xl font-bold"
                      style={{ color: safety.risk_level === 'LOW' ? '#2dd4bf' : safety.risk_level === 'MODERATE' ? '#fbbf24' : '#fb923c' }}
                    >
                      {safety.risk_level}
                    </div>
                    <div className="text-xs text-slate-500">Contextual risk {safety.risk_score.toFixed(1)}/100</div>
                  </div>
                  <DataBadge status={safety.data_status} />
                </div>
                <p className="mt-2 text-[11px] text-slate-500">
                  Model: TravelGuard ML {safety.model_version} · {safety.disclaimer}
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-500 animate-pulse">Checking…</p>
            )}
          </Panel>

          <Panel title="Local services">
            {needsLocation ? (
              <p className="text-sm text-slate-500">Location needed — set it above.</p>
            ) : services === null ? (
              <p className="text-sm text-slate-500 animate-pulse">Loading…</p>
            ) : (
              <ul className="space-y-2">
                {services.slice(0, 5).map((s) => (
                  <li key={s.id} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 truncate">{s.name}</span>
                    <span className="text-slate-500 shrink-0 ml-2">{s.service_type.replace(/_/g, ' ')} · {s.distance_km.toFixed(1)} km</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  )
}
