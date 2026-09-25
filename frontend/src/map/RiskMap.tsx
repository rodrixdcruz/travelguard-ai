import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import type { Segment } from '../types'
import { scoreColor } from '../utils/format'
import { KIND_META, type MapMarker } from '../utils/markers'

function FitRoute({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [45, 45], maxZoom: 11 })
    }
  }, [map, points])
  return null
}

function FitMarkers({ points }: { points: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 14 })
    }
  }, [map, points])
  return null
}

/** Reports the visible map bounds upward so panels can search within them. */
function BoundsReporter({ onBounds }: { onBounds: (b: { lat1: number; lon1: number; lat2: number; lon2: number } | null) => void }) {
  const map = useMap()
  useEffect(() => {
    const emit = () => {
      const b = map.getBounds()
      if (b) onBounds({ lat1: b.getNorth(), lon1: b.getWest(), lat2: b.getSouth(), lon2: b.getEast() })
    }
    emit()
    map.on('moveend zoomend', emit)
    return () => {
      map.off('moveend zoomend', emit)
    }
  }, [map, onBounds])
  return null
}

/**
 * Animated fly-to for a fresh GPS fix (or any location reselection). The
 * nonce changes per fix; ``untilMoveEnd`` suppresses marker auto-fit during
 * the animation so it can finish, and notifies the parent on arrival so
 * area-based discovery can re-run against the new view.
 */
function FlyTo({
  target,
  nonce,
  untilMoveEnd,
  onArrival,
}: {
  target: { lat: number; lon: number }
  nonce: number
  untilMoveEnd: (v: boolean) => void
  onArrival?: () => void
}) {
  const map = useMap()
  const lastNonce = useRef(0)
  // Latest-ref pattern: parents pass inline callbacks that change identity on
  // every render. If they were effect deps, a mid-flight re-render (discovery
  // results landing) would tear down the moveend listener and the arrival
  // callback would never fire. The flight is registered ONCE per nonce.
  const arrivalRef = useRef(onArrival)
  arrivalRef.current = onArrival
  const untilRef = useRef(untilMoveEnd)
  untilRef.current = untilMoveEnd
  const targetRef = useRef(target)
  targetRef.current = target
  useEffect(() => {
    const tgt = targetRef.current
    if (!tgt || nonce === lastNonce.current) return
    lastNonce.current = nonce
    const current = map.getCenter()
    // Same spot as the current view: skip the animation, arrive immediately.
    if (map.distance(current, [tgt.lat, tgt.lon]) < 50) {
      arrivalRef.current?.()
      return
    }
    untilRef.current(true)
    let alive = true
    const onDone = () => {
      if (!alive) return
      untilRef.current(false)
      arrivalRef.current?.()
    }
    map.once('moveend', onDone)
    map.flyTo([tgt.lat, tgt.lon], 13, { duration: 1.2 })
    return () => {
      alive = false
      map.off('moveend', onDone)
      untilRef.current(false)
    }
  }, [nonce, map])
  return null
}

