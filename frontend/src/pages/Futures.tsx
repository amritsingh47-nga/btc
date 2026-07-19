import { useMemo, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { PageTitle } from '../components/Shell'
import { CandleChart } from '../components/CandleChart'
import { fmt, pctClass, usePoll } from '../lib/api'

const INTERVALS = ['15m', '1h', '5m'] as const

export default function FuturesPage() {
  const { data: overview } = usePoll<any>('/api/modules/futures/overview', 10000)
  const { data: decisions } = usePoll<any>('/api/modules/futures/decisions?limit=60', 15000)
  const { data: feed } = usePoll<any>('/api/modules/futures/feed?limit=120', 8000)
  const { data: pnl } = usePoll<any>('/api/modules/futures/pnl-curve', 20000)

  const symbols: any[] = overview?.symbols ?? []
  const [active, setActive] = useState<string | null>(null)
  const [interval, setInterval_] = useState<(typeof INTERVALS)[number]>('15m')
  const activeSymbol = active ?? symbols[0]?.symbol ?? 'NQ=F'

  const { data: chart } = usePoll<any>(
    `/api/modules/futures/candles/${encodeURIComponent(activeSymbol)}?interval=${interval}&limit=200`,
    30000
  )

  const va = overview?.virtual_account
  const equitySeries = useMemo(
    () =>
      (pnl?.equity_history ?? []).map((p: any) => ({
        time: String(p.time).slice(5, 16),
        value: p.value,
      })),
    [pnl]
  )

  return (
    <div className="space-y-5">
      <PageTitle
        title="Futures Signals"
        subtitle="NQ · MES (via ES) · GOLD · USOIL — every 15 minutes the agents post what they WOULD trade. Nothing is ever executed."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Virtual balance" value={`$${fmt(va?.balance)}`} />
        <Stat label="Equity" value={`$${fmt(va?.equity)}`} />
        <Stat
          label="Total P&L (hypothetical)"
          value={`$${fmt(va?.total_pnl)}`}
          className={pctClass(va?.total_pnl)}
        />
        <Stat label="Realized P&L" value={`$${fmt(va?.realized_pnl)}`} className={pctClass(va?.realized_pnl)} />
        <Stat label="Cycle" value={`#${overview?.cycle ?? '—'}`} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {symbols.map((s) => (
          <button
            key={s.symbol}
            onClick={() => setActive(s.symbol)}
            className={`btn ${activeSymbol === s.symbol ? 'btn-primary' : ''}`}
            title={s.name}
          >
            {s.display}
            <span className="text-xs opacity-75">{s.price ? fmt(s.price) : ''}</span>
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1">
          {INTERVALS.map((iv) => (
            <button
              key={iv}
              onClick={() => setInterval_(iv)}
              className={`btn text-xs ${interval === iv ? 'btn-primary' : ''}`}
            >
              {iv}
              {iv === '5m' && <span className="text-[10px] opacity-75">advisory</span>}
            </button>
          ))}
        </div>
      </div>

      {interval === '5m' && (
        <div className="text-xs text-amber-400">
          ⚠️ 5m is ADVISORY-ONLY: yfinance data is ~15 minutes delayed, so 5m
          triggers describe the past, not the tape.
        </div>
      )}

      <div className="card">
        {chart?.available ? (
          <CandleChart candles={chart.candles} markers={chart.markers} />
        ) : (
          <div className="py-24 text-center text-sm text-zinc-500">
            {chart ? `No chart data: ${chart.reason ?? 'unavailable'}` : 'Loading chart…'}
          </div>
        )}
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="card">
          <h2 className="mb-3 text-sm font-semibold text-zinc-300">
            Hypothetical P&L curve (signal quality tracker)
          </h2>
          {equitySeries.length > 1 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={equitySeries}>
                <XAxis dataKey="time" stroke="#52525b" fontSize={10} minTickGap={40} />
                <YAxis stroke="#52525b" fontSize={10} domain={['auto', 'auto']} width={60} />
                <Tooltip
                  contentStyle={{ background: '#18181b', border: '1px solid #3f3f46' }}
                />
                <ReferenceLine
                  y={pnl?.initial_balance ?? 1000}
                  stroke="#71717a"
                  strokeDasharray="4 4"
                />
                <Line type="monotone" dataKey="value" stroke="#10b981" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="py-16 text-center text-sm text-zinc-500">
              The curve appears after a few cycles. It exists so you can judge
              signal quality over weeks before any real money follows anything.
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="mb-3 text-sm font-semibold text-zinc-300">
            Live agent feed
          </h2>
          <div className="h-56 space-y-1 overflow-y-auto font-mono text-xs text-zinc-400">
            {(feed?.agent_messages ?? [])
              .slice()
              .reverse()
              .map((m: any, i: number) => (
                <div key={i} className="flex gap-2">
                  <span className="shrink-0 text-zinc-600">{m.time ?? m.timestamp ?? ''}</span>
                  <span className="shrink-0 text-emerald-500">[{m.agent ?? 'system'}]</span>
                  <span className="break-all">{m.message ?? m.text ?? ''}</span>
                </div>
              ))}
            {!feed?.agent_messages?.length && (
              <div className="py-16 text-center text-zinc-500">
                Agent chatter appears here once the engine is running.
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">Decisions</h2>
        <table className="data w-full">
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Action</th>
              <th>Confidence</th>
              <th>Risk audit</th>
              <th>Regime</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {(decisions?.decisions ?? []).map((d: any, i: number) => (
              <tr key={i} className="hover:bg-zinc-900/60">
                <td className="whitespace-nowrap text-zinc-400">{d.time}</td>
                <td className="font-semibold">{d.display}</td>
                <td>
                  <ActionBadge action={d.action} />
                </td>
                <td>{d.confidence != null ? `${Math.round(d.confidence)}%` : '—'}</td>
                <td>
                  <span
                    className={`badge ${
                      d.risk_label === 'PASS'
                        ? 'bg-emerald-950 text-emerald-400'
                        : 'bg-amber-950 text-amber-400'
                    }`}
                  >
                    {d.risk_label}
                  </span>
                </td>
                <td className="text-zinc-400">{d.regime ?? '—'}</td>
                <td className="max-w-md truncate text-zinc-400" title={d.reason}>
                  {d.reason}
                </td>
              </tr>
            ))}
            {!decisions?.decisions?.length && (
              <tr>
                <td colSpan={7} className="py-10 text-center text-zinc-500">
                  No decisions yet — they appear after the first cycle.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Stat({
  label,
  value,
  className = '',
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className="card">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`mt-1 text-lg font-bold ${className}`}>{value}</div>
    </div>
  )
}

function ActionBadge({ action }: { action: string }) {
  const a = String(action ?? '').toLowerCase()
  if (a === 'open_long')
    return <span className="badge bg-emerald-950 text-emerald-400">LONG</span>
  if (a === 'open_short')
    return <span className="badge bg-red-950 text-red-400">SHORT</span>
  if (a.startsWith('close'))
    return <span className="badge bg-blue-950 text-blue-400">CLOSE</span>
  return <span className="badge bg-zinc-800 text-zinc-400">WAIT</span>
}
