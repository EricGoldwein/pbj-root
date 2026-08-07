"""End-to-end contact submission decisioning (spam gates before email)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from contact_protection import store
from contact_protection.config import HONEYPOT_FIELD, MAX_REQUEST_BODY_BYTES
from contact_protection.rate_limit import check_rate_limits, record_accepted_attempt
from contact_protection.spam import score_submission
from contact_protection.store import message_fingerprint
from contact_protection.turnstile import verify_turnstile_token
from contact_protection.validation import ValidatedContact, validate_contact_fields

_log = logging.getLogger('pbj.contact_protection')


@dataclass(frozen=True)
class ContactDecision:
    outcome: str  # accept | reject | soft_drop | rate_limited | retry
    reason: str
    validated: Optional[ValidatedContact] = None


def process_contact_submission(
    *,
    form: Mapping[str, Any],
    content_type: Optional[str],
    content_length: Optional[int],
    client_ip: Optional[str],
    turnstile_token: Optional[str],
) -> ContactDecision:
    if content_length is not None and content_length > MAX_REQUEST_BODY_BYTES:
        store.record_reason('validation_failed')
        return ContactDecision(outcome='reject', reason='validation_failed')

    ct = (content_type or '').split(';')[0].strip().lower()
    if ct and ct not in ('application/x-www-form-urlencoded', 'multipart/form-data'):
        store.record_reason('validation_failed')
        return ContactDecision(outcome='reject', reason='validation_failed')

    hp = (form.get(HONEYPOT_FIELD) or '').strip()
    if hp:
        _log.info('reason=honeypot_filled')
        store.record_reason('honeypot_filled')
        return ContactDecision(outcome='soft_drop', reason='honeypot_filled')

    validated, verr = validate_contact_fields(form)
    if validated is None:
        store.record_reason('validation_failed')
        return ContactDecision(outcome='reject', reason=verr or 'validation_failed')

    ts = verify_turnstile_token(
        turnstile_token,
        remoteip=client_ip if client_ip else None,
    )
    if not ts.ok:
        reason = ts.reason or 'turnstile_failed'
        store.record_reason(reason if reason.startswith('turnstile') else 'turnstile_failed')
        if reason == 'turnstile_unavailable':
            return ContactDecision(outcome='retry', reason=reason, validated=validated)
        return ContactDecision(outcome='reject', reason='turnstile_failed', validated=validated)

    rl = check_rate_limits(ip=client_ip, email=validated.email)
    if not rl.allowed:
        store.record_reason('rate_limited')
        _log.info('reason=rate_limited detail=%s', rl.reason)
        return ContactDecision(outcome='rate_limited', reason='rate_limited', validated=validated)

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
                message_fp=message_fingerprint(validated.message),
            )
        except Exception as exc:
            _log.warning('quarantine_failed err=%s', type(exc).__name__)
        _log.info('reason=high_confidence_spam codes=%s', ','.join(spam.reasons))
        store.record_reason('high_confidence_spam')
        return ContactDecision(
            outcome='soft_drop',
            reason='high_confidence_spam',
            validated=validated,
        )

    try:
        record_accepted_attempt(ip=client_ip, email=validated.email)
        store.record_message(validated.message)
    except Exception as exc:
        _log.warning('post_accept_store_error err=%s', type(exc).__name__)
        store.record_reason('rate_limited')
        return ContactDecision(outcome='rate_limited', reason='rate_limited', validated=validated)

    store.record_reason('accepted')
    _log.info('reason=accepted press=%s', int(validated.is_press))
    return ContactDecision(outcome='accept', reason='accepted', validated=validated)
