import type { DataStatus } from '../types/discovery'

const STYLES: Record<DataStatus, string> = {
  LIVE: 'text-emerald-300 border-emerald-400/40 bg-emerald-400/10',
  DEMO: 'text-sky-300 border-sky-400/40 bg-sky-400/10',
  ESTIMATED: 'text-amber-300 border-amber-400/40 bg-amber-400/10',
  UNAVAILABLE: 'text-slate-400 border-white/15 bg-white/5',
}

/** Compact inline badge — visually distinguishes demo/estimated from live. */
export function DataBadge({ status }: { status: DataStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold tracking-widest border ${STYLES[status] ?? STYLES.UNAVAILABLE}`}
      title={
        status === 'LIVE'
          ? 'Obtained from a live data provider'
          : status === 'DEMO'
            ? 'Demo dataset — representative sample, not a live record'
            : status === 'ESTIMATED'
              ? 'Modeled estimate — not an actual quote'
              : 'Not available in current data'
      }
    >
      {status} DATA
    </span>
  )
}

/** Opening status chip: open/closed/unknown with honest unknown state. */
export function OpeningChip({ status }: { status: string | null | undefined }) {
  const s = (status ?? 'unknown').toLowerCase()
  const style =
    s === 'open'
      ? 'text-emerald-300 border-emerald-400/30 bg-emerald-400/10'
      : s === 'closed'
        ? 'text-red-300 border-red-400/30 bg-red-400/10'
        : 'text-slate-400 border-white/15 bg-white/5'
  const label = s === 'open' ? 'Open' : s === 'closed' ? 'Closed' : 'Unknown'
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold tracking-widest border ${style}`}>
      {label}
    </span>
  )
}
