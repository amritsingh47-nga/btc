"""
YFinance market-data client (signals-only).

Drop-in replacement for the data side of BinanceClient, used when
config `data.source == "yfinance"`. Serves CME futures continuous
contracts (NQ=F, ES=F, GC=F, CL=F) over the same method surface the
agent pipeline calls on BinanceClient.

Notes / accepted quirks (see spec):
- yfinance data is ~15 minutes delayed. 5m candles are therefore
  advisory-only for triggers.
- No funding rate / open interest / orderbook exists for this feed;
  those methods return neutral placeholders.
- Every order-placing method raises SignalsOnlyError: this client can
  never trade. The virtual account lives in global_state, not here.
"""

import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.utils.logger import log


class SignalsOnlyError(RuntimeError):
    """Raised if any code path ever tries to place a real order."""


# Minimum seconds between two Yahoo requests (politeness throttle)
_REQUEST_SPACING = 0.35

# interval -> (yfinance interval, period to request, ms per bar)
_INTERVAL_MAP = {
    '1m':  ('1m',  '2d',  60_000),
    '5m':  ('5m',  '5d',  300_000),
    '15m': ('15m', '10d', 900_000),
    '1h':  ('1h',  '60d', 3_600_000),
    '4h':  ('1h',  '60d', 3_600_000),   # resampled below
    '1d':  ('1d',  '2y',  86_400_000),
}


