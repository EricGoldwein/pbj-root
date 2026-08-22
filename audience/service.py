"""Audience signup, preferences, feedback, exports, and subscription queries."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from audience.constants import (
    CONSENT_COPY_VERSION,
    CTA_VARIANT_PRIMARY,
    ROLES,
    SUBSCRIPTION_NATIONAL,
    SUBSCRIPTION_PBJ320_INSIGHTS,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_UNSUBSCRIBED,
    SUBSCRIPTION_TYPES,
    SUBSTACK_BASE_URL,
    normalize_subscription_type,
)
from audience.db import db_session, execute_with_retry, init_db

_log = logging.getLogger(__name__)
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Fields that must never appear in analytics metadata.
_ANALYTICS_BLOCKLIST = frozenset({'email', 'token', 'unsubscribeToken', 'csrfToken'})


def normalize_email(raw: str | None) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    email = raw.strip().lower()
    if not email or len(email) > 255:
        return None
    if not _EMAIL_RE.match(email):
        return None
    return email


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _secret_key() -> bytes:
    key = (
        os.environ.get('SECRET_KEY')
        or os.environ.get('FLASK_SECRET_KEY')
        or 'pbj-audience-dev-key'
    ).encode('utf-8')
    return key


def make_unsubscribe_token(contact_id: int, subscription_type: str, resource_key: str = '') -> str:
    payload = f'{contact_id}:{subscription_type}:{resource_key}'
    sig = hmac.new(_secret_key(), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:32]
    return f'{contact_id}.{subscription_type}.{resource_key}.{sig}'


def verify_unsubscribe_token(token: str) -> tuple[int, str, str] | None:
    parts = (token or '').split('.')
    if len(parts) != 4:
        return None
    contact_id_s, sub_type, resource_key, sig = parts
    try:
        contact_id = int(contact_id_s)
    except ValueError:
        return None
    expected = hmac.new(
        _secret_key(),
        f'{contact_id}:{sub_type}:{resource_key}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        return None
    return contact_id, sub_type, resource_key


def substack_outbound_url(*, cta_variant: str, page_type: str | None) -> str:
    """Eric's Substack — separate from PBJ320 Insights product."""
    from urllib.parse import urlencode

    params = {
        'utm_source': 'pbj320',
        'utm_medium': 'website',
        'utm_campaign': 'eric_substack',
        'utm_content': cta_variant or page_type or 'unknown',
    }
    return f'{SUBSTACK_BASE_URL}?{urlencode(params)}'


def sanitize_analytics_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {k: v for k, v in metadata.items() if k not in _ANALYTICS_BLOCKLIST and 'email' not in k.lower()}


def csv_safe_cell(value: Any) -> str:
    """Prevent spreadsheet formula injection in CSV exports."""
    s = str(value if value is not None else '')
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


