"""End-to-end contact submission pipeline (spam gates before email)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from contact_protection.config import (
    HONEYPOT_FIELD,
    MAX_REQUEST_BODY_BYTES,
    RATE_EMAIL_ATTEMPTS_24H,
    RATE_IP_ACCEPTED_15M,
    RATE_IP_ATTEMPTS_24H,
    RATE_WINDOW_15M,
    RATE_WINDOW_24H,
)
from contact_protection import store
from contact_protection.spam_score import score_submission
from contact_protection.turnstile import verify_turnstile_token
from contact_protection.validation import ValidatedContact, validate_contact_fields

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContactOutcome:
    """Result of process_contact_submission.

    status values:
      accepted — send email
      honeypot — fake success, no email
      high_confidence_spam — quarantine, fake-ish success (no email)
      rate_limited — HTTP 429 path
      turnstile_failed / turnstile_unavailable / validation_failed — user error
      rejected — content-type / body size
    """

    status: str
    reason: str
    validated: ValidatedContact | None = None
    http_status: int = 200
    user_message: str = ''
    send_email: bool = False


def _client_ip(request) -> str:
    forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    if forwarded:
        return forwarded
    return (request.remote_addr or '').strip() or 'unknown'


def _content_type_ok(request) -> bool:
    ct = (request.content_type or '').split(';')[0].strip().lower()
    return ct in (
        'application/x-www-form-urlencoded',
        'multipart/form-data',
    )


def process_contact_submission(
    request,
    *,
    send_email_fn: Callable[[ValidatedContact], bool] | None = None,
) -> ContactOutcome:
    """Run spam gates. Caller sends email only when outcome.send_email is True,
    or pass send_email_fn to send inside the pipeline after acceptance.
    """
    # Body size: prefer Content-Length; also guard form parse size via Flask MAX_CONTENT_LENGTH if set.
    try:
        cl = request.content_length
        if cl is not None and cl > MAX_REQUEST_BODY_BYTES:
            store.record_reason('validation_failed')
            return ContactOutcome(
                status='rejected',
                reason='validation_failed',
                http_status=413,
                user_message='Something went wrong. Please try again.',
            )
    except Exception:
        pass

    if not _content_type_ok(request):
        store.record_reason('validation_failed')
        return ContactOutcome(
            status='rejected',
            reason='validation_failed',
            http_status=400,
            user_message='Something went wrong. Please try again.',
        )

    # Honeypot: fake success, no email, no rate teaching.
    hp = (request.form.get(HONEYPOT_FIELD) or '').strip()
    if hp:
        _log.info('[PBJ_CONTACT] reason=honeypot_filled')
        store.record_reason('honeypot_filled')
        return ContactOutcome(
            status='honeypot',
            reason='honeypot_filled',
            send_email=False,
            user_message='Message sent. We will be in touch.',
        )

    validated, verr = validate_contact_fields(request.form)
    if validated is None:
        store.record_reason('validation_failed')
        return ContactOutcome(
            status='validation_failed',
            reason=verr or 'validation_failed',
            http_status=400,
            user_message='Something went wrong. Please try again.',
        )

    ip = _client_ip(request)
    ip_bucket = 'ip:' + store.hash_identifier(ip)
    email_bucket = 'email:' + store.hash_identifier(validated.email)

    # Attempt counters (pre-delivery)
    try:
        if store.count_events(ip_bucket, 'attempt', RATE_WINDOW_24H) >= RATE_IP_ATTEMPTS_24H:
            store.record_reason('rate_limited')
            return ContactOutcome(
                status='rate_limited',
                reason='rate_limited',
                validated=validated,
                http_status=429,
                user_message='Too many requests. Please try again later.',
            )
        if store.count_events(email_bucket, 'attempt', RATE_WINDOW_24H) >= RATE_EMAIL_ATTEMPTS_24H:
            store.record_reason('rate_limited')
            return ContactOutcome(
                status='rate_limited',
                reason='rate_limited',
                validated=validated,
                http_status=429,
                user_message='Too many requests. Please try again later.',
            )
        store.add_event(ip_bucket, 'attempt')
        store.add_event(email_bucket, 'attempt')
    except Exception as exc:
        _log.warning('[PBJ_CONTACT] rate_store_error_attempt err=%s', type(exc).__name__)
        # Fail open on store errors for attempts would enable spam; fail closed for durability requirement.
        store.record_reason('rate_limited')
        return ContactOutcome(
            status='rate_limited',
            reason='rate_limited',
            validated=validated,
            http_status=429,
            user_message='Too many requests. Please try again later.',
        )

    token = request.form.get('cf-turnstile-response') or request.form.get('turnstile_token')
    ts = verify_turnstile_token(token, remoteip=ip if ip != 'unknown' else None)
    if not ts.ok:
        reason = ts.reason or 'turnstile_failed'
        store.record_reason(reason)
        user_msg = (
            'Verification temporarily unavailable. Please try again in a moment.'
            if reason == 'turnstile_unavailable'
            else 'Something went wrong. Please try again.'
        )
        return ContactOutcome(
            status=reason,
            reason=reason,
            validated=validated,
            http_status=503 if reason == 'turnstile_unavailable' else 400,
            user_message=user_msg,
        )

    spam = score_submission(
        name=validated.name,
        message=validated.message,
        is_press=validated.is_press,
    )
    if spam.high_confidence:
        try:
            domain = validated.email.split('@')[-1] if '@' in validated.email else ''
            store.quarantine_submission(
                reason_codes=list(spam.reasons) or ['high_confidence_spam'],
                email_domain=domain,
                name_len=len(validated.name),
                message_len=len(validated.message),
                message_fp=spam.message_fp,
            )
        except Exception as exc:
            _log.warning('[PBJ_CONTACT] quarantine_failed err=%s', type(exc).__name__)
        _log.info(
            '[PBJ_CONTACT] reason=high_confidence_spam codes=%s',
            ','.join(spam.reasons),
        )
        store.record_reason('high_confidence_spam')
        # Do not teach bots — success-looking response, no email.
        return ContactOutcome(
            status='high_confidence_spam',
            reason='high_confidence_spam',
            validated=validated,
            send_email=False,
            user_message='Message sent. We will be in touch.',
        )

    # Accepted short-window limit
    try:
        if store.count_events(ip_bucket, 'accepted', RATE_WINDOW_15M) >= RATE_IP_ACCEPTED_15M:
            store.record_reason('rate_limited')
            return ContactOutcome(
                status='rate_limited',
                reason='rate_limited',
                validated=validated,
                http_status=429,
                user_message='Too many requests. Please try again later.',
            )
    except Exception as exc:
        _log.warning('[PBJ_CONTACT] rate_store_error_accepted err=%s', type(exc).__name__)
        store.record_reason('rate_limited')
        return ContactOutcome(
            status='rate_limited',
            reason='rate_limited',
            validated=validated,
            http_status=429,
            user_message='Too many requests. Please try again later.',
        )

    if send_email_fn is not None:
        try:
            ok = bool(send_email_fn(validated))
        except Exception as exc:
            _log.warning('[PBJ_CONTACT] send_email_failed err=%s', type(exc).__name__)
            ok = False
        if not ok:
            return ContactOutcome(
                status='send_failed',
                reason='send_failed',
                validated=validated,
                http_status=500,
                user_message='Something went wrong. Please try again.',
                send_email=False,
            )

    try:
        store.add_event(ip_bucket, 'accepted')
        store.record_message_fingerprint(spam.message_fp)
    except Exception as exc:
        _log.warning('[PBJ_CONTACT] post_accept_store_error err=%s', type(exc).__name__)

    store.record_reason('accepted')
    _log.info('[PBJ_CONTACT] reason=accepted press=%s', int(validated.is_press))
    return ContactOutcome(
        status='accepted',
        reason='accepted',
        validated=validated,
        send_email=send_email_fn is None,
        user_message='Message sent. We will be in touch.',
    )


def outcome_to_dict(outcome: ContactOutcome) -> dict[str, Any]:
    return {
        'status': outcome.status,
        'reason': outcome.reason,
        'send_email': outcome.send_email,
        'http_status': outcome.http_status,
    }
