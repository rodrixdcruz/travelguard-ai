import { useEffect, useState } from 'react'
import { useTouristLocation } from '../context/LocationContext'
import { DEMO_LOCATIONS } from '../types/discovery'

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
 * India ↔ Juhu), so 30 km keeps all of greater Mumbai inside coverage while
 * flagging other cities/regions.
 */
const COVERAGE_LIMIT_KM = 30

/**
 * Gentle notice when the chosen location lies far outside the labeled demo
 * coverage (Mumbai). Live-mode results there depend on open-data availability
 * and may be sparse — this explains why instead of leaving silent empty
 * lists, and reaffirms that demo data is never fabricated for other places.
 * Demo Mode is exempt: it pins a labeled Mumbai location by design.
 */
export default function CoverageNotice() {
  const { mode, location } = useTouristLocation()
  const [dismissed, setDismissed] = useState(false)

  const latKey = Math.round(location.latitude)
  const lonKey = Math.round(location.longitude)

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

  return (
    <div className="mx-auto w-full max-w-7xl px-4 sm:px-6">
      <div className="mt-4 flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-200">
        <span aria-hidden className="mt-0.5">
          📍
        </span>
        <p className="flex-1 leading-relaxed">
          You&apos;re about {Math.round(farKm)} km outside the labeled demo area (Mumbai). Live results here depend on
          open-data availability and may be sparse — demo data only covers Mumbai, so it is never shown for this place.
        </p>
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
