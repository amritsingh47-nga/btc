import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { PageTitle, Degraded } from '../components/Shell'
import { Sparkline } from '../components/CandleChart'
import { fmt, pctClass, usePoll } from '../lib/api'

export default function CryptoPage() {
  const { data: markets } = usePoll<any>('/api/modules/crypto/markets?limit=25', 120000)
  const { data: trending } = usePoll<any>('/api/modules/crypto/trending', 600000)
  const { data: fng } = usePoll<any>('/api/modules/crypto/fear-greed', 3600000)
  const [coin, setCoin] = useState<string | null>(null)
  const { data: chart } = usePoll<any>(
    coin ? `/api/modules/crypto/chart/${coin}?days=30` : null,
    600000
  )

  return (
    <div className="space-y-5">
      <PageTitle title="Crypto" subtitle="CoinGecko free API (keyless) + Fear & Greed Index. No Binance anywhere." />

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="card lg:col-span-2 overflow-x-auto">
          {markets && !markets.available && <Degraded reason={markets.reason} />}
          <table className="data w-full">
            <thead>
              <tr>
                <th>#</th>
                <th>Coin</th>
                <th>Price</th>
                <th>24h %</th>
                <th>7d %</th>
                <th>7d</th>
                <th>Mkt cap</th>
              </tr>
            </thead>
            <tbody>
              {(markets?.coins ?? []).map((c: any) => (
                <tr
                  key={c.id}
                  className="cursor-pointer hover:bg-zinc-900/60"
                  onClick={() => setCoin(c.id)}
                >
                  <td className="text-zinc-500">{c.rank}</td>
                  <td className="font-semibold">
                    {c.name} <span className="text-zinc-500">{c.symbol}</span>
                  </td>
                  <td>${fmt(c.price, c.price < 1 ? 4 : 2)}</td>
                  <td className={pctClass(c.change_24h_pct)}>
                    {c.change_24h_pct != null ? `${fmt(c.change_24h_pct)}%` : '—'}
                  </td>
                  <td className={pctClass(c.change_7d_pct)}>
                    {c.change_7d_pct != null ? `${fmt(c.change_7d_pct)}%` : '—'}
                  </td>
                  <td><Sparkline values={c.sparkline_7d ?? []} width={90} height={24} /></td>
                  <td className="text-zinc-400">${fmt((c.market_cap ?? 0) / 1e9, 1)}B</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-5">
          <div className="card">
            <h2 className="mb-2 text-sm font-semibold text-zinc-300">Fear &amp; Greed</h2>
            {fng?.available && fng.current ? (
              <FearGreedGauge value={fng.current.value} label={fng.current.label} />
            ) : (
              <Degraded reason={fng?.reason} />
            )}
          </div>
          <div className="card">
            <h2 className="mb-2 text-sm font-semibold text-zinc-300">Trending</h2>
            {trending?.available ? (
              <ul className="space-y-1.5 text-sm">
                {(trending.trending ?? []).slice(0, 8).map((t: any) => (
                  <li
                    key={t.id}
                    className="flex cursor-pointer items-center gap-2 text-zinc-300 hover:text-white"
                    onClick={() => setCoin(t.id)}
                  >
                    {t.thumb && <img src={t.thumb} alt="" className="h-4 w-4 rounded-full" />}
                    {t.name}
                    <span className="text-xs text-zinc-500">#{t.rank ?? '—'}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Degraded reason={trending?.reason} />
            )}
          </div>
        </div>
      </div>

      {coin && (
        <div className="card">
          <div className="mb-2 flex items-center">
            <h2 className="text-sm font-semibold">{coin} — 30 days</h2>
            <button className="btn ml-auto text-xs" onClick={() => setCoin(null)}>
              Close
            </button>
          </div>
          {chart?.available ? (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart
                data={(chart.prices ?? []).map((p: [number, number]) => ({
                  time: new Date(p[0]).toISOString().slice(5, 10),
                  price: p[1],
                }))}
              >
                <XAxis dataKey="time" stroke="#52525b" fontSize={10} minTickGap={40} />
                <YAxis stroke="#52525b" fontSize={10} domain={['auto', 'auto']} width={70} />
                <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46' }} />
                <Line type="monotone" dataKey="price" stroke="#10b981" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="py-16 text-center text-sm text-zinc-500">
              {chart ? chart.reason ?? 'No data' : 'Loading…'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FearGreedGauge({ value, label }: { value: number; label: string }) {
  const angle = (value / 100) * 180 - 90
  const color =
    value >= 60 ? '#10b981' : value >= 40 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex flex-col items-center py-2">
      <svg width="160" height="90" viewBox="0 0 160 90">
        <path d="M 10 85 A 70 70 0 0 1 150 85" fill="none" stroke="#3f3f46" strokeWidth="10" strokeLinecap="round" />
        <path
          d="M 10 85 A 70 70 0 0 1 150 85"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(value / 100) * 220} 400`}
        />
        <line
          x1="80"
          y1="85"
          x2={80 + 55 * Math.sin((angle * Math.PI) / 180)}
          y2={85 - 55 * Math.cos((angle * Math.PI) / 180)}
          stroke="#e4e4e7"
          strokeWidth="2.5"
        />
      </svg>
      <div className="text-2xl font-bold" style={{ color }}>{value}</div>
      <div className="text-sm text-zinc-400">{label}</div>
    </div>
  )
}
