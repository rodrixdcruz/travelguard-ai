import { useEffect, useMemo, useRef, useState } from 'react'
import RiskMap from '../map/RiskMap'
import { DataBadge, OpeningChip } from './DataStatusBadge'
import Panel from './Panel'
import { ProviderSummaryLine, type ProviderSummary } from './ProviderSummaryLine'
import { browserLocation, fetchNearbyFood, fetchNearbyPlaces, fetchNearbyServices, fetchNearbyTransport } from '../services/discovery'
import LocationSearch from './LocationSearch'
import { DEMO_LOCATIONS, type FoodPlace, type LocalService, type Place, type TransportResponse } from '../types/discovery'
import { useTouristLocation } from '../context/LocationContext'
import {
  markersFromDiscovery,
  transportMarkers,
  FILTER_KINDS,
  KIND_META,
  TRANSPORT_GROUP_KINDS,
  type MapFilter,
  type MapMarker,
  type TransportGroup,
} from '../utils/markers'

const NEAR_ME_BUTTONS: { key: string; label: string; filter?: MapFilter; serviceType?: string }[] = [
  { key: 'attractions', label: '🏛 Attractions', filter: 'ATTRACTIONS' },
  { key: 'food', label: '🍽 Food', filter: 'FOOD' },
  { key: 'safety', label: '🆘 Safety', filter: 'SAFETY' },
  { key: 'hospitals', label: '✚ Hospitals', serviceType: 'hospital' },
  { key: 'police', label: '🛡 Police', serviceType: 'police' },
  { key: 'pharmacies', label: '℞ Pharmacies', serviceType: 'pharmacy' },
  { key: 'atms', label: '₹ ATMs', serviceType: 'atm' },
  { key: 'transport', label: '🚉 Transport', serviceType: 'transport' },
  { key: 'bus', label: '🚌 Bus stands', serviceType: 'bus_stand' },
  { key: 'railway', label: '🚆 Railway', serviceType: 'railway_station' },
  { key: 'metro', label: '🚇 Metro', serviceType: 'metro_station' },
  { key: 'taxis', label: '🚖 Taxi / Auto stands', serviceType: 'taxi' },
]

const FILTERS: MapFilter[] = ['ALL', 'ATTRACTIONS', 'FOOD', 'SAFETY', 'SERVICES', 'TRANSPORT']

const TRANSPORT_GROUP_LABELS: Record<TransportGroup, string> = {
  ALL: 'All Transport',
  BUS: 'Bus',
  METRO: 'Metro',
  RAILWAY: 'Railway',
  OTHER: 'Other Transit',
}

const TRANSPORT_RADII_KM = [2, 5, 10, 20]

