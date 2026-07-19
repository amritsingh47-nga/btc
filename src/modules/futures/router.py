"""
Futures Signals dashboard API — clean JSON endpoints the new React
frontend polls. Reads the live pipeline state (global_state) and the
market client; never touches any execution surface.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter

from src.server.state import global_state
from src.utils.logger import log

router = APIRouter(prefix="/api/modules/futures", tags=["futures"])


def _instruments() -> Dict[str, Dict[str, str]]:
    try:
        from src.config import Config
        return Config().get('instruments', {}) or {}
    except Exception:
        return {}


def _display(symbol: str) -> str:
    meta = _instruments().get(symbol, {})
    return meta.get('display', symbol)


@router.get("/overview")
async def overview():
    instruments = _instruments()
    from src.config import Config
    data_source = str(Config().get('data.source', 'yfinance')).lower()
    with global_state.locked():
        return {
            'signals_only': True,
            'data_source': data_source,
            'synthetic': data_source == 'synthetic',
            'is_running': global_state.is_running,
            'execution_mode': global_state.execution_mode,
            'cycle': global_state.cycle_counter,
            'cycle_interval_minutes': global_state.cycle_interval,
            'symbols': [
                {
                    'symbol': sym,
                    'display': (instruments.get(sym) or {}).get('display', sym),
                    'name': (instruments.get(sym) or {}).get('name', ''),
                    'price': global_state.current_price.get(sym),
                    'regime': global_state.market_regime.get(sym)
                              if isinstance(global_state.market_regime, dict) else None,
                }
                for sym in (global_state.symbols or list(instruments))
            ],
            'virtual_account': {
                'initial_balance': global_state.virtual_initial_balance,
                'balance': global_state.virtual_balance,
                'equity': global_state.account_overview.get('total_equity'),
                'total_pnl': global_state.account_overview.get('total_pnl'),
                'realized_pnl': global_state.cumulative_realized_pnl,
                'open_positions': global_state.virtual_positions,
            },
            'last_update': global_state.last_update,
        }


@router.get("/decisions")
async def decisions(limit: int = 50):
    with global_state.locked():
        history = list(global_state.decision_history)[:limit]
    out = []
    for d in history:
        out.append({
            'time': d.get('timestamp'),
            'cycle': d.get('cycle_number'),
            'symbol': d.get('symbol'),
            'display': _display(d.get('symbol', '')),
            'action': d.get('action'),
            'confidence': d.get('confidence'),
            'reason': d.get('reason'),
            'risk_label': 'PASS' if d.get('guardian_passed') else 'WOULD-VETO',
            'risk_reason': d.get('guardian_reason'),
            'regime': (d.get('regime') or {}).get('regime') if isinstance(d.get('regime'), dict) else None,
            'weighted_score': d.get('weighted_score'),
        })
    return {'decisions': out}


@router.get("/feed")
async def signal_feed(limit: int = 120):
    """Chatroom-style agent messages for the live feed panel."""
    with global_state.locked():
        messages = list(global_state.agent_messages)[-limit:]
        logs = list(global_state.recent_logs)[-limit:]
    return {'agent_messages': messages, 'logs': logs}


@router.get("/pnl-curve")
async def pnl_curve():
    with global_state.locked():
        return {
            'initial_balance': global_state.virtual_initial_balance,
            'equity_history': list(global_state.equity_history),
            'trade_history': list(global_state.trade_history)[:100],
        }


@router.get("/candles/{symbol:path}")
async def candles(symbol: str, interval: str = '15m', limit: int = 200):
    """Candles + decision markers for the chart. `symbol:path` because
    futures symbols contain '=' (e.g. NQ=F)."""
    from src.api.market_client_factory import create_market_client
    client = create_market_client()
    try:
        klines = client.get_klines(symbol.upper(), interval, limit=min(max(limit, 20), 500))
    except Exception as e:
        log.warning(f"candles fetch failed {symbol}: {e}")
        return {'available': False, 'reason': str(e)}

    with global_state.locked():
        history = [d for d in global_state.decision_history
                   if d.get('symbol') == symbol.upper()][:60]
    markers = []
    for d in history:
        action = str(d.get('action', '')).lower()
        if action not in ('open_long', 'open_short'):
            continue
        markers.append({
            'time': d.get('timestamp'),
            'action': 'long' if action == 'open_long' else 'short',
            'confidence': d.get('confidence'),
            'would_veto': not d.get('guardian_passed', True),
        })
    return {
        'available': bool(klines),
        'symbol': symbol.upper(),
        'display': _display(symbol.upper()),
        'interval': interval,
        'advisory_only': interval == '5m',
        'candles': klines,
        'markers': markers,
    }


@router.post("/quiet-mode")
async def set_quiet_mode(enabled: bool):
    from src.notifications import get_notifier
    n = get_notifier()
    n.quiet_mode = bool(enabled)
    if not n.quiet_mode:
        n.maybe_flush_pass_digest(force=True)
    return {'quiet_mode': n.quiet_mode}


@router.get("/discord-status")
async def discord_status():
    try:
        from src.notifications import get_notifier
        n = get_notifier()
        return {
            'configured': bool(n.webhook_url),
            'quiet_mode': n.quiet_mode,
            'sent_count': n.sent_count,
            'last_error': n.last_error,
        }
    except Exception as e:
        return {'configured': False, 'error': str(e)}
