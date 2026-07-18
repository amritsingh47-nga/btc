"""
Synthetic market-data client (offline/demo mode).

Selected with config `data.source: synthetic`. Generates a plausible
random-walk OHLCV series per symbol so the full agent pipeline, the
dashboard, and the Discord formatting can be exercised with no network
access. Every payload is tagged `synthetic: True` and the UI/Discord
label the mode clearly — this is for development and demos, never for
judging real markets.
"""

import hashlib
import math
import random
import time
from typing import Dict, List, Optional

from src.api.yfinance_client import YFinanceClient
from src.utils.logger import log

_BASE_PRICES = {
    'NQ=F': 24000.0,
    'ES=F': 6600.0,
    'GC=F': 3350.0,
    'CL=F': 66.0,
}

_INTERVAL_MS = {'1m': 60_000, '5m': 300_000, '15m': 900_000,
                '1h': 3_600_000, '4h': 14_400_000, '1d': 86_400_000}


class SyntheticMarketClient(YFinanceClient):
    """YFinanceClient with the network swapped for a deterministic random walk."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.warning("🧪 SYNTHETIC data mode — generated prices, for pipeline demo/tests only")

    def _seed_for(self, symbol: str) -> int:
        return int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)

    def get_klines(self, symbol: str, interval: str, limit: int = 500,
                   start_time: int = None) -> List[Dict]:
        ms = _INTERVAL_MS.get(interval)
        if ms is None:
            raise ValueError(f"Unsupported interval: {interval}")
        base = _BASE_PRICES.get(symbol.upper(), 100.0)
        now_ms = int(time.time() * 1000)
        last_closed = (now_ms // ms) * ms

        count = max(limit, 10)
        first_ts = last_closed - (count - 1) * ms

        rng = random.Random(self._seed_for(symbol))
        # Walk deterministically from a fixed epoch so successive calls
        # agree on overlapping candles.
        epoch = 1_700_000_000_000
        steps_before = max(0, (first_ts - epoch) // ms)
        price = base
        # fast-forward the RNG state cheaply: reseed with the bar index
        klines = []
        for i in range(count):
            ts = first_ts + i * ms
            bar_index = (ts - epoch) // ms
            bar_rng = random.Random(self._seed_for(symbol) ^ bar_index)
            # slow sinusoidal drift + noise => visible regimes/trends
            drift = math.sin(bar_index / 96.0) * 0.0008
            change = drift + bar_rng.gauss(0, 0.0018)
            open_ = price
            close = price * (1 + change)
            spread = abs(bar_rng.gauss(0, 0.0012))
            high = max(open_, close) * (1 + spread)
            low = min(open_, close) * (1 - spread)
            volume = abs(bar_rng.gauss(1500, 400))
            klines.append({
                'timestamp': ts,
                'open': round(open_, 4),
                'high': round(high, 4),
                'low': round(low, 4),
                'close': round(close, 4),
                'volume': round(volume, 2),
                'close_time': ts + ms - 1,
                'quote_volume': round(volume * close, 2),
                'trades': int(volume),
                'taker_buy_base': round(volume / 2, 2),
                'taker_buy_quote': round(volume * close / 2, 2),
                'synthetic': True,
            })
            price = close
        if start_time is not None:
            klines = [k for k in klines if k['timestamp'] >= start_time]
        return klines[-limit:]

    def get_ticker_price(self, symbol: str) -> Dict:
        k = self.get_klines(symbol, '5m', limit=1)
        return {'symbol': symbol, 'price': k[-1]['close'] if k else 0.0,
                'synthetic': True}
