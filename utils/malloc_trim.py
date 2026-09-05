"""Linux/glibc malloc_trim(0) proof-of-fix hook for Render RSS growth.

Controlled-A/B mechanism (see fix/malloc-trim-proof-20260905): called only
after a successfully admitted expensive cold provider/entity/owner build
(the same _EXPENSIVE_BUILD_GATE admission used for those three routes in
app.py), gated by an RSS high-water threshold and a minimum interval between
trims. Fails open (no-op) on any non-Linux platform, when libc/malloc_trim is
unavailable, or when RSS can't be read. Never touches Python-level caches --
this only asks glibc to return already-freed arena pages to the OS.

Env vars (conservative test defaults -- not tuned for production):
  PBJ_MALLOC_TRIM_ENABLED           default '1'
  PBJ_MALLOC_TRIM_RSS_THRESHOLD_MB  default '1200'
  PBJ_MALLOC_TRIM_MIN_INTERVAL_S    default '60'
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import sys
import threading
import time

from utils.memory_debug import mem_rss_mb


def _env_bool(name: str, default: bool) -> bool:
    v = (os.environ.get(name) or '').strip().lower()
    if v in ('1', 'true', 'yes', 'on'):
        return True
    if v in ('0', 'false', 'no', 'off'):
        return False
    return default


def _env_float(name: str, default: float) -> float:
    try:
        v = (os.environ.get(name) or '').strip()
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def _load_libc():
    if not sys.platform.startswith('linux'):
        return None
    try:
        lib_name = ctypes.util.find_library('c') or 'libc.so.6'
        libc = ctypes.CDLL(lib_name, use_errno=True)
        trim_fn = getattr(libc, 'malloc_trim', None)
        if trim_fn is None:
            return None
        trim_fn.argtypes = [ctypes.c_size_t]
        trim_fn.restype = ctypes.c_int
        return libc
    except Exception:
        return None


_LIBC = _load_libc()
_LOCK = threading.Lock()
_LAST_TRIM_MONOTONIC = 0.0


def _emit(payload: dict) -> None:
    try:
        sys.stderr.write('[MALLOC_TRIM] ' + json.dumps(payload, sort_keys=True) + '\n')
        sys.stderr.flush()
    except Exception:
        pass


def malloc_trim_available() -> bool:
    return _LIBC is not None


def maybe_trim(route_family: str) -> None:
    """Best-effort malloc_trim(0) after a successful expensive cold build.

    Fail-open no-op unless: enabled, running on Linux with libc malloc_trim
    resolved, RSS is readable and >= the configured threshold, and the
    min-interval cooldown has elapsed. Thread-safe via a non-blocking lock --
    a trim already in flight on another thread is skipped, not queued.
    """
    global _LAST_TRIM_MONOTONIC

    if not _env_bool('PBJ_MALLOC_TRIM_ENABLED', True):
        _emit({'event': 'malloc_trim', 'route_family': route_family, 'ran': False, 'skip_reason': 'disabled'})
        return
    if _LIBC is None:
        _emit({'event': 'malloc_trim', 'route_family': route_family, 'ran': False, 'skip_reason': 'libc_unavailable'})
        return

    rss_before = mem_rss_mb()
    if rss_before is None:
        _emit({'event': 'malloc_trim', 'route_family': route_family, 'ran': False, 'skip_reason': 'rss_unavailable'})
        return

    threshold_mb = _env_float('PBJ_MALLOC_TRIM_RSS_THRESHOLD_MB', 1200.0)
    if rss_before < threshold_mb:
        _emit({
            'event': 'malloc_trim',
            'route_family': route_family,
            'ran': False,
            'skip_reason': 'below_threshold',
            'rss_before_mb': rss_before,
            'threshold_mb': threshold_mb,
        })
        return

    if not _LOCK.acquire(blocking=False):
        _emit({
            'event': 'malloc_trim',
            'route_family': route_family,
            'ran': False,
            'skip_reason': 'trim_in_progress',
            'rss_before_mb': rss_before,
        })
        return

    try:
        min_interval_s = _env_float('PBJ_MALLOC_TRIM_MIN_INTERVAL_S', 60.0)
        now = time.monotonic()
        elapsed = now - _LAST_TRIM_MONOTONIC
        if _LAST_TRIM_MONOTONIC and elapsed < min_interval_s:
            _emit({
                'event': 'malloc_trim',
                'route_family': route_family,
                'ran': False,
                'skip_reason': 'cooldown',
                'rss_before_mb': rss_before,
                'seconds_since_last_trim': round(elapsed, 1),
                'min_interval_s': min_interval_s,
            })
            return

        t0 = time.monotonic()
        try:
            _LIBC.malloc_trim(0)
        except Exception:
            _emit({
                'event': 'malloc_trim',
                'route_family': route_family,
                'ran': False,
                'skip_reason': 'trim_call_failed',
                'rss_before_mb': rss_before,
            })
            return
        duration_ms = (time.monotonic() - t0) * 1000.0
        _LAST_TRIM_MONOTONIC = time.monotonic()

        rss_after = mem_rss_mb()
        reclaimed_mb = (rss_before - rss_after) if rss_after is not None else None
        _emit({
            'event': 'malloc_trim',
            'route_family': route_family,
            'ran': True,
            'rss_before_mb': rss_before,
            'rss_after_mb': rss_after,
            'reclaimed_mb': round(reclaimed_mb, 1) if reclaimed_mb is not None else None,
            'trim_duration_ms': round(duration_ms, 2),
        })
    finally:
        _LOCK.release()
