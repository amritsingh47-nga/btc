# Analysts Trading Bot — All-Finance Dashboard + Futures Signal Analysts

A self-hosted "everything finance" dashboard built around a **multi-agent
futures signal engine**. Every 15 minutes the agents analyze **NQ, MES (via
ES), GOLD (GC) and USOIL (CL)** and post what they **WOULD** trade — or why
they're passing — to **Discord** and the dashboard.

> ### Hard rule #1 — SIGNALS ONLY
> This system **never places, routes, or executes any trade**, paper or live,
> on any venue. There is no live mode: order execution is stubbed to a
> log-only virtual $1,000 account, and no broker/exchange trading credentials
> are configured anywhere. The risk-audit veto is a **label**
> (`PASS` / `WOULD-VETO`), not a blocker, so you see vetoed ideas too.
>
> ### Hard rule #2 — free-tier everything
> No paid APIs, no paid data. Where a free key helps (FRED, Finnhub), it goes
> in `.env` and the app runs **degraded but clearly labeled** without it.

Built on the agent pipeline from
[EthanAlgoX/LLM-TradeBot](https://github.com/EthanAlgoX/LLM-TradeBot)
(vendored in this repo — original readme: `docs/BASE_REPO_README.md`), with
the Binance data layer replaced by **yfinance** and the execution layer
permanently disabled.

---

## Modules

| Tab | What it does | Data source |
|---|---|---|
| **Futures Signals** | Live signal feed, candle charts with signal markers, hypothetical P&L curve, decisions table | yfinance (free, ~15-min delay) |
| **Stocks** | Editable watchlist, quotes, movers, sparklines, candles; earnings + news | yfinance; Finnhub (free key, optional) |
| **Crypto** | Top coins, trending, detail charts, Fear & Greed gauge | CoinGecko + alternative.me (keyless) |
| **Macro** | CPI, unemployment, Fed funds, 10Y, USD index + release calendar with high-impact flags | FRED (free key) |
| **News** | Finance RSS + Trump post monitoring, keyword sentiment per instrument | keyless RSS + Truth Social mirror |
| **Portfolio** | Manual position entry, live P&L. **No broker linking. Ever.** | yfinance / CoinGecko lookups |
| **Settings** | Agent toggles, LLM provider + key, Discord quiet mode | — |

## The signal engine

```
DataSync (yfinance 5m/15m/1h)
  → Quant Analyst → Regime + Position detection
  → 4-layer filter (trend/fuel → ML alignment → setup zone → trigger)
  → Bull/Bear debate → Decision Core (LONG/SHORT/WAIT + confidence + reasoning)
  → Risk Audit label (PASS / WOULD-VETO)
  → Discord embed + dashboard + hypothetical $1k book
```

- **1h = trend, 15m = setup (primary), 5m = trigger — ADVISORY-ONLY** because
  yfinance data is ~15 minutes delayed. This is a swing/position signal tool,
  not a scalping tool.
- MES is proxied by ES data (the micro tracks the standard contract
  tick-for-tick).
- Before posting, the engine checks the FRED calendar for high-impact
  releases (CPI, NFP, GDP, …) and appends a macro warning to the signal.
- News sentiment (including flagged "market-moving political posts") is
  attached to each TAKE embed.
- The **hypothetical P&L curve** exists so you can judge signal quality over
  weeks before any real money follows anything. Not financial advice.

### Discord message format

- **TAKE** — rich embed: confidence %, regime, risk-audit label, entry
  zone/stop/target, 1h/15m alignment, one-line reasoning, macro warning,
  sentiment read. Footer: *"Signals only — nothing is ever executed. Not
  financial advice."*
- **PASS** — one compact line: `🟡 PASS NQ — <reason>`.
- `DISCORD_QUIET_MODE=true` posts TAKEs immediately and batches PASSes into
  an hourly digest (also toggleable at runtime in Settings).

---

## Setup

Requirements: Python 3.11+, Node 18+ (only to build the frontend once).

```bash
git clone <this repo> && cd btc

# 1. Python environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend (one-time build; rebuild after UI changes)
cd frontend && npm install && npm run build && cd ..

# 3. Configuration
cp .env.example .env
#    → paste your DISCORD_WEBHOOK_URL, add FRED/Finnhub keys if you have them
#    config.example.yaml is used as-is; copy to config.yaml to customize.

# 4. Run
python main.py --mode continuous
```

Dashboard: <http://localhost:8000> · legacy debug UI: `/legacy` ·
API docs: `/docs`.

Smoke-test a single cycle without waiting: `python main.py --mode once`.
No network? `DATA_SOURCE=synthetic python main.py --mode once` runs the whole
pipeline on clearly-labeled generated demo data.

### Verify your webhook quickly

```bash
python - <<'EOF'
import os; from dotenv import load_dotenv; load_dotenv()
import requests
r = requests.post(os.environ['DISCORD_WEBHOOK_URL'],
    json={'content': '✅ Analysts Trading Bot webhook test'})
print(r.status_code)  # 204 = success
EOF
```

---

## Remote access with Tailscale (no port forwarding!)

1. Install [Tailscale](https://tailscale.com/download) on the PC running the
   bot and on your phone; sign both into the same tailnet.
2. Find the PC's Tailscale IP: `tailscale ip -4` (looks like `100.x.y.z`).
3. On your phone, open `http://100.x.y.z:8000`.

Do **not** port-forward the dashboard to the public internet. If you must
share beyond your tailnet, set `WEB_PASSWORD` in `.env` at minimum.

## Later: 24/7 on a small VPS (not built now)

When you want signals without your PC on: a ~$5/mo VPS (Hetzner CX22,
DigitalOcean basic) or an Oracle always-free ARM VM is plenty.

```bash
# on the VPS
docker build -t analysts-bot . && docker run --env-file .env -p 8000:8000 analysts-bot
```

The Dockerfile in this repo stays working for exactly this migration
(build the frontend before building the image so `frontend/dist` is copied
in). Put the VPS on your tailnet and nothing else changes.

---

## Configuration reference

`.env` (see `.env.example` for full comments):

| Var | Required | Purpose |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | ✅ | signal alerts (secret — never commit, rotate if leaked) |
| `DISCORD_QUIET_MODE` | – | `true` = hourly PASS digest |
| `FRED_API_KEY` | – | macro module + macro warnings |
| `FINNHUB_API_KEY` | – | stocks earnings/news |
| `LLM_PROVIDER` + key | – | LLM agent variants / debate / sentiment |
| `TRUMP_RSS_URL` | – | Truth Social mirror feed (mirrors change; config not code) |
| `WEB_PASSWORD` | – | require dashboard login |

`config.yaml` (falls back to `config.example.yaml`): futures universe +
display names, cycle interval/autostart, data source, RSS feed list, agent
toggles.

## Backtesting

The base repo's backtester is wired to the same yfinance data source and
replays the full agent pipeline (quant analysis → 4-layer filter → decision →
portfolio) bar by bar:

```bash
# one instrument, 15-minute decision step
python backtest.py --start 2026-06-01 --end 2026-07-15 --symbol NQ=F --capital 1000 --step 3

# all four instruments, hourly step (faster)
python backtest.py --start 2026-06-01 --end 2026-07-15 --symbol ALL --step 12
```

Each run prints return / drawdown / Sharpe / win rate and writes an HTML
report to `reports/` (also served at `http://localhost:8000/reports/...`).

**Honest limits:** yfinance only provides ~60 days of 5m/15m history, so
backtests are capped to roughly the last two months — enough for a sanity
check, not a statistically meaningful sample. Treat backtest output as a
smoke test of the rules; the forward-running hypothetical P&L curve is the
real signal-quality tracker. (Longer lookbacks would need paid data, which
is out of scope by design.)

## Known limitations (accepted — do not "fix" with paid services)

- yfinance is ~15 minutes delayed → 5m triggers are advisory-only.
- Signals are rule-based heuristics (+ optional LLM opinion) on delayed
  data. The hypothetical P&L curve is there precisely so you can judge them.
  **Not financial advice.**
- Truth Social mirror feeds die; the feed URL is config, not hardcoded.
- MES is proxied by ES data.
- Free API rate limits are respected via caching; if an upstream API is
  down, its module reports "degraded" and everything else keeps working.

## Explicitly out of scope

Any order execution (paper or live), broker/exchange account linking,
Binance/Tradovate/IBKR keys, paid data upgrades.