def upsert_contact(
    conn: sqlite3.Connection,
    email: str,
    *,
    name: str | None = None,
    organization: str | None = None,
    role: str | None = None,
    context: dict[str, Any] | None = None,
) -> tuple[int, bool]:
    ctx = context or {}
    existing = conn.execute(
        'SELECT id FROM contacts WHERE email = ? COLLATE NOCASE', (email,)
    ).fetchone()
    now = _now_iso()
    visitor_id = (ctx.get('visitorKey') or ctx.get('anonymousVisitorId') or '')[:128] or None
    if existing:
        contact_id = int(existing['id'])
        updates: list[str] = ['updated_at = ?', 'last_seen_at = ?']
        params: list[Any] = [now, now]
        if name:
            updates.append('name = ?')
            params.append(name[:200])
        if organization:
            updates.append('organization = ?')
            params.append(organization[:200])
        if role and role in ROLES:
            updates.append('role = ?')
            params.append(role)
        if visitor_id:
            updates.append('anonymous_visitor_id = COALESCE(anonymous_visitor_id, ?)')
            params.append(visitor_id)
        params.append(contact_id)
        execute_with_retry(
            conn,
            f'UPDATE contacts SET {", ".join(updates)} WHERE id = ?',
            tuple(params),
        )
        return contact_id, False

    execute_with_retry(
        conn,
        '''
        INSERT INTO contacts (
            email, name, organization, role,
            first_source_url, first_referrer,
            first_utm_source, first_utm_medium, first_utm_campaign,
            anonymous_visitor_id,
            created_at, updated_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            email,
            (name or '')[:200] or None,
            (organization or '')[:200] or None,
            role if role in ROLES else None,
            (ctx.get('sourceUrl') or ctx.get('source_url') or '')[:2000] or None,
            (ctx.get('referrer') or '')[:2000] or None,
            (ctx.get('utmSource') or ctx.get('utm_source') or '')[:128] or None,
            (ctx.get('utmMedium') or ctx.get('utm_medium') or '')[:128] or None,
            (ctx.get('utmCampaign') or ctx.get('utm_campaign') or '')[:128] or None,
            visitor_id,
            now, now, now,
        ),
    )
    row = conn.execute(
        'SELECT id FROM contacts WHERE email = ? COLLATE NOCASE', (email,)
    ).fetchone()
    return int(row['id']), True


def _resource_for_type(sub_type: str, ctx: dict[str, Any]) -> tuple[str | None, str | None]:
    if sub_type == 'facility':
        ccn = (ctx.get('ccn') or ctx.get('resourceId') or '').strip()
        return ('facility', ccn) if ccn else (None, None)
    if sub_type == 'state':
        abbr = (ctx.get('stateAbbr') or ctx.get('state') or '').strip().upper()
        return ('state', abbr) if abbr and abbr != 'USA' else (None, None)
    if sub_type == SUBSCRIPTION_NATIONAL:
        return ('national', 'usa')
    return None, None


def record_signup_context(
    conn: sqlite3.Connection,
    contact_id: int,
    subscription_id: int | None,
    ctx: dict[str, Any],
    *,
    cta_variant: str,
    trigger_reason: str | None = None,
) -> None:
    meta = sanitize_analytics_metadata(ctx)
    execute_with_retry(
        conn,
        '''
        INSERT INTO signup_context (
            contact_id, subscription_id, source_url, page_type,
            facility_ccn, facility_name, state_abbr, state_name, chain_identifier,
            search_filters, referrer, utm_source, utm_medium, utm_campaign,
            cta_variant, cta_id, device_category, visitor_status,
            facility_pages_viewed, trigger_reason, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            contact_id,
            subscription_id,
            (ctx.get('sourceUrl') or '')[:2000] or None,
            (ctx.get('pageType') or ctx.get('page_type') or '')[:32] or None,
            (ctx.get('ccn') or '')[:16] or None,
            (ctx.get('facilityName') or '')[:200] or None,
            (ctx.get('stateAbbr') or '')[:8] or None,
            (ctx.get('stateName') or '')[:64] or None,
            (ctx.get('chainId') or ctx.get('entityId') or '')[:64] or None,
            json.dumps(ctx.get('searchStateFilters') or ctx.get('searchFilters') or [], separators=(',', ':')),
            (ctx.get('referrer') or '')[:2000] or None,
            (ctx.get('utmSource') or '')[:128] or None,
            (ctx.get('utmMedium') or '')[:128] or None,
            (ctx.get('utmCampaign') or '')[:128] or None,
            cta_variant[:64],
            (ctx.get('ctaId') or cta_variant)[:64],
            (ctx.get('deviceCategory') or '')[:16] or None,
            (ctx.get('visitorStatus') or '')[:16] or None,
            int(ctx.get('facilityPageViews') or ctx.get('pageviewCount') or 0) or None,
            (trigger_reason or ctx.get('triggerReason') or '')[:64] or None,
            json.dumps(meta, separators=(',', ':')),
            _now_iso(),
        ),
    )


