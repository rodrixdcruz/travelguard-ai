import type { DayPlan, FoodPlace, LocalSafety, LocalService, Place, TouristLocation } from '../types/discovery'
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
}): Promise<{ places: Place[]; count: number; data_status: string }> {
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
}): Promise<{ food: FoodPlace[]; count: number; data_status: string }> {
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
}): Promise<{ services: LocalService[]; count: number; data_status: string }> {
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
}): Promise<DayPlan> {
  return post<DayPlan>('/api/plan/day', req)
}

/** Local safety context — the existing ML safety model via GET /api/safety/local. */
export function fetchLocalSafety(latitude: number, longitude: number): Promise<LocalSafety> {
  return get(`/api/safety/local?latitude=${latitude}&longitude=${longitude}`)
}

/** Browser geolocation with a 8s timeout; rejects when unavailable or denied. */
export function browserLocation(): Promise<TouristLocation> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Geolocation unavailable in this browser'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          name: 'Your location',
          source: 'browser',
        }),
      (err) => reject(new Error(err.message || 'Location permission denied')),
      { timeout: 8000, maximumAge: 60000 },
    )
  })
}
