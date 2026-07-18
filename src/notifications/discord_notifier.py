"""
Discord webhook notifier for futures signals.

Message contract (see build spec §3):
- TAKE (open_long / open_short, including WOULD-VETO ideas): rich embed
  with confidence, regime, risk-audit label, entry/stop/target,
  1h/15m alignment, one-line reasoning, macro warning, sentiment read.
- PASS (wait/hold): one compact line. With DISCORD_QUIET_MODE=true,
  PASSes are batched into an hourly digest while TAKEs post immediately.

The webhook URL comes exclusively from the DISCORD_WEBHOOK_URL env var
(.env). It is a secret: never commit it, rotate it in Discord if leaked.

Posting happens on a single daemon worker thread so a slow/unreachable
Discord can never stall the trading cycle.
"""

import os
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.utils.logger import log

FOOTER_TEXT = "Signals only — nothing is ever executed. Not financial advice."

_COLOR_LONG = 0x2ECC71      # green
_COLOR_SHORT = 0xE74C3C     # red
_COLOR_VETO = 0xE67E22      # orange
_COLOR_INFO = 0x3498DB      # blue

# Common Chinese fragments from the base repo's rule engine -> English
_REASON_TRANSLATIONS = [
    ('加权得分', 'weighted score'),
    ('周期对齐', 'period alignment'),
    ('震荡市观望', 'choppy market, standing aside'),
    ('震荡市', 'choppy market'),
    ('趋势市', 'trending market'),
    ('观望', 'standing aside'),
    ('位置', 'position'),
    ('多头', 'long'),
    ('空头', 'short'),
    ('信号不足', 'insufficient signal'),
    ('高波动', 'high volatility'),
]


def _clean_reason(reason: Optional[str], limit: int = 220) -> str:
    text = str(reason or '').strip()
    for cn, en in _REASON_TRANSLATIONS:
        text = text.replace(cn, en)
    text = ' '.join(text.split())
    return (text[: limit - 1] + '…') if len(text) > limit else (text or 'n/a')


