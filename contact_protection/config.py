"""Environment and threshold configuration for contact spam protection."""

from __future__ import annotations

import os

# Cloudflare official always-pass test keys (automated tests / local default).
TURNSTILE_TEST_SITE_KEY = '1x00000000000000000000AA'
TURNSTILE_TEST_SECRET_PASS = '1x0000000000000000000000000000000AA'
TURNSTILE_TEST_SECRET_FAIL = '2x0000000000000000000000000000000AB'

TURNSTILE_ACTION = 'pbj_request'
TURNSTILE_SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

HONEYPOT_FIELD = 'company_website'

NAME_MIN_LEN = 2
NAME_MAX_LEN = 100
EMAIL_MAX_LEN = 254
MESSAGE_MIN_LEN = 10
MESSAGE_MAX_LEN = 5000
MAX_REQUEST_BODY_BYTES = 64 * 1024

RATE_IP_PER_15M = int(os.environ.get('CONTACT_RATE_IP_15M', os.environ.get('PBJ_CONTACT_RATE_IP_15M', '3')))
RATE_IP_PER_24H = int(os.environ.get('CONTACT_RATE_IP_24H', os.environ.get('PBJ_CONTACT_RATE_IP_24H', '10')))
RATE_EMAIL_PER_24H = int(os.environ.get('CONTACT_RATE_EMAIL_24H', os.environ.get('PBJ_CONTACT_RATE_EMAIL_24H', '3')))

SPAM_SCORE_THRESHOLD = int(os.environ.get('CONTACT_SPAM_SCORE_THRESHOLD', os.environ.get('PBJ_CONTACT_SPAM_SCORE_THRESHOLD', '5')))

DEFAULT_HOSTNAMES = (
    'www.pbj320.com',
    'pbj320.com',
    'pbj.onrender.com',
)


def is_production_environment() -> bool:
    return bool(
        os.environ.get('RENDER')
        or os.environ.get('RENDER_SERVICE_ID')
        or os.environ.get('PBJ_ENV', '').strip().lower() in ('production', 'prod')
    )


def turnstile_secret_key() -> str:
    return (os.environ.get('TURNSTILE_SECRET_KEY') or '').strip()


def public_site_key() -> str:
    explicit = (os.environ.get('TURNSTILE_SITE_KEY') or '').strip()
    if explicit:
        return explicit
    if is_production_environment():
        return ''
    return TURNSTILE_TEST_SITE_KEY


def turnstile_site_key() -> str:
    return public_site_key()


def expected_hostnames() -> frozenset[str]:
    raw = (os.environ.get('TURNSTILE_EXPECTED_HOSTNAMES') or '').strip()
    if raw:
        return frozenset(h.strip().lower() for h in raw.split(',') if h.strip())
    hosts = set(DEFAULT_HOSTNAMES)
    render_host = (os.environ.get('RENDER_EXTERNAL_HOSTNAME') or '').strip().lower()
    if render_host:
        hosts.add(render_host)
    if not is_production_environment():
        hosts.update({'localhost', '127.0.0.1', 'testserver'})
    return frozenset(hosts)


def turnstile_required() -> bool:
    """Production always requires Turnstile. Local skip only via PBJ_CONTACT_SKIP_TURNSTILE."""
    if is_production_environment():
        return True
    if (os.environ.get('PBJ_CONTACT_SKIP_TURNSTILE') or '').strip().lower() in (
        '1',
        'true',
        'yes',
    ):
        return False
    return True


def contact_protection_db_path() -> str:
    explicit = (os.environ.get('CONTACT_PROTECTION_DB_PATH') or '').strip()
    if explicit:
        return explicit
    subscribers = (os.environ.get('SUBSCRIBERS_DB_PATH') or '').strip()
    if subscribers:
        parent = os.path.dirname(subscribers) or '.'
        return os.path.join(parent, 'contact_protection.db')
    instance = os.path.join(os.getcwd(), 'instance')
    if os.path.isdir(instance):
        return os.path.join(instance, 'contact_protection.db')
    return os.path.join(os.getcwd(), 'contact_protection.db')


def hash_pepper() -> str:
    return (os.environ.get('CONTACT_RATE_HASH_PEPPER') or 'pbj320-contact-protection').strip()
