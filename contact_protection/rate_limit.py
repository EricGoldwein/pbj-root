"""Durable rate limiting for contact form submissions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from contact_protection import config
from contact_protection import store


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    reason: str = ''  # '' | ip_15m | ip_24h | email_24h


def check_rate_limits(*, ip: Optional[str], email: str) -> RateLimitResult:
    ip_hash = store.hash_ip(ip or 'unknown')
    email_hash = store.hash_email(email)

    if store.count_rate_events(f'ip:{ip_hash}', 15 * 60) >= config.RATE_IP_PER_15M:
        return RateLimitResult(allowed=False, reason='ip_15m')
    if store.count_rate_events(f'ip:{ip_hash}', 24 * 3600) >= config.RATE_IP_PER_24H:
        return RateLimitResult(allowed=False, reason='ip_24h')
    if store.count_rate_events(f'email:{email_hash}', 24 * 3600) >= config.RATE_EMAIL_PER_24H:
        return RateLimitResult(allowed=False, reason='email_24h')
    return RateLimitResult(allowed=True)


def record_accepted_attempt(*, ip: Optional[str], email: str) -> None:
    ip_hash = store.hash_ip(ip or 'unknown')
    email_hash = store.hash_email(email)
    store.add_rate_event(f'ip:{ip_hash}')
    store.add_rate_event(f'email:{email_hash}')
