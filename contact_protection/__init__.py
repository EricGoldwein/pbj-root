"""PBJ320 contact-form spam protection (Turnstile, honeypot, rate limits, spam score)."""

from contact_protection.config import (
    HONEYPOT_FIELD,
    TURNSTILE_ACTION,
    TURNSTILE_TEST_SECRET_KEY,
    TURNSTILE_TEST_SECRET_PASS,
    TURNSTILE_TEST_SITE_KEY,
    is_production_environment,
    public_site_key,
    turnstile_site_key,
)
from contact_protection.email_build import build_contact_email_parts, build_mime_message, sanitize_header_value
from contact_protection.html_inject import (
    CONTACT_PROTECT_JS_VERSION,
    contact_protect_assets_html,
    honeypot_field_html,
    inject_contact_form_tokens,
    turnstile_widget_html,
)
from contact_protection.pipeline import ProcessResult, process_contact_submission
from contact_protection.spam import SpamAssessment, score_submission
from contact_protection.store import (
    aggregate_reason_counts,
    init_store,
    outcome_counts_for_day,
    reset_store_for_tests,
)
from contact_protection.validation import ValidatedContact

__all__ = [
    'CONTACT_PROTECT_JS_VERSION',
    'HONEYPOT_FIELD',
    'ProcessResult',
    'SpamAssessment',
    'TURNSTILE_ACTION',
    'TURNSTILE_TEST_SECRET_KEY',
    'TURNSTILE_TEST_SECRET_PASS',
    'TURNSTILE_TEST_SITE_KEY',
    'ValidatedContact',
    'aggregate_reason_counts',
    'build_contact_email_parts',
    'build_mime_message',
    'contact_protect_assets_html',
    'honeypot_field_html',
    'init_store',
    'inject_contact_form_tokens',
    'is_production_environment',
    'outcome_counts_for_day',
    'process_contact_submission',
    'public_site_key',
    'reset_store_for_tests',
    'sanitize_header_value',
    'score_submission',
    'turnstile_site_key',
    'turnstile_widget_html',
]
