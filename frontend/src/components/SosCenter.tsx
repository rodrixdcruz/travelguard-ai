import { useEffect, useState } from 'react'
import { fetchSosInfo } from '../services/sos'
import { DataBadge } from './DataStatusBadge'
import type { LocalService, SosInfo } from '../types/discovery'

interface SosCenterProps {
  latitude: number | null
  longitude: number | null
  onClose: () => void
}

/**
 * SOS Center — emergency assistance overlay.
 *
 * Shows only verified emergency numbers returned by /api/sos/info. Anything
 * missing is explicitly labelled "unavailable in current data" — never invented.
 */
export default function SosCenter({ latitude, longitude, onClose }: SosCenterProps) {
  const [info, setInfo] = useState<SosInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [shareStatus, setShareStatus] = useState<string | null>(null)
  const [trustedContact, setTrustedContact] = useState('')

  useEffect(() => {
    let alive = true
    fetchSosInfo(latitude ?? undefined, longitude ?? undefined)
      .then((d) => { if (alive) setInfo(d) })
      .catch(() => { if (alive) setError('Emergency data unavailable — still dial 112 for national emergency services.') })
    return () => { alive = false }
  }, [latitude, longitude])

  const shareLocation = () => {
    if (typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          setShareStatus(
            `Live location: ${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)} (±${Math.round(pos.coords.accuracy)} m)`,
          ),
        () =>
          setShareStatus(
            latitude != null && longitude != null
              ? `Browser location denied — using selected map point: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`
              : 'Browser location denied and no map location selected.',
          ),
        { timeout: 8000 },
      )
    } else {
      setShareStatus(
        latitude != null && longitude != null
          ? `Geolocation unavailable — using selected map point: ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`
          : 'Geolocation unavailable and no map location selected.',
      )
    }
  }

  const serviceRow = (label: string, svc: LocalService | undefined) =>
    svc ? (
      <div className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2">
        <div>
          <p className="text-sm font-medium text-white">{svc.name}</p>
          <p className="text-xs text-slate-400">{svc.address} · {svc.distance_km.toFixed(1)} km</p>
        </div>
        <DataBadge status={svc.data_status} />
      </div>
    ) : (
      <div className="rounded-lg bg-white/5 px-3 py-2 text-sm text-slate-400">
        {label}: unavailable in current data.
      </div>
    )

  const numberRow = (key: string, label: string) => {
    const entry = info?.emergency_numbers?.[key]
    if (!entry) {
      return (
        <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <p className="text-sm font-semibold text-white">{label}</p>
          <p className="text-xs text-slate-400">Emergency number unavailable in current data.</p>
        </div>
      )
    }
    return (
      <a
        href={`tel:${entry.number}`}
        className="block rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 transition hover:border-red-400/60 hover:bg-red-500/20"
      >
        <p className="text-sm font-semibold text-white">{label}</p>
        <p className="font-mono text-2xl font-bold text-red-300">{entry.number}</p>
        <p className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
          {entry.source} <DataBadge status={entry.data_status} />
        </p>
      </a>
    )
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-red-400/30 bg-slate-900/95 p-6 shadow-2xl shadow-red-900/30">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">🚨 Emergency Assistance</h2>
            <p className="text-sm text-slate-400">Verified help, one tap away.</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-white/10 px-3 py-1 text-sm text-slate-300 hover:bg-white/10"
          >
            Close
          </button>
        </div>

        {error && (
          <p className="mt-4 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
            {error}
          </p>
        )}

        {/* Verified emergency numbers */}
        <div className="mt-4 grid grid-cols-1 gap-2">
          {numberRow('all_in_one', 'National Emergency Line')}
          {numberRow('police', 'Police')}
          {numberRow('ambulance', 'Ambulance')}
          {numberRow('fire', 'Fire')}
          {numberRow('tourist_help', 'Tourist Help')}
        </div>

        {/* Nearest verified services */}
        {info && (
          <div className="mt-4 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Nearest verified services</p>
            {serviceRow('Nearest hospital', info.nearest.hospital)}
            {serviceRow('Nearest police', info.nearest.police)}
            {serviceRow('Nearest pharmacy', info.nearest.pharmacy)}
          </div>
        )}

        {/* Share location + trusted contact */}
        <div className="mt-4 space-y-2 rounded-xl border border-white/10 bg-white/5 p-3">
          <button
            onClick={shareLocation}
            className="w-full rounded-lg bg-cyan-500/20 px-3 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-500/30"
          >
            📍 Share My Location
          </button>
          {shareStatus && <p className="text-xs text-slate-300">{shareStatus}</p>}
          <div className="flex gap-2">
            <input
              value={trustedContact}
              onChange={(e) => setTrustedContact(e.target.value)}
              placeholder="Trusted contact (phone or email)"
              className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-cyan-400/50 focus:outline-none"
            />
            {trustedContact.trim() && latitude != null && longitude != null && (
              <a
                href={`sms:${encodeURIComponent(trustedContact)}?body=${encodeURIComponent(
                  `I'm travelling. My location: https://maps.google.com/?q=${latitude},${longitude}`,
                )}`}
                className="rounded-lg bg-cyan-500/20 px-3 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-500/30"
              >
                Send
              </a>
            )}
          </div>
          <p className="text-xs text-slate-500">
            The Send link opens your messaging app with your map location pre-filled.
          </p>
        </div>

        {info && (
          <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <DataBadge status={info.data_status} /> {info.note}
          </p>
        )}
      </div>
    </div>
  )
}
