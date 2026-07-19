import { NavLink, Outlet } from 'react-router-dom'
import {
  CandlestickChart,
  LineChart,
  Bitcoin,
  Landmark,
  Newspaper,
  Briefcase,
  Settings,
  ShieldCheck,
  FlaskConical,
} from 'lucide-react'
import { usePoll } from '../lib/api'

const nav = [
  { to: '/futures', label: 'Futures Signals', icon: CandlestickChart },
  { to: '/stocks', label: 'Stocks', icon: LineChart },
  { to: '/crypto', label: 'Crypto', icon: Bitcoin },
  { to: '/macro', label: 'Macro', icon: Landmark },
  { to: '/news', label: 'News', icon: Newspaper },
  { to: '/portfolio', label: 'Portfolio', icon: Briefcase },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Shell() {
  const { data: overview } = usePoll<any>('/api/modules/futures/overview', 15000)

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r border-zinc-800 bg-zinc-950 p-4 flex flex-col gap-6 sticky top-0 h-screen">
        <div>
          <div className="text-lg font-bold tracking-tight">Analysts Bot</div>
          <div className="mt-1 flex items-center gap-1 text-xs text-emerald-400">
            <ShieldCheck size={14} /> Signals only — never trades
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-zinc-800 text-white'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100'
                }`
              }
            >
              <Icon size={16} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-2 text-xs text-zinc-500">
          {overview?.synthetic && (
            <div className="badge bg-amber-950 text-amber-400 border border-amber-800">
              <FlaskConical size={12} /> SYNTHETIC DEMO DATA
            </div>
          )}
          <div>
            Cycle #{overview?.cycle ?? '—'} · every{' '}
            {overview?.cycle_interval_minutes ?? '—'}m
          </div>
          <div>
            Engine:{' '}
            <span
              className={
                overview?.is_running ? 'text-emerald-400' : 'text-zinc-400'
              }
            >
              {overview?.is_running ? overview?.execution_mode ?? 'running' : 'stopped'}
            </span>
          </div>
          <div className="text-zinc-600">
            Not financial advice. Hypothetical signals on ~15-min delayed data.
          </div>
        </div>
      </aside>
      <main className="flex-1 min-w-0 p-6">
        <Outlet />
      </main>
    </div>
  )
}

export function PageTitle({
  title,
  subtitle,
}: {
  title: string
  subtitle?: string
}) {
  return (
    <div className="mb-5">
      <h1 className="text-xl font-bold tracking-tight">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-zinc-400">{subtitle}</p>}
    </div>
  )
}

export function Degraded({ reason }: { reason?: string }) {
  return (
    <div className="card border-amber-900/60 bg-amber-950/20 text-sm text-amber-300">
      Feature degraded: {reason ?? 'upstream API unavailable'}. The app keeps
      running — add the missing free API key in .env or check connectivity.
    </div>
  )
}
