"""
Stocks / watchlist module (yfinance quotes + optional Finnhub extras).

- Server-side user-editable watchlist (data/modules/watchlist.json).
- Quotes: last price, day change %, sparkline (1d/5m closes) per ticker.
- Candles for the detail chart via the shared yfinance interval mapping.
- Finnhub (free key): earnings calendar + per-ticker news when
  FINNHUB_API_KEY is present; degraded marker otherwise.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from src.modules.common import cached, http_get_json, load_json_store, save_json_store, unavailable
from src.utils.logger import log

DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'SPY', 'QQQ']

FINNHUB_BASE = 'https://finnhub.io/api/v1'


def _finnhub_key():
    key = (os.getenv('FINNHUB_API_KEY') or '').strip()
    return key or None


def get_watchlist() -> List[str]:
    wl = load_json_store('watchlist', DEFAULT_WATCHLIST)
    return [str(t).upper() for t in wl if str(t).strip()]


def set_watchlist(tickers: List[str]) -> List[str]:
    clean = []
    for t in tickers[:50]:
        t = str(t).strip().upper()
        if t and len(t) <= 12 and t.replace('.', '').replace('-', '').replace('=', '').isalnum():
            clean.append(t)
    save_json_store('watchlist', clean)
    return clean


def _quote_for(ticker: str) -> Dict[str, Any]:
    import yfinance as yf
    t = yf.Ticker(ticker)
    hist = t.history(period='2d', interval='5m', auto_adjust=False, actions=False)
    if hist is None or hist.empty:
        return {'symbol': ticker, 'available': False}
    closes = hist['Close'].dropna()
    last = float(closes.iloc[-1])
    # previous close: last value of the prior session if present
    day_index = hist.index.normalize().unique()
    if len(day_index) > 1:
        prev_session = hist[hist.index.normalize() == day_index[-2]]['Close'].dropna()
        prev_close = float(prev_session.iloc[-1]) if len(prev_session) else float(closes.iloc[0])
        today = hist[hist.index.normalize() == day_index[-1]]['Close'].dropna()
    else:
        prev_close = float(closes.iloc[0])
        today = closes
    change_pct = ((last - prev_close) / prev_close * 100) if prev_close else 0.0
    spark = [round(float(v), 4) for v in today.tail(78)]
    return {
        'symbol': ticker,
        'available': True,
        'price': round(last, 4),
        'prev_close': round(prev_close, 4),
        'change_pct': round(change_pct, 2),
        'sparkline': spark,
        'as_of': datetime.now(timezone.utc).isoformat(),
    }


def get_quotes() -> Dict[str, Any]:
    watchlist = get_watchlist()

    def fetch():
        quotes = []
        for ticker in watchlist:
            try:
                quotes.append(_quote_for(ticker))
            except Exception as e:
                log.warning(f"quote failed {ticker}: {e}")
                quotes.append({'symbol': ticker, 'available': False, 'error': str(e)})
        return quotes

    try:
        quotes = cached(f"stocks:quotes:{','.join(watchlist)}", ttl=60, fetch=fetch)
    except Exception as e:
        return unavailable(f'quotes failed: {e}', watchlist=watchlist)
    ok = [q for q in quotes if q.get('available')]
    movers = sorted(ok, key=lambda q: abs(q.get('change_pct', 0)), reverse=True)[:5]
    return {'available': True, 'watchlist': watchlist, 'quotes': quotes,
            'movers': movers}


def get_candles(ticker: str, interval: str = '1d', limit: int = 180) -> Dict[str, Any]:
    from src.api.yfinance_client import YFinanceClient
    client = YFinanceClient()
    try:
        klines = client.get_klines(ticker.upper(), interval, limit=limit)
    except ValueError as e:
        return unavailable(str(e))
    if not klines:
        return unavailable('no data returned')
    return {'available': True, 'symbol': ticker.upper(), 'interval': interval,
            'candles': klines}


def get_earnings_calendar(days_ahead: int = 14) -> Dict[str, Any]:
    key = _finnhub_key()
    if not key:
        return unavailable('FINNHUB_API_KEY not configured')

    def fetch():
        today = datetime.now(timezone.utc).date()
        data = http_get_json(f'{FINNHUB_BASE}/calendar/earnings', params={
            'from': str(today), 'to': str(today + timedelta(days=days_ahead)),
            'token': key,
        })
        cal = data.get('earningsCalendar', [])
        watch = set(get_watchlist())
        for item in cal:
            item['on_watchlist'] = item.get('symbol') in watch
        return {'available': True, 'earnings': cal[:200]}

    try:
        return cached('finnhub:earnings', ttl=6 * 3600, fetch=fetch)
    except Exception as e:
        return unavailable(f'Finnhub fetch failed: {e}')


def get_ticker_news(ticker: str) -> Dict[str, Any]:
    key = _finnhub_key()
    if not key:
        return unavailable('FINNHUB_API_KEY not configured')

    def fetch():
        today = datetime.now(timezone.utc).date()
        data = http_get_json(f'{FINNHUB_BASE}/company-news', params={
            'symbol': ticker.upper(),
            'from': str(today - timedelta(days=7)), 'to': str(today),
            'token': key,
        })
        return {'available': True, 'symbol': ticker.upper(), 'news': data[:30]}

    try:
        return cached(f'finnhub:news:{ticker.upper()}', ttl=1800, fetch=fetch)
    except Exception as e:
        return unavailable(f'Finnhub fetch failed: {e}')
