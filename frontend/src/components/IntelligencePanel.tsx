import { useEffect, useState } from 'react'
import { mlInfo } from '../services/api'
import type { MlInfo } from '../types'
import Panel from './Panel'

function Dot({ on }: { on: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full mr-2 ${on ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]' : 'bg-slate-600'}`}
    />
  )
}

function ModelRow({ name, status }: { name: string; status?: { kind: string; model_used: string; model_version: string } }) {
  const active = !!status
  const label =
    status?.kind === 'ml'
      ? `Active — ${status.model_used} v${status.model_version}`
      : status
        ? `Active — ${status.model_used.replace(/_/g, ' ')}`
        : 'Inactive'
  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
      <div>
        <div className="text-sm text-slate-200 font-medium">{name}</div>
        <div className="text-[11px] text-slate-500">{label}</div>
      </div>
      <span className="text-[10px] uppercase tracking-widest text-slate-400">
        <Dot on={active} />
        {active ? 'Active' : 'Off'}
      </span>
    </div>
  )
}

// Share one in-flight request across every mounted panel instance.
let infoPromise: Promise<MlInfo | null> | null = null
function loadInfo(): Promise<MlInfo | null> {
  if (!infoPromise) infoPromise = mlInfo().catch(() => null)
  return infoPromise
}

export default function IntelligencePanel() {
  const [info, setInfo] = useState<MlInfo | null>(null)

  useEffect(() => {
    loadInfo().then(setInfo)
  }, [])

  return (
    <Panel title="TravelGuard Intelligence">
      {info ? (
        <>
          <ModelRow name="Contextual Risk Model" status={info.safety_model} />
          <ModelRow name="Recommendation Engine" status={info.recommendation_model} />
          <ModelRow
            name="AI Assistant"
            status={{ kind: 'ml', model_used: 'LLM + deterministic fallback', model_version: '0.1' }}
          />
          <p className="mt-3 text-[11px] text-slate-500 leading-relaxed">
            Risk output is a contextual travel-risk indicator (0–100), not a probability of an accident.
            Trained on synthetic demonstration data.
          </p>
        </>
      ) : (
        <p className="text-sm text-slate-500">Intelligence service unreachable.</p>
      )}
    </Panel>
  )
}