class YFinanceClient:
    """Market data via yfinance; account methods are virtual; trading is impossible."""

    def __init__(self, api_key: str = None, api_secret: str = None,
                 testnet: bool = None, test_mode: bool = True):
        # Signature kept compatible with BinanceClient; keys are ignored.
        self.test_mode = True          # permanently true, never trades
        self.offline = False
        self.testnet = True
        self._lock = threading.Lock()
        self._last_request_ts = 0.0
        # (symbol, interval) -> (fetch_monotonic, klines list)
        self._kline_cache: Dict = {}
        self._price_cache: Dict = {}
        log.info("📈 YFinance client initialized (signals-only, no trading surface)")

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _throttle(self):
        with self._lock:
            wait = _REQUEST_SPACING - (time.monotonic() - self._last_request_ts)
            if wait > 0:
                time.sleep(wait)
            self._last_request_ts = time.monotonic()

    def _history(self, symbol: str, yf_interval: str, period: str,
                 start_ms: Optional[int] = None):
        import yfinance as yf
        self._throttle()
        ticker = yf.Ticker(symbol)
        kwargs = dict(interval=yf_interval, auto_adjust=False, actions=False)
        if start_ms:
            kwargs['start'] = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        else:
            kwargs['period'] = period
        df = ticker.history(**kwargs)
        return df

    @staticmethod
    def _df_to_klines(df, ms_per_bar: int) -> List[Dict]:
        klines = []
        for ts, row in df.iterrows():
            open_ = float(row['Open'])
            close = float(row['Close'])
            volume = float(row['Volume']) if row['Volume'] == row['Volume'] else 0.0
            if open_ != open_ or close != close:      # NaN row (holiday gap)
                continue
            t_ms = int(ts.timestamp() * 1000)
            klines.append({
                'timestamp': t_ms,
                'open': open_,
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': close,
                'volume': volume,
                'close_time': t_ms + ms_per_bar - 1,
                'quote_volume': volume * close,
                'trades': 0,
                # No taker split in this feed; a 50/50 split keeps
                # buy-ratio style features neutral instead of zeroed.
                'taker_buy_base': volume / 2.0,
                'taker_buy_quote': (volume * close) / 2.0,
            })
        return klines

    # ------------------------------------------------------------------
    # market data (the surface DataSync/kline_cache actually use)
    # ------------------------------------------------------------------
    def get_klines(self, symbol: str, interval: str, limit: int = 500,
                   start_time: int = None) -> List[Dict]:
        if interval not in _INTERVAL_MAP:
            raise ValueError(f"Unsupported interval for yfinance: {interval}")
        yf_interval, period, ms_per_bar = _INTERVAL_MAP[interval]

        # Scale the requested period up when the caller wants more bars than
        # the default window holds (e.g. ML training wants weeks of 5m).
        # Yahoo caps intraday history at ~60 days.
        if limit:
            bars_per_day = max(1, 86_400_000 // ms_per_bar)
            needed_days = min(60, (limit // bars_per_day) + 3)
            default_days = int(period.rstrip('dy')) if period.endswith('d') else 9999
            if needed_days > default_days and yf_interval != '1d':
                period = f"{needed_days}d"

        # Short in-memory TTL so one cycle's repeated callers share a fetch.
        cache_key = (symbol.upper(), interval, bool(start_time))
        ttl = 60 if start_time is None else 30
        cached = self._kline_cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < ttl and start_time is None:
            return cached[1][-limit:]

        try:
            df = self._history(symbol, yf_interval, period, start_ms=start_time)
        except Exception as e:
            log.error(f"[yfinance] fetch failed {symbol}/{interval}: {e}")
            if cached:
                log.warning(f"[yfinance] serving stale cache for {symbol}/{interval}")
                return cached[1][-limit:]
            return []

        if df is None or df.empty:
            if start_time is not None:
                return []          # incremental fetch with nothing new is normal
            log.warning(f"[yfinance] empty history for {symbol}/{interval}")
            return cached[1][-limit:] if cached else []

        if interval == '4h':
            df = (df.resample('4h', origin='start_day')
                    .agg({'Open': 'first', 'High': 'max', 'Low': 'min',
                          'Close': 'last', 'Volume': 'sum'})
                    .dropna(subset=['Open', 'Close']))

        klines = self._df_to_klines(df, ms_per_bar)
        if start_time is not None:
            klines = [k for k in klines if k['timestamp'] >= start_time]
        else:
            self._kline_cache[cache_key] = (time.monotonic(), klines)
        return klines[-limit:] if limit else klines

    def get_ticker_price(self, symbol: str) -> Dict:
        cached = self._price_cache.get(symbol.upper())
        if cached and time.monotonic() - cached[0] < 30:
            return cached[1]
        price = 0.0
        try:
            import yfinance as yf
            self._throttle()
            info = yf.Ticker(symbol).fast_info
            price = float(info['last_price'])
        except Exception as e:
            log.warning(f"[yfinance] fast_info failed for {symbol}: {e}")
            klines = self.get_klines(symbol, '5m', limit=1)
            if klines:
                price = klines[-1]['close']
        result = {'symbol': symbol, 'price': price}
        self._price_cache[symbol.upper()] = (time.monotonic(), result)
        return result

    def get_all_tickers(self) -> List[Dict]:
        # Only used by the AUTO symbol selector (disabled for futures mode).
        return []

    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        return {'bids': [], 'asks': [], 'symbol': symbol}

    # ------------------------------------------------------------------
    # derivatives metadata that has no equivalent in this feed
    # ------------------------------------------------------------------
    def get_funding_rate(self, symbol: str) -> Dict:
        return {'symbol': symbol, 'funding_rate': 0.0, 'funding_time': 0,
                'mark_price': 0.0, 'unavailable': True}

    def get_funding_rate_with_cache(self, symbol: str) -> Dict:
        return self.get_funding_rate(symbol)

    def get_open_interest(self, symbol: str) -> Dict:
        return {'symbol': symbol, 'open_interest': 0.0, 'timestamp': None,
                'unavailable': True}

    # ------------------------------------------------------------------
    # account surface: virtual only (test mode / hypothetical PnL)
    # ------------------------------------------------------------------
    def get_account_info(self) -> Dict:
        return {'balances': [], 'virtual': True}

    def get_futures_account(self) -> Dict:
        from src.server.state import global_state
        balance = float(getattr(global_state, 'virtual_balance', 1000.0) or 1000.0)
        return {
            'totalWalletBalance': balance,
            'totalUnrealizedProfit': 0.0,
            'totalMarginBalance': balance,
            'availableBalance': balance,
            'assets': [],
            'positions': [],
            'virtual': True,
        }

    def get_futures_position(self, symbol: str) -> Optional[Dict]:
        from src.server.state import global_state
        pos = (getattr(global_state, 'virtual_positions', {}) or {}).get(symbol)
        if not pos:
            return None
        qty = float(pos.get('quantity', 0.0) or 0.0)
        if pos.get('side') == 'short':
            qty = -qty
        return {
            'symbol': symbol,
            'position_amt': qty,
            'entry_price': float(pos.get('entry_price', 0.0) or 0.0),
            'unrealized_pnl': float(pos.get('unrealized_pnl', 0.0) or 0.0),
            'leverage': 1,
            'virtual': True,
        }

    def get_account_balance(self) -> float:
        from src.server.state import global_state
        return float(getattr(global_state, 'virtual_balance', 1000.0) or 1000.0)

    def get_account_equity_estimate(self) -> float:
        return self.get_account_balance()

    def get_symbol_info(self, symbol: str) -> Dict:
        return {'symbol': symbol, 'status': 'TRADING'}

    def get_symbol_min_notional(self, symbol: str) -> float:
        return 0.0

    def get_market_data_snapshot(self, symbol: str) -> Dict:
        return {'symbol': symbol, 'price': self.get_ticker_price(symbol).get('price', 0.0)}

    # ------------------------------------------------------------------
    # trading surface: intentionally unreachable (HARD RULE #1)
    # ------------------------------------------------------------------
    def _refuse(self, what: str):
        raise SignalsOnlyError(
            f"{what} requested, but this system is signals-only and can never "
            f"place, route, or execute a trade on any venue."
        )

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        return True   # meaningless for a virtual book; accept and ignore

    def place_market_order(self, *args, **kwargs):
        self._refuse("place_market_order")

    def place_futures_market_order(self, *args, **kwargs):
        self._refuse("place_futures_market_order")

    def place_limit_order(self, *args, **kwargs):
        self._refuse("place_limit_order")

    def set_stop_loss_take_profit(self, *args, **kwargs):
        self._refuse("set_stop_loss_take_profit")

    def cancel_all_orders(self, symbol: str) -> Dict:
        return {'symbol': symbol, 'status': 'noop'}
