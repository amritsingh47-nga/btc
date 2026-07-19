import { useState } from 'react'
import { PageTitle, Degraded } from '../components/Shell'
import { CandleChart, Sparkline } from '../components/CandleChart'
import { apiSend, fmt, pctClass, usePoll } from '../lib/api'

export default function StocksPage() {
  const { data: quotes } = usePoll<any>('/api/modules/stocks/quotes', 60000)
  const { data: earnings } = usePoll<any>('/api/modules/stocks/earnings', 6 * 3600 * 1000)
  const [selected, setSelected] = useState<string | null>(null)
  const [interval, setInterval_] = useState('1d')
  const [newTicker, setNewTicker] = useState('')
  const [busy, setBusy] = useState(false)

  const { data: chart } = usePoll<any>(
    selected
      ? `/api/modules/stocks/candles/${selected}?interval=${interval}&limit=200`
      : null,
    120000
  )

  const watchlist: string[] = quotes?.watchlist ?? []

  const saveWatchlist = async (tickers: string[]) => {
    setBusy(true)
    try {
      await apiSend('/api/modules/stocks/watchlist', 'POST', { tickers })
      window.location.reload()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Stocks" subtitle="Watchlist quotes via yfinance (delayed). Earnings & news via Finnhub when a free key is set." />

      {quotes && !quotes.available && <Degraded reason={quotes.reason} />}

      <div className="card">
        <div className="mb-3 flex items-center gap-2">
          <input
            className="input w-40"
            placeholder="Add ticker…"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newTicker.trim()) {
                saveWatchlist([...watchlist, newTicker.trim()])
                setNewTicker('')
              }
            }}
          />
          <button
            className="btn"
            disabled={busy || !newTicker.trim()}
            onClick={() => {
              saveWatchlist([...watchlist, newTicker.trim()])
              setNewTicker('')
            }}
          >
            Add
          </button>
          <div className="ml-auto text-xs text-zinc-500">
            {quotes?.movers?.length ? (
              <>
                Movers:{' '}
                {quotes.movers.map((m: any) => (
                  <span key={m.symbol} className={`ml-2 font-semibold ${pctClass(m.change_pct)}`}>
                    {m.symbol} {m.change_pct > 0 ? '+' : ''}
                    {fmt(m.change_pct)}%
                  </span>
                ))}
              </>
            ) : null}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="data w-full">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Price</th>
                <th>Day %</th>
                <th>Today</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {(quotes?.quotes ?? []).map((q: any) => (
                <tr
                  key={q.symbol}
                  className="cursor-pointer hover:bg-zinc-900/60"
                  onClick={() => setSelected(q.symbol)}
                >
                  <td className="font-semibold">{q.symbol}</td>
                  <td>{q.available ? fmt(q.price) : '—'}</td>
                  <td className={pctClass(q.change_pct)}>
                    {q.available ? `${q.change_pct > 0 ? '+' : ''}${fmt(q.change_pct)}%` : 'n/a'}
                  </td>
                  <td>
                    <Sparkline values={q.sparkline ?? []} />
                  </td>
                  <td className="text-right">
                    <button
                      className="btn text-xs"
                      disabled={busy}
                      onClick={(e) => {
                        e.stopPropagation()
                        saveWatchlist(watchlist.filter((t) => t !== q.symbol))
                      }}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="card">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold">{selected}</h2>
            {['1d', '1h', '15m'].map((iv) => (
              <button
                key={iv}
                className={`btn text-xs ${interval === iv ? 'btn-primary' : ''}`}
                onClick={() => setInterval_(iv)}
              >
                {iv}
              </button>
            ))}
            <button className="btn ml-auto text-xs" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          {chart?.available ? (
            <CandleChart candles={chart.candles} height={320} />
          ) : (
            <div className="py-16 text-center text-sm text-zinc-500">
              {chart ? chart.reason ?? 'No data' : 'Loading…'}
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">Earnings calendar (next 2 weeks)</h2>
        {earnings && !earnings.available ? (
          <Degraded reason={earnings.reason} />
        ) : (
          <div className="max-h-72 overflow-y-auto">
            <table className="data w-full">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Symbol</th>
                  <th>EPS est.</th>
                  <th>Revenue est.</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {(earnings?.earnings ?? [])
                  .filter((e: any) => e.on_watchlist)
                  .concat((earnings?.earnings ?? []).filter((e: any) => !e.on_watchlist).slice(0, 30))
                  .map((e: any, i: number) => (
                    <tr key={i} className={e.on_watchlist ? 'bg-emerald-950/20' : ''}>
                      <td>{e.date}</td>
                      <td className="font-semibold">{e.symbol}</td>
                      <td>{e.epsEstimate ?? '—'}</td>
                      <td>{e.revenueEstimate ? fmt(e.revenueEstimate / 1e6, 0) + 'M' : '—'}</td>
                      <td className="text-zinc-400">{e.hour ?? ''}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
