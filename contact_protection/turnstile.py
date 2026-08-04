"""Cloudflare Turnstile server-side verification for contact submissions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from contact_protection import config
from contact_protection import store

_log = logging.getLogger('pbj.contact_protection')

# Test hook: (url, data=None, timeout=None) -> response with .json()
_siteverify_post_for_tests: Optional[Callable[..., Any]] = None


def set_siteverify_post_for_tests(fn: Optional[Callable[..., Any]]) -> None:
    global _siteverify_post_for_tests
    _siteverify_post_for_tests = fn


@dataclass(frozen=True)
class TurnstileResult:
    ok: bool
    reason: str  # ok | missing | failed | hostname | action | reused | unavailable | bypass
    hostname: str = ''
    action: str = ''
    error_codes: tuple[str, ...] = ()


def _default_post(url: str, data=None, timeout=None):
    import requests

    return requests.post(url, data=data, timeout=timeout)


def _post_siteverify(secret: str, token: str, remoteip: Optional[str]) -> dict[str, Any]:
    payload = {
        'secret': secret,
        'response': token,
    }
    if remoteip:
        payload['remoteip'] = remoteip
    post = _siteverify_post_for_tests or _default_post
    resp = post(config.TURNSTILE_SITEVERIFY_URL, data=payload, timeout=8)
    if hasattr(resp, 'json'):
        return resp.json()
    if isinstance(resp, dict):
        return resp
    raise ValueError('invalid siteverify response')


def verify_turnstile(
    token: str,
    *,
    remoteip: Optional[str] = None,
) -> TurnstileResult:
    if config.allow_turnstile_bypass_for_tests():
        return TurnstileResult(ok=True, reason='bypass')

    secret = config.turnstile_secret_key()
    if not secret:
        return TurnstileResult(ok=False, reason='unavailable')

    token = (token or '').strip()
    if not token:
        return TurnstileResult(ok=False, reason='missing')

    if store.token_already_used(token):
        return TurnstileResult(ok=False, reason='reused')

    try:
        payload = _post_siteverify(secret, token, remoteip)
    except Exception as exc:  # noqa: BLE001 — fail closed
        _log.warning('turnstile_network_error err=%s', type(exc).__name__)
        return TurnstileResult(ok=False, reason='unavailable')

    if not isinstance(payload, dict) or not payload.get('success'):
        codes = ()
        if isinstance(payload, dict):
            codes = tuple(str(c) for c in (payload.get('error-codes') or [])[:8])
        return TurnstileResult(ok=False, reason='failed', error_codes=codes)

    hostname = str(payload.get('hostname') or '').strip().lower()
    action = str(payload.get('action') or '').strip()
    using_test_secret = secret == config.TURNSTILE_TEST_SECRET_PASS
    expected = config.expected_hostnames()

    if hostname and hostname not in expected:
        return TurnstileResult(ok=False, reason='hostname', hostname=hostname, action=action)

    # Require expected action. Empty action allowed only with Cloudflare test secret outside production.
    action_ok = action == config.TURNSTILE_ACTION or (
        not action
        and using_test_secret
        and not config.is_production_environment()
    )
    if not action_ok:
        return TurnstileResult(ok=False, reason='action', hostname=hostname, action=action)

    store.mark_token_used(token)
    return TurnstileResult(ok=True, reason='ok', hostname=hostname, action=action)
