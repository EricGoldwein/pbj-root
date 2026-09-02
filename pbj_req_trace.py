"""Temporary lightweight request/health concurrency tracing for Render healthz timeouts.

Enable (default on Render): unset or PBJ_HEALTH_TRACE=1
Disable: PBJ_HEALTH_TRACE=0

Logs are one-line, no query strings, no headers, no secrets.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()
_ACTIVE = 0
_ACTIVE_COLD = 0


def health_trace_enabled() -> bool:
    v = (os.environ.get("PBJ_HEALTH_TRACE") or "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    # Default on for Render so the next incident is diagnosable without a Dashboard trip.
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))


def _thread_label() -> str:
    t = threading.current_thread()
    return f"{t.name}:{t.ident}"


def snapshot() -> tuple[int, int]:
    with _LOCK:
        return _ACTIVE, _ACTIVE_COLD


def begin_request(path: str) -> dict[str, Any]:
    """Increment active count; return context for end_request."""
    global _ACTIVE
    with _LOCK:
        _ACTIVE += 1
        active = _ACTIVE
        cold = _ACTIVE_COLD
    ctx = {
        "path": path or "",
        "t0": time.perf_counter(),
        "active_at_start": active,
        "cold_at_start": cold,
        "pid": os.getpid(),
        "thread": _thread_label(),
    }
    if not health_trace_enabled():
        return ctx
    if path in ("/health", "/healthz"):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        print(
            f"[PBJ_HEALTH] enter path={path} ts={ts} pid={ctx['pid']} "
            f"thread={ctx['thread']} active={active} cold={cold}",
            flush=True,
        )
    elif active >= 4:
        # Saturation signal: all gthread slots likely occupied (Render default threads=4).
        print(
            f"[PBJ_REQ] start path={path} pid={ctx['pid']} thread={ctx['thread']} "
            f"active={active} cold={cold}",
            flush=True,
        )
    return ctx


def end_request(ctx: dict[str, Any] | None, status: int | None = None) -> None:
    global _ACTIVE
    if not ctx:
        with _LOCK:
            if _ACTIVE > 0:
                _ACTIVE -= 1
        return
    elapsed_ms = round((time.perf_counter() - float(ctx["t0"])) * 1000.0, 1)
    with _LOCK:
        if _ACTIVE > 0:
            _ACTIVE -= 1
        active = _ACTIVE
        cold = _ACTIVE_COLD
    if not health_trace_enabled():
        return
    path = str(ctx.get("path") or "")
    if path in ("/health", "/healthz"):
        # Only log slow health probes (should be sub-ms); late dispatch shows up as high elapsed.
        if elapsed_ms >= 50.0:
            print(
                f"[PBJ_HEALTH] slow path={path} elapsed_ms={elapsed_ms} status={status} "
                f"pid={ctx.get('pid')} thread={ctx.get('thread')} "
                f"active_at_start={ctx.get('active_at_start')} active_now={active} cold={cold}",
                flush=True,
            )
        return
    active_at_start = int(ctx.get("active_at_start") or 0)
    if active_at_start >= 4 or elapsed_ms >= 2000.0:
        print(
            f"[PBJ_REQ] end path={path} elapsed_ms={elapsed_ms} status={status} "
            f"pid={ctx.get('pid')} thread={ctx.get('thread')} "
            f"active_at_start={active_at_start} active_now={active} "
            f"cold_at_start={ctx.get('cold_at_start')} cold_now={cold}",
            flush=True,
        )


def cold_enter() -> None:
    global _ACTIVE_COLD
    with _LOCK:
        _ACTIVE_COLD += 1


def cold_exit() -> None:
    global _ACTIVE_COLD
    with _LOCK:
        if _ACTIVE_COLD > 0:
            _ACTIVE_COLD -= 1
