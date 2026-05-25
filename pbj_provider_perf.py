"""Provider page performance: UA classification, structured request logs, bot policy helpers."""

from __future__ import annotations

import hashlib
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

# Off by default — critical provider sections must not be skipped for real users.
_DEFAULT_SECTION_BUDGETS_MS: dict[str, float] = {
    'facility_quarterly': 3500.0,
    'state_percentile': 2000.0,
    'entity': 2500.0,
    'charts': 2000.0,
}


def provider_section_budget_enabled() -> bool:
    v = (os.environ.get('PBJ_PROVIDER_SECTION_BUDGET') or '').strip().lower()
    return v in ('1', 'true', 'yes', 'on')


def _on_render() -> bool:
    return bool(os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'))


def provider_perf_log_enabled() -> bool:
    v = (os.environ.get('PBJ_PROVIDER_PERF_LOG') or '').strip().lower()
    if v in ('0', 'false', 'no', 'off'):
        return False
    if v in ('1', 'true', 'yes', 'on'):
        return True
    return _on_render()


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
    return _on_render()


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
    if _on_render():
        return 'private, max-age=300, must-revalidate'
    return 'no-store, must-revalidate'


def provider_section_budget_ms(section: str) -> float:
    """Per-section wall-clock budget (ms) for optional cold-render work."""
    key = f'PBJ_PROVIDER_BUDGET_{section.upper()}'
    raw = (os.environ.get(key) or os.environ.get('PBJ_PROVIDER_SECTION_BUDGET_MS') or '').strip()
    if raw:
        try:
            return max(100.0, float(raw))
        except ValueError:
            pass
    return _DEFAULT_SECTION_BUDGETS_MS.get(section, 2500.0)


def provider_cold_total_budget_ms() -> float:
    """Hard cap on total optional-section work during one cold provider render."""
    raw = (os.environ.get('PBJ_PROVIDER_COLD_TOTAL_BUDGET_MS') or '').strip()
    if raw:
        try:
            return max(500.0, float(raw))
        except ValueError:
            pass
    return 9000.0 if _on_render() else 20000.0


def init_provider_sections() -> None:
    """Reset per-request section timings and skip list (cold provider path)."""
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return
        g.pbj_provider_sections_ms = {}
        g.pbj_provider_sections_skipped = []
        g.pbj_provider_cold_t0 = time.perf_counter()
    except Exception:
        pass


def _append_section_skipped(name: str, reason: str) -> None:
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return
        bucket = getattr(g, 'pbj_provider_sections_skipped', None)
        if bucket is None:
            bucket = []
            g.pbj_provider_sections_skipped = bucket
        entry = {'section': name, 'reason': reason}
        if entry not in bucket:
            bucket.append(entry)
    except Exception:
        pass


def provider_section_skip(name: str, reason: str) -> None:
    """Record and log that an optional provider section was skipped."""
    _append_section_skipped(name, reason)
    if not provider_perf_log_enabled():
        return
    print(
        f'[PBJ_PROVIDER] section_skipped section={name} reason={reason}',
        flush=True,
    )


def provider_section_should_skip(name: str) -> bool:
    """True when cumulative cold time exceeded or section already marked skipped (opt-in only)."""
    if not provider_section_budget_enabled():
        return False
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return False
        skipped = getattr(g, 'pbj_provider_sections_skipped', None) or []
        if any(s.get('section') == name for s in skipped if isinstance(s, dict)):
            return True
        t0 = getattr(g, 'pbj_provider_cold_t0', None)
        if t0 is None:
            return False
        elapsed = (time.perf_counter() - t0) * 1000.0
        if elapsed >= provider_cold_total_budget_ms():
            provider_section_skip(name, 'cold_budget')
            return True
        return False
    except Exception:
        return False


def provider_section_finish(name: str, t0: float) -> None:
    """If a section exceeded its budget, mark it skipped (page still renders core content)."""
    elapsed = (time.perf_counter() - t0) * 1000.0
    provider_section_record(name, t0)
    if elapsed > provider_section_budget_ms(name):
        provider_section_skip(name, 'timeout')


def provider_section_record(name: str, t0: float) -> None:
    """Accumulate elapsed ms for a named cold-render section."""
    if not provider_perf_log_enabled():
        return
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return
        ms = round((time.perf_counter() - t0) * 1000, 1)
        bucket = getattr(g, 'pbj_provider_sections_ms', None)
        if bucket is None:
            bucket = {}
            g.pbj_provider_sections_ms = bucket
        bucket[name] = round(float(bucket.get(name, 0.0)) + ms, 1)
    except Exception:
        pass


def get_provider_sections_ms() -> dict[str, float]:
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return {}
        raw = getattr(g, 'pbj_provider_sections_ms', None)
        if not isinstance(raw, dict):
            return {}
        return {k: round(float(v), 1) for k, v in raw.items()}
    except Exception:
        return {}


def get_provider_sections_skipped() -> list[dict[str, str]]:
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return []
        raw = getattr(g, 'pbj_provider_sections_skipped', None)
        if not isinstance(raw, list):
            return []
        return [x for x in raw if isinstance(x, dict)]
    except Exception:
        return []


def provider_log_index_event(index: str, *, reused: bool, build_ms: float | None = None, **extra: Any) -> None:
    if not provider_perf_log_enabled():
        return
    payload: dict[str, Any] = {
        'index': index,
        'reused': reused,
    }
    if build_ms is not None:
        payload['build_ms'] = round(build_ms, 1)
    payload.update(extra)
    print(
        '[PBJ_PROVIDER_INDEX] ' + json.dumps(payload, separators=(',', ':'), sort_keys=True),
        flush=True,
    )


def provider_crawler_bucket_key(ip: str, ua: str) -> str:
    """Stable bucket for IP + normalized UA (mobile crawlers often rotate only IP)."""
    ua_norm = (ua or '').strip()[:240].lower()
    digest = hashlib.sha256(ua_norm.encode('utf-8', errors='replace')).hexdigest()[:16]
    return f'{ip}|{digest}'


class ProviderRequestTimer:
    """Per-request timings for /provider/<ccn> logging."""

    __slots__ = (
        'ccn',
        't0',
        'cache',
        'queue_wait_ms',
        'cold_render_ms',
        'chart_build_ms',
        'sections_ms',
        'sections_skipped',
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
        self.chart_build_ms = 0.0
        self.sections_ms: dict[str, float] = {}
        self.sections_skipped: list[dict[str, str]] = []
        self.status = 200
        self.stale_serve = False
        self.ua_class = ua_class
        self.pid = pid
        self.outcome = 'ok'

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 1)

    def to_log_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            'ccn': self.ccn,
            'cache': self.cache,
            'total_ms': self.total_ms(),
            'cold_render_ms': round(self.cold_render_ms, 1),
            'chart_build_ms': round(self.chart_build_ms, 1),
            'queue_wait_ms': round(self.queue_wait_ms, 1),
            'pid': self.pid,
            'ua': self.ua_class,
            'status': self.status,
            'stale': self.stale_serve,
            'outcome': self.outcome,
        }
        if self.cache == 'MISS' and self.sections_ms:
            out['sections_ms'] = dict(sorted(self.sections_ms.items()))
        if self.sections_skipped:
            out['sections_skipped'] = self.sections_skipped
        return out

    def emit_log(self) -> None:
        if not provider_perf_log_enabled():
            return
        line = json.dumps(self.to_log_dict(), separators=(',', ':'), sort_keys=True)
        print(f'[PBJ_PROVIDER] {line}', flush=True)
