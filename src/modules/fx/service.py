"""
FX panel — Frankfurter (free, keyless, ECB reference rates).

Small currencies panel giving dollar-strength context for GC/CL:
USD vs EUR, GBP, JPY, CHF, AUD, CAD + 30-day USD/EUR trend.
"""

from datetime import date, timedelta
from typing import Any, Dict

from src.modules.common import cached, http_get_json, unavailable

BASE = 'https://api.frankfurter.app'
PAIRS = ['EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD']


def get_rates() -> Dict[str, Any]:
    def fetch():
        data = http_get_json(f'{BASE}/latest', params={
            'from': 'USD', 'to': ','.join(PAIRS)})
        return {'available': True, 'date': data.get('date'),
                'base': 'USD', 'rates': data.get('rates', {})}

    try:
        return cached('fx:latest', ttl=3600, fetch=fetch)
    except Exception as e:
        return unavailable(f'Frankfurter fetch failed: {e}')


def get_usd_trend(days: int = 30) -> Dict[str, Any]:
    def fetch():
        start = date.today() - timedelta(days=days)
        data = http_get_json(f'{BASE}/{start}..', params={
            'from': 'USD', 'to': 'EUR,JPY'})
        series = [
            {'date': d, 'eur': rates.get('EUR'), 'jpy': rates.get('JPY')}
            for d, rates in sorted((data.get('rates') or {}).items())
        ]
        return {'available': True, 'series': series}

    try:
        return cached(f'fx:trend:{days}', ttl=6 * 3600, fetch=fetch)
    except Exception as e:
        return unavailable(f'Frankfurter fetch failed: {e}')
