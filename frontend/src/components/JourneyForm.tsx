import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyzeJourney, fetchBriefing } from '../services/api'
import { useJourney } from '../context/JourneyContext'

export const LOADING_STEPS = [
  'Finding route…',
  'Analyzing weather…',
  'Checking road conditions…',
  'Checking accident risk…',
  'Calculating journey risk…',
  'Preparing safety briefing…',
]

const SUGGESTIONS = ['Mumbai', 'Pune', 'Delhi', 'Jaipur', 'Bengaluru', 'Mysuru', 'Chennai', 'Hyderabad']

function defaultDate(): string {
  const d = new Date(Date.now() + 24 * 3600 * 1000)
  return d.toISOString().slice(0, 10)
}

export default function JourneyForm({ compact = false }: { compact?: boolean }) {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [date, setDate] = useState(defaultDate())
  const [time, setTime] = useState('09:00')
  const [localError, setLocalError] = useState<string | null>(null)
  const { loading, loadingStep, setLoading, error, setError, setAnalysis, setBriefing } = useJourney()
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLocalError(null)
    if (!origin.trim() || !destination.trim()) {
      setLocalError('Enter both origin and destination.')
      return
    }
    if (origin.trim().toLowerCase() === destination.trim().toLowerCase()) {
      setLocalError('Origin and destination must be different.')
      return
    }

    setError(null)
    setLoading(true, 0)

    let step = 0
    const advance = setInterval(() => {
      step = Math.min(step + 1, LOADING_STEPS.length - 1)
      setLoading(true, step)
    }, 420)

    try {
      const result = await analyzeJourney({
        origin: origin.trim(),
        destination: destination.trim(),
        date,
        time,
      })
      setAnalysis(result)

      try {
        const b = await fetchBriefing(result)
        setBriefing(b.briefing, b.source)
      } catch {
        setBriefing('Briefing unavailable — see segment details below.', 'fallback')
      }

      clearInterval(advance)
      setLoading(false, 0)
      navigate('/plan')
    } catch (err) {
      clearInterval(advance)
      const message = err instanceof Error ? err.message : 'Analysis failed'
      setError(
        message.includes('Failed to fetch')
          ? 'Cannot reach the backend. Is it running on the configured API URL?'
          : message,
      )
      setLoading(false, 0)
    }
  }

  const shownError = localError ?? error

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className={compact ? 'space-y-4' : 'grid md:grid-cols-2 gap-4'}>
        <div>
          <label className="label" htmlFor="origin">Origin</label>
          <input
            id="origin" list="city-suggestions" className="field" placeholder="e.g. Mumbai"
            value={origin} onChange={(e) => setOrigin(e.target.value)} disabled={loading}
          />
        </div>
        <div>
          <label className="label" htmlFor="destination">Destination</label>
          <input
            id="destination" list="city-suggestions" className="field" placeholder="e.g. Pune"
            value={destination} onChange={(e) => setDestination(e.target.value)} disabled={loading}
          />
        </div>
        <div className="grid grid-cols-2 gap-4 md:col-span-2">
          <div>
            <label className="label" htmlFor="date">Date</label>
            <input
              id="date" type="date" className="field" value={date}
              onChange={(e) => setDate(e.target.value)} disabled={loading}
            />
          </div>
          <div>
            <label className="label" htmlFor="time">Time</label>
            <input
              id="time" type="time" className="field" value={time}
              onChange={(e) => setTime(e.target.value)} disabled={loading}
            />
          </div>
        </div>
      </div>

      <datalist id="city-suggestions">
        {SUGGESTIONS.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      {shownError && (
        <p className="text-sm text-red-300 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
          {shownError}
        </p>
      )}

      <button type="submit" className="btn-primary" disabled={loading}>
        {loading ? 'Analyzing…' : '⚡ Analyze Journey'}
      </button>

      {loading && (
        <div className="glass p-4 space-y-2.5" aria-live="polite">
          {LOADING_STEPS.map((s, i) => (
            <div
              key={s}
              className={`flex items-center gap-2.5 text-sm transition-opacity duration-300 ${
                i < loadingStep ? 'opacity-60' : i === loadingStep ? 'opacity-100' : 'opacity-30'
              }`}
            >
              <span
                className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                  i < loadingStep
                    ? 'bg-cyan-400 border-cyan-400'
                    : i === loadingStep
                      ? 'border-cyan-400'
                      : 'border-slate-600'
                }`}
              >
                {i < loadingStep && (
                  <svg viewBox="0 0 12 12" className="w-2.5 h-2.5 text-ink-950" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M2 6l3 3 5-6" />
                  </svg>
                )}
              </span>
              <span className={i === loadingStep ? 'text-cyan-300 font-medium' : 'text-slate-400'}>{s}</span>
            </div>
          ))}
        </div>
      )}
    </form>
  )
}
