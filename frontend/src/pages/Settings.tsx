import { useEffect, useState } from 'react'
import { PageTitle } from '../components/Shell'
import { apiGet, apiSend, usePoll } from '../lib/api'

const LLM_PROVIDERS = [
  'claude', 'openai', 'deepseek', 'qwen', 'gemini', 'kimi', 'minimax', 'glm', 'openrouter',
]

export default function SettingsPage() {
  const { data: overview } = usePoll<any>('/api/modules/futures/overview', 30000)
  const { data: discord } = usePoll<any>('/api/modules/futures/discord-status', 30000)

  const [agents, setAgents] = useState<Record<string, boolean> | null>(null)
  const [agentMsg, setAgentMsg] = useState<string | null>(null)

  const [provider, setProvider] = useState('claude')
  const [apiKey, setApiKey] = useState('')
  const [llmMsg, setLlmMsg] = useState<string | null>(null)

  useEffect(() => {
    apiGet('/api/agents/config')
      .then((d: any) => setAgents(d.agents ?? {}))
      .catch((e: any) => setAgentMsg(String(e)))
  }, [])

  const toggleAgent = async (name: string, value: boolean) => {
    const next = { ...(agents ?? {}), [name]: value }
    setAgents(next)
    try {
      await apiSend('/api/agents/config', 'POST', { agents: { [name]: value } })
      setAgentMsg(null)
    } catch (e: any) {
      setAgentMsg(String(e.message ?? e))
    }
  }

  const saveLlm = async () => {
    setLlmMsg(null)
    try {
      const payload: any = { llm: { llm_provider: provider } }
      if (apiKey.trim()) payload.llm[`${provider}_api_key`] = apiKey.trim()
      await apiSend('/api/config', 'POST', payload)
      setLlmMsg('Saved. Restart the bot to apply new API keys.')
      setApiKey('')
    } catch (e: any) {
      setLlmMsg(String(e.message ?? e))
    }
  }

  const setQuiet = async (enabled: boolean) => {
    await apiSend(`/api/modules/futures/quiet-mode?enabled=${enabled}`, 'POST')
    window.location.reload()
  }

  return (
    <div className="space-y-5">
      <PageTitle
        title="Settings"
        subtitle="Agent toggles, LLM provider, Discord quiet mode. Data & signal universe live in config.yaml / .env."
      />

      <div className="card">
        <h2 className="mb-1 text-sm font-semibold text-zinc-300">System</h2>
        <div className="grid gap-1 text-sm text-zinc-400 md:grid-cols-2">
          <div>Data source: <b className={overview?.synthetic ? 'text-amber-400' : 'text-zinc-200'}>{overview?.data_source ?? '—'}</b>{overview?.synthetic && ' (demo data — set data.source: yfinance for real quotes)'}</div>
          <div>Cycle interval: <b className="text-zinc-200">{overview?.cycle_interval_minutes ?? '—'} min</b></div>
          <div>Mode: <b className="text-emerald-400">signals-only, permanent test mode</b></div>
          <div>Virtual account: <b className="text-zinc-200">${overview?.virtual_account?.initial_balance ?? 1000} start</b></div>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">Discord alerts</h2>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div>
            Webhook:{' '}
            {discord?.configured ? (
              <span className="text-emerald-400">configured ✓ ({discord.sent_count} sent)</span>
            ) : (
              <span className="text-amber-400">not configured — set DISCORD_WEBHOOK_URL in .env</span>
            )}
          </div>
          {discord?.last_error && (
            <div className="text-red-400">last error: {discord.last_error}</div>
          )}
          <label className="ml-auto flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!discord?.quiet_mode}
              onChange={(e) => setQuiet(e.target.checked)}
            />
            Quiet mode (batch PASSes into hourly digest; TAKEs post immediately)
          </label>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">
          Agent toggles <span className="font-normal text-zinc-500">(local rule-based agents ON by default; LLM variants need a key)</span>
        </h2>
        {agentMsg && <div className="mb-2 text-xs text-red-400">{agentMsg}</div>}
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {agents &&
            Object.entries(agents).map(([name, enabled]) => (
              <label
                key={name}
                className="flex items-center gap-2 rounded-lg border border-zinc-800 px-3 py-2 text-sm hover:bg-zinc-900"
              >
                <input
                  type="checkbox"
                  checked={!!enabled}
                  onChange={(e) => toggleAgent(name, e.target.checked)}
                />
                <span className="font-mono text-xs">{name}</span>
              </label>
            ))}
          {!agents && <div className="text-sm text-zinc-500">Loading agent config…</div>}
        </div>
      </div>

      <div className="card">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">LLM provider (optional)</h2>
        <p className="mb-3 text-xs text-zinc-500">
          Enables LLM agent variants, Bull/Bear LLM debate and LLM sentiment.
          The app runs fully without it (rule-based agents).
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {LLM_PROVIDERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <input
            className="input w-80"
            type="password"
            placeholder={`${provider} API key`}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
          <button className="btn btn-primary" onClick={saveLlm}>Save</button>
          {llmMsg && <span className="text-xs text-zinc-400">{llmMsg}</span>}
        </div>
      </div>

      <div className="card text-xs text-zinc-500">
        <div className="mb-1 font-semibold text-zinc-400">Signals-only guarantee</div>
        This build has no live mode: order execution code is stubbed to a $1k
        virtual account, the risk-audit veto is a label (PASS / WOULD-VETO),
        and no broker or exchange trading credentials are configured anywhere.
        Watchlist editing lives on the Stocks page; the futures universe
        (NQ/MES/GOLD/USOIL) is config.yaml.
      </div>
    </div>
  )
}
