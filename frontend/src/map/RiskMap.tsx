import { useEffect, useMemo } from 'react'
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

/** Pulsing "you are here" halo + dot for the user's selected location. */
const userHereIcon = L.divIcon({
  className: '',
  html: `
    <div style="position:relative;width:34px;height:34px">
      <div class="you-are-here-halo-wrap"><div class="you-are-here-halo"></div></div>
      <div style="position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;
        border-radius:50%;background:#22d3ee;border:2.5px solid #ffffff;
        box-shadow:0 0 10px #22d3eecc"></div>
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
      {segments.length === 0 && markerPoints.length > 0 && fitToMarkers && (
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
      {userLocation && (
        <Marker
          position={[userLocation.latitude, userLocation.longitude]}
          icon={userHereIcon}
          interactive={false}
          zIndexOffset={1000}
          key={`you-are-here-${userLocation.latitude}-${userLocation.longitude}`}
        />
      )}
      {onBounds && <BoundsReporter onBounds={onBounds} />}
    </MapContainer>
  )
}
