export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'

export interface Coordinate {
  lat: number
  lon: number
}

export interface RoutePoint extends Coordinate {
  name: string
}

export interface SegmentFactor {
  category: string
  score: number
  weight: number
  reason: string
}

export interface Segment {
  id: number
  name: string
  start: Coordinate
  end: Coordinate
  path: Coordinate[]
  distance_km: number
  duration_min: number
  score: number
  level: RiskLevel
  factors: SegmentFactor[]
  weather: Record<string, unknown>
  road_condition: Record<string, unknown>
  recommended_action: string
  ml_score?: number | null
  ml_model_used?: string | null
}

export interface Alert {
  id: string
  severity: RiskLevel
  title: string
  detail: string
  segment_id: number | null
}

export interface Recommendation {
  id: string
  priority: number
  text: string
}

export interface OverallRisk {
  score: number
  level: RiskLevel
  main_concern: string
  breakdown: Record<string, number>
}

export interface Journey {
  origin: RoutePoint
  destination: RoutePoint
  date: string
  time: string
  distance_km: number
  duration_min: number
  eta: string
}

export interface AnalyzeResponse {
  journey: Journey
  overall_risk: OverallRisk
  segments: Segment[]
  alerts: Alert[]
  recommendations: Recommendation[]
  briefing: string
  data_mode: string
  intelligence_mode: string
  generated_at: string
}

export interface AnalyzeRequest {
  origin: string
  destination: string
  date: string
  time: string
}

export interface HistoryEntry {
  id: string
  origin: string
  destination: string
  date: string
  time: string
  score: number
  level: RiskLevel
  ts: number
}

export type FactorDict = Record<string, number>

export interface MlFactor {
  label: string
  weight: number
  detail: string
}

export interface MlSafetyResponse {
  risk_score: number
  risk_level: RiskLevel
  model_used: string
  model_version: string
  dataset_type: string
  factors: MlFactor[]
  model_features: FactorDict
  feature_importance: { feature: string; importance: number }[]
}

export interface MlModelStatus {
  active: boolean
  kind: string
  model_used: string
  model_version: string
  metrics: Record<string, number>
  dataset_type?: string
}

export interface MlInfo {
  safety_model: MlModelStatus
  recommendation_model: MlModelStatus
  features: string[]
  transparency: { score_meaning: string; dataset_type: string }
}
