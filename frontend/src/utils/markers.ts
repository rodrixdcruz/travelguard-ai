import type { DataStatus, FoodPlace, LocalService, Place } from '../types/discovery'

export type MarkerKind =
  | 'attraction'
  | 'food'
  | 'hospital'
  | 'police'
  | 'pharmacy'
  | 'atm'
  | 'transport'
  | 'sos'

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
  ALL: ['attraction', 'food', 'hospital', 'police', 'pharmacy', 'atm', 'transport', 'sos'],
  ATTRACTIONS: ['attraction'],
  FOOD: ['food'],
  SAFETY: ['hospital', 'police', 'sos'],
  SERVICES: ['pharmacy', 'atm'],
  TRANSPORT: ['transport'],
}

export const KIND_META: Record<MarkerKind, { glyph: string; color: string; label: string }> = {
  attraction: { glyph: '🏛', color: '#22d3ee', label: 'Attraction' },
  food: { glyph: '🍽', color: '#fbbf24', label: 'Food' },
  hospital: { glyph: '✚', color: '#f87171', label: 'Hospital' },
  police: { glyph: '🛡', color: '#60a5fa', label: 'Police' },
  pharmacy: { glyph: '℞', color: '#2dd4bf', label: 'Pharmacy' },
  atm: { glyph: '₹', color: '#a78bfa', label: 'ATM' },
  transport: { glyph: '🚉', color: '#94a3b8', label: 'Transport' },
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
    kind: SAFETY_TYPES[s.service_type] ?? (s.service_type === 'atm' ? 'atm' : s.service_type === 'transport' ? 'transport' : 'pharmacy'),
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
