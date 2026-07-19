"""
Crypto module — CoinGecko free API (keyless; NOT Binance) plus the
alternative.me Fear & Greed Index (free, keyless).

CoinGecko free tier is ~10-30 calls/min: every endpoint is cached.
"""

from typing import Any, Dict

from src.modules.common import cached, http_get_json, unavailable
from src.utils.logger import log

CG = 'https://api.coingecko.com/api/v3'


def get_markets(limit: int = 25) -> Dict[str, Any]:
    def fetch():
        data = http_get_json(f'{CG}/coins/markets', params={
            'vs_currency': 'usd', 'order': 'market_cap_desc',
            'per_page': limit, 'page': 1, 'sparkline': 'true',
            'price_change_percentage': '24h,7d',
        })
        coins = [{
            'id': c.get('id'),
            'symbol': (c.get('symbol') or '').upper(),
            'name': c.get('name'),
            'image': c.get('image'),
            'price': c.get('current_price'),
            'market_cap': c.get('market_cap'),
            'rank': c.get('market_cap_rank'),
            'change_24h_pct': c.get('price_change_percentage_24h'),
            'change_7d_pct': c.get('price_change_percentage_7d_in_currency'),
            'sparkline_7d': (c.get('sparkline_in_7d') or {}).get('price', [])[::4],
        } for c in data]
        return {'available': True, 'coins': coins}

    try:
        return cached(f'cg:markets:{limit}', ttl=120, fetch=fetch)
    except Exception as e:
        log.warning(f"CoinGecko markets failed: {e}")
        return unavailable(f'CoinGecko fetch failed: {e}')


def get_trending() -> Dict[str, Any]:
    def fetch():
        data = http_get_json(f'{CG}/search/trending')
        coins = [{
            'id': i['item'].get('id'),
            'symbol': i['item'].get('symbol'),
            'name': i['item'].get('name'),
            'rank': i['item'].get('market_cap_rank'),
            'thumb': i['item'].get('thumb'),
        } for i in data.get('coins', [])]
        return {'available': True, 'trending': coins}

    try:
        return cached('cg:trending', ttl=600, fetch=fetch)
    except Exception as e:
        return unavailable(f'CoinGecko fetch failed: {e}')


def get_coin_chart(coin_id: str, days: int = 30) -> Dict[str, Any]:
    def fetch():
        data = http_get_json(f'{CG}/coins/{coin_id}/market_chart', params={
            'vs_currency': 'usd', 'days': days,
        })
        return {
            'available': True,
            'coin_id': coin_id,
            'days': days,
            'prices': data.get('prices', []),
            'volumes': data.get('total_volumes', []),
        }

    try:
        return cached(f'cg:chart:{coin_id}:{days}', ttl=600, fetch=fetch)
    except Exception as e:
        return unavailable(f'CoinGecko fetch failed: {e}')


def get_fear_greed(limit: int = 30) -> Dict[str, Any]:
    def fetch():
        data = http_get_json('https://api.alternative.me/fng/', params={'limit': limit})
        entries = [{
            'value': int(d['value']),
            'label': d['value_classification'],
            'timestamp': int(d['timestamp']),
        } for d in data.get('data', [])]
        return {'available': True, 'current': entries[0] if entries else None,
                'history': entries}

    try:
        return cached('fng', ttl=3600, fetch=fetch)
    except Exception as e:
        return unavailable(f'Fear & Greed fetch failed: {e}')