def add_subscription(
    conn: sqlite3.Connection,
    contact_id: int,
    subscription_type: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    cta_variant: str | None = None,
    source_url: str | None = None,
) -> tuple[str, int | None]:
    if subscription_type not in SUBSCRIPTION_TYPES:
        raise ValueError(f'invalid subscription_type: {subscription_type}')
    rt = (resource_type or '') or None
    rid = (resource_id or '') or None
    existing = conn.execute(
        '''
        SELECT id, status FROM subscriptions
        WHERE contact_id = ? AND subscription_type = ?
          AND COALESCE(resource_type, '') = COALESCE(?, '')
          AND COALESCE(resource_id, '') = COALESCE(?, '')
        ''',
        (contact_id, subscription_type, rt, rid),
    ).fetchone()
    now = _now_iso()
    if existing:
        if existing['status'] == SUBSCRIPTION_STATUS_ACTIVE:
            return 'already_active', int(existing['id'])
        execute_with_retry(
            conn,
            '''
            UPDATE subscriptions
            SET status = ?, unsubscribed_at = NULL, subscribed_at = ?,
                cta_variant = COALESCE(?, cta_variant),
                source_url = COALESCE(?, source_url)
            WHERE id = ?
            ''',
            (SUBSCRIPTION_STATUS_ACTIVE, now, cta_variant, source_url, existing['id']),
        )
        return 'reactivated', int(existing['id'])

    cur = execute_with_retry(
        conn,
        '''
        INSERT INTO subscriptions (
            contact_id, subscription_type, resource_type, resource_id,
            status, source_url, cta_variant, subscribed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (contact_id, subscription_type, rt, rid, SUBSCRIPTION_STATUS_ACTIVE, source_url, cta_variant, now),
    )
    return 'created', int(cur.lastrowid)


def record_consent(
    conn: sqlite3.Connection,
    contact_id: int,
    action: str,
    subscription_type: str | None,
    source_url: str | None,
    *,
    consent_language: str | None = None,
) -> None:
    execute_with_retry(
        conn,
        '''
        INSERT INTO consent_events (
            contact_id, action, subscription_type, consent_copy_version,
            consent_language, source_url, occurred_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            contact_id, action, subscription_type, CONSENT_COPY_VERSION,
            (consent_language or CONSENT_COPY_VERSION)[:2000], source_url, _now_iso(),
        ),
    )


def _normalize_preferences(preferences: list[str] | None, primary: str | None) -> list[str]:
    out: list[str] = []
    for raw in preferences or []:
        norm = normalize_subscription_type(raw)
        if norm and norm not in out:
            out.append(norm)
    if primary and primary not in out:
        out.insert(0, primary)
    return out


def signup(
    email: str,
    *,
    cta_variant: str,
    context: dict[str, Any] | None = None,
    name: str | None = None,
    organization: str | None = None,
    role: str | None = None,
    preferences: list[str] | None = None,
) -> dict[str, Any]:
    init_db()
    ctx = dict(context or {})
    primary_raw = CTA_VARIANT_PRIMARY.get(cta_variant, SUBSCRIPTION_PBJ320_INSIGHTS)
    pref_types = _normalize_preferences(preferences, primary_raw)
    source_url = (ctx.get('sourceUrl') or ctx.get('source_url') or '')[:2000] or None
    results: list[dict[str, Any]] = []
    contact_id = 0
    contact_created = False

    with db_session() as conn:
        contact_id, contact_created = upsert_contact(
            conn, email, name=name, organization=organization, role=role, context=ctx,
        )
        for sub_type in pref_types:
            rt, rid = _resource_for_type(sub_type, ctx)
            result, sub_id = add_subscription(
                conn, contact_id, sub_type,
                resource_type=rt, resource_id=rid,
                cta_variant=cta_variant, source_url=source_url,
            )
            record_consent(conn, contact_id, 'subscribe', sub_type, source_url)
            record_signup_context(conn, contact_id, sub_id, ctx, cta_variant=cta_variant)
            results.append({
                'subscriptionType': sub_type,
                'result': result,
                'subscriptionId': sub_id,
                'resourceType': rt,
                'resourceId': rid,
            })

    threading.Thread(
        target=_notify_admin_signup,
        kwargs={
            'email': email,
            'cta_variant': cta_variant,
            'results': results,
            'context': ctx,
            'name': name,
            'organization': organization,
            'role': role,
            'source_url': source_url,
            'contact_created': contact_created,
        },
        daemon=True,
    ).start()
    _sync_loops_async(contact_id, email, results, ctx)

    return {
        'ok': True,
        'contactId': contact_id,
        'contactCreated': contact_created,
        'subscriptions': results,
        'managePreferencesPath': '/audience/preferences',
    }