export default function NearMe() {
  const { location, setLocation, needsLocation, mode } = useTouristLocation()
  const [places, setPlaces] = useState<Place[]>([])
  const [food, setFood] = useState<FoodPlace[]>([])
  const [services, setServices] = useState<LocalService[]>([])
  const [loading, setLoading] = useState(false)
  const [locError, setLocError] = useState<string | null>(null)
  const [filter, setFilter] = useState<MapFilter>('ALL')
  const [activeButton, setActiveButton] = useState<string>('attractions')
  const [selected, setSelected] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)
  const [statuses, setStatuses] = useState<{ places: string; food: string; services: string } | null>(null)
  const [summary, setSummary] = useState<ProviderSummary | null>(null)

  // ── Transport discovery state ──
  const [transport, setTransport] = useState<TransportResponse | null>(null)
  const [transportError, setTransportError] = useState<string | null>(null)
  const [transportLoading, setTransportLoading] = useState(false)
  const [transportRadius, setTransportRadius] = useState(5)
  const [transportMode, setTransportMode] = useState<TransportGroup>('ALL')
  const [useMapBounds, setUseMapBounds] = useState(false)
  const [mapBbox, setMapBbox] = useState<{ lat1: number; lon1: number; lat2: number; lon2: number } | null>(null)
  const transportAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    // Live mode, no location yet: nothing to discover (never silently Mumbai).
    if (needsLocation) {
      setPlaces([])
      setFood([])
      setServices([])
      setTransport(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setLocError(null)
    Promise.all([
      fetchNearbyPlaces({ latitude: location.latitude, longitude: location.longitude, radius_km: 12, limit: 30 }),
      fetchNearbyFood({ latitude: location.latitude, longitude: location.longitude, radius_km: 10, limit: 20 }),
      fetchNearbyServices({ latitude: location.latitude, longitude: location.longitude, radius_km: 10, limit: 25 }),
    ])
      .then(([p, f, s]) => {
        if (cancelled) return
        setPlaces(p.places)
        setFood(f.food)
        setServices(s.services)
        setStatuses({ places: p.data_status, food: f.data_status, services: s.data_status })
        // One merged provenance line across the three discovery responses.
        const all: string[] = [...p.provider_summary.sources, ...f.provider_summary.sources, ...s.provider_summary.sources]
        const anyLive = [p, f, s].some((r) => r.provider_summary.status === 'LIVE')
        const anyDemo = [p, f, s].some((r) => r.provider_summary.status === 'DEMO')
        setSummary({
          status: anyLive && anyDemo ? 'MIXED' : anyLive ? 'LIVE' : 'DEMO',
          sources: [...new Set(all)],
          line: `places ${p.provider_summary.status.toLowerCase()} · food ${f.provider_summary.status.toLowerCase()} · services ${s.provider_summary.status.toLowerCase()} — ` +
            [...new Set(all)].join(' + '),
        })
      })
      .catch((e) => !cancelled && setLocError(e instanceof Error ? e.message : 'Discovery failed'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [location.latitude, location.longitude, needsLocation])

  // ── Full transport discovery: independent per-category paginated queries on
  // the backend; fetched only while the Transport view is open, re-fetched when
  // the location, radius or search area changes. Stale requests are aborted so
  // a slow earlier area never overwrites a new one.
  useEffect(() => {
    if (needsLocation || activeButton !== 'transport') return
    const bbox = useMapBounds && mapBbox
      ? `${mapBbox.lat1},${mapBbox.lon1},${mapBbox.lat2},${mapBbox.lon2}`
      : undefined
    if (useMapBounds && !mapBbox) return // bounds not reported yet
    transportAbortRef.current?.abort()
    const controller = new AbortController()
    transportAbortRef.current = controller
    let cancelled = false
    setTransportLoading(true)
    setTransportError(null)
    fetchNearbyTransport({
      latitude: location.latitude,
      longitude: location.longitude,
      radius_km: transportRadius,
      bbox,
      signal: controller.signal,
    })
      .then((data) => {
        if (cancelled) return
        setTransport(data)
      })
      .catch((e) => {
        if (cancelled || controller.signal.aborted) return
        setTransportError(e instanceof Error ? e.message : 'Transport discovery failed')
      })
      .finally(() => {
        if (!cancelled) setTransportLoading(false)
      })
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [location.latitude, location.longitude, needsLocation, transportRadius, useMapBounds, mapBbox, activeButton])

  const allMarkers = useMemo(
    () => markersFromDiscovery(places, food, services),
    [places, food, services],
  )

  // Services rows that are transit (bus/metro/railway stops from the small
  // services lookup) are superseded by the dedicated, paginated transport
  // discovery — excluded here so no stop is ever double-listed or double-pinned.
  const TRANSIT_KINDS = ['transport', 'bus_stand', 'railway_station', 'metro_station', 'metro_entrance', 'tram']
  const transitMarkers = useMemo(
    () => transportMarkers(transport?.transport ?? []),
    [transport],
  )

  const mergedMarkers = useMemo(
    () => [...allMarkers.filter((m) => !TRANSIT_KINDS.includes(m.kind)), ...transitMarkers],
    [allMarkers, transitMarkers],
  )

  // Taxis are a services lookup, not part of transport-station discovery.
  const taxiMarkers = useMemo(
    () => allMarkers.filter((m) => m.kind === 'taxi'),
    [allMarkers],
  )

  const transportVisible = useMemo(() => {
    const allowed = TRANSPORT_GROUP_KINDS[transportMode]
    return transitMarkers.filter((m) => allowed.includes(m.kind))
  }, [transitMarkers, transportMode])

  const visibleMarkers = useMemo(() => {
    const allowed = FILTER_KINDS[filter]
    const filtered = mergedMarkers.filter((m) => allowed.includes(m.kind))
    if (activeButton === 'ALL' || !NEAR_ME_BUTTONS.some((b) => b.key === activeButton)) return filtered
    const btn = NEAR_ME_BUTTONS.find((b) => b.key === activeButton)
    if (btn?.serviceType === 'transport') {
      // Transport shows every transit kind from the dedicated discovery
      // (plus the taxi markers from the services lookup).
      const transitKinds = ['transport', 'bus_stand', 'railway_station', 'metro_station', 'metro_entrance', 'tram']
      return [...filtered.filter((m) => transitKinds.includes(m.kind)), ...taxiMarkers]
    }
    if (btn?.serviceType) {
      return filtered.filter((m) => m.kind === btn.serviceType)
    }
    return filtered
  }, [mergedMarkers, filter, activeButton, taxiMarkers])

  const selectedMarker: MapMarker | null =
    visibleMarkers.find((m) => m.id === selected) ?? null

  async function useMyLocation() {
    setLocating(true)
    setLocError(null)
    try {
      const loc = await browserLocation()
      setLocation(loc)
    } catch (e) {
      setLocError(
        (e instanceof Error ? e.message : 'Location unavailable') +
          ' — enter coordinates or pick a place below instead.',
      )
    } finally {
      setLocating(false)
    }
  }

  function pickButton(key: string) {
    setActiveButton(key)
    const btn = NEAR_ME_BUTTONS.find((b) => b.key === key)
    if (btn?.filter) setFilter(btn.filter)
    else if (btn?.serviceType) setFilter('ALL')
    else setFilter('ALL')
  }

  const transportActive = activeButton === 'transport'

  return (
    <div className="grid lg:grid-cols-3 gap-6 items-start">
      {/* ── Left: location + categories ── */}
      <div className="space-y-6">
        <Panel title="Where are you?">
          <div className="flex items-center justify-between gap-2 mb-3">
            <div className="text-sm text-slate-200">{location.name}</div>
            <span className="text-[9px] font-bold tracking-widest text-slate-500 border border-white/10 rounded px-1.5 py-0.5">
              {location.source === 'browser'
                ? 'GPS'
                : location.source === 'demo'
                  ? 'DEMO'
                  : location.source === 'search'
                    ? 'SELECTED'
                    : 'NOT SET'}
            </span>
          </div>
          <div className="space-y-2">
            <LocationSearch />
            <div className="grid grid-cols-2 gap-2">
              <button onClick={useMyLocation} disabled={locating} className="btn-primary !py-2.5 !text-xs col-span-2">
                {locating ? 'Locating…' : '📍 Use my location'}
              </button>
              {mode === 'demo' && (
                <select
                  className="field !py-2.5 !text-xs col-span-2"
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
              )}
            </div>
          </div>
          {locError && (
            <p className="mt-2 text-[11px] text-amber-300 bg-amber-400/10 border border-amber-400/20 rounded-lg px-2.5 py-1.5">
              {locError}
            </p>
          )}
          {needsLocation && (
            <p className="mt-2 text-[11px] text-amber-300 bg-amber-400/10 border border-amber-400/20 rounded-lg px-2.5 py-1.5">
              Location permission denied or not set — use “Use my location”, enter
              coordinates, or pick a place. Nothing is assumed.
            </p>
          )}
        </Panel>

        <Panel title="Near Me">
          <div className="grid grid-cols-2 gap-2">
            {NEAR_ME_BUTTONS.map((b) => (
              <button
                key={b.key}
                onClick={() => pickButton(b.key)}
                className={`text-xs rounded-xl border px-3 py-2.5 text-left transition-colors ${
                  activeButton === b.key
                    ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                    : 'border-white/10 text-slate-300 hover:border-cyan-400/30 hover:bg-white/5'
                }`}
              >
                {b.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => pickButton('ALL')}
            className={`mt-2 w-full text-xs rounded-xl border px-3 py-2 transition-colors ${
              activeButton === 'ALL'
                ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                : 'border-white/10 text-slate-400 hover:bg-white/5'
            }`}
          >
            Show everything nearby
          </button>
        </Panel>

        {/* Transport controls — visible while the Transport view is active */}
        {transportActive && (
          <Panel title="Transport search">
            <div className="space-y-3">
              <div>
                <div className="text-[10px] font-bold tracking-widest text-slate-500 mb-1.5">SEARCH AREA</div>
                {useMapBounds ? (
                  <div className="flex items-center justify-between gap-2 text-[11px] text-slate-400">
                    <span>Visible map area{mapBbox ? ' (detected)' : ' (move the map)'}</span>
                    <button
                      onClick={() => setUseMapBounds(false)}
                      className="text-cyan-300 hover:text-cyan-200 shrink-0"
                    >
                      Use radius
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5">
                    {TRANSPORT_RADII_KM.map((km) => (
                      <button
                        key={km}
                        onClick={() => setTransportRadius(km)}
                        className={`flex-1 text-[10px] font-bold rounded-lg border px-2 py-1.5 transition-colors ${
                          transportRadius === km
                            ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                            : 'border-white/10 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {km} km
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={() => setUseMapBounds((v) => !v)}
                className={`w-full text-[11px] rounded-xl border px-3 py-2 transition-colors ${
                  useMapBounds
                    ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                    : 'border-white/10 text-slate-400 hover:bg-white/5'
                }`}
              >
                {useMapBounds ? '✓ Searching the visible map area' : 'Search within the visible map area'}
              </button>
              {transport && transport.count === 0 && (
                <p className="text-[11px] text-amber-300 bg-amber-400/10 border border-amber-400/20 rounded-lg px-2.5 py-1.5">
                  No matching stations were found in the selected area — the live
                  provider may simply have none mapped here (e.g. no metro).
                </p>
              )}
              {transport && transport.failed_groups.length > 0 && (
                <p className="text-[11px] text-slate-500">
                  {transport.failed_groups.length} of 8 provider category queries
                  failed — other categories are still shown.
                </p>
              )}
              <p className="text-[10px] text-slate-600">
                Station locations from OpenStreetMap — not live vehicle tracking
                or arrival schedules.
              </p>
            </div>
          </Panel>
        )}

        {/* Selected marker detail card */}
        {selectedMarker && (
          <Panel title="Details">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-100">{selectedMarker.name}</div>
                <div className="text-xs text-slate-500 capitalize">
                  {KIND_META[selectedMarker.kind]?.label ?? selectedMarker.category} · {selectedMarker.category}
                </div>
              </div>
              <DataBadge status={selectedMarker.data_status} />
            </div>
            <div className="mt-3 space-y-1.5 text-xs text-slate-300">
              <div>📍 {selectedMarker.distance_km} km away</div>
              <div>ℹ {selectedMarker.detail}</div>
              {transportActive && transitMarkers.some((m) => m.id === selectedMarker.id) && (
                <div className="text-slate-400">
                  🌐 {selectedMarker.latitude.toFixed(5)}, {selectedMarker.longitude.toFixed(5)}
                </div>
              )}
              {selectedMarker.phone ? (
                <div>📞 {selectedMarker.phone}</div>
              ) : (
                <div className="text-slate-500">📞 Emergency number unavailable in current data.</div>
              )}
            </div>
            <button
              onClick={() => setSelected(null)}
              className="mt-3 text-xs text-slate-500 hover:text-slate-300"
            >
              ← Back to list
            </button>
          </Panel>
        )}
      </div>

      {/* ── Right: map + list ── */}
      <div className="lg:col-span-2 space-y-4">
        <div className="h-[420px] relative">
          <RiskMap
            markers={visibleMarkers}
            selectedMarkerId={selected}
            onSelectMarker={setSelected}
            fitToMarkers
            userLocation={
              needsLocation
                ? null
                : { latitude: location.latitude, longitude: location.longitude, name: location.name }
            }
            onBounds={useMapBounds ? (b) => {
              if (!b) return
              // Round the bbox onto a ~0.05° (~5 km) grid so ordinary panning
              // does not refetch on every render — only materially new areas do.
              const snap = (v: number) => Math.round(v * 20) / 20
              const next = { lat1: snap(b.lat1), lon1: snap(b.lon1), lat2: snap(b.lat2), lon2: snap(b.lon2) }
              setMapBbox((prev) => {
                const changed = !prev || prev.lat1 !== next.lat1 || prev.lon1 !== next.lon1
                  || prev.lat2 !== next.lat2 || prev.lon2 !== next.lon2
                return changed ? next : prev
              })
            } : undefined}
          />
        </div>

        {transportActive ? (
          <>
            <p className="text-[11px] text-slate-500">
              {transportLoading
                ? 'Searching transit in the selected area…'
                : `${transportVisible.length} of ${transport?.count ?? 0} transport result${(transport?.count ?? 0) === 1 ? '' : 's'} in the selected area`}
              {transport && !transportLoading && (transport.area_filter === 'bbox' ? ' · map area' : ` · ${transportRadius} km radius`)}
            </p>
            {transport && !transportLoading && (
              <p className="text-[10px] text-slate-500">
                {transport.provider_summary.status === 'LIVE' ? 'LIVE' : transport.provider_summary.status} · {transport.provider_summary.line}
              </p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(TRANSPORT_GROUP_LABELS) as TransportGroup[]).map((g) => (
                <button
                  key={g}
                  onClick={() => setTransportMode(g)}
                  className={`text-[10px] font-bold tracking-widest rounded-full px-3 py-1.5 border transition-colors ${
                    transportMode === g
                      ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                      : 'border-white/10 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {TRANSPORT_GROUP_LABELS[g].toUpperCase()}
                </button>
              ))}
            </div>
            {transportLoading ? (
              <p className="text-sm text-slate-500 animate-pulse">Discovering transit…</p>
            ) : transportError ? (
              <p className="text-sm text-red-300">{transportError}</p>
            ) : (
              <ul className="space-y-2 max-h-96 overflow-y-auto pr-1">
                {transportVisible.slice(0, 40).map((m) => (
                  <li key={`t-${m.kind}-${m.id}`}>
                    <button
                      onClick={() => setSelected(m.id)}
                      className={`w-full text-left glass glass-hover p-3 flex items-center justify-between gap-3 ${
                        selected === m.id ? 'border-cyan-400/40' : ''
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="text-sm text-slate-200 truncate">
                          <span className="mr-1.5">{KIND_META[m.kind]?.glyph}</span>
                          {m.name}
                        </div>
                        <div className="text-[11px] text-slate-500 truncate">{m.detail}</div>
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        <span className="text-xs text-cyan-300">{m.distance_km} km</span>
                        <DataBadge status={m.data_status} />
                      </div>
                    </button>
                  </li>
                ))}
                {transportVisible.length === 0 && !transportLoading && (
                  <li className="text-sm text-slate-500">
                    No matching stations found in the selected area — nothing is
                    invented. Try a wider radius or move the map.
                  </li>
                )}
              </ul>
            )}
          </>
        ) : (
          <>
            <p className="text-[11px] text-slate-500">
              {visibleMarkers.length} nearby result{visibleMarkers.length === 1 ? '' : 's'}
            </p>
            <ProviderSummaryLine summary={summary} />
            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => {
                    setFilter(f)
                    setActiveButton('ALL')
                  }}
                  className={`text-[10px] font-bold tracking-widest rounded-full px-3 py-1.5 border transition-colors ${
                    filter === f
                      ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-300'
                      : 'border-white/10 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
            {loading ? (
              <p className="text-sm text-slate-500 animate-pulse">Discovering nearby…</p>
            ) : locError ? (
              <p className="text-sm text-red-300">{locError}</p>
            ) : (
              <ul className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {visibleMarkers.slice(0, 12).map((m) => (
                  <li key={`${m.kind}-${m.id}`}>
                    <button
                      onClick={() => setSelected(m.id)}
                      className={`w-full text-left glass glass-hover p-3 flex items-center justify-between gap-3 ${
                        selected === m.id ? 'border-cyan-400/40' : ''
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="text-sm text-slate-200 truncate">
                          <span className="mr-1.5">{KIND_META[m.kind]?.glyph}</span>
                          {m.name}
                        </div>
                        <div className="text-[11px] text-slate-500 truncate">{m.detail}</div>
                      </div>
                      <div className="shrink-0 flex flex-col items-end gap-1">
                        <span className="text-xs text-cyan-300">{m.distance_km} km</span>
                        <DataBadge status={m.data_status} />
                      </div>
                    </button>
                  </li>
                ))}
                {visibleMarkers.length === 0 && (
                  <li className="text-sm text-slate-500">Nothing matches this filter nearby.</li>
                )}
              </ul>
            )}
          </>
        )}

        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <OpeningChip status="open" /> <OpeningChip status="unknown" />
          <span>· every record carries its data status — nothing here is presented as live</span>
        </div>
      </div>
    </div>
  )
}
