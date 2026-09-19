import type { RiskLevel } from '../types'
import { levelText } from '../utils/format'

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold tracking-wider border ${levelText[level]}`}>
      {level}
    </span>
  )
}

export function ScoreRing({ score, level }: { score: number; level: RiskLevel }) {
  const colors: Record<RiskLevel, string> = {
    LOW: '#2dd4bf',
    MODERATE: '#fbbf24',
    HIGH: '#fb923c',
    CRITICAL: '#f87171',
  }
  const color = colors[level]
  const r = 52
  const c = 2 * Math.PI * r
  const filled = (Math.min(score, 100) / 100) * c

  return (
    <div className="relative w-32 h-32">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="10" />
        <circle
          cx="60" cy="60" r={r} fill="none"
          stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${filled} ${c - filled}`}
          style={{ filter: `drop-shadow(0 0 6px ${color}66)`, transition: 'stroke-dasharray 0.8s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-3xl font-display font-bold" style={{ color }}>
          {Math.round(score)}
        </div>
        <div className="text-[10px] uppercase tracking-widest text-slate-500">/ 100</div>
      </div>
    </div>
  )
}
