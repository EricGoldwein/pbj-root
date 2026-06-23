"""Process RSS logging and cache size helpers for Render memory diagnosis.

Enable with PBJ_MEM_DEBUG=1 (verbose [MEM] step labels + /debug/mem).
Route-level lines: PBJ_MEM_ROUTE_LOG=1 or when PBJ_MEM_DEBUG=1.
"""

from __future__ import annotations

import gc
import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator

try:
    import psutil  # type: ignore[reportMissingImports]

    _PSUTIL_PROCESS = psutil.Process()
except ImportError:
    _PSUTIL_PROCESS = None


def mem_debug_enabled() -> bool:
    return os.environ.get('PBJ_MEM_DEBUG', '').strip().lower() in ('1', 'true', 'yes', 'on')


def mem_route_log_enabled() -> bool:
    v = (os.environ.get('PBJ_MEM_ROUTE_LOG') or '').strip().lower()
    if v in ('1', 'true', 'yes', 'on'):
        return True
    if v in ('0', 'false', 'no', 'off'):
        return False
    return mem_debug_enabled()


def mem_rss_mb() -> float | None:
    """Process RSS in MB, or None when psutil is unavailable."""
    if _PSUTIL_PROCESS is None:
        return None
    try:
        return round(_PSUTIL_PROCESS.memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def log_mem(label: str, *, gc_collect: bool = False) -> float | None:
    """Log RSS when PBJ_MEM_DEBUG=1. Optionally run gc.collect() first."""
    if not mem_debug_enabled():
        return mem_rss_mb()
    rss_before = mem_rss_mb()
    freed = 0
    if gc_collect:
        freed = gc.collect()
    rss = mem_rss_mb()
    if rss is not None:
        gc_part = f' gc_freed={freed}' if gc_collect else ''
        delta = ''
        if gc_collect and rss_before is not None:
            delta = f' delta={rss - rss_before:+.1f}MB'
        print(f'[MEM] {label}: {rss:.1f} MB RSS{gc_part}{delta}', flush=True)
    return rss


@contextmanager
def mem_step(label: str, *, gc_after: bool = False) -> Iterator[None]:
    """Context manager: log RSS before/after a heavy step when PBJ_MEM_DEBUG=1."""
    if mem_debug_enabled():
        log_mem(f'{label}_before')
    try:
        yield
    finally:
        log_mem(f'{label}_after', gc_collect=gc_after)


def estimate_object_bytes(obj: Any) -> int | None:
    """Rough deep size estimate (best-effort; may return None on failure)."""
    try:
        return _deep_size(obj, seen=set())
    except Exception:
        return None


def _deep_size(obj: Any, seen: set[int]) -> int:
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(_deep_size(k, seen) + _deep_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(_deep_size(x, seen) for x in obj)
    elif hasattr(obj, '__dict__'):
        size += _deep_size(obj.__dict__, seen)
    return size


def format_bytes(n: int | None) -> str | None:
    if n is None:
        return None
    if n >= 1024 * 1024:
        return f'{n / (1024 * 1024):.1f}MB'
    if n >= 1024:
        return f'{n / 1024:.1f}KB'
    return f'{n}B'


def summarize_byte_sizes(sizes: list[int]) -> dict[str, Any]:
    """Aggregate byte sizes: total, avg, max (empty list → zeros)."""
    if not sizes:
        return {
            'count': 0,
            'total_bytes': 0,
            'avg_bytes': 0,
            'max_bytes': 0,
            'total_human': '0B',
            'avg_human': '0B',
            'max_human': '0B',
        }
    total = sum(sizes)
    avg = int(round(total / len(sizes)))
    mx = max(sizes)
    return {
        'count': len(sizes),
        'total_bytes': total,
        'avg_bytes': avg,
        'max_bytes': mx,
        'total_human': format_bytes(total),
        'avg_human': format_bytes(avg),
        'max_human': format_bytes(mx),
    }


def utf8_text_bytes(text: str) -> int:
    """UTF-8 encoded length for cached HTML/text."""
    try:
        return len(text.encode('utf-8'))
    except Exception:
        return sys.getsizeof(text)


def estimate_dataframe_bytes(df: Any) -> int | None:
    """pandas DataFrame deep memory_usage when available."""
    if df is None:
        return 0
    try:
        import pandas as pd  # type: ignore[reportMissingImports]

        if isinstance(df, pd.DataFrame):
            return int(df.memory_usage(deep=True).sum())
    except Exception:
        pass
    return estimate_object_bytes(df)


def cache_entry_summary(
    *,
    name: str,
    count: int | None = None,
    max_size: int | None = None,
    ttl_seconds: float | None = None,
    stores: str = '',
    scope: str = '',
    sample_bytes: int | None = None,
    populated: bool | None = None,
    total_bytes: int | None = None,
    avg_bytes: int | None = None,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    """Structured cache metadata for /debug/mem (no sensitive payloads)."""
    out: dict[str, Any] = {'name': name}
    if count is not None:
        out['entries'] = count
    if max_size is not None:
        out['max_entries'] = max_size
    if ttl_seconds is not None:
        out['ttl_seconds'] = ttl_seconds
    if stores:
        out['stores'] = stores
    if scope:
        out['scope'] = scope
    if sample_bytes is not None:
        out['sample_bytes'] = sample_bytes
        out['sample_human'] = format_bytes(sample_bytes)
    if total_bytes is not None:
        out['total_bytes'] = total_bytes
        out['total_human'] = format_bytes(total_bytes)
    if avg_bytes is not None:
        out['avg_bytes'] = avg_bytes
        out['avg_human'] = format_bytes(avg_bytes)
    if max_bytes is not None:
        out['max_bytes'] = max_bytes
        out['max_human'] = format_bytes(max_bytes)
    if populated is not None:
        out['populated'] = populated
    return out
