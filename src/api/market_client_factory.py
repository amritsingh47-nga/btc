"""
Market client factory.

Chooses the market-data client from config `data.source`:
  - "yfinance" (default): CME futures via yfinance, signals-only
  - "binance": the original BinanceClient (kept for reference/backtests;
    trading paths remain stubbed out regardless)
"""

from src.utils.logger import log

_client_singleton = None


def create_market_client(test_mode: bool = True, fresh: bool = False):
    global _client_singleton
    if _client_singleton is not None and not fresh:
        return _client_singleton

    from src.config import Config
    source = str(Config().get('data.source', 'yfinance') or 'yfinance').lower()

    if source == 'binance':
        from src.api.binance_client import BinanceClient
        log.warning("data.source=binance — using BinanceClient (data only; trading is stubbed)")
        client = BinanceClient(test_mode=True)
    elif source == 'synthetic':
        from src.api.synthetic_client import SyntheticMarketClient
        client = SyntheticMarketClient(test_mode=True)
    else:
        from src.api.yfinance_client import YFinanceClient
        client = YFinanceClient(test_mode=True)

    _client_singleton = client
    return client
