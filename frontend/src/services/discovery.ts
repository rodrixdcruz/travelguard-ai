import type { DayPlan, FoodPlace, GeoSearchResponse, LocalSafety, LocalService, Place, TouristLocation } from '../types/discovery'
import type { ProviderSummary } from '../components/ProviderSummaryLine'
import { apiConfig } from './api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${apiConfig.API_BASE}${path}`)
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`API error ${res.status}: ${detail.slice(0, 160)}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${apiConfig.API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`API error ${res.status}: ${detail.slice(0, 160)}`)
  }
  return res.json() as Promise<T>
}

export function fetchNearbyPlaces(opts: {
  latitude: number
  longitude: number
  radius_km?: number
  category?: string
  interest?: string
  limit?: number
}): Promise<{ places: Place[]; count: number; data_status: string; provider_summary: ProviderSummary }> {
  const q = new URLSearchParams({
    latitude: String(opts.latitude),
    longitude: String(opts.longitude),
    radius_km: String(opts.radius_km ?? 10),
    limit: String(opts.limit ?? 20),
  })
  if (opts.category) q.set('category', opts.category)
  if (opts.interest) q.set('interest', opts.interest)
  return get(`/api/places/nearby?${q}`)
}

export function fetchNearbyFood(opts: {
  latitude: number
  longitude: number
  radius_km?: number
  vegetarian?: boolean
  budget?: number
  cuisine?: string
  limit?: number
}): Promise<{ food: FoodPlace[]; count: number; data_status: string; provider_summary: ProviderSummary }> {
  const q = new URLSearchParams({
    latitude: String(opts.latitude),
    longitude: String(opts.longitude),
    radius_km: String(opts.radius_km ?? 8),
    limit: String(opts.limit ?? 20),
  })
  if (opts.vegetarian !== undefined) q.set('vegetarian', String(opts.vegetarian))
  if (opts.budget !== undefined) q.set('budget', String(opts.budget))
  if (opts.cuisine) q.set('cuisine', opts.cuisine)
  return get(`/api/food/nearby?${q}`)
}

export function fetchNearbyServices(opts: {
  latitude: number
  longitude: number
  radius_km?: number
  service_type?: string
  limit?: number
}): Promise<{ services: LocalService[]; count: number; data_status: string; provider_summary: ProviderSummary }> {
  const q = new URLSearchParams({
    latitude: String(opts.latitude),
    longitude: String(opts.longitude),
    radius_km: String(opts.radius_km ?? 8),
    limit: String(opts.limit ?? 20),
  })
  if (opts.service_type) q.set('service_type', opts.service_type)
  return get(`/api/services/nearby?${q}`)
}

export function planDay(req: {
  latitude: number
  longitude: number
  location_name?: string
  duration: string
  budget: string | number
  interests: string[]
  travelers: string | number
  start_time?: string
  days?: number
}): Promise<DayPlan> {
  return post<DayPlan>('/api/plan/day', req)
}

/** Local safety context — the existing ML safety model via GET /api/safety/local. */
export function fetchLocalSafety(latitude: number, longitude: number): Promise<LocalSafety> {
  return get(`/api/safety/local?latitude=${latitude}&longitude=${longitude}`)
}

/**
 * Browser geolocation for an explicit "use my location" click.
 * Fresh fix (no cache) named via the backend's reverse geocoder when it can
 * be — "Nagpur, Maharashtra" instead of an anonymous "Your location".
 * Rejects when unavailable or denied; never resolves to a demo city.
 */
export async function browserLocation(): Promise<TouristLocation> {
  const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation unavailable in this browser'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      resolve,
      (err) => reject(new Error(err.message || 'Location permission denied')),
      { timeout: 8000, maximumAge: 0, enableHighAccuracy: true },
    )
  })
  const base: TouristLocation = {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
    name: 'Your location',
    source: 'browser',
  }
  const name = await reverseName(base.latitude, base.longitude)
  return name ? { ...base, name } : base
}

/** Place-name search via the backend's Nominatim proxy (real coordinates). */
export function searchPlaces(query: string): Promise<GeoSearchResponse> {
  return get(`/api/geo/search?q=${encodeURIComponent(query)}`)
}

/** Resolve a coordinate to a human place name (best-effort, may return null). */
export async function reverseName(latitude: number, longitude: number): Promise<string | null> {
  try {
    const r = await get<{ name: string | null; data_status: string }>(
      `/api/geo/reverse?latitude=${latitude}&longitude=${longitude}`,
    )
    return r.name
  } catch {
    return null
  }
}
