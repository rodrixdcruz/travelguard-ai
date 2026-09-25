import type { DataStatus, FoodPlace, LocalService, Place, TransportStop } from '../types/discovery'

export type MarkerKind =
  | 'attraction'
  | 'food'
  | 'hospital'
  | 'police'
  | 'pharmacy'
  | 'atm'
  | 'transport'
  | 'bus_stand'
  | 'railway_station'
  | 'metro_station'
  | 'metro_entrance'
  | 'tram'
  | 'taxi'
  | 'sos'

/** Transport-kind groups for the Transport tab's sub-filters. */
export type TransportGroup = 'ALL' | 'BUS' | 'METRO' | 'RAILWAY' | 'OTHER'

export const TRANSPORT_GROUP_KINDS: Record<TransportGroup, MarkerKind[]> = {
  ALL: ['bus_stand', 'metro_station', 'metro_entrance', 'railway_station', 'tram', 'transport'],
  BUS: ['bus_stand'],
  METRO: ['metro_station', 'metro_entrance'],
  RAILWAY: ['railway_station'],
  OTHER: ['tram', 'transport'],
}

export interface MapMarker {
  id: string
  name: string
  kind: MarkerKind
  category: string
  latitude: number
  longitude: number
  distance_km: number
  detail: string
  data_status: DataStatus
  phone?: string | null
}

export type MapFilter = 'ALL' | 'ATTRACTIONS' | 'FOOD' | 'SAFETY' | 'SERVICES' | 'TRANSPORT'

export const FILTER_KINDS: Record<MapFilter, MarkerKind[]> = {
  ALL: ['attraction', 'food', 'hospital', 'police', 'pharmacy', 'atm', 'transport', 'bus_stand', 'railway_station', 'metro_station', 'metro_entrance', 'tram', 'taxi', 'sos'],
  ATTRACTIONS: ['attraction'],
  FOOD: ['food'],
  SAFETY: ['hospital', 'police', 'sos'],
  SERVICES: ['pharmacy', 'atm'],
  TRANSPORT: ['transport', 'bus_stand', 'railway_station', 'metro_station', 'metro_entrance', 'tram', 'taxi'],
}

export const KIND_META: Record<MarkerKind, { glyph: string; color: string; label: string }> = {
  attraction: { glyph: '🏛', color: '#22d3ee', label: 'Attraction' },
  food: { glyph: '🍽', color: '#fbbf24', label: 'Food' },
  hospital: { glyph: '✚', color: '#f87171', label: 'Hospital' },
  police: { glyph: '🛡', color: '#60a5fa', label: 'Police' },
  pharmacy: { glyph: '℞', color: '#2dd4bf', label: 'Pharmacy' },
  atm: { glyph: '₹', color: '#a78bfa', label: 'ATM' },
  transport: { glyph: '🚉', color: '#94a3b8', label: 'Transport' },
  bus_stand: { glyph: '🚌', color: '#7dd3fc', label: 'Bus stop' },
  railway_station: { glyph: '🚆', color: '#c4b5fd', label: 'Railway station' },
  metro_station: { glyph: '🚇', color: '#f0abfc', label: 'Metro station' },
  metro_entrance: { glyph: '🚪', color: '#fda4af', label: 'Metro entrance' },
  tram: { glyph: '🚋', color: '#fcd34d', label: 'Tram' },
  taxi: { glyph: '🚖', color: '#fde68a', label: 'Taxi / auto stand' },
  sos: { glyph: '🆘', color: '#fb923c', label: 'Emergency' },
}

const SAFETY_TYPES: Record<string, MarkerKind> = {
  hospital: 'hospital',
  ambulance: 'sos',
  fire: 'sos',
  police: 'police',
  tourist_help: 'sos',
}

export function markersFromDiscovery(
  places: Place[],
  food: FoodPlace[],
  services: LocalService[],
): MapMarker[] {
  const placeMarkers: MapMarker[] = places.map((p) => ({
    id: p.id,
    name: p.name,
    kind: 'attraction',
    category: p.category,
    latitude: p.latitude,
    longitude: p.longitude,
    distance_km: p.distance_km,
    detail:
      p.entry_fee > 0
        ? `Entry ₹${p.entry_fee} · ${(p.estimated_visit_minutes ?? 60)} min`
        : `Free entry · ${(p.estimated_visit_minutes ?? 60)} min`,
    data_status: p.data_status,
  }))

  const foodMarkers: MapMarker[] = food.map((f) => ({
    id: f.id,
    name: f.name,
    kind: 'food',
    category: f.cuisine,
    latitude: f.latitude,
    longitude: f.longitude,
    distance_km: f.distance_km,
    detail: `${f.cuisine} · ${f.price_range}${f.rating ? ` · ★${f.rating}` : ''}`,
    data_status: f.data_status,
  }))

  const serviceMarkers: MapMarker[] = services.map((s) => ({
    id: s.id,
    name: s.name,
    kind: SAFETY_TYPES[s.service_type] ?? (
      s.service_type === 'atm' ? 'atm'
      : s.service_type === 'transport' ? 'transport'
      : s.service_type === 'bus_stand' ? 'bus_stand'
      : s.service_type === 'railway_station' ? 'railway_station'
      : s.service_type === 'metro_station' ? 'metro_station'
      : s.service_type === 'taxi' || s.service_type === 'auto_stand' ? 'taxi'
      : 'pharmacy'
    ),
    category: s.service_type,
    latitude: s.latitude,
    longitude: s.longitude,
    distance_km: s.distance_km,
    detail: s.service_type.replace(/_/g, ' '),
    data_status: s.data_status,
    phone: s.phone,
  }))

  return [...placeMarkers, ...foodMarkers, ...serviceMarkers]
}


/** Transport-stop rows (GET /api/transport/nearby) → map markers. */
export function transportMarkers(stops: TransportStop[]): MapMarker[] {
  return stops.map((t) => ({
    id: t.id,
    name: t.name,
    kind:
      t.transport_type === 'bus_stop' || t.transport_type === 'bus_terminal' ? 'bus_stand'
      : t.transport_type === 'metro_station' ? 'metro_station'
      : t.transport_type === 'metro_entrance' ? 'metro_entrance'
      : t.transport_type === 'railway_station' ? 'railway_station'
      : t.transport_type === 'tram' || t.transport_type === 'light_rail' || t.transport_type === 'monorail' ? 'tram'
      : 'transport',
    category: t.transport_type,
    latitude: t.latitude,
    longitude: t.longitude,
    distance_km: t.distance_km,
    detail: `${t.transport_type.replace(/_/g, ' ')}${t.address ? ` · ${t.address}` : ''}`,
    data_status: t.data_status,
  }))
}
