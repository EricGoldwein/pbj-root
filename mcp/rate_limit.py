"""Simple in-memory rate limiter for public MCP endpoint."""

from __future__ import annotations

import os
import time
from collections import deque

_WINDOW_SEC = max(30, int(os.environ.get("PBJ_MCP_RATE_WINDOW_SEC", "60")))
_LIMIT = max(1, int(os.environ.get("PBJ_MCP_RATE_LIMIT", "120")))
_HITS: dict[str, deque[float]] = {}


def _client_ip() -> str:
    try:
        from flask import request

        fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return fwd or (request.remote_addr or "unknown")
    except Exception:
        return "unknown"


def mcp_rate_limit_exceeded() -> int | None:
    if os.environ.get("PBJ_MCP_RATE_LIMIT", "").strip().lower() in ("0", "off", "false", "no"):
        return None
    ip = _client_ip()
    now = time.time()
    q = _HITS.setdefault(ip, deque())
    while q and now - q[0] > _WINDOW_SEC:
        q.popleft()
    if len(q) >= _LIMIT:
        retry = max(1, int(_WINDOW_SEC - (now - q[0]))) if q else _WINDOW_SEC
        return retry
    q.append(now)
    return None
