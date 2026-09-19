import type { AnalyzeRequest, AnalyzeResponse, MlInfo, MlSafetyResponse } from '../types'

/** Central API configuration — the only place the backend URL appears. */
const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ||
  'http://localhost:8000'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    throw new Error(`API error ${res.status}: ${detail.slice(0, 200)}`)
  }
  return res.json() as Promise<T>
}

export function analyzeJourney(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  return post<AnalyzeResponse>('/api/analyze-journey', req)
}

export function fetchBriefing(context: AnalyzeResponse): Promise<{ briefing: string; source: string }> {
  return post<{ briefing: string; source: string }>('/api/ai/explain', { context, question: '' })
}

export function chat(
  context: AnalyzeResponse | null,
  question: string,
): Promise<{ answer: string; source: string }> {
  return post<{ answer: string; source: string }>('/api/ai/chat', { context: context ?? {}, question })
}

/** Discovery-aware chat — answers only from the provided day-plan payload. */
export function chatDiscovery(
  discovery: Record<string, unknown>,
  question: string,
): Promise<{ answer: string; source: string }> {
  return post<{ answer: string; source: string }>('/api/ai/chat', {
    context: { discovery },
    question,
  })
}

export function mlInfo(): Promise<MlInfo> {
  return fetch(`${API_BASE}/api/ml/info`).then((r) => {
    if (!r.ok) throw new Error(`API error ${r.status}`)
    return r.json() as Promise<MlInfo>
  })
}

export function mlSafetyPredict(payload: Record<string, unknown>): Promise<MlSafetyResponse> {
  return post<MlSafetyResponse>('/api/ml/safety-predict', payload)
}

export const apiConfig = { API_BASE }
