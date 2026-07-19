import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { PageTitle, Degraded } from '../components/Shell'
import { fmt, usePoll } from '../lib/api'

export default function MacroPage() {
  const { data: overview } = usePoll<any>('/api/modules/macro/overview', 3600000)
  const { data: calendar } = usePoll<any>('/api/modules/macro/calendar?days=14', 3600000)
  const { data: warning } = usePoll<any>('/api/modules/macro/warning', 600000)
  const { data: fx } = usePoll<any>('/api/modules/fx/rates', 3600000)

  return (
    <div className="space-y-5">
      <PageTitle
        title="Macro / Econ Calendar"
        subtitle="FRED key series and upcoming releases. High-impact releases within 2h add a warning to futures signals."
      />

      {warning?.warning && (
        <div className="card border-amber-800 bg-amber-950/30 text-sm font-medium text-amber-300">
          ⚠️ {warning.warning}
        </div>
      )}

      {overview && !overview.available ? (
        <Degraded reason={`${overview.reason}. Get a free key at fred.stlouisfed.org/docs/api/api_key.html and set FRED_API_KEY in .env.`} />
      ) : (
        <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
          {Object.entries(overview?.series ?? {}).map(([sid, s]: [string, any]) => (
            <div key={sid} className="card">
              <div className="flex items-baseline justify-between">
                <h2 className="text-sm font-semibold text-zinc-300">{s.label ?? sid}</h2>
                <div className="text-lg font-bold">
                  {s.latest ? fmt(s.latest.value) : '—'}
                  <span className="ml-1 text-xs font-normal text-zinc-500">{s.units}</span>
                </div>
              </div>
              <div className="text-xs text-zinc-500">{s.latest?.date}</div>
              {s.observations?.length > 1 && (
                <ResponsiveContainer width="100%" height={140}>
                  <LineChart data={s.observations.slice(-120)}>
                    <XAxis dataKey="date" stroke="#52525b" fontSize={9} minTickGap={50} />
                    <YAxis stroke="#52525b" fontSize={9} domain={['auto', 'auto']} width={45} />
                    <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46' }} />
                    <Line type="monotone" dataKey="value" stroke="#60a5fa" dot={false} strokeWidth={1.5} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-3 text-sm font-semibold text-zinc-300">
            Upcoming releases (14 days)
          </h2>
          {calendar && !calendar.available ? (
            <Degraded reason={calendar.reason} />
          ) : (
            <div className="max-h-80 overflow-y-auto">
              <table className="data w-full">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Release</th>
                    <th>Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {(calendar?.releases ?? []).map((r: any, i: number) => (
                    <tr key={i} className={r.high_impact ? 'bg-amber-950/20' : ''}>
                      <td className="whitespace-nowrap">{r.date}</td>
                      <td>{r.name}</td>
                      <td>
                        {r.high_impact ? (
                          <span className="badge bg-amber-950 text-amber-400">HIGH</span>
                        ) : (
                          <span className="text-xs text-zinc-600">low</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="mb-3 text-sm font-semibold text-zinc-300">
            USD panel (Frankfurter, dollar-strength context for GOLD/USOIL)
          </h2>
          {fx && !fx.available ? (
            <Degraded reason={fx.reason} />
          ) : (
            <table className="data w-full">
              <thead>
                <tr>
                  <th>Pair</th>
                  <th>Rate</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(fx?.rates ?? {}).map(([cur, rate]: [string, any]) => (
                  <tr key={cur}>
                    <td className="font-semibold">USD/{cur}</td>
                    <td>{fmt(rate, 4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="mt-2 text-xs text-zinc-500">As of {fx?.date ?? '—'} (ECB reference)</div>
        </div>
      </div>
    </div>
  )
}
