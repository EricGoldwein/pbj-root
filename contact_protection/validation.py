"""Server-side validation / normalization for contact form fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from contact_protection import config

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_HEADER_INJECTION_RE = re.compile(r'[\r\n]')


@dataclass(frozen=True)
class ValidatedContact:
    name: str
    email: str
    message: str
    is_press: bool
    subject_type: str
    honeypot: str


@dataclass(frozen=True)
class ValidationFailure:
    code: str = 'validation_failed'


def _strip_controls(value: str) -> str:
    return _CONTROL_RE.sub('', value)


def _reject_header_injection(value: str) -> bool:
    return bool(_HEADER_INJECTION_RE.search(value or ''))


def parse_press(raw: Any) -> Tuple[Optional[bool], bool]:
    if raw is None:
        return False, True
    s = str(raw).strip().lower()
    if s in config.VALID_PRESS_FALSE:
        return False, True
    if s in config.VALID_PRESS_VALUES:
        return True, True
    return None, False


def validate_content_type(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ct = content_type.split(';', 1)[0].strip().lower()
    return ct in config.ALLOWED_CONTENT_TYPES


def validate_body_size(content_length: Optional[int]) -> bool:
    if content_length is None:
        return True
    try:
        return int(content_length) <= config.MAX_BODY_BYTES
    except (TypeError, ValueError):
        return False


def validate_submission(form: Mapping[str, Any]) -> Tuple[Optional[ValidatedContact], Optional[ValidationFailure]]:
    honeypot = _strip_controls(str(form.get(config.HONEYPOT_FIELD) or '')).strip()

    name_raw = str(form.get('name') or '')
    email_raw = str(form.get('email') or '')
    message_raw = str(form.get('message') or '')
    subject_type_raw = str(form.get('subject_type') or '')

    if _reject_header_injection(name_raw) or _reject_header_injection(email_raw):
        return None, ValidationFailure()
    if _reject_header_injection(subject_type_raw):
        return None, ValidationFailure()

    name = _strip_controls(name_raw).strip()
    email = _strip_controls(email_raw).strip().lower()
    message = _strip_controls(message_raw).strip()
    subject_type = _strip_controls(subject_type_raw).strip().lower()[: config.SUBJECT_TYPE_MAX]

    if len(name) < config.NAME_MIN or len(name) > config.NAME_MAX:
        return None, ValidationFailure()
    if not email or len(email) > config.EMAIL_MAX or not _EMAIL_RE.match(email):
        return None, ValidationFailure()
    if len(message) < config.MESSAGE_MIN or len(message) > config.MESSAGE_MAX:
        return None, ValidationFailure()

    is_press, press_ok = parse_press(form.get('press'))
    if not press_ok or is_press is None:
        return None, ValidationFailure()

    return (
        ValidatedContact(
            name=name,
            email=email,
            message=message,
            is_press=is_press,
            subject_type=subject_type,
            honeypot=honeypot,
        ),
        None,
    )