def _fmt_price(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 'n/a'
    if v >= 1000:
        return f"{v:,.2f}"
    return f"{v:,.4g}" if v < 10 else f"{v:,.2f}"


def _trend_word(score: Any) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return '·'
    if s > 15:
        return f"LONG (+{s:.0f})"
    if s < -15:
        return f"SHORT ({s:.0f})"
    return f"FLAT ({s:+.0f})"


class DiscordNotifier:
    def __init__(self):
        self.webhook_url = (os.getenv('DISCORD_WEBHOOK_URL') or '').strip()
        self.quiet_mode = str(os.getenv('DISCORD_QUIET_MODE', 'false')).lower() in ('1', 'true', 'yes')
        self._warned_missing = False
        self._queue: "queue.Queue[Dict]" = queue.Queue(maxsize=200)
        self._pass_buffer: List[str] = []
        self._pass_lock = threading.Lock()
        self._last_digest_ts = time.monotonic()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name='discord-notifier')
        self._worker.start()
        self.last_error: Optional[str] = None
        self.sent_count = 0

        self._display_map = self._load_display_map()

        if self.webhook_url:
            log.info(f"📣 Discord notifier ready (quiet_mode={self.quiet_mode})")
        else:
            log.warning("📣 DISCORD_WEBHOOK_URL not set — Discord alerts disabled (dashboard still works)")

    # ------------------------------------------------------------------
    @staticmethod
    def _load_display_map() -> Dict[str, str]:
        try:
            from src.config import Config
            instruments = Config().get('instruments', {}) or {}
            return {sym.upper(): (meta or {}).get('display', sym)
                    for sym, meta in instruments.items()}
        except Exception:
            return {}

    def display(self, symbol: str) -> str:
        return self._display_map.get(str(symbol).upper(), symbol)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def notify_cycle_result(self, symbol: str, result: Dict[str, Any],
                            cycle_num: Optional[int] = None,
                            synthetic: bool = False) -> None:
        """Route one per-symbol cycle result to the right message shape."""
        try:
            status = str(result.get('status', '')).lower()
            action = str(result.get('action', 'wait')).lower()

            if status in ('error', 'failed'):
                return  # runtime errors belong in logs, not the signal channel
            if action in ('open_long', 'open_short') and status in ('suggested', 'success', 'would_veto'):
                self._send_take(symbol, result, synthetic=synthetic)
            elif action.startswith('close') and status == 'success':
                self._send_close(symbol, result, synthetic=synthetic)
            else:
                reason = (result.get('details') or {}).get('reason') or result.get('reason')
                self._send_pass(symbol, reason, synthetic=synthetic)
        except Exception as e:
            log.warning(f"Discord notify failed for {symbol}: {e}")

    def maybe_flush_pass_digest(self, force: bool = False) -> None:
        """Post the batched PASS digest if an hour has elapsed (quiet mode)."""
        if not self.quiet_mode:
            return
        with self._pass_lock:
            elapsed = time.monotonic() - self._last_digest_ts
            if not self._pass_buffer or (elapsed < 3600 and not force):
                return
            lines = self._pass_buffer[:]
            self._pass_buffer.clear()
            self._last_digest_ts = time.monotonic()
        self._enqueue({
            'embeds': [{
                'title': '🟡 PASS digest (hourly)',
                'description': '\n'.join(lines[-40:]),
                'color': _COLOR_INFO,
                'footer': {'text': FOOTER_TEXT},
            }]
        })

    def send_text(self, content: str) -> None:
        self._enqueue({'content': content[:1900]})

    # ------------------------------------------------------------------
    # message builders
    # ------------------------------------------------------------------
    def _macro_warning_line(self) -> Optional[str]:
        try:
            from src.modules.macro.service import get_macro_warning
            return get_macro_warning()
        except Exception:
            return None

    def _sentiment_line(self, symbol: str) -> Optional[str]:
        try:
            from src.modules.news.service import get_instrument_sentiment_line
            return get_instrument_sentiment_line(symbol)
        except Exception:
            return None

    def _send_take(self, symbol: str, result: Dict[str, Any], synthetic: bool) -> None:
        action = str(result.get('action', '')).lower()
        direction = 'LONG' if action == 'open_long' else 'SHORT'
        disp = self.display(symbol)
        would_veto = str(result.get('status', '')).lower() == 'would_veto'

        order = result.get('order_params') or {}
        details = result.get('details') or {}
        vote = result.get('vote_result')
        confidence = result.get('confidence', order.get('confidence', 0)) or 0
        reason = getattr(vote, 'reason', None) or details.get('reason') or order.get('reason')

        regime = order.get('regime') or getattr(vote, 'regime', None) or {}
        regime_txt = regime.get('regime', 'Unknown') if isinstance(regime, dict) else str(regime)

        trend_scores = order.get('trend_scores') or {}
        align_1h = _trend_word(trend_scores.get('trend_1h_score'))
        align_15m = _trend_word(trend_scores.get('trend_15m_score'))
        aligned = getattr(vote, 'multi_period_aligned', None)
        align_txt = f"1h {align_1h} · 15m {align_15m}"
        if aligned is not None:
            align_txt += ' — aligned ✅' if aligned else ' — misaligned ⚠️'
        align_txt += "\n5m trigger is ADVISORY-ONLY (delayed data)"

        risk_txt = '🏷️ WOULD-VETO — ' + _clean_reason(details.get('reason'), 120) if would_veto else '✅ PASS'

        title = f"🚀 TAKE: {direction} {disp}"
        if would_veto:
            title = f"🏷️ TAKE (WOULD-VETO): {direction} {disp}"
        if synthetic:
            title = f"🧪 [SYNTHETIC DEMO] {title}"

        entry = order.get('entry_price', result.get('current_price'))
        fields = [
            {'name': 'Confidence', 'value': f"{float(confidence):.0f}%", 'inline': True},
            {'name': 'Regime', 'value': str(regime_txt), 'inline': True},
            {'name': 'Risk audit', 'value': risk_txt, 'inline': True},
            {'name': 'Entry zone', 'value': _fmt_price(entry), 'inline': True},
            {'name': 'Stop', 'value': _fmt_price(order.get('stop_loss')), 'inline': True},
            {'name': 'Target', 'value': _fmt_price(order.get('take_profit')), 'inline': True},
            {'name': '1h / 15m alignment', 'value': align_txt, 'inline': False},
            {'name': 'Reasoning', 'value': _clean_reason(reason), 'inline': False},
        ]

        macro = self._macro_warning_line()
        if macro:
            fields.append({'name': '⚠️ Macro', 'value': macro[:1000], 'inline': False})
        senti = self._sentiment_line(symbol)
        if senti:
            fields.append({'name': 'Sentiment', 'value': senti[:1000], 'inline': False})

        color = _COLOR_VETO if would_veto else (_COLOR_LONG if direction == 'LONG' else _COLOR_SHORT)
        self._enqueue({
            'embeds': [{
                'title': title,
                'color': color,
                'fields': fields,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'footer': {'text': FOOTER_TEXT},
            }]
        })

    def _send_close(self, symbol: str, result: Dict[str, Any], synthetic: bool) -> None:
        disp = self.display(symbol)
        details = result.get('details') or {}
        title = f"📕 Hypothetical close: {disp}"
        if synthetic:
            title = f"🧪 [SYNTHETIC DEMO] {title}"
        self._enqueue({
            'embeds': [{
                'title': title,
                'description': _clean_reason(details.get('reason') or result.get('action')),
                'color': _COLOR_INFO,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'footer': {'text': FOOTER_TEXT},
            }]
        })

    def _send_pass(self, symbol: str, reason: Optional[str], synthetic: bool) -> None:
        disp = self.display(symbol)
        line = f"🟡 PASS {disp} — {_clean_reason(reason, 160)}"
        if synthetic:
            line = f"🧪 {line}"
        if self.quiet_mode:
            with self._pass_lock:
                self._pass_buffer.append(f"`{datetime.now().strftime('%H:%M')}` {line}")
            self.maybe_flush_pass_digest()
            return
        self.send_text(line)

    # ------------------------------------------------------------------
    # delivery
    # ------------------------------------------------------------------
    def _enqueue(self, payload: Dict) -> None:
        if not self.webhook_url:
            if not self._warned_missing:
                log.warning("Discord alert skipped — DISCORD_WEBHOOK_URL is not configured")
                self._warned_missing = True
            return
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            log.warning("Discord queue full, dropping message")

    def _worker_loop(self) -> None:
        while True:
            payload = self._queue.get()
            for attempt in range(3):
                try:
                    resp = requests.post(self.webhook_url, json=payload, timeout=10)
                    if resp.status_code in (200, 204):
                        self.last_error = None
                        self.sent_count += 1
                        break
                    if resp.status_code == 429:
                        retry_after = float(resp.headers.get('Retry-After', 2))
                        time.sleep(min(retry_after, 30))
                        continue
                    self.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    log.warning(f"Discord webhook error {self.last_error}")
                    break
                except Exception as e:
                    self.last_error = str(e)
                    time.sleep(2 * (attempt + 1))
            else:
                log.warning(f"Discord webhook giving up: {self.last_error}")
            # Respect Discord webhook rate limits (~30 req/min)
            time.sleep(2.1)


_notifier: Optional[DiscordNotifier] = None
_notifier_lock = threading.Lock()


def get_notifier() -> DiscordNotifier:
    global _notifier
    with _notifier_lock:
        if _notifier is None:
            _notifier = DiscordNotifier()
        return _notifier
