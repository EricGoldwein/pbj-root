"""PBJ320 contact / request form spam protections.

Primary defenses: Turnstile, honeypot, durable SQLite rate limits, validation.
Secondary: conservative spam scoring. Media/press is metadata only — never a trust signal.
"""

from __future__ import annotations

from contact_protection.config import (
    HONEYPOT_FIELD,
    MAX_REQUEST_BODY_BYTES,
    TURNSTILE_ACTION,
    TURNSTILE_TEST_SECRET_PASS,
    TURNSTILE_TEST_SITE_KEY,
    public_site_key,
    turnstile_required,
    turnstile_site_key,
)
from contact_protection.email_build import build_contact_email_parts
from contact_protection.html_inject import inject_contact_form_tokens
from contact_protection.pipeline import ContactDecision, process_contact_submission
from contact_protection.spam import score_submission
from contact_protection.store import (
    aggregate_reason_counts,
    init_store,
    reset_store_for_tests,
    set_store_path_for_tests,
)
from contact_protection.validation import sanitize_header_value

__all__ = [
    'ContactDecision',
    'HONEYPOT_FIELD',
    'MAX_REQUEST_BODY_BYTES',
    'TURNSTILE_ACTION',
    'TURNSTILE_TEST_SECRET_PASS',
    'TURNSTILE_TEST_SITE_KEY',
    'aggregate_reason_counts',
    'build_contact_email_parts',
    'init_store',
    'inject_contact_form_tokens',
    'process_contact_submission',
    'public_site_key',
    'reset_store_for_tests',
    'sanitize_header_value',
    'score_submission',
    'set_store_path_for_tests',
    'turnstile_required',
    'turnstile_site_key',
]
