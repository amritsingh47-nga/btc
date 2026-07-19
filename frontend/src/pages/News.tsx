import { useState } from 'react'
import { PageTitle, Degraded } from '../components/Shell'
import { usePoll } from '../lib/api'

const FILTERS = [
  { key: '', label: 'All' },
  { key: 'NQ=F', label: 'NQ' },
  { key: 'ES=F', label: 'MES' },
  { key: 'GC=F', label: 'GOLD' },
  { key: 'CL=F', label: 'USOIL' },
]

export default function NewsPage() {
  const [filter, setFilter] = useState('')
  const [politicalOnly, setPoliticalOnly] = useState(false)
  const { data } = usePoll<any>(
    `/api/modules/news/feed?limit=120${filter ? `&instrument=${encodeURIComponent(filter)}` : ''}${politicalOnly ? '&political=true' : ''}`,
    60000
  )

  const sentiments: Record<string, any> = {}
  for (const f of FILTERS.slice(1)) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { data: s } = usePoll<any>(`/api/modules/news/sentiment/${encodeURIComponent(f.key)}`, 120000)
    sentiments[f.key] = s
  }

  return (
    <div className="space-y-5">
      <PageTitle
        title="News / Sentiment"
        subtitle="Keyless RSS + Truth Social mirror. Keyword sentiment feeds the futures Discord messages."
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {FILTERS.slice(1).map((f) => {
          const s = sentiments[f.key]
          return (
            <div key={f.key} className="card">
              <div className="text-xs text-zinc-500">{f.label} sentiment</div>
              <div
                className={`mt-1 text-lg font-bold ${
                  (s?.score ?? 0) > 0.05
                    ? 'text-emerald-400'
                    : (s?.score ?? 0) < -0.05
                    ? 'text-red-400'
                    : 'text-zinc-300'
                }`}
              >
                {s ? `${s.mood} (${s.score >= 0 ? '+' : ''}${s.score})` : '—'}
              </div>
              <div className="text-xs text-zinc-500">
                {s?.headline_count ?? 0} headlines
                {s?.political_flags ? ` · ⚑ ${s.political_flags} political` : ''}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`btn text-xs ${filter === f.key ? 'btn-primary' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-xs text-zinc-400">
          <input
            type="checkbox"
            checked={politicalOnly}
            onChange={(e) => setPoliticalOnly(e.target.checked)}
          />
          Political posts only
        </label>
      </div>

      {data && !data.available && <Degraded reason={data.reason} />}

      <div className="card divide-y divide-zinc-800/60">
        {(data?.items ?? []).map((item: any, i: number) => (
          <div key={i} className="flex items-start gap-3 py-2.5">
            <SentimentDot score={item.sentiment} />
            <div className="min-w-0 flex-1">
              <a
                href={item.link ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-medium text-zinc-200 hover:text-white hover:underline"
              >
                {item.title}
              </a>
              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                <span>{item.source}</span>
                {item.published && <span>{String(item.published).slice(0, 16).replace('T', ' ')}</span>}
                {(item.instruments ?? []).map((sym: string) => (
                  <span key={sym} className="badge bg-zinc-800 text-zinc-400">
                    {FILTERS.find((f) => f.key === sym)?.label ?? sym}
                  </span>
                ))}
                {item.market_moving_political_post && (
                  <span className="badge bg-red-950 text-red-400">
                    ⚑ market-moving political post
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        {!data?.items?.length && (
          <div className="py-16 text-center text-sm text-zinc-500">
            No headlines yet — feeds refresh every 5 minutes. Check Settings →
            feed status if this persists.
          </div>
        )}
      </div>

      <div className="card text-xs text-zinc-500">
        <div className="mb-1 font-semibold text-zinc-400">Feed status</div>
        {Object.entries(data?.feed_status ?? {}).map(([name, status]: [string, any]) => (
          <div key={name}>
            <span className="text-zinc-400">{name}:</span>{' '}
            <span className={String(status).startsWith('ok') ? 'text-emerald-500' : 'text-red-400'}>
              {String(status).slice(0, 120)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SentimentDot({ score }: { score: number }) {
  const color =
    score > 0.05 ? 'bg-emerald-500' : score < -0.05 ? 'bg-red-500' : 'bg-zinc-600'
  return <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${color}`} title={`sentiment ${score}`} />
}