const icon = L.divIcon({
  className: '',
  html: `<div style="width:14px;height:14px;border-radius:50%;background:#22d3ee;box-shadow:0 0 12px #22d3ee88;border:2px solid #ffffffcc"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

const destIcon = L.divIcon({
  className: '',
  html: `<div style="width:14px;height:14px;border-radius:50%;background:#f87171;box-shadow:0 0 12px #f8717188;border:2px solid #ffffffcc"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

/**
 * Pulsing "you are here" halo + dot for the user's selected location.
 * Carries a "You are here" label that pops in and fades after ~4 s; hovering
 * the dot swaps the text for the location name and holds it visible (pure-DOM
 * inline handlers — Leaflet injects this HTML outside React's tree).
 */
function userHereIcon(name: string): L.DivIcon {
  const safeName = name
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
  return L.divIcon({
    className: '',
    html: `
      <div style="position:relative;width:34px;height:34px"
        onmouseenter="const l=this.querySelector('.you-are-here-label');if(l){l.textContent=l.dataset.name||'';l.classList.add('you-are-here-label--hold')}"
        onmouseleave="const l=this.querySelector('.you-are-here-label');if(l){l.textContent='You are here';l.classList.remove('you-are-here-label--hold')}">
        <div class="you-are-here-halo-wrap"><div class="you-are-here-halo"></div></div>
        <div style="position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;
          border-radius:50%;background:#22d3ee;border:2.5px solid #ffffff;
          box-shadow:0 0 10px #22d3eecc"></div>
        <div class="you-are-here-label" data-name="${safeName}">You are here</div>
      </div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  })
}

/** One-shot GPS-arrival flash — a separate overlay marker so mounting and
 * unmounting it never restarts the dot's label animation. */
const userFlashIcon = L.divIcon({
  className: '',
  html: `
    <div style="position:relative;width:34px;height:34px">
      <div class="you-are-here-flash-wrap"><div class="you-are-here-flash"></div></div>
    </div>`,
  iconSize: [34, 34],
  iconAnchor: [17, 17],
})

function markerIcon(marker: MapMarker, selected: boolean): L.DivIcon {
  const meta = KIND_META[marker.kind] ?? KIND_META.attraction
  const size = selected ? 30 : 24
  return L.divIcon({
    className: '',
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50% 50% 50% 4px;
      transform:rotate(-45deg);
      background:${meta.color}22;border:2px solid ${meta.color};
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 0 ${selected ? 14 : 8}px ${meta.color}66;
    "><span style="transform:rotate(45deg);font-size:${selected ? 14 : 12}px;line-height:1">${meta.glyph}</span></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
}

interface Props {
  segments?: Segment[]
  origin?: { lat: number; lon: number; name: string }
  destination?: { lat: number; lon: number; name: string }
  selectedId?: number | null
  onSelect?: (id: number) => void
  markers?: MapMarker[]
  selectedMarkerId?: string | null
  onSelectMarker?: (id: string) => void
  fitToMarkers?: boolean
  heightClass?: string
  onBounds?: (b: { lat1: number; lon1: number; lat2: number; lon2: number } | null) => void
  /** Selected location — rendered as a distinct pulsing "you are here" dot. */
  userLocation?: { latitude: number; longitude: number; name: string } | null
  /**
   * Fly the map to this point when ``flyNonce`` changes (GPS fix / fresh
   * selection). ``onFlyArrival`` fires once the animation lands.
   */
  flyTarget?: { lat: number; lon: number } | null
  flyNonce?: number
  onFlyArrival?: () => void
  /** Brief bright-flash highlight of the you-are-here dot. */
  userFlashing?: boolean
}

export default function RiskMap({
  segments = [],
  origin,
  destination,
  selectedId = null,
  onSelect,
  markers = [],
  selectedMarkerId = null,
  onSelectMarker,
  fitToMarkers = false,
  heightClass = 'h-full w-full',
  onBounds,
  userLocation = null,
  flyTarget = null,
  flyNonce = 0,
  onFlyArrival,
  userFlashing = false,
}: Props) {
  const routePoints = useMemo(() => segments.flatMap((s) => s.path), [segments])
  const center: [number, number] = useMemo(() => {
    const src =
      routePoints.length > 0
        ? routePoints
        : [
            ...markers.map((m) => ({ lat: m.latitude, lon: m.longitude })),
            ...(userLocation
              ? [{ lat: userLocation.latitude, lon: userLocation.longitude }]
              : []),
          ]
    // Neutral default: whole-of-India view. Never center on Mumbai unless
    // Mumbai data is actually on the map (selected trip / demo mode / GPS).
    if (src.length === 0) return [21.5, 79.0] as [number, number]
    const n = src.length
    return [
      src.reduce((a, p) => a + p.lat, 0) / n,
      src.reduce((a, p) => a + p.lon, 0) / n,
    ]
  }, [routePoints, markers, userLocation])

  const isEmpty =
    center.length === 2 && routePoints.length === 0 && markers.length === 0 && !userLocation

  const markerPoints = useMemo(
    () => markers.map((m) => [m.latitude, m.longitude] as [number, number]),
    [markers],
  )

  // Hold marker auto-fit while a fly-to animation is in progress — otherwise
  // new markers landing mid-flight would cancel the animation.
  const [flying, setFlying] = useState(false)

  // Icon identity is keyed by the location so the "You are here" label
  // animation replays when the user moves, and is otherwise stable — flash
  // mount/unmount or unrelated re-renders must not restart it.
  const userLocKey = userLocation
    ? `${userLocation.latitude},${userLocation.longitude},${userLocation.name}`
    : ''
  const userIcon = useMemo(
    () => (userLocation ? userHereIcon(userLocation.name) : null),
    [userLocKey],
  )

  return (
    <MapContainer
      center={center}
      zoom={isEmpty ? 5 : 13}
      className={`${heightClass} rounded-2xl z-0`}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='Tiles &copy; Esri — Source: Esri, HERE, Garmin, &copy; OpenStreetMap contributors'
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
      />
      {segments.length > 0 && (
        <>
          {segments.map((s) => (
            <Polyline
              key={s.id}
              positions={s.path.map((p) => [p.lat, p.lon] as [number, number])}
              pathOptions={{
                color: selectedId === s.id ? '#ffffff' : scoreColor(s.score),
                weight: selectedId === s.id ? 7 : 5,
                opacity: selectedId === s.id ? 1 : 0.85,
              }}
              eventHandlers={{ click: () => onSelect?.(s.id) }}
            />
          ))}
          {origin && <Marker position={[origin.lat, origin.lon]} icon={icon} />}
          {destination && <Marker position={[destination.lat, destination.lon]} icon={destIcon} />}
          <FitRoute points={routePoints.map((p) => [p.lat, p.lon] as [number, number])} />
        </>
      )}
      {segments.length === 0 && markerPoints.length > 0 && fitToMarkers && !flying && (
        <FitMarkers points={markerPoints} />
      )}
      {markers.map((m) => (
        <Marker
          key={`${m.kind}-${m.id}`}
          position={[m.latitude, m.longitude]}
          icon={markerIcon(m, selectedMarkerId === m.id)}
          eventHandlers={{ click: () => onSelectMarker?.(m.id) }}
        />
      ))}
      {userLocation && userIcon && (
        <Marker
          position={[userLocation.latitude, userLocation.longitude]}
          icon={userIcon}
          zIndexOffset={1000}
          keyboard={false}
          key={`you-are-here-${userLocation.latitude}-${userLocation.longitude}`}
        />
      )}
      {userLocation && userFlashing && (
        <Marker
          position={[userLocation.latitude, userLocation.longitude]}
          icon={userFlashIcon}
          interactive={false}
          zIndexOffset={1001}
        />
      )}
      {onBounds && <BoundsReporter onBounds={onBounds} />}
      {flyTarget && (
        <FlyTo
          target={flyTarget}
          nonce={flyNonce}
          untilMoveEnd={setFlying}
          onArrival={onFlyArrival}
        />
      )}
    </MapContainer>
  )
}
