import { useEffect, useRef, useState } from 'react'
import { searchPlaces } from '../services/discovery'
import { type GeoSearchResult, type TouristLocation } from '../types/discovery'
import { useTouristLocation } from '../context/LocationContext'

/**
 * Honest place search ("Set your location"): type a place name, pick a real
 * result geocoded via OpenStreetMap Nominatim through the backend. Selecting
 * one sets the location with source 'search' — real coordinates, labeled
 * SELECTED. Never silently substitutes a demo city.
 */
export default function LocationSearch() {
  const { mode, setLocation } = useTouristLocation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GeoSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 3) {
      setResults([])
      setOpen(false)
      setMsg(null)
      return
    }
    let alive = true
    setBusy(true)
    const t = setTimeout(() => {
      searchPlaces(q)
        .then((r) => {
          if (!alive) return
          setResults(r.results)
          setOpen(true)
          setMsg(r.results.length ? null : 'No matches — check the spelling or add the state.')
        })
        .catch(() => alive && setMsg('Place search unavailable — use GPS or the demo places below.'))
        .finally(() => alive && setBusy(false))
    }, 350)
    return () => {
      alive = false
      clearTimeout(t)
    }
  }, [query])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  if (mode === 'demo') {
    return (
      <p className="text-[11px] text-slate-500 border border-white/10 rounded-xl px-3 py-2">
        Demo Mode uses labeled demo places only. Switch to Live Mode to search any real place.
      </p>
    )
  }

  function pick(r: GeoSearchResult) {
    const loc: TouristLocation = {
      latitude: r.latitude,
      longitude: r.longitude,
      name: r.short_name || r.name.split(',')[0],
      source: 'search',
    }
    setLocation(loc)
    setQuery('')
    setResults([])
    setOpen(false)
    setMsg(null)
  }

  return (
    <div ref={boxRef} className="relative">
      <input
        className="field !py-2.5 !text-xs w-full"
        placeholder="Search any place — city, town, landmark…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        aria-label="Search a place by name"
      />
      {busy && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-slate-500 animate-pulse">
          searching…
        </span>
      )}
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-slate-900/95 backdrop-blur shadow-xl">
          {results.map((r, i) => (
            <li key={`${r.latitude},${r.longitude},${i}`}>
              <button
                onClick={() => pick(r)}
                className="w-full text-left px-3 py-2 hover:bg-cyan-400/10 border-b border-white/5 last:border-0"
              >
                <div className="text-xs text-slate-200 truncate">{r.short_name || r.name.split(',')[0]}</div>
                <div className="text-[10px] text-slate-500 truncate">{r.name}</div>
              </button>
            </li>
          ))}
        </ul>
      )}
      {msg && <p className="mt-1 text-[10px] text-slate-500">{msg}</p>}
    </div>
  )
}
