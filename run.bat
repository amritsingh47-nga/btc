@echo off
REM One-tap launcher for Windows. Double-click this file (or run in a terminal).
REM First run: creates a virtualenv, installs deps, copies example config/.env.
cd /d "%~dp0"

if not exist .venv (
  echo Setting up for the first time...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

if not exist config.yaml (
  copy config.example.yaml config.yaml >nul
  echo Created config.yaml (already set to watch SMF1/SMF6).
)
if not exist .env (
  copy .env.example .env >nul
  echo.
  echo ^>^>^> Open .env and fill in AMZ_AUTH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, then run this again.
  pause
  exit /b 1
)

echo Starting detector. Leave this window open. Press Ctrl+C to stop.
set "PYTHONPATH=src"
python -m amazon_job_detector run --config config.yaml
pause
