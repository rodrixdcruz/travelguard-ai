import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { DEMO_LOCATIONS, type TouristLocation } from '../types/discovery'

interface LocationState {
  location: TouristLocation
  setLocation: (loc: TouristLocation) => void
  sosOpen: boolean
  setSosOpen: (v: boolean) => void
}

const Ctx = createContext<LocationState | null>(null)
const STORAGE_KEY = 'tg_location_v1'

function initial(): TouristLocation {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as TouristLocation
      if (typeof parsed.latitude === 'number') return parsed
    }
  } catch {
    /* ignore */
  }
  return DEMO_LOCATIONS[0]
}

export function TouristLocationProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState<TouristLocation>(initial)
  const [sosOpen, setSosOpen] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(location))
    } catch {
      /* ignore */
    }
  }, [location])

  return (
    <Ctx.Provider value={{ location, setLocation, sosOpen, setSosOpen }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTouristLocation(): LocationState {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useTouristLocation must be used within TouristLocationProvider')
  return ctx
}
