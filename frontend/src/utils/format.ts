import type { RiskLevel } from '../types'

export const levelColor: Record<RiskLevel, string> = {
  LOW: '#2dd4bf',
  MODERATE: '#fbbf24',
  HIGH: '#fb923c',
  CRITICAL: '#f87171',
}

export const levelText: Record<RiskLevel, string> = {
  LOW: 'text-teal-300 border-teal-400/30 bg-teal-400/10',
  MODERATE: 'text-amber-300 border-amber-400/30 bg-amber-400/10',
  HIGH: 'text-orange-300 border-orange-400/30 bg-orange-400/10',
  CRITICAL: 'text-red-300 border-red-400/30 bg-red-400/10',
}

export function scoreColor(score: number): string {
  if (score >= 75) return levelColor.CRITICAL
  if (score >= 55) return levelColor.HIGH
  if (score >= 35) return levelColor.MODERATE
  return levelColor.LOW
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return h > 0 ? `${h}h ${m.toString().padStart(2, '0')}m` : `${m}m`
}

export function formatEta(etaIso: string): string {
  const d = new Date(etaIso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleString([], {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
