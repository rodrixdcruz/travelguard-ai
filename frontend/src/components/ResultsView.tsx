import { useState } from 'react'
import type { AnalyzeResponse, Segment } from '../types'
import { formatDuration, formatEta } from '../utils/format'
import { RiskBadge, ScoreRing } from './RiskBadge'
import RiskBreakdown from './RiskBreakdown'
import AlertsList from './AlertsList'
import FareComparison from './FareComparison'
import RecommendationsList from './RecommendationsList'
import SegmentDetail from './SegmentDetail'
import Panel from './Panel'
import RiskMap from '../map/RiskMap'
import { useJourney } from '../context/JourneyContext'
import { useTouristLocation } from '../context/LocationContext'
import SafetyCard from './SafetyCard'
import IntelligencePanel from './IntelligencePanel'

interface Props {
  mapHeight?: string
}

export default function ResultsView({ mapHeight = 'h-[420px]' }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { analysis, briefing, briefingSource } = useJourney()
  const { location, needsLocation } = useTouristLocation()
  if (!analysis) return null

  const selected: Segment | null =
    analysis.segments.find((s) => s.id === selectedId) ?? null

  const journey = analysis.journey

  return (
    <div className="space-y-6">
      {/* ── Fare comparison: all 8 modes, cheapest first ── */}
      <FareComparison analysis={analysis} />

      {/* ── Journey info + overall risk ── */}
      <div className="grid lg:grid-cols-3 gap-6">
        <Panel className="lg:col-span-2">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 text-lg font-display font-semibold text-slate-100">
                <span className="text-cyan-300">{journey.origin.name}</span>
                <svg viewBox="0 0 24 24" className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
                <span className="text-cyan-300">{journey.destination.name}</span>
              </div>
              <div className="mt-1 text-sm text-slate-400">
                {journey.date} · departs {journey.time}
              </div>
            </div>
            <span className="text-[10px] uppercase tracking-widest text-cyan-300/80 border border-cyan-400/20 bg-cyan-400/5 rounded-lg px-2 py-1">
              {analysis.data_mode === 'demo' ? 'Demo data' : analysis.data_mode}
            </span>
          </div>
          {analysis.provider_summary?.line && (
            <p className="mt-2 text-[11px] text-slate-500">
              <span className={`font-semibold uppercase tracking-wider ${analysis.provider_summary.status === 'LIVE' ? 'text-emerald-300' : analysis.provider_summary.status === 'MIXED' ? 'text-cyan-300' : 'text-slate-400'}`}>
                {analysis.provider_summary.status}
              </span>
              <span className="mx-1.5 text-slate-600">·</span>
              {analysis.provider_summary.line}
            </p>
          )}
          <dl className="mt-5 grid grid-cols-3 gap-4">
            <Stat label="Distance" value={`${Math.round(journey.distance_km)} km`} />
            <Stat label="Duration" value={formatDuration(journey.duration_min)} />
            <Stat label="ETA" value={formatEta(journey.eta)} />
          </dl>
        </Panel>

        <Panel className="flex flex-col items-center justify-center">
          <div className="text-xs uppercase tracking-widest text-slate-400 mb-3">Overall Risk</div>
          <ScoreRing score={analysis.overall_risk.score} level={analysis.overall_risk.level} />
          <div className="mt-3"><RiskBadge level={analysis.overall_risk.level} /></div>
          <p className="mt-3 text-xs text-slate-400 text-center leading-relaxed">
            {analysis.overall_risk.main_concern}
          </p>
        </Panel>
      </div>

      {/* ── ML safety card + intelligence status ── */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SafetyCard analysis={analysis} />
        </div>
        <IntelligencePanel />
      </div>

      {/* ── Safety briefing ── */}
      <section className="relative glass p-6 overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-400/60 to-transparent" />
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-cyan-300">
            ✦ Journey Safety Briefing
          </h2>
          {briefingSource && (
            <span className="text-[10px] uppercase tracking-widest text-slate-500 border border-white/10 rounded-md px-2 py-0.5">
              {briefingSource === 'ai' ? 'AI generated' : 'Deterministic engine'}
            </span>
          )}
        </div>
        <pre className="whitespace-pre-wrap font-sans text-sm text-slate-300 leading-relaxed">
          {briefing ?? 'Preparing briefing…'}
        </pre>
      </section>

      {/* ── Map + segment detail ── */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className={`${mapHeight} relative`}>
            <RiskMap
              segments={analysis.segments}
              origin={analysis.journey.origin}
              destination={analysis.journey.destination}
              selectedId={selectedId}
              onSelect={setSelectedId}
              userLocation={
                needsLocation
                  ? null
                  : { latitude: location.latitude, longitude: location.longitude, name: location.name }
              }
            />
          </div>
          <p className="mt-2 text-xs text-slate-500 text-center">
            Click a colored segment to inspect it · teal = low risk, red = critical
          </p>
        </div>
        <div>
          <SegmentDetail segment={selected} onSelect={setSelectedId} segments={analysis.segments} />
        </div>
      </div>

      {/* ── Breakdown / alerts / recommendations ── */}
      <div className="grid lg:grid-cols-3 gap-6">
        <RiskBreakdown breakdown={analysis.overall_risk.breakdown} />
        <AlertsList alerts={analysis.alerts} />
        <RecommendationsList recommendations={analysis.recommendations} />
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-widest text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-base font-semibold text-slate-100">{value}</dd>
    </div>
  )
}
