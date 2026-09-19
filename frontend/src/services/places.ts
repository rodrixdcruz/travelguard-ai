/**
 * Demo place catalog — SYNTHETIC sample data for the recommendation demo.
 * Clearly labeled in the UI; not a real POI database.
 */
export interface DemoPlace {
  place_id: string
  name: string
  category: string
  tags: string[]
  distance_km: number
  estimated_cost: number
  popularity: number
  visit_duration_hours: number
  is_open: boolean
  safety_context: number
  lat: number
  lon: number
}

export const DEMO_PLACES: DemoPlace[] = [
  { place_id: 'p1', name: 'Shaniwar Wada', category: 'history', tags: ['history', 'culture'], distance_km: 2.1, estimated_cost: 50, popularity: 88, visit_duration_hours: 1.5, is_open: true, safety_context: 82, lat: 18.5194, lon: 73.8553 },
  { place_id: 'p2', name: 'Aga Khan Palace', category: 'history', tags: ['history', 'photography'], distance_km: 5.4, estimated_cost: 25, popularity: 76, visit_duration_hours: 1.5, is_open: true, safety_context: 85, lat: 18.5527, lon: 73.8922 },
  { place_id: 'p3', name: 'Sinhagad Fort', category: 'history', tags: ['history', 'nature', 'photography'], distance_km: 28, estimated_cost: 20, popularity: 91, visit_duration_hours: 4, is_open: true, safety_context: 62, lat: 18.3663, lon: 73.7551 },
  { place_id: 'p4', name: 'VD Savarkar Smarak', category: 'culture', tags: ['culture', 'history'], distance_km: 6.2, estimated_cost: 0, popularity: 55, visit_duration_hours: 1, is_open: true, safety_context: 80, lat: 18.5210, lon: 73.8540 },
  { place_id: 'p5', name: 'Osho Teerth Park', category: 'nature', tags: ['nature', 'family'], distance_km: 4.0, estimated_cost: 0, popularity: 68, visit_duration_hours: 1.5, is_open: true, safety_context: 84, lat: 18.5372, lon: 73.8939 },
  { place_id: 'p6', name: 'Phoenix Marketcity', category: 'shopping', tags: ['shopping', 'food', 'family'], distance_km: 7.8, estimated_cost: 1500, popularity: 82, visit_duration_hours: 3, is_open: true, safety_context: 78, lat: 18.5620, lon: 73.9160 },
  { place_id: 'p7', name: 'Pataleshwar Cave', category: 'history', tags: ['history', 'culture'], distance_km: 3.3, estimated_cost: 0, popularity: 60, visit_duration_hours: 1, is_open: false, safety_context: 79, lat: 18.5268, lon: 73.8420 },
  { place_id: 'p8', name: 'Pune Food Walk', category: 'food', tags: ['food'], distance_km: 1.8, estimated_cost: 600, popularity: 85, visit_duration_hours: 2, is_open: true, safety_context: 75, lat: 18.5180, lon: 73.8560 },
  { place_id: 'p9', name: 'Katraj Snake Park', category: 'family', tags: ['family', 'nature'], distance_km: 12, estimated_cost: 40, popularity: 64, visit_duration_hours: 2, is_open: true, safety_context: 72, lat: 18.4570, lon: 73.8620 },
  { place_id: 'p10', name: 'Lavasa Lakeside', category: 'nature', tags: ['nature', 'photography'], distance_km: 55, estimated_cost: 800, popularity: 70, visit_duration_hours: 5, is_open: true, safety_context: 58, lat: 18.4030, lon: 73.5100 },
]

export const INTEREST_OPTIONS = ['history', 'food', 'nature', 'shopping', 'culture', 'photography', 'family']
