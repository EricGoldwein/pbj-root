"""Configuration for PBJ320 contact-form spam protections."""

from __future__ import annotations

import os
from typing import FrozenSet

# Cloudflare Turnstile official test keys
TURNSTILE_TEST_SITE_KEY = '1x00000000000000000000AA'
TURNSTILE_TEST_SECRET_PASS = '1x0000000000000000000000000000000AA'
TURNSTILE_TEST_SECRET_KEY = TURNSTILE_TEST_SECRET_PASS  # alias
TURNSTILE_TEST_BLOCK_SECRET = '2x0000000000000000000000000000000AB'

TURNSTILE_ACTION = 'pbj_request'
TURNSTILE_SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

DEFAULT_EXPECTED_HOSTNAMES: FrozenSet[str] = frozenset(
    {
        'pbj320.com',
        'www.pbj320.com',
        'pbj.onrender.com',
    }
)

NAME_MIN = 2
NAME_MAX = 100
EMAIL_MAX = 254
MESSAGE_MIN = 10
MESSAGE_MAX = 5000
SUBJECT_TYPE_MAX = 64
MAX_BODY_BYTES = 64_000

RATE_IP_PER_15M = int(os.environ.get('CONTACT_RATE_IP_15M', '3') or '3')
RATE_IP_PER_24H = int(os.environ.get('CONTACT_RATE_IP_24H', '10') or '10')
RATE_EMAIL_PER_24H = int(os.environ.get('CONTACT_RATE_EMAIL_24H', '3') or '3')

SPAM_SCORE_THRESHOLD = int(
    os.environ.get('CONTACT_SPAM_SCORE_THRESHOLD')
    or os.environ.get('CONTACT_SPAM_SCORE_SUPPRESS')
    or '5'
)

HONEYPOT_FIELD = 'company_website'

VALID_PRESS_VALUES = frozenset({'yes', '1', 'on', 'true'})
VALID_PRESS_FALSE = frozenset({'', 'no', '0', 'off', 'false'})

ALLOWED_CONTENT_TYPES = (
    'application/x-www-form-urlencoded',
    'multipart/form-data',
)


def is_production_environment() -> bool:
    if (os.environ.get('RENDER') or '').strip():
        return True
    if (os.environ.get('RENDER_SERVICE_ID') or '').strip():
        return True
    env = (os.environ.get('PBJ_ENV') or '').strip().lower()
    if env in ('production', 'prod'):
        return True
    if (os.environ.get('PBJ_PRODUCTION') or '').strip().lower() in ('1', 'true', 'yes'):
        return True
    return False


def turnstile_site_key() -> str:
    return (os.environ.get('TURNSTILE_SITE_KEY') or '').strip()


def public_site_key() -> str:
    """Site key exposed to HTML. Empty disables widget client-side."""
    return turnstile_site_key()


def turnstile_secret_key() -> str:
    return (os.environ.get('TURNSTILE_SECRET_KEY') or '').strip()


def expected_hostnames() -> FrozenSet[str]:
    raw = (os.environ.get('TURNSTILE_EXPECTED_HOSTNAMES') or '').strip()
    if not raw:
        extra = set(DEFAULT_EXPECTED_HOSTNAMES)
        render_ext = (os.environ.get('RENDER_EXTERNAL_HOSTNAME') or '').strip().lower()
        if render_ext:
            extra.add(render_ext)
        return frozenset(extra)
    return frozenset(h.strip().lower() for h in raw.split(',') if h.strip())


def rate_limit_pepper() -> str:
    for key in (
        'CONTACT_RATE_HASH_PEPPER',
        'CONTACT_RATE_LIMIT_PEPPER',
        'TURNSTILE_SECRET_KEY',
        'SECRET_KEY',
        'FLASK_SECRET_KEY',
    ):
        val = (os.environ.get(key) or '').strip()
        if val:
            return val
    return 'pbj320-contact-dev-pepper-not-for-production'


def db_path() -> str:
    explicit = (os.environ.get('CONTACT_PROTECTION_DB_PATH') or '').strip()
    if explicit:
        return explicit
    subs = (os.environ.get('SUBSCRIBERS_DB_PATH') or '').strip()
    if subs:
        parent = os.path.dirname(subs) or '.'
        return os.path.join(parent, 'contact_protection.db')
    instance = os.path.join(os.getcwd(), 'instance')
    if os.path.isdir(instance):
        return os.path.join(instance, 'contact_protection.db')
    return os.path.join(os.getcwd(), 'contact_protection.db')


def allow_turnstile_bypass_for_tests() -> bool:
    if is_production_environment():
        return False
    flag = (os.environ.get('PBJ_CONTACT_SKIP_TURNSTILE') or '').strip().lower()
    return flag in ('1', 'true', 'yes')


def turnstile_required() -> bool:
    """True when Turnstile must be enforced (always in production; skip flag ignored there)."""
    if is_production_environment():
        return True
    if allow_turnstile_bypass_for_tests():
        return False
    return bool(turnstile_secret_key())
