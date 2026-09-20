import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { DEMO_LOCATIONS, type TouristLocation } from '../types/discovery'

/**
 * Data mode + location state.
 *
 * LIVE is the default experience: the app never initializes as Mumbai demo
 * mode. On first visit the app asks the browser for geolocation; if that is
 * denied or unavailable the user gets an explicit choice — manual
 * coordinates or the labeled demo dataset — never a silent Mumbai fallback.
 * Demo data is used only when the user explicitly enables Demo Mode (or a
 * specific provider falls back, which is labeled in the response payload).
 */
export type DataMode = 'live' | 'demo'

/** Sentinel until the user grants geolocation or picks a location manually. */
export const UNSET_LOCATION: TouristLocation = {
  latitude: 0,
  longitude: 0,
  name: 'Set your location',
  source: 'unset',
}

export interface LocationState {
  mode: DataMode
  setMode: (m: DataMode) => void
  location: TouristLocation
  /** True in live mode when no real location exists yet (never silent Mumbai). */
  needsLocation: boolean
  /** Set the current location; persists unless the demo dataset supplies it. */
  setLocation: (loc: TouristLocation, opts?: { persist?: boolean }) => void
  /** True once the initial geolocation attempt has resolved (either way). */
  locationReady: boolean
  sosOpen: boolean
  setSosOpen: (v: boolean) => void
}

const Ctx = createContext<LocationState | null>(null)

// v2: the v1 key could hold a pre-live-mode DEMO location (Mumbai), which
// suppressed geolocation forever — "stuck in Mumbai". Bumping the key makes
// every existing visitor re-resolve honestly (GPS prompt or explicit choice).
const LOC_STORAGE_KEY = 'tg_location_v2'
const MODE_STORAGE_KEY = 'tg_data_mode_v1'

function initialMode(): DataMode {
  try {
    const stored = localStorage.getItem(MODE_STORAGE_KEY)
    if (stored === 'demo' || stored === 'live') return stored
  } catch {
    /* ignore */
  }
  return 'live'
}

/** Never silently Mumbai: no stored location → unknown until geolocation resolves. */
function initialLocation(): TouristLocation | null {
  try {
    const raw = localStorage.getItem(LOC_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as TouristLocation
      if (typeof parsed.latitude === 'number' && typeof parsed.longitude === 'number') return parsed
    }
  } catch {
    /* ignore */
  }
  return null
}

export function TouristLocationProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DataMode>(initialMode)
  const [location, setLocationState] = useState<TouristLocation | null>(initialLocation)
  const [locationReady, setLocationReady] = useState(false)
  const [sosOpen, setSosOpen] = useState(false)

  const setMode = (m: DataMode) => {
    setModeState(m)
    try {
      localStorage.setItem(MODE_STORAGE_KEY, m)
    } catch {
      /* ignore */
    }
    // Leaving Demo Mode must not leave demo-Mumbai as the user's location.
    if (m === 'live' && location?.source === 'demo') {
      setLocationState(null)
      try {
        localStorage.removeItem(LOC_STORAGE_KEY)
      } catch {
        /* ignore */
      }
      setLocationReady(false)
    }
  }

  const setLocation = (loc: TouristLocation, opts?: { persist?: boolean }) => {
    setLocationState(loc)
    if (opts?.persist !== false) {
      try {
        localStorage.setItem(LOC_STORAGE_KEY, JSON.stringify(loc))
      } catch {
        /* ignore */
      }
    }
  }

  // Initial geolocation: only in live mode, only when no stored location.
  useEffect(() => {
    if (location !== null) {
      setLocationReady(true)
      return
    }
    if (mode !== 'live' || !navigator.geolocation) {
      setLocationReady(true)
      return
    }
    let cancelled = false
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        if (cancelled) return
        setLocation(
          {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            name: 'Your location',
            source: 'browser',
          },
          { persist: false },
        )
        setLocationReady(true)
      },
      () => {
        // Denied/unavailable: stay unknown — the UI shows the explicit
        // manual-entry choice. Never silently switch to Mumbai.
        if (!cancelled) setLocationReady(true)
      },
      { timeout: 8000, maximumAge: 60000 },
    )
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value: LocationState = {
    mode,
    setMode,
    // Demo mode always pins the demo dataset's first location (explicitly
    // labeled); live mode uses the resolved/selected location, or the unset
    // sentinel until the user grants geolocation or picks one manually.
    location: mode === 'demo' ? DEMO_LOCATIONS[0] : (location ?? UNSET_LOCATION),
    needsLocation: mode === 'live' && location === null,
    setLocation,
    locationReady,
    sosOpen,
    setSosOpen,
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useTouristLocation(): LocationState {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTouristLocation must be used within TouristLocationProvider')
  return ctx
}
