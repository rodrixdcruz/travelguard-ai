import { useEffect, useState, useSyncExternalStore } from 'react'
import { useTouristLocation } from '../context/LocationContext'
import { DEMO_LOCATIONS } from '../types/discovery'
import {
  getDiscoveryOutcomes,
  subscribeDiscoveryOutcomes,
  type DiscoveryOutcome,
} from '../services/discovery'

/** Great-circle distance in km (haversine). */
function distanceKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371
  const dLat = ((bLat - aLat) * Math.PI) / 180
  const dLon = ((bLon - aLon) * Math.PI) / 180
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((aLat * Math.PI) / 180) * Math.cos((bLat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(s))
}

/**
 * Beyond this distance from EVERY labeled demo location, the demo dataset
 * cannot describe the area. The dataset's own points span ~21 km (Gateway of
 * India ↔ Juhu), so 30 km keeps all of greater Mumbai inside coverage.
 */
const COVERAGE_LIMIT_KM = 30

/** Live results at or below this count count as "sparse" for messaging. */
const SPARSE_RESULTS = 3

/**
 * Gentle notice for locations far outside the labeled demo coverage (Mumbai).
 *
 * Results-aware by design: it never fires on distance alone. It appears only
 * once live discovery has actually come back empty or sparse at this place —
 * a far-away city with healthy live results (e.g. Nagpur, 694 km out, 20 live
 * attractions) shows nothing, because nothing is wrong. The message then
 * states exactly what happened and reaffirms that demo data is never
 * fabricated for other places. Demo Mode is exempt: it pins a labeled Mumbai
 * location by design.
 */
export default function CoverageNotice() {
  const { mode, location } = useTouristLocation()
  const [dismissed, setDismissed] = useState(false)

  const latKey = Math.round(location.latitude)
  const lonKey = Math.round(location.longitude)
  const cell = `${latKey}:${lonKey}`

  const outcomes = useSyncExternalStore(subscribeDiscoveryOutcomes, () => getDiscoveryOutcomes(cell))

  // Re-arm the dismissal whenever the place changes (rounded to ~1 km so GPS
  // jitter doesn't nag again) or the mode switches.
  useEffect(() => {
    setDismissed(false)
  }, [latKey, lonKey, mode])

  const farKm =
    mode === 'live' && location.source !== 'unset'
      ? Math.min(...DEMO_LOCATIONS.map((d) => distanceKm(location.latitude, location.longitude, d.latitude, d.longitude)))
      : 0

  if (farKm <= COVERAGE_LIMIT_KM || dismissed) return null

  if (outcomes.length === 0) return null // still loading — don't nag before data arrives

  const empty = outcomes.filter((o) => o.count === 0)
  const emptyKinds = empty.map((o) => o.kind)
  const liveTotal = outcomes.filter((o) => o.status !== 'DEMO').reduce((n, o) => n + o.count, 0)

  if (emptyKinds.length === 0 && liveTotal > SPARSE_RESULTS) return null

  const label: Record<DiscoveryOutcome['kind'], string> = {
    places: 'sightseeing results',
    food: 'food results',
    services: 'helpful-services results',
  }

  let message: string
  if (emptyKinds.length === outcomes.length) {
    message =
      'No open-data results found here yet — this spot is ' +
      `${Math.round(farKm)} km outside the labeled demo area (Mumbai), and demo data is never shown for other places. Try a better-known landmark nearby, or switch on Demo Mode to explore the labeled dataset.`
  } else if (emptyKinds.length > 0) {
    message =
      `${Math.round(farKm)} km from the labeled demo area (Mumbai): live results here depend on open-data availability — ` +
      `${label[emptyKinds[0]]}${emptyKinds.length > 1 ? ` and ${emptyKinds.slice(1).map((k) => label[k]).join(' and ')}` : ''} came back empty. What loaded below is live; demo data is never shown for this place.`
  } else {
    message =
      `Only ${liveTotal} live result${liveTotal === 1 ? '' : 's'} found here — ` +
      `${Math.round(farKm)} km outside the labeled demo area (Mumbai), open-data coverage can be thin. Demo data is never shown for this place.`
  }

  return (
    <div className="mx-auto w-full max-w-7xl px-4 sm:px-6">
      <div className="mt-4 flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-200">
        <span aria-hidden className="mt-0.5">
          📍
        </span>
        <p className="flex-1 leading-relaxed">{message}</p>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Dismiss notice"
          title="Dismiss"
          className="mt-0.5 w-5 h-5 leading-none rounded text-amber-300/70 hover:text-amber-200 hover:bg-amber-400/10 transition-colors"
        >
          ×
        </button>
      </div>
    </div>
  )
}
