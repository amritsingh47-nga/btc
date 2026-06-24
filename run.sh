#!/usr/bin/env bash
# One-tap launcher for macOS / Linux.
# First run: creates a virtualenv, installs deps, and copies the example
# config/.env if you don't have them yet. Then starts the detector.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Setting up for the first time..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

[ -f config.yaml ] || { cp config.example.yaml config.yaml; echo "Created config.yaml (already set to watch SMF1/SMF6)."; }
if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo ">>> Open .env and fill in AMZ_AUTH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, then run this again."
  exit 1
fi

echo "Starting detector. Leave this window open. Press Ctrl+C to stop."
export PYTHONPATH=src
python -m amazon_job_detector run --config config.yaml
