"""
Portfolio tracker — manual position entry only. No broker linking. Ever.

Positions live in data/modules/portfolio.json. Live P&L marks against
yfinance (stocks/futures/FX tickers) or CoinGecko (asset_type=crypto,
symbol=coingecko id like "bitcoin").
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.modules.common import cached, http_get_json, load_json_store, save_json_store
from src.utils.logger import log


def _load() -> List[Dict[str, Any]]:
    return load_json_store('portfolio', [])


def _save(positions: List[Dict[str, Any]]) -> None:
    save_json_store('portfolio', positions)


def list_positions() -> List[Dict[str, Any]]:
    return _load()


def add_position(symbol: str, direction: str, size: float, entry_price: float,
                 asset_type: str = 'stock', notes: str = '') -> Dict[str, Any]:
    direction = direction.lower()
    if direction not in ('long', 'short'):
        raise ValueError('direction must be long or short')
    if asset_type not in ('stock', 'futures', 'crypto', 'fx'):
        raise ValueError('asset_type must be stock, futures, crypto or fx')
    position = {
        'id': uuid.uuid4().hex[:12],
        'symbol': symbol.strip(),
        'asset_type': asset_type,
        'direction': direction,
        'size': float(size),
        'entry_price': float(entry_price),
        'notes': str(notes)[:500],
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    positions = _load()
    positions.append(position)
    _save(positions)
    return position


def update_position(pos_id: str, **changes) -> Optional[Dict[str, Any]]:
    positions = _load()
    for pos in positions:
        if pos['id'] == pos_id:
            for key in ('symbol', 'direction', 'size', 'entry_price', 'notes', 'asset_type'):
                if key in changes and changes[key] is not None:
                    pos[key] = changes[key]
            pos['size'] = float(pos['size'])
            pos['entry_price'] = float(pos['entry_price'])
            _save(positions)
            return pos
    return None


def delete_position(pos_id: str) -> bool:
    positions = _load()
    remaining = [p for p in positions if p['id'] != pos_id]
    _save(remaining)
    return len(remaining) < len(positions)


def _crypto_price(coin_id: str) -> Optional[float]:
    def fetch():
        data = http_get_json('https://api.coingecko.com/api/v3/simple/price',
                             params={'ids': coin_id, 'vs_currencies': 'usd'})
        return data.get(coin_id, {}).get('usd')
    try:
        return cached(f'cg:simple:{coin_id}', ttl=120, fetch=fetch)
    except Exception:
        return None


def _yf_price(symbol: str) -> Optional[float]:
    def fetch():
        from src.api.yfinance_client import YFinanceClient
        price = YFinanceClient().get_ticker_price(symbol).get('price')
        return price or None
    try:
        return cached(f'yf:price:{symbol}', ttl=120, fetch=fetch)
    except Exception:
        return None


def get_portfolio_with_pnl() -> Dict[str, Any]:
    positions = _load()
    total_value = 0.0
    total_pnl = 0.0
    priced = 0
    for pos in positions:
        if pos['asset_type'] == 'crypto':
            price = _crypto_price(pos['symbol'].lower())
        else:
            price = _yf_price(pos['symbol'])
        pos['current_price'] = price
        if price:
            sign = 1 if pos['direction'] == 'long' else -1
            pnl = (price - pos['entry_price']) * pos['size'] * sign
            pos['pnl'] = round(pnl, 2)
            pos['pnl_pct'] = round(
                (price / pos['entry_price'] - 1) * 100 * sign, 2
            ) if pos['entry_price'] else None
            pos['market_value'] = round(abs(price * pos['size']), 2)
            total_value += pos['market_value']
            total_pnl += pnl
            priced += 1
        else:
            pos['pnl'] = None
            pos['pnl_pct'] = None
            pos['market_value'] = None
    return {
        'available': True,
        'positions': positions,
        'totals': {
            'market_value': round(total_value, 2),
            'pnl': round(total_pnl, 2),
            'priced': priced,
            'unpriced': len(positions) - priced,
        },
    }
