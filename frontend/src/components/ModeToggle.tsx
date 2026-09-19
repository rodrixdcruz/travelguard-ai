import { useTouristLocation } from '../context/LocationContext'

/**
 * Footer mode indicator + switch. LIVE MODE is shown when the app is in
 * live mode; DEMO MODE only when the user explicitly enabled it. Both
 * states expose a one-click switch, as specified.
 */
export default function ModeToggle() {
  const { mode, setMode } = useTouristLocation()

  if (mode === 'live') {
    return (
      <span className="inline-flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-bold tracking-widest text-emerald-300 border border-emerald-400/30 bg-emerald-400/10 rounded px-2 py-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> LIVE MODE
        </span>
        <button
          onClick={() => setMode('demo')}
          className="text-[10px] font-bold tracking-widest text-slate-400 hover:text-slate-200 underline underline-offset-2"
        >
          Use Demo Mode
        </button>
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex items-center gap-1.5 text-[10px] font-bold tracking-widest text-sky-300 border border-sky-400/30 bg-sky-400/10 rounded px-2 py-0.5">
        <span className="w-1.5 h-1.5 rounded-full bg-sky-400" /> DEMO MODE
      </span>
      <button
        onClick={() => setMode('live')}
        className="text-[10px] font-bold tracking-widest text-slate-400 hover:text-slate-200 underline underline-offset-2"
      >
        Switch to Live Mode
      </button>
    </span>
  )
}
