/**
 * One consistent data-source line, rendered from the response-level
 * `provider_summary` the backend derives from what actually served the
 * request. Never hardcoded — when the summary is missing the component
 * renders nothing rather than inventing a claim.
 */
export interface ProviderSummary {
  status: string
  sources: string[]
  line: string
}

const STATUS_STYLES: Record<string, string> = {
  LIVE: 'text-emerald-300',
  MIXED: 'text-cyan-300',
  ESTIMATED: 'text-amber-300',
  DEMO: 'text-slate-400',
  UNAVAILABLE: 'text-rose-300',
}

export function providerSummaryLine(summary: ProviderSummary | null | undefined): string {
  return summary?.line ?? ''
}

export function ProviderSummaryLine({ summary }: { summary: ProviderSummary | null | undefined }) {
  if (!summary?.line) return null
  const color = STATUS_STYLES[summary.status] ?? 'text-slate-400'
  return (
    <p className="text-[11px] text-slate-500">
      <span className={`font-semibold uppercase tracking-wider ${color}`}>{summary.status}</span>
      <span className="mx-1.5 text-slate-600">·</span>
      {summary.line}
    </p>
  )
}
