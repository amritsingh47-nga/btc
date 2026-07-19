import { useState } from 'react'
import { PageTitle } from '../components/Shell'
import { apiSend, fmt, pctClass, usePoll } from '../lib/api'

const EMPTY = {
  symbol: '',
  direction: 'long',
  size: '',
  entry_price: '',
  asset_type: 'stock',
  notes: '',
}

export default function PortfolioPage() {
  const { data, error } = usePoll<any>('/api/modules/portfolio', 60000)
  const [form, setForm] = useState<any>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const submit = async () => {
    setBusy(true)
    setMsg(null)
    try {
      await apiSend('/api/modules/portfolio', 'POST', {
        ...form,
        size: parseFloat(form.size),
        entry_price: parseFloat(form.entry_price),
      })
      setForm(EMPTY)
      window.location.reload()
    } catch (e: any) {
      setMsg(String(e.message ?? e))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: string) => {
    await apiSend(`/api/modules/portfolio/${id}`, 'DELETE')
    window.location.reload()
  }

  const totals = data?.totals

  return (
    <div className="space-y-5">
      <PageTitle
        title="Portfolio"
        subtitle="Manual position tracking with live P&L. No broker linking — ever."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Market value" value={`$${fmt(totals?.market_value)}`} />
        <Stat label="Open P&L" value={`$${fmt(totals?.pnl)}`} className={pctClass(totals?.pnl)} />
        <Stat label="Positions priced" value={String(totals?.priced ?? 0)} />
        <Stat label="Unpriced (no quote)" value={String(totals?.unpriced ?? 0)} />
      </div>

      <div className="card">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">Add position</h2>
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Symbol">
            <input
              className="input w-32"
              placeholder="AAPL / NQ=F / bitcoin"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value })}
            />
          </Field>
          <Field label="Type">
            <select
              className="input"
              value={form.asset_type}
              onChange={(e) => setForm({ ...form, asset_type: e.target.value })}
            >
              <option value="stock">stock</option>
              <option value="futures">futures</option>
              <option value="crypto">crypto (CoinGecko id)</option>
              <option value="fx">fx</option>
            </select>
          </Field>
          <Field label="Direction">
            <select
              className="input"
              value={form.direction}
              onChange={(e) => setForm({ ...form, direction: e.target.value })}
            >
              <option value="long">long</option>
              <option value="short">short</option>
            </select>
          </Field>
          <Field label="Size">
            <input
              className="input w-24"
              type="number"
              value={form.size}
              onChange={(e) => setForm({ ...form, size: e.target.value })}
            />
          </Field>
          <Field label="Entry price">
            <input
              className="input w-28"
              type="number"
              value={form.entry_price}
              onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
            />
          </Field>
          <Field label="Notes">
            <input
              className="input w-48"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Field>
          <button
            className="btn btn-primary"
            disabled={busy || !form.symbol || !form.size || !form.entry_price}
            onClick={submit}
          >
            Add
          </button>
        </div>
        {msg && <div className="mt-2 text-xs text-red-400">{msg}</div>}
      </div>

      <div className="card overflow-x-auto">
        {error && <div className="text-xs text-red-400">{error}</div>}
        <table className="data w-full">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Type</th>
              <th>Dir</th>
              <th>Size</th>
              <th>Entry</th>
              <th>Now</th>
              <th>P&L</th>
              <th>P&L %</th>
              <th>Notes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data?.positions ?? []).map((p: any) => (
              <tr key={p.id} className="hover:bg-zinc-900/60">
                <td className="font-semibold">{p.symbol}</td>
                <td className="text-zinc-400">{p.asset_type}</td>
                <td>
                  <span
                    className={`badge ${
                      p.direction === 'long'
                        ? 'bg-emerald-950 text-emerald-400'
                        : 'bg-red-950 text-red-400'
                    }`}
                  >
                    {p.direction}
                  </span>
                </td>
                <td>{fmt(p.size, 4)}</td>
                <td>{fmt(p.entry_price)}</td>
                <td>{p.current_price != null ? fmt(p.current_price) : '—'}</td>
                <td className={pctClass(p.pnl)}>{p.pnl != null ? `$${fmt(p.pnl)}` : '—'}</td>
                <td className={pctClass(p.pnl_pct)}>
                  {p.pnl_pct != null ? `${fmt(p.pnl_pct)}%` : '—'}
                </td>
                <td className="max-w-xs truncate text-zinc-400" title={p.notes}>
                  {p.notes}
                </td>
                <td className="text-right">
                  <button className="btn text-xs" onClick={() => remove(p.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!data?.positions?.length && (
              <tr>
                <td colSpan={10} className="py-10 text-center text-zinc-500">
                  No positions yet — add one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Stat({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="card">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className={`mt-1 text-lg font-bold ${className}`}>{value}</div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-zinc-500">
      {label}
      {children}
    </label>
  )
}
