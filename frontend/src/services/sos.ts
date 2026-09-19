/** SOS / emergency-assistance API calls. */

import type { SosInfo } from '../types/discovery'
import { apiConfig } from './api'

export async function fetchSosInfo(lat?: number, lon?: number): Promise<SosInfo> {
  const params = new URLSearchParams()
  if (typeof lat === 'number' && typeof lon === 'number') {
    params.set('latitude', String(lat))
    params.set('longitude', String(lon))
  }
  const res = await fetch(`${apiConfig.API_BASE}/api/sos/info?${params.toString()}`)
  if (!res.ok) throw new Error(`SOS info failed: ${res.status}`)
  return res.json() as Promise<SosInfo>
}