def add_preferences(
    email: str,
    preferences: list[str],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    ctx = dict(context or {})
    source_url = (ctx.get('sourceUrl') or '')[:2000] or None
    pref_types = _normalize_preferences(preferences, None)
    with db_session() as conn:
        row = conn.execute(
            'SELECT id FROM contacts WHERE email = ? COLLATE NOCASE', (email,)
        ).fetchone()
        if not row:
            return {'ok': False, 'error': 'contact_not_found'}
        contact_id = int(row['id'])
        out = []
        for sub_type in pref_types:
            rt, rid = _resource_for_type(sub_type, ctx)
            result, sub_id = add_subscription(
                conn, contact_id, sub_type,
                resource_type=rt, resource_id=rid,
                source_url=source_url,
            )
            record_consent(conn, contact_id, 'preference_added', sub_type, source_url)
            record_signup_context(conn, contact_id, sub_id, ctx, cta_variant='preference_step')
            out.append({'subscriptionType': sub_type, 'result': result, 'subscriptionId': sub_id})
    return {'ok': True, 'subscriptions': out}


def get_contact_subscriptions(email: str) -> dict[str, Any]:
    init_db()
    with db_session() as conn:
        row = conn.execute(
            'SELECT id, email, role FROM contacts WHERE email = ? COLLATE NOCASE', (email,)
        ).fetchone()
        if not row:
            return {'ok': True, 'subscribed': False, 'subscriptions': [], 'activeTypes': []}
        subs = conn.execute(
            '''
            SELECT subscription_type, resource_type, resource_id, status, cta_variant, subscribed_at
            FROM subscriptions WHERE contact_id = ? AND status = ?
            ORDER BY subscribed_at DESC
            ''',
            (row['id'], SUBSCRIPTION_STATUS_ACTIVE),
        ).fetchall()
        active_types = {s['subscription_type'] for s in subs}
        return {
            'ok': True,
            'subscribed': bool(subs),
            'email': row['email'],
            'role': row['role'],
            'subscriptions': [dict(s) for s in subs],
            'activeTypes': list(active_types),
        }


def unsubscribe_token(contact_id: int, subscription_type: str, resource_type: str | None, resource_id: str | None) -> str:
    key = f'{resource_type or ""}:{resource_id or ""}'
    return make_unsubscribe_token(contact_id, subscription_type, key)


def unsubscribe_by_token(token: str) -> dict[str, Any]:
    init_db()
    parsed = verify_unsubscribe_token(token)
    if not parsed:
        return {'ok': False, 'error': 'invalid_token'}
    contact_id, sub_type, resource_key = parsed
    if sub_type == 'all':
        return unsubscribe_all(contact_id)
    rt, rid = '', ''
    if resource_key and ':' in resource_key:
        rt, rid = resource_key.split(':', 1)
    with db_session() as conn:
        execute_with_retry(
            conn,
            '''
            UPDATE subscriptions SET status = ?, unsubscribed_at = ?
            WHERE contact_id = ? AND subscription_type = ?
              AND COALESCE(resource_type, '') = ?
              AND COALESCE(resource_id, '') = ?
            ''',
            (SUBSCRIPTION_STATUS_UNSUBSCRIBED, _now_iso(), contact_id, sub_type, rt, rid),
        )
        record_consent(conn, contact_id, 'unsubscribe', sub_type, None)
    return {'ok': True, 'subscriptionType': sub_type}


def unsubscribe_all(contact_id: int) -> dict[str, Any]:
    init_db()
    with db_session() as conn:
        execute_with_retry(
            conn,
            '''
            UPDATE subscriptions SET status = ?, unsubscribed_at = ?
            WHERE contact_id = ? AND status = ?
            ''',
            (SUBSCRIPTION_STATUS_UNSUBSCRIBED, _now_iso(), contact_id, SUBSCRIPTION_STATUS_ACTIVE),
        )
        record_consent(conn, contact_id, 'unsubscribe_all', None, None)
    return {'ok': True, 'subscriptionType': 'all'}


def make_unsubscribe_all_token(contact_id: int) -> str:
    return make_unsubscribe_token(contact_id, 'all', '')


def submit_feedback(
    *,
    rating: str | None,
    response: str,
    source_url: str | None = None,
    context: str | None = None,
    email: str | None = None,
    quote_permission: str | None = None,
    attribution_name: str | None = None,
    attribution_organization: str | None = None,
) -> dict[str, Any]:
    init_db()
    text = (response or '').strip()
    if not text:
        return {'ok': False, 'error': 'empty_response'}
    contact_id = None
    is_anonymous = 1 if not email else 0
    with db_session() as conn:
        if email:
            norm = normalize_email(email)
            if norm:
                row = conn.execute(
                    'SELECT id FROM contacts WHERE email = ? COLLATE NOCASE', (norm,)
                ).fetchone()
                if row:
                    contact_id = int(row['id'])
                    is_anonymous = 0
        execute_with_retry(
            conn,
            '''
            INSERT INTO feedback (
                contact_id, rating, response, source_url, context,
                quote_permission, attribution_name, attribution_organization,
                is_anonymous, review_status, publication_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', 'pending_review')
            ''',
            (
                contact_id,
                (rating or '')[:16] or None,
                text[:8000],
                (source_url or '')[:2000] or None,
                (context or '')[:2000] or None,
                (quote_permission or '')[:32] or None,
                (attribution_name or '')[:200] or None,
                (attribution_organization or '')[:200] or None,
                is_anonymous,
            ),
        )
    return {'ok': True}


def record_engagement_event(
    *,
    visitor_key: str,
    event_name: str,
    page_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    safe_meta = sanitize_analytics_metadata(metadata)
    with db_session() as conn:
        execute_with_retry(
            conn,
            '''
            INSERT INTO engagement_events (
                anonymous_or_contact_id, event_name, page_type, resource_id, metadata, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                visitor_key[:128],
                event_name[:64],
                (page_type or '')[:32] or None,
                (resource_id or '')[:64] or None,
                json.dumps(safe_meta, separators=(',', ':')),
                _now_iso(),
            ),
        )
    return {'ok': True}


def record_prompt_dismissal(visitor_key: str, prompt_type: str) -> dict[str, Any]:
    init_db()
    with db_session() as conn:
        execute_with_retry(
            conn,
            '''
            INSERT INTO prompt_dismissals (visitor_key, prompt_type, dismissed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(visitor_key, prompt_type) DO UPDATE SET dismissed_at = excluded.dismissed_at
            ''',
            (visitor_key[:128], prompt_type[:64], _now_iso()),
        )
    return {'ok': True}


def is_prompt_suppressed(visitor_key: str, prompt_type: str, *, days: int = 30) -> bool:
    init_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    with db_session() as conn:
        row = conn.execute(
            '''
            SELECT dismissed_at FROM prompt_dismissals
            WHERE visitor_key = ? AND prompt_type = ? AND dismissed_at >= ?
            ''',
            (visitor_key[:128], prompt_type[:64], cutoff),
        ).fetchone()
    return row is not None


def has_active_subscription(
    email: str | None,
    subscription_type: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> bool:
    norm_type = normalize_subscription_type(subscription_type) or subscription_type
    if not email:
        return False
    norm = normalize_email(email)
    if not norm:
        return False
    init_db()
    with db_session() as conn:
        row = conn.execute(
            'SELECT id FROM contacts WHERE email = ? COLLATE NOCASE', (norm,)
        ).fetchone()
        if not row:
            return False
        q = '''
            SELECT 1 FROM subscriptions
            WHERE contact_id = ? AND subscription_type = ? AND status = ?
        '''
        params: list[Any] = [row['id'], norm_type, SUBSCRIPTION_STATUS_ACTIVE]
        if resource_type is not None:
            q += ' AND resource_type = ?'
            params.append(resource_type)
        if resource_id is not None:
            q += ' AND resource_id = ?'
            params.append(resource_id)
        return conn.execute(q, tuple(params)).fetchone() is not None


def admin_export_csv_rows() -> list[list[str]]:
    data = admin_export()
    headers = [
        'email', 'name', 'organization', 'role', 'subscription_type',
        'resource_type', 'resource_id', 'status', 'cta_variant', 'subscribed_at',
    ]
    rows = [headers]
    for r in data:
        rows.append([
            csv_safe_cell(r.get('email')),
            csv_safe_cell(r.get('name')),
            csv_safe_cell(r.get('organization')),
            csv_safe_cell(r.get('role')),
            csv_safe_cell(r.get('subscription_type')),
            csv_safe_cell(r.get('resource_type')),
            csv_safe_cell(r.get('resource_id')),
            csv_safe_cell(r.get('status')),
            csv_safe_cell(r.get('cta_variant')),
            csv_safe_cell(r.get('subscribed_at')),
        ])
    return rows


def admin_export() -> list[dict[str, Any]]:
    init_db()
    with db_session() as conn:
        rows = conn.execute(
            '''
            SELECT c.email, c.name, c.organization, c.role, c.created_at,
                   s.subscription_type, s.resource_type, s.resource_id, s.status,
                   s.cta_variant, s.source_url, s.subscribed_at
            FROM contacts c
            LEFT JOIN subscriptions s ON s.contact_id = c.id
            ORDER BY c.created_at DESC, s.subscribed_at DESC
            '''
        ).fetchall()
    return [dict(r) for r in rows]


def conversion_report_queries() -> dict[str, str]:
    return {
        'signups_by_page': '''
            SELECT source_url, cta_variant, COUNT(*) AS signups
            FROM subscriptions WHERE status = 'active'
            GROUP BY source_url, cta_variant ORDER BY signups DESC;
        ''',
        'facility_state_cta_conversion': '''
            SELECT cta_variant, subscription_type, COUNT(*) AS signups
            FROM subscriptions WHERE status = 'active'
              AND subscription_type IN ('facility', 'state', 'national')
            GROUP BY cta_variant, subscription_type ORDER BY signups DESC;
        ''',
        'multi_product_subscribers': '''
            SELECT contact_id, COUNT(DISTINCT subscription_type) AS products
            FROM subscriptions WHERE status = 'active'
            GROUP BY contact_id HAVING products > 1;
        ''',
        'insights_and_app_overlap': '''
            SELECT COUNT(DISTINCT i.contact_id)
            FROM subscriptions i
            JOIN subscriptions a ON a.contact_id = i.contact_id
            WHERE i.subscription_type = 'pbj320_insights' AND i.status = 'active'
              AND a.subscription_type = 'app_early_access' AND a.status = 'active';
        ''',
        'substack_clicks': '''
            SELECT COUNT(*) FROM engagement_events WHERE event_name = 'substack_link_clicked';
        ''',
        'prompt_dismissals': '''
            SELECT prompt_type, COUNT(*) FROM prompt_dismissals GROUP BY prompt_type;
        ''',
        'mobile_vs_desktop': '''
            SELECT json_extract(metadata_json, '$.deviceCategory') AS device, COUNT(*)
            FROM signup_context GROUP BY device;
        ''',
    }


def format_admin_signup_notification(
    email: str,
    cta_variant: str,
    results: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
    name: str | None = None,
    organization: str | None = None,
    role: str | None = None,
    source_url: str | None = None,
    contact_created: bool = False,
) -> tuple[str, str]:
    """Build admin alert subject/body for a new audience signup."""
    ctx = dict(context or {})
    page_url = (source_url or ctx.get('sourceUrl') or ctx.get('source_url') or '').strip()
    lines = [
        'PBJ320 audience signup',
        '',
        f'Email: {email}',
    ]
    if name and name.strip():
        lines.append(f'Name: {name.strip()}')
    if organization and organization.strip():
        lines.append(f'Organization: {organization.strip()}')
    if role and role.strip():
        lines.append(f'Role: {role.strip()}')
    lines.append(f'CTA: {cta_variant}')
    lines.append(f'New contact: {"yes" if contact_created else "no (existing)"}')
    lines.append('')
    lines.append('Subscriptions:')
    for row in results:
        sub_type = row.get('subscriptionType') or 'unknown'
        result = row.get('result') or 'unknown'
        rt = row.get('resourceType')
        rid = row.get('resourceId')
        if rt and rid:
            lines.append(f'  - {sub_type} ({rt}: {rid}) [{result}]')
        else:
            lines.append(f'  - {sub_type} [{result}]')
    facility_name = (ctx.get('facilityName') or ctx.get('facility_name') or '').strip()
    ccn = (ctx.get('ccn') or ctx.get('resourceId') or '').strip()
    state_abbr = (ctx.get('stateAbbr') or ctx.get('state_abbr') or '').strip()
    state_name = (ctx.get('stateName') or ctx.get('state_name') or '').strip()
    page_type = (ctx.get('pageType') or ctx.get('page_type') or '').strip()
    chain_id = (ctx.get('chainId') or ctx.get('entityId') or '').strip()
    context_lines: list[str] = []
    if facility_name:
        context_lines.append(f'Facility: {facility_name}')
    if ccn:
        context_lines.append(f'CCN: {ccn}')
    if state_name or state_abbr:
        context_lines.append(f'State: {state_name or state_abbr}' + (f' ({state_abbr})' if state_name and state_abbr else ''))
    if chain_id:
        context_lines.append(f'Chain/entity: {chain_id}')
    if page_type:
        context_lines.append(f'Page type: {page_type}')
    if page_url:
        context_lines.append(f'Source URL: {page_url}')
    if context_lines:
        lines.extend(['', 'Context:'])
        lines.extend(context_lines)
    subject = f'PBJ320 audience signup: {email}'
    return subject, '\n'.join(lines) + '\n'


def _notify_admin_signup(
    email: str,
    cta_variant: str,
    results: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
    name: str | None = None,
    organization: str | None = None,
    role: str | None = None,
    source_url: str | None = None,
    contact_created: bool = False,
) -> None:
    try:
        import smtplib

        to_list = os.environ.get('SUBSCRIBE_NOTIFY_TO', '').strip().split(',')
        to_list = [a.strip() for a in to_list if a.strip()]
        host = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_HOST', '').strip()
        if not host or not to_list:
            return
        port = int(os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PORT', '587'))
        user = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_USER', '').strip()
        password = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PASSWORD', '').strip()
        from_addr = os.environ.get('SUBSCRIBE_NOTIFY_FROM', user or 'noreply@pbj320.com').strip()
        subject, body = format_admin_signup_notification(
            email,
            cta_variant,
            results,
            context=context,
            name=name,
            organization=organization,
            role=role,
            source_url=source_url,
            contact_created=contact_created,
        )
        msg = (
            f'Subject: {subject}\r\nFrom: {from_addr}\r\n'
            f'To: {", ".join(to_list)}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}'
        )
        with smtplib.SMTP(host, port, timeout=10) as s:
            if port == 587:
                s.starttls()
            if user and password:
                s.login(user, password)
            s.sendmail(from_addr, to_list, msg.encode('utf-8'))
    except Exception as exc:
        _log.warning('Audience admin notification failed: %s', exc)


def _sync_loops_async(contact_id: int, email: str, results: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
    api_key = os.environ.get('PBJ_AUDIENCE_LOOPS_API_KEY', '').strip()
    if not api_key:
        return
    threading.Thread(
        target=_sync_loops,
        args=(api_key, email, results, ctx),
        daemon=True,
    ).start()


def _sync_loops(api_key: str, email: str, results: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
    try:
        import urllib.request

        payload = {
            'email': email,
            'source': 'pbj320',
            'subscribed': True,
            'userGroup': ','.join(r['subscriptionType'] for r in results),
            'pageType': ctx.get('pageType'),
        }
        req = urllib.request.Request(
            'https://app.loops.so/api/v1/contacts/create',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception as exc:
        _log.info('Loops sync skipped or failed: %s', exc)


def new_visitor_key() -> str:
    return secrets.token_hex(16)
