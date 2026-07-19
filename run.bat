@echo off
REM ============================================================
REM  Analysts Trading Bot - one-click launcher (Windows)
REM  Double-click this file to start the signal engine.
REM  Dashboard: http://localhost:8010 (or your PORT in .env)
REM  Close this window or press Ctrl+C to stop the bot.
REM ============================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment not found.
    echo Run setup first:  python -m venv .venv  then  pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo [WARNING] No .env file found - Discord alerts will be disabled.
    echo Copy .env.example to .env and add your DISCORD_WEBHOOK_URL.
    echo.
)

echo Starting Analysts Trading Bot (signals only - never trades)...
".venv\Scripts\python.exe" main.py --mode continuous

echo.
echo Bot stopped.
pause
