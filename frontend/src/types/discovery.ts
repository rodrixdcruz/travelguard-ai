export type DataStatus = 'LIVE' | 'DEMO' | 'ESTIMATED' | 'UNAVAILABLE'

export interface Place {
  id: string
  name: string
  category: string
  description: string
  latitude: number
  longitude: number
  address: string
  distance_km: number
  entry_fee: number
  ticket_required: boolean | null
  opening_status: string
  opening_hours: string
  estimated_visit_minutes: number
  rating: number | null
  tags: string[]
  safety_context: number
  data_source: string
  data_status: DataStatus
}

export interface FoodPlace {
  id: string
  name: string
  cuisine: string
  vegetarian: boolean
  non_vegetarian: boolean
  price_range: string
  rating: number | null
  latitude: number
  longitude: number
  address: string
  distance_km: number
  opening_status: string
  data_source: string
  data_status: DataStatus
}

export interface LocalService {
  id: string
  name: string
  service_type: string
  latitude: number
  longitude: number
  address: string
  distance_km: number
  phone: string | null
  opening_status: string
  data_source: string
  data_status: DataStatus
}

/** Row of GET /api/transport/nearby — one real transit stop/station. */
export interface TransportStop {
  id: string
  name: string
  transport_type: 'bus_stop' | 'bus_terminal' | 'metro_station' | 'metro_entrance' | 'railway_station' | 'tram' | 'monorail' | 'light_rail' | 'transit'
  latitude: number
  longitude: number
  address: string
  distance_km: number
  data_source: string
  data_status: DataStatus
}

/** Response shape of GET /api/transport/nearby. */
export interface TransportResponse {
  origin: { latitude: number; longitude: number }
  radius_km: number
  count: number
  transport: TransportStop[]
  data_status: DataStatus
  data_source: string
  provider_summary: import('../components/ProviderSummaryLine').ProviderSummary
  failed_groups: string[]
  area_filter: 'circle' | 'bbox'
  note: string
}

export interface PlanItem {
  type: 'travel' | 'attraction' | 'meal'
  time: string
  name: string
  detail: string
  duration_min: number
  cost_inr: number
  data_status: DataStatus
  safety: string | null
  place_id?: string
  ticket_required?: boolean | null
  recommendation_score?: number | null
  latitude?: number
  longitude?: number
  category?: string
  travel_time_min?: number
  reasons?: string[]
  day?: number
}

export interface DayPlan {
  location: { latitude: number; longitude: number; name: string | null }
  preferences: {
    duration: string
    hours: number
    budget_per_person: number
    interests: string[]
    travelers: number
    start_time: string
  }
  itinerary: {
    start_time: string
    end_time: string
    days?: number
    days_scheduled?: number
    per_day?: { day: number; places: number; time_min: number; cost_inr: number }[]
    items: PlanItem[]
    totals: {
      places: number
      total_time_min: number
      total_estimated_cost_inr: number
      within_budget: boolean
    }
  }
  cost_breakdown: {
    tickets: number
    food_estimate: number
    transport_estimate: number
    total_estimate: number
    budget_total: number
    travelers: number
    line_status: Record<string, DataStatus>
  }
  safety: {
    risk_score: number
    risk_level: string
    model_used: string
    model_version: string
    disclaimer: string
    data_status?: DataStatus
  }
  ranking_model: string
  optimizer: string
  skipped: { name: string; why: string }[]
  weather: Record<string, unknown>
  data_status: DataStatus
  provider_summary?: import('../components/ProviderSummaryLine').ProviderSummary
}

export interface TouristLocation {
  latitude: number
  longitude: number
  name: string
  source: 'browser' | 'search' | 'demo' | 'unset'
}

/** Response shape of GET /api/safety/local (existing ML model, reused). */
export interface LocalSafety {
  risk_score: number
  risk_level: RiskLevelType
  model_used: string
  model_version: string
  disclaimer: string
  data_status: DataStatus
}
export type RiskLevelType = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'

/** SOS center payload from /api/sos/info. */
export interface SosInfo {
  emergency_numbers: Record<
    string,
    { number: string; label: string; source: string; data_status: DataStatus }
  >
  nearest: Partial<Record<'hospital' | 'police' | 'pharmacy', LocalService>>
  data_status: DataStatus
  note: string
}

/** Recognizable demo locations for users without geolocation (Demo Mode only). */
export const DEMO_LOCATIONS: TouristLocation[] = [
  { latitude: 18.9220, longitude: 72.8347, name: 'Gateway of India, Colaba', source: 'demo' },
  { latitude: 18.9398, longitude: 72.8355, name: 'CSMT, Fort', source: 'demo' },
  { latitude: 18.9533, longitude: 72.8117, name: 'Girgaum Chowpatty', source: 'demo' },
  { latitude: 19.1075, longitude: 72.8263, name: 'Juhu Beach', source: 'demo' },
  { latitude: 19.0170, longitude: 72.8298, name: 'Siddhivinayak, Dadar', source: 'demo' },
]

/** Result of GET /api/geo/search — real coordinates from OpenStreetMap. */
export interface GeoSearchResult {
  name: string
  short_name: string
  latitude: number
  longitude: number
  type: string
}

/** Response shape of GET /api/geo/search. */
export interface GeoSearchResponse {
  results: GeoSearchResult[]
  count: number
  data_status: string
  data_source: string
}
