import JourneyForm from '../components/JourneyForm'
import ResultsView from '../components/ResultsView'
import Panel from '../components/Panel'
import { useJourney } from '../context/JourneyContext'

export default function PlanJourney() {
  const { analysis, clear } = useJourney()

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-100">Plan Journey</h1>
          <p className="text-sm text-slate-400 mt-1">Analyze a route before you travel.</p>
        </div>
        {analysis && (
          <button
            onClick={clear}
            className="text-sm text-slate-400 border border-white/10 rounded-lg px-3.5 py-2 hover:text-slate-200 hover:border-cyan-400/30 transition-colors"
          >
            New analysis
          </button>
        )}
      </div>
      <div className="grid lg:grid-cols-3 gap-6 items-start">
        <Panel className="lg:col-span-1">
          <JourneyForm compact />
        </Panel>
        <div className="lg:col-span-2">
          {analysis ? (
            <ResultsView mapHeight="h-[360px]" />
          ) : (
            <Panel className="h-full flex items-center justify-center text-center min-h-[320px]">
              <div>
                <p className="text-slate-400 text-sm">No analysis yet.</p>
                <p className="text-slate-500 text-xs mt-1">Enter a route and press Analyze Journey.</p>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}
