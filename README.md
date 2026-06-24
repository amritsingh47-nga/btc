# Amazon SMF1 / SMF6 Hourly-Job Detector

Polls [hiring.amazon.com](https://hiring.amazon.com) for hourly warehouse /
fulfillment-center jobs, filters them to the buildings you care about (e.g.
**SMF1** and **SMF6** near Sacramento), and sends you an **instant alert** the
moment a matching posting appears — so you can tap through and apply before it's
gone.

Auto-apply is intentionally **not** included yet. Alerting is reliable and safe;
the code is structured so an auto-apply step can be bolted on later (see
[Roadmap](#roadmap)) without touching the detection core.

---

## How it works

```
hiring.amazon.com GraphQL  ->  matcher (SMF1/SMF6, title, pay)  ->  dedupe  ->  notifiers (Telegram/Discord/console)
        amazon_source.py            matcher.py                      state.py        notifiers.py
                                              \__ runner.py loop __/
```

Every ~25 seconds it asks Amazon's job-search API for postings near your
coordinates, keeps the ones matching your criteria, skips anything it already
told you about, and pings every alert channel you enabled.

---

## ⚠️ Important reality check

Amazon does **not** publish this API. The detector talks to the same private
GraphQL endpoint the website uses. That means:

- **You need a session token** from your own logged-in browser (instructions
  below). Unauthenticated requests are rejected.
- **The token expires** (often within hours/days). When it does, you'll see
  `HTTP 401/403` in the logs and need to refresh it.
- **The endpoint/schema can change** without notice. When that happens, use
  `probe` (below) to see the new response and adjust `config.yaml`.
- Automated access is **against Amazon's terms**. This is a personal-use alerter;
  keep the poll interval polite (don't hammer it) to avoid getting blocked.

In short: this works, but it's a scraper of a private API, not a stable
integration. Budget a few minutes now and then to refresh the token.

---

## Setup

### 1. Install

```bash
git clone <this-repo> && cd btc
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp .env.example .env
```

### 2. Getting your auth token

1. Open <https://hiring.amazon.com/app#/jobSearch> in Chrome/Firefox and **log in**.
2. Open **DevTools → Network** tab. Filter for `graphql`.
3. Do a job search on the page. Click the `graphql` request that appears.
4. Under **Request Headers**, copy the full value of **`Authorization`**
   (it's a long token, often starting with `Status|` or `Bearer`).
5. Paste it into `.env` as `AMZ_AUTH_TOKEN=...`.

While you're in that request, also confirm the **Request URL** matches
`source.endpoint` in `config.yaml`. If it differs, update the config.

### 3. Set up Telegram alerts (fastest)

1. On Telegram, message **@BotFather**, send `/newbot`, follow prompts, copy the
   **bot token** → `.env` `TELEGRAM_BOT_TOKEN`.
2. Send your new bot any message (say "hi").
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and copy the
   `chat.id` number → `.env` `TELEGRAM_CHAT_ID`.

Prefer Discord instead/as well? Uncomment the `discord` block in `config.yaml`
and set `DISCORD_WEBHOOK_URL` in `.env`.

### 4. Tell it what to watch

Edit `config.yaml` → `match.site_codes` (already set to `["SMF1", "SMF6"]`).
Add `title_contains` / `min_pay_rate` if you want to narrow it further.

---

## Running

### Easiest: one-tap launcher on your own PC

No server needed. This catches jobs while your PC is on and the window is open;
alerts still go to your **phone** via Telegram, so you don't have to sit at the
computer — it just has to stay powered on and awake.

- **Windows:** double-click **`run.bat`**
- **macOS / Linux:** run **`./run.sh`** (first time: `chmod +x run.sh`)

The first run installs everything, then stops and asks you to fill in `.env`
(your three tokens — see setup above). Fill it in, launch again, and it starts
watching. Leave the window open; closing it stops the detector. Turn off
auto-sleep in your power settings so it keeps running while you're away.

### Manual commands

```bash
# Send yourself a fake match to confirm alerts work:
python -m amazon_job_detector test-notify

# Dump the raw API response (use this to debug / adjust field mappings):
python -m amazon_job_detector probe

# One poll then exit (good for a cron-style check or a smoke test):
python -m amazon_job_detector once

# The real thing — poll forever:
python -m amazon_job_detector run
```

Run `probe` first after setup. If it prints job cards, you're good. If you get
an HTTP error, your token/endpoint needs fixing (see the reality-check section).

---

## Deploying on a VPS (24/7)

The tool must run continuously to catch postings. Two easy options:

### Docker (recommended)

```bash
touch seen_jobs.json
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f
```

### systemd

```bash
sudo mkdir -p /opt/amazon-job-detector
sudo cp -r src config.yaml .env requirements.txt /opt/amazon-job-detector/
cd /opt/amazon-job-detector && python -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo cp deploy/systemd/amazon-job-detector.service /etc/systemd/system/
# edit User/paths in the unit file if needed
sudo systemctl daemon-reload && sudo systemctl enable --now amazon-job-detector
journalctl -u amazon-job-detector -f
```

---

## Keeping it working

| Symptom | Cause | Fix |
|---|---|---|
| `HTTP 401` / `403` | Session token expired | Re-grab `AMZ_AUTH_TOKEN` (step 2), restart |
| `GraphQL errors` / 0 jobs but site has jobs | Schema/endpoint changed | Run `probe`, compare fields, update `source.query_override` and the field map in `amazon_source.py` |
| Telegram alert not arriving | Bad token/chat id | Re-run `test-notify`; re-check step 3 |
| Same job alerted twice | `seen_jobs.json` not persisted | Ensure the file is writable / mounted (Docker volume) |

---

## Configuration reference

See `config.example.yaml` — every field is commented. Secrets are referenced by
the **name** of an environment variable (`*_env`), never stored in the YAML.

---

## Tests

```bash
pip install pytest
pytest
```

Covers the matcher logic (site-code / title / pay filtering) and the dedupe
store. The Amazon API client isn't unit-tested against the live endpoint by
design — use `probe` for that.

---

## Roadmap

- [ ] **Auto-apply (best-effort).** Add an `applier.py` that, on a match, drives
      the application flow via your session. Brittle + against ToS + may hit an
      assessment/SMS step, so it'll always run *behind* alerting, never instead
      of it.
- [x] SMS channel (Twilio).
- [ ] Multiple geo regions in one process.

---

## Disclaimer

For personal use only. You are responsible for complying with Amazon's terms of
service. This project is not affiliated with Amazon.
