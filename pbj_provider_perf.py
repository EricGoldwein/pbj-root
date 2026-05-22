"""Provider page performance: UA classification, structured request logs, bot policy helpers."""

from __future__ import annotations

import json
import os
import time
from typing import Any

# Search / AI crawlers — cold renders blocked when PBJ_AI_PROVIDER_CACHE_ONLY is enabled.
_DEFAULT_AI_CRAWLER_MARKERS = (
    'gptbot',
    'oai-searchbot',
    'chatgpt-user',
    'claudebot',
    'claude-searchbot',
    'claude-web',
    'anthropic-ai',
    'perplexitybot',
    'perplexity-user',
    'cohere-ai',
    'meta-externalagent',
    'bytespider',
    'ccbot',
    'amazonbot',
)

_GOOGLEBOT_MARKERS = ('googlebot', 'google-inspectiontool', 'adsbot-google')
_BINGBOT_MARKERS = ('bingbot', 'msnbot', 'adidxbot')


def provider_perf_log_enabled() -> bool:
    v = (os.environ.get('PBJ_PROVIDER_PERF_LOG') or '').strip().lower()
    if v in ('0', 'false', 'no', 'off'):
        return False
    if v in ('1', 'true', 'yes', 'on'):
        return True
    return bool(os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'))


def ai_crawler_markers() -> tuple[str, ...]:
    raw = (os.environ.get('PBJ_AI_CRAWLER_MARKERS') or '').strip()
    if raw:
        parts = [p.strip().lower() for p in raw.split(',') if p.strip()]
        return tuple(parts) if parts else _DEFAULT_AI_CRAWLER_MARKERS
    return _DEFAULT_AI_CRAWLER_MARKERS


def classify_user_agent(ua: str) -> str:
    """human | googlebot | bingbot | ai_crawler | aggressive_bot | other_bot"""
    low = (ua or '').lower()
    if not low:
        return 'human'
    aggressive = (
        'semrushbot',
        'ahrefsbot',
        'dotbot',
        'dataforseo',
        'petalbot',
        'sleepbot',
    )
    if any(m in low for m in aggressive):
        return 'aggressive_bot'
    if any(m in low for m in _GOOGLEBOT_MARKERS):
        return 'googlebot'
    if any(m in low for m in _BINGBOT_MARKERS):
        return 'bingbot'
    if any(m in low for m in ai_crawler_markers()):
        return 'ai_crawler'
    if 'bot' in low or 'crawler' in low or 'spider' in low:
        return 'other_bot'
    return 'human'


def ai_heavy_routes_cache_only_enabled() -> bool:
    """When true, AI crawlers must not trigger expensive /provider or /entity renders."""
    v = (os.environ.get('PBJ_AI_PROVIDER_CACHE_ONLY') or '').strip().lower()
    if v in ('0', 'false', 'no', 'off'):
        return False
    if v in ('1', 'true', 'yes', 'on'):
        return True
    return bool(os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'))


def ai_provider_cache_only_enabled() -> bool:
    """Alias for ai_heavy_routes_cache_only_enabled (provider cache MISS policy)."""
    return ai_heavy_routes_cache_only_enabled()


def provider_browser_cache_control() -> str:
    """Browser cache for provider HTML (quarterly CMS/PBJ data)."""
    v = (os.environ.get('PBJ_PROVIDER_BROWSER_CACHE') or '').strip().lower()
    if v in ('0', 'false', 'no', 'off'):
        return 'no-store, must-revalidate'
    if v in ('1', 'true', 'yes', 'on'):
        return 'private, max-age=300, must-revalidate'
    if os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'):
        return 'private, max-age=300, must-revalidate'
    return 'no-store, must-revalidate'


class ProviderRequestTimer:
    """Per-request timings for /provider/<ccn> logging."""

    __slots__ = (
        'ccn',
        't0',
        'cache',
        'queue_wait_ms',
        'cold_render_ms',
        'status',
        'stale_serve',
        'ua_class',
        'pid',
        'outcome',
    )

    def __init__(self, ccn: str, *, ua_class: str, pid: int) -> None:
        self.ccn = ccn
        self.t0 = time.perf_counter()
        self.cache = 'MISS'
        self.queue_wait_ms = 0.0
        self.cold_render_ms = 0.0
        self.status = 200
        self.stale_serve = False
        self.ua_class = ua_class
        self.pid = pid
        self.outcome = 'ok'

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 1)

    def to_log_dict(self) -> dict[str, Any]:
        return {
            'ccn': self.ccn,
            'cache': self.cache,
            'total_ms': self.total_ms(),
            'cold_render_ms': round(self.cold_render_ms, 1),
            'queue_wait_ms': round(self.queue_wait_ms, 1),
            'pid': self.pid,
            'ua': self.ua_class,
            'status': self.status,
            'stale': self.stale_serve,
            'outcome': self.outcome,
        }

    def emit_log(self) -> None:
        if not provider_perf_log_enabled():
            return
        line = json.dumps(self.to_log_dict(), separators=(',', ':'), sort_keys=True)
        print(f'[PBJ_PROVIDER] {line}', flush=True)
