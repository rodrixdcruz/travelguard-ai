import type { Recommendation } from '../types'

export default function RecommendationsList({ recommendations }: { recommendations: Recommendation[] }) {
  return (
    <section className="glass p-5">
      <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-slate-300 mb-4">
        Recommended Actions
      </h2>
      <ol className="space-y-3">
        {recommendations.map((r, i) => (
          <li key={r.id} className="flex gap-3 text-sm">
            <span className="shrink-0 w-6 h-6 rounded-lg bg-cyan-400/10 border border-cyan-400/20 text-cyan-300 text-xs font-bold flex items-center justify-center">
              {i + 1}
            </span>
            <span className="text-slate-300 leading-relaxed">{r.text}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
