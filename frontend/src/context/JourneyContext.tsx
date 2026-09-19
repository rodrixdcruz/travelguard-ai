import { createContext, useContext, useState, type ReactNode } from 'react'
import type { AnalyzeResponse, HistoryEntry } from '../types'

interface JourneyState {
  analysis: AnalyzeResponse | null
  briefing: string | null
  briefingSource: string | null
  loading: boolean
  loadingStep: number
  error: string | null
  history: HistoryEntry[]
  setAnalysis: (a: AnalyzeResponse) => void
  setBriefing: (b: string, source: string) => void
  setLoading: (v: boolean, step?: number) => void
  setError: (e: string | null) => void
  clear: () => void
}

const Ctx = createContext<JourneyState | null>(null)

export function JourneyProvider({ children }: { children: ReactNode }) {
  const [analysis, setAnalysisState] = useState<AnalyzeResponse | null>(null)
  const [briefing, setBriefingState] = useState<string | null>(null)
  const [briefingSource, setBriefingSource] = useState<string | null>(null)
  const [loading, setLoadingState] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])

  const value: JourneyState = {
    analysis,
    briefing,
    briefingSource,
    loading,
    loadingStep,
    error,
    history,
    setAnalysis: (a) => {
      setAnalysisState(a)
      const entry: HistoryEntry = {
        id: `${a.generated_at}`,
        origin: a.journey.origin.name,
        destination: a.journey.destination.name,
        date: a.journey.date,
        time: a.journey.time,
        score: a.overall_risk.score,
        level: a.overall_risk.level,
        ts: Date.now(),
      }
      setHistory((h) => [entry, ...h].slice(0, 20))
    },
    setBriefing: (b, source) => {
      setBriefingState(b)
      setBriefingSource(source)
    },
    setLoading: (v, step) => {
      setLoadingState(v)
      if (step !== undefined) setLoadingStep(step)
    },
    setError,
    clear: () => {
      setAnalysisState(null)
      setBriefingState(null)
      setBriefingSource(null)
      setError(null)
      setLoadingState(false)
      setLoadingStep(0)
    },
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useJourney(): JourneyState {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useJourney must be used within JourneyProvider')
  return ctx
}
