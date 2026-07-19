"""
Macro / econ-calendar module backed by FRED (free API key).

- Key series (CPI, unemployment, Fed funds, 10Y yield, broad dollar
  index) as chart-ready observations + latest values.
- Upcoming release calendar via the FRED releases/dates endpoint with
  high-impact flags (CPI / employment / FOMC-adjacent keywords).
- get_macro_warning(): the hook the futures Discord signal calls — any
  high-impact release within the next 2 hours produces a warning line.

Degrades cleanly: without FRED_API_KEY every endpoint answers
{"available": false, ...} and the warning hook returns None.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.modules.common import cached, http_get_json, unavailable
from src.utils.logger import log

FRED_BASE = "https://api.stlouisfed.org/fred"

SERIES = {
    'CPIAUCSL': {'label': 'CPI (all items, SA)', 'units': 'index'},
    'UNRATE': {'label': 'Unemployment rate', 'units': '%'},
    'FEDFUNDS': {'label': 'Fed funds effective rate', 'units': '%'},
    'DGS10': {'label': '10Y Treasury yield', 'units': '%'},
    'DTWEXBGS': {'label': 'Broad USD index (goods & services)', 'units': 'index'},
}

# Release-name keywords considered high impact for NQ/ES/GC/CL
HIGH_IMPACT_KEYWORDS = (
    'consumer price index',      # CPI
    'employment situation',      # NFP
    'gross domestic product',
    'personal income',           # PCE inflation
    'producer price index',
    'h.4.1', 'h.15',             # Fed releases
    'fomc', 'federal open market',
    'advance monthly sales',     # retail sales
)


def _api_key() -> Optional[str]:
    key = (os.getenv('FRED_API_KEY') or '').strip()
    return key or None


def _fred(path: str, **params) -> Any:
    params.update({'api_key': _api_key(), 'file_type': 'json'})
    return http_get_json(f"{FRED_BASE}/{path}", params=params)


def get_series(series_id: str, limit: int = 240) -> Dict[str, Any]:
    if not _api_key():
        return unavailable('FRED_API_KEY not configured')
    if series_id not in SERIES:
        return unavailable(f'unknown series {series_id}')

    def fetch():
        data = _fred('series/observations', series_id=series_id,
                     sort_order='desc', limit=limit)
        obs = [
            {'date': o['date'], 'value': float(o['value'])}
            for o in data.get('observations', [])
            if o.get('value') not in ('.', None, '')
        ]
        obs.reverse()
        meta = SERIES[series_id]
        return {
            'available': True,
            'series_id': series_id,
            'label': meta['label'],
            'units': meta['units'],
            'observations': obs,
            'latest': obs[-1] if obs else None,
        }

    try:
        return cached(f'fred:{series_id}', ttl=6 * 3600, fetch=fetch)
    except Exception as e:
        log.warning(f"FRED series {series_id} failed: {e}")
        return unavailable(f'FRED fetch failed: {e}')


def get_overview() -> Dict[str, Any]:
    if not _api_key():
        return unavailable('FRED_API_KEY not configured')
    return {
        'available': True,
        'series': {sid: get_series(sid) for sid in SERIES},
    }


def get_release_calendar(days_ahead: int = 14) -> Dict[str, Any]:
    if not _api_key():
        return unavailable('FRED_API_KEY not configured')

    def fetch():
        today = datetime.now(timezone.utc).date()
        data = _fred(
            'releases/dates',
            realtime_start=str(today),
            realtime_end=str(today + timedelta(days=days_ahead)),
            include_release_dates_with_no_data='true',
            sort_order='asc',
            limit=200,
        )
        releases: List[Dict[str, Any]] = []
        for rd in data.get('release_dates', []):
            name = rd.get('release_name', '')
            date = rd.get('date')
            if not date:
                continue
            releases.append({
                'date': date,
                'release_id': rd.get('release_id'),
                'name': name,
                'high_impact': any(k in name.lower() for k in HIGH_IMPACT_KEYWORDS),
            })
        return {'available': True, 'releases': releases}

    try:
        return cached('fred:releases', ttl=3600, fetch=fetch)
    except Exception as e:
        log.warning(f"FRED release calendar failed: {e}")
        return unavailable(f'FRED fetch failed: {e}')


def get_macro_warning(window_hours: float = 2.0) -> Optional[str]:
    """Warning line for signals when a high-impact release is imminent.

    FRED release dates carry no intraday timestamp, so any high-impact
    release dated today (or tomorrow when the window crosses midnight UTC)
    triggers the warning — deliberately conservative."""
    cal = get_release_calendar(days_ahead=2)
    if not cal.get('available'):
        return None
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=window_hours)
    todays = [
        r for r in cal['releases']
        if r['high_impact'] and r['date'] in {str(now.date()), str(horizon.date())}
    ]
    if not todays:
        return None
    names = sorted({r['name'] for r in todays})[:3]
    return (f"High-impact release today ({', '.join(names)}) — "
            f"expect volatility; timing per official calendar")
