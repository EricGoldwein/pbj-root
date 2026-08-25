"""Server-side field validation for the contact form."""

from __future__ import annotations

import re
from dataclasses import dataclass

from contact_protection.config import (
    EMAIL_MAX_LEN,
    MESSAGE_MAX_LEN,
    MESSAGE_MIN_LEN,
    NAME_MAX_LEN,
    NAME_MIN_LEN,
)

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_HEADER_INJECT_RE = re.compile(r'[\r\n]')


@dataclass(frozen=True)
class ValidatedContact:
    name: str
    email: str
    message: str
    is_press: bool
    subject_type: str
    next_url: str


def sanitize_header_value(value: str, max_len: int = 200) -> str:
    return re.sub(r'[\r\n]+', ' ', (value or '')).strip()[:max_len]


def parse_press(raw) -> bool | None:
    if raw is None or raw == '':
        return False
    value = str(raw).strip().lower()
    if value in ('1', 'on', 'yes', 'true'):
        return True
    if value in ('0', 'off', 'no', 'false'):
        return False
    return None


def validate_contact_fields(form) -> tuple[ValidatedContact | None, str]:
    name = (form.get('name') or '').strip()
    email = (form.get('email') or '').strip().lower()
    message = (form.get('message') or '').strip()
    is_press = parse_press(form.get('press'))
    if is_press is None:
        return None, 'validation_failed'

    if len(name) < NAME_MIN_LEN or len(name) > NAME_MAX_LEN:
        return None, 'validation_failed'
    if _HEADER_INJECT_RE.search(name) or _CTRL_RE.search(name):
        return None, 'validation_failed'

    if not email or len(email) > EMAIL_MAX_LEN or not _EMAIL_RE.match(email):
        return None, 'validation_failed'
    if _HEADER_INJECT_RE.search(email) or _CTRL_RE.search(email):
        return None, 'validation_failed'

    if len(message) < MESSAGE_MIN_LEN or len(message) > MESSAGE_MAX_LEN:
        return None, 'validation_failed'
    if _CTRL_RE.search(message) or '\x00' in message:
        return None, 'validation_failed'

    subject_type = (form.get('subject_type') or '').strip().lower()[:64]
    if subject_type and (
        _HEADER_INJECT_RE.search(subject_type) or not re.match(r'^[a-z0-9_]+$', subject_type)
    ):
        return None, 'validation_failed'

    next_url = (form.get('next') or '').strip()
    if not next_url.startswith('/') or next_url.startswith('//') or _HEADER_INJECT_RE.search(next_url):
        next_url = '/'
    next_url = next_url[:500]

    return (
        ValidatedContact(
            name=name,
            email=email,
            message=message.replace('\r\n', '\n').replace('\r', '\n'),
            is_press=bool(is_press),
            subject_type=subject_type,
            next_url=next_url,
        ),
        '',
    )
