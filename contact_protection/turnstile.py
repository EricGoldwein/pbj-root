"""Cloudflare Turnstile Siteverify client."""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Optional

from contact_protection import store
from contact_protection.config import (
    TURNSTILE_ACTION,
    TURNSTILE_SITEVERIFY_URL,
    TURNSTILE_TEST_SECRET_PASS,
    expected_hostnames,
    is_production_environment,
    turnstile_required,
    turnstile_secret_key,
)

_log = logging.getLogger('pbj.contact_protection')

# Injectable for tests: (url, data=dict|None, timeout=...) -> response with .json()
_siteverify_post: Callable[..., Any] | None = None


@dataclass(frozen=True)
class TurnstileResult:
    ok: bool
    reason: str = ''  # '' | turnstile_failed | turnstile_unavailable
    detail: str = ''


def set_siteverify_post_for_tests(fn: Callable[..., Any] | None) -> None:
    global _siteverify_post
    _siteverify_post = fn


def _default_http_post(url: str, data: Optional[dict] = None, timeout: float = 8.0):
    body = urllib.parse.urlencode(data or {}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )

    class _Resp:
        def __init__(self, payload: dict[str, Any]):
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
    return _Resp(json.loads(raw))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def verify_turnstile_token(
    token: Optional[str],
    *,
    remoteip: Optional[str] = None,
) -> TurnstileResult:
    if not turnstile_required():
        return TurnstileResult(ok=True, reason='', detail='skip_non_production')

    secret = turnstile_secret_key()
    if not secret:
        _log.warning('turnstile_secret_missing')
        return TurnstileResult(ok=False, reason='turnstile_unavailable', detail='secret_missing')

    token = (token or '').strip()
    if not token or len(token) > 4096:
        return TurnstileResult(ok=False, reason='turnstile_failed', detail='missing_token')

    th = _token_hash(token)
    try:
        if store.token_already_used(th):
            return TurnstileResult(ok=False, reason='turnstile_failed', detail='token_reused')
    except Exception as exc:
        _log.warning('token_reuse_check_failed err=%s', type(exc).__name__)
        if is_production_environment():
            return TurnstileResult(ok=False, reason='turnstile_unavailable', detail='store_error')

    payload = {'secret': secret, 'response': token}
    if remoteip:
        payload['remoteip'] = remoteip

    http = _siteverify_post or _default_http_post
    try:
        resp = http(TURNSTILE_SITEVERIFY_URL, data=payload, timeout=8.0)
        data = resp.json() if hasattr(resp, 'json') else resp
    except Exception as exc:
        _log.warning('turnstile_network_error err=%s', type(exc).__name__)
        return TurnstileResult(ok=False, reason='turnstile_unavailable', detail='network')

    if not isinstance(data, dict) or data.get('success') is not True:
        return TurnstileResult(ok=False, reason='turnstile_failed', detail='success_false')

    action = (data.get('action') or '').strip()
    # Cloudflare always-pass test secret may omit action; enforce for real secrets.
    enforce_action = secret != TURNSTILE_TEST_SECRET_PASS
    if enforce_action:
        if action != TURNSTILE_ACTION:
            return TurnstileResult(ok=False, reason='turnstile_failed', detail='bad_action')

    hostname = (data.get('hostname') or '').strip().lower()
    enforce_host = secret != TURNSTILE_TEST_SECRET_PASS
    if enforce_host:
        allowed = expected_hostnames()
        if not hostname or hostname not in allowed:
            return TurnstileResult(ok=False, reason='turnstile_failed', detail='bad_hostname')

    try:
        store.mark_token_used(th)
    except Exception as exc:
        _log.warning('token_mark_failed err=%s', type(exc).__name__)

    return TurnstileResult(ok=True, reason='')
