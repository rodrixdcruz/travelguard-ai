import { Link, Outlet, useLocation } from 'react-router-dom'
import { useTouristLocation } from '../context/LocationContext'
import SosCenter from '../components/SosCenter'

const NAV = [
  { to: '/', label: 'Home' },
  { to: '/near-me', label: 'Near Me' },
  { to: '/plan-day', label: 'Plan My Day' },
  { to: '/food', label: 'Food' },
  { to: '/safety', label: 'Safety' },
  { to: '/plan', label: 'Road Risk' },
  { to: '/assistant', label: 'AI Assistant' },
  { to: '/settings', label: 'Settings' },
]

export default function AppLayout() {
  const { pathname } = useLocation()
  const { sosOpen, setSosOpen, location } = useTouristLocation()

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-40 border-b border-white/5 bg-ink-950/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-glow">
              <svg viewBox="0 0 24 24" className="w-5 h-5 text-white" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z" />
                <path d="M9 12l2 2 4-4" />
              </svg>
            </div>
            <div className="leading-tight">
              <div className="font-display font-bold tracking-tight text-slate-100 group-hover:text-cyan-300 transition-colors">
                TravelGuard <span className="text-cyan-400">AI</span>
              </div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">
                Explore smarter. Travel with confidence.
              </div>
            </div>
          </Link>

          <nav className="hidden lg:flex items-center gap-1">
            {NAV.map((item) => {
              const active = item.to === '/' ? pathname === '/' : pathname.startsWith(item.to)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    active
                      ? 'text-cyan-300 bg-cyan-400/10 border border-cyan-400/20'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
                  }`}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>

          {/* SOS — always visible */}
          <button
            onClick={() => setSosOpen(true)}
            className="shrink-0 px-4 py-2 rounded-xl text-xs font-bold tracking-widest bg-red-500/15 border border-red-400/40 text-red-300 hover:bg-red-500/25 transition-colors"
          >
            🚨 SOS
          </button>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-white/5 py-4 text-center text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5 text-[10px] font-bold tracking-widest text-sky-300 border border-sky-400/30 bg-sky-400/10 rounded px-2 py-0.5 mr-2">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400" /> DEMO MODE
        </span>
        Places, food &amp; services are DEMO data · transport, meal costs &amp; weather context are ESTIMATED ·
        Not a substitute for official advisories
      </footer>

      {sosOpen && (
        <SosCenter latitude={location.latitude} longitude={location.longitude} onClose={() => setSosOpen(false)} />
      )}
    </div>
  )
}
