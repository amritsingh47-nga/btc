"""
News / sentiment module.

- Keyless RSS ingestion from major finance feeds (config `news.feeds`,
  overridable without code changes since feeds die).
- Trump post monitoring via a free Truth Social RSS mirror
  (TRUMP_RSS_URL env or config `news.trump_rss_url`). Mirrors change —
  the URL is config, never hardcoded logic. Posts matching market
  keywords are flagged "market-moving political post" and attached as
  sentiment events to NQ / GC / CL.
- Rule-based keyword sentiment per headline (v1; LLM scoring can be
  added behind the LLM key later).
- get_instrument_sentiment_line(symbol): one-line summary consumed by
  the futures Discord embed.

The official Truth Social API (institutional/paid) and paid scraper
APIs are deliberately NOT integrated — see config for the commented
future-upgrade slot.
"""

import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.modules.common import cached, http_get_text, load_json_store, save_json_store, unavailable
from src.utils.logger import log

DEFAULT_FEEDS = [
    # Feeds are free/keyless; verify they still resolve on first run
    # (the module tolerates dead feeds and reports per-feed status).
    {'name': 'CNBC Top News', 'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html'},
    {'name': 'CNBC Markets', 'url': 'https://www.cnbc.com/id/20910258/device/rss/rss.html'},
    {'name': 'MarketWatch Top', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_topstories'},
    {'name': 'MarketWatch Pulse', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines'},
    {'name': 'Yahoo Finance', 'url': 'https://finance.yahoo.com/news/rssindex'},
]

# Default Truth Social mirror — mirrors die; override via TRUMP_RSS_URL.
DEFAULT_TRUMP_RSS = 'https://trumpstruth.org/feed'

BULLISH_WORDS = {
    'rally', 'rallies', 'surge', 'surges', 'soar', 'soars', 'jump', 'jumps',
    'gain', 'gains', 'record high', 'beat', 'beats', 'upbeat', 'optimism',
    'strong', 'boost', 'boosts', 'rebound', 'recovers', 'recovery', 'bullish',
    'rate cut', 'rate cuts', 'stimulus', 'dovish', 'cooling inflation', 'soft landing',
}
BEARISH_WORDS = {
    'fall', 'falls', 'drop', 'drops', 'plunge', 'plunges', 'slump', 'slumps',
    'tumble', 'tumbles', 'sink', 'sinks', 'slide', 'slides', 'crash', 'selloff',
    'sell-off', 'fear', 'fears', 'recession', 'bearish', 'miss', 'misses',
    'weak', 'warning', 'warns', 'downgrade', 'cuts forecast', 'layoffs',
    'rate hike', 'rate hikes', 'hawkish', 'hot inflation', 'default', 'tariff',
    'tariffs', 'sanctions', 'war', 'strike', 'shutdown',
}

# Map headlines to instruments by keyword
INSTRUMENT_KEYWORDS = {
    'NQ=F': ['nasdaq', 'tech', 'ai ', 'artificial intelligence', 'chip', 'semiconductor',
             'nvidia', 'apple', 'microsoft', 'google', 'alphabet', 'amazon', 'meta',
             'tesla', 'software', 'rates', 'fed ', 'federal reserve', 'yields'],
    'ES=F': ['s&p', 'sp 500', 's&p 500', 'stocks', 'wall street', 'equities', 'dow',
             'earnings', 'fed ', 'federal reserve', 'rates', 'economy', 'inflation'],
    'GC=F': ['gold', 'bullion', 'safe haven', 'safe-haven', 'inflation', 'dollar',
             'treasury', 'yields', 'fed ', 'geopolitic', 'war', 'central bank'],
    'CL=F': ['oil', 'crude', 'opec', 'wti', 'brent', 'energy', 'gasoline', 'barrel',
             'petroleum', 'saudi', 'iran', 'russia', 'sanctions'],
}

# Political-post keywords that historically move NQ/GC/CL
POLITICAL_MARKET_KEYWORDS = [
    'tariff', 'trade', 'china', 'fed', 'powell', 'rates', 'dollar', 'tax',
    'oil', 'opec', 'energy', 'war', 'sanction', 'iran', 'russia', 'ukraine',
    'israel', 'economy', 'inflation', 'crypto', 'bitcoin',
]

_items_lock = threading.Lock()
_items: List[Dict[str, Any]] = []          # newest first
_feed_status: Dict[str, str] = {}
_last_refresh: Optional[str] = None
_poller_started = False


def _get_feeds() -> List[Dict[str, str]]:
    try:
        from src.config import Config
        feeds = Config().get('news.feeds', None)
        if feeds:
            return [f if isinstance(f, dict) else {'name': f, 'url': f} for f in feeds]
    except Exception:
        pass
    return DEFAULT_FEEDS


def _get_trump_url() -> Optional[str]:
    url = (os.getenv('TRUMP_RSS_URL') or '').strip()
    if url:
        return url
    try:
        from src.config import Config
        return Config().get('news.trump_rss_url', DEFAULT_TRUMP_RSS)
    except Exception:
        return DEFAULT_TRUMP_RSS


def score_headline(text: str) -> float:
    """Keyword sentiment in [-1, 1]."""
    t = ' ' + re.sub(r'\s+', ' ', str(text).lower()) + ' '
    bull = sum(1 for w in BULLISH_WORDS if w in t)
    bear = sum(1 for w in BEARISH_WORDS if w in t)
    if bull == bear == 0:
        return 0.0
    return max(-1.0, min(1.0, (bull - bear) / max(bull + bear, 1)))


def instruments_for(text: str) -> List[str]:
    t = ' ' + str(text).lower() + ' '
    return [sym for sym, words in INSTRUMENT_KEYWORDS.items()
            if any(w in t for w in words)]


def _parse_feed(name: str, url: str, is_political: bool) -> List[Dict[str, Any]]:
    import feedparser
    raw = http_get_text(url, timeout=20)
    parsed = feedparser.parse(raw)
    out = []
    for e in parsed.entries[:40]:
        title = getattr(e, 'title', '') or ''
        summary = re.sub(r'<[^>]+>', ' ', getattr(e, 'summary', '') or '')[:400]
        text = f"{title} {summary}"
        published = None
        for attr in ('published_parsed', 'updated_parsed'):
            tm = getattr(e, attr, None)
            if tm:
                published = datetime(*tm[:6], tzinfo=timezone.utc).isoformat()
                break
        score = score_headline(text)
        syms = instruments_for(text)
        item = {
            'id': getattr(e, 'id', None) or getattr(e, 'link', None) or title,
            'source': name,
            'title': title.strip(),
            'link': getattr(e, 'link', None),
            'published': published,
            'sentiment': round(score, 3),
            'instruments': syms,
            'political': is_political,
        }
        if is_political:
            market_moving = any(k in text.lower() for k in POLITICAL_MARKET_KEYWORDS)
            item['market_moving_political_post'] = market_moving
            if market_moving:
                # political posts land on the politically-sensitive contracts
                item['instruments'] = sorted(set(syms) | {'NQ=F', 'GC=F', 'CL=F'})
        out.append(item)
    return out


def refresh(force: bool = False) -> Dict[str, Any]:
    global _items, _last_refresh

    def do_refresh():
        collected: List[Dict[str, Any]] = []
        feeds = list(_get_feeds())
        trump_url = _get_trump_url()
        if trump_url:
            feeds.append({'name': 'Trump / Truth Social mirror', 'url': trump_url,
                          'political': True})
        for feed in feeds:
            try:
                items = _parse_feed(feed['name'], feed['url'],
                                    bool(feed.get('political')))
                collected.extend(items)
                _feed_status[feed['name']] = f'ok ({len(items)} items)'
            except Exception as e:
                _feed_status[feed['name']] = f'error: {e}'
                log.warning(f"RSS feed '{feed['name']}' failed: {e}")

        seen = set()
        unique = []
        for item in sorted(collected, key=lambda x: x.get('published') or '',
                           reverse=True):
            if item['id'] in seen:
                continue
            seen.add(item['id'])
            unique.append(item)
        return unique[:300]

    try:
        items = cached('news:items', ttl=0 if force else 300, fetch=do_refresh)
        with _items_lock:
            _items = items
        _last_refresh = datetime.now(timezone.utc).isoformat()
        save_json_store('news_cache', {'refreshed': _last_refresh, 'items': items[:100]})
        return {'available': True, 'count': len(items)}
    except Exception as e:
        # keep whatever we have (possibly persisted from a previous run)
        with _items_lock:
            if not _items:
                persisted = load_json_store('news_cache', {})
                _items = persisted.get('items', [])
        return unavailable(f'news refresh failed: {e}')


def ensure_poller() -> None:
    """Background refresh every 5 minutes."""
    global _poller_started
    if _poller_started:
        return
    _poller_started = True

    def loop():
        while True:
            try:
                refresh()
            except Exception as e:
                log.warning(f"news poll failed: {e}")
            time.sleep(300)

    threading.Thread(target=loop, daemon=True, name='news-poller').start()


def get_news(limit: int = 100, instrument: Optional[str] = None,
             political_only: bool = False) -> Dict[str, Any]:
    ensure_poller()
    with _items_lock:
        items = list(_items)
    if not items:
        refresh()
        with _items_lock:
            items = list(_items)
    if instrument:
        items = [i for i in items if instrument.upper() in (i.get('instruments') or [])]
    if political_only:
        items = [i for i in items if i.get('political')]
    return {
        'available': True,
        'last_refresh': _last_refresh,
        'feed_status': dict(_feed_status),
        'items': items[:limit],
    }


def get_instrument_sentiment(symbol: str) -> Dict[str, Any]:
    data = get_news(limit=300)
    relevant = [i for i in data['items']
                if symbol.upper() in (i.get('instruments') or [])]
    scores = [i['sentiment'] for i in relevant if i.get('sentiment') is not None]
    political = [i for i in relevant if i.get('market_moving_political_post')]
    avg = sum(scores) / len(scores) if scores else 0.0
    if avg > 0.15:
        mood = 'bullish'
    elif avg > 0.05:
        mood = 'mildly bullish'
    elif avg < -0.15:
        mood = 'bearish'
    elif avg < -0.05:
        mood = 'mildly bearish'
    else:
        mood = 'neutral'
    return {
        'symbol': symbol,
        'score': round(avg, 3),
        'mood': mood,
        'headline_count': len(relevant),
        'political_flags': len(political),
        'latest_political': political[0]['title'][:140] if political else None,
    }


def get_instrument_sentiment_line(symbol: str) -> Optional[str]:
    s = get_instrument_sentiment(symbol)
    if s['headline_count'] == 0:
        return None
    line = f"News: {s['mood']} ({s['score']:+.2f}, {s['headline_count']} headlines)"
    if s['political_flags']:
        line += f" · ⚑ {s['political_flags']} market-moving political post(s)"
    return line
