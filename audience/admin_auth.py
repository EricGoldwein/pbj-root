"""Admin authentication for audience management routes."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any

from flask import Request, session

SESSION_KEY = 'pbj_audience_admin_auth'
_LOGIN_WINDOW_SEC = 900
_MAX_LOGIN_ATTEMPTS = 8
_login_attempts: dict[str, tuple[int, float]] = {}


def admin_key_configured() -> str:
    return (os.environ.get('ADMIN_VIEW_KEY') or os.environ.get('PBJ_ADMIN_KEY') or '').strip()


def _session_token(expected: str) -> str:
    return hmac.new(
        expected.encode('utf-8'),
        b'pbj-audience-admin-session',
        hashlib.sha256,
    ).hexdigest()


def verify_admin_request(request: Request) -> bool:
    """
    Authenticate admin via Authorization: Bearer, X-PBJ-Admin-Key header,
    or signed browser session (set by POST /admin/audience/login).
    Query-string keys are NOT accepted.
    """
    expected = admin_key_configured()
    if not expected:
        return False
    auth = (request.headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        token = auth[7:].strip()
        if token and hmac.compare_digest(token, expected):
            return True
    header = (request.headers.get('X-PBJ-Admin-Key') or '').strip()
    if header and hmac.compare_digest(header, expected):
        return True
    sess = session.get(SESSION_KEY)
    return bool(sess and hmac.compare_digest(str(sess), _session_token(expected)))


def establish_admin_session() -> None:
    expected = admin_key_configured()
    if not expected:
        raise RuntimeError('admin_key_not_configured')
    session[SESSION_KEY] = _session_token(expected)
    session.permanent = True


def clear_admin_session() -> None:
    session.pop(SESSION_KEY, None)


def login_rate_limit_ok(remote_addr: str | None) -> bool:
    key = (remote_addr or 'unknown').strip()
    now = time.time()
    count, window_start = _login_attempts.get(key, (0, now))
    if now - window_start > _LOGIN_WINDOW_SEC:
        _login_attempts[key] = (0, now)
        return True
    return count < _MAX_LOGIN_ATTEMPTS


def record_login_attempt(remote_addr: str | None, *, success: bool) -> None:
    key = (remote_addr or 'unknown').strip()
    now = time.time()
    count, window_start = _login_attempts.get(key, (0, now))
    if now - window_start > _LOGIN_WINDOW_SEC:
        count, window_start = 0, now
    if success:
        _login_attempts[key] = (0, window_start)
    else:
        _login_attempts[key] = (count + 1, window_start)


def admin_noindex_headers() -> dict[str, str]:
    return {
        'X-Robots-Tag': 'noindex, nofollow',
        'Cache-Control': 'private, no-store',
    }


def reset_login_attempts_for_tests() -> None:
    _login_attempts.clear()
