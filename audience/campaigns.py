"""Campaign send workflow: validated recipients, frozen audience, idempotent sends."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from typing import Any

from audience.constants import (
    RESOURCE_FACILITY,
    RESOURCE_NATIONAL,
    RESOURCE_STATE,
    SUBSCRIPTION_FACILITY,
    SUBSCRIPTION_NATIONAL,
    SUBSCRIPTION_STATE,
    SUBSCRIPTION_STATUS_ACTIVE,
    SUBSCRIPTION_STATUS_UNSUBSCRIBED,
    SUBSCRIPTION_TYPES,
)
from audience.db import db_session, execute_with_retry, init_db
from utils.seo_utils import STATE_ABBR_TO_NAME

_log = logging.getLogger(__name__)
_CCN_RE = re.compile(r'^\d{6}$')
_send_lock = threading.Lock()
US_STATE_ABBRS = frozenset(k.upper() for k in STATE_ABBR_TO_NAME.keys())

SUPPORTED_PROVIDERS = frozenset({'loops'})


class CampaignScopeError(ValueError):
    def __init__(self, code: str, message: str = ''):
        super().__init__(message or code)
        self.code = code


def normalize_state_abbr(raw: str | None) -> str | None:
    abbr = (raw or '').strip().upper()
    return abbr if abbr in US_STATE_ABBRS else None


def normalize_ccn(raw: str | None) -> str | None:
    ccn = (raw or '').strip()
    return ccn if _CCN_RE.match(ccn) else None


def validate_campaign_scope(
    subscription_type: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> tuple[str, str | None, str | None]:
    sub = (subscription_type or '').strip()
    if sub not in SUBSCRIPTION_TYPES:
        raise CampaignScopeError('invalid_subscription_type')
    rt = (resource_type or '').strip() or None
    rid = (resource_id or '').strip() or None
    if sub == SUBSCRIPTION_FACILITY:
        ccn = normalize_ccn(rid)
        if not ccn:
            raise CampaignScopeError('facility_ccn_required')
        return sub, RESOURCE_FACILITY, ccn
    if sub == SUBSCRIPTION_STATE:
        abbr = normalize_state_abbr(rid or rt)
        if not abbr:
            raise CampaignScopeError('state_abbr_required')
        return sub, RESOURCE_STATE, abbr
    if sub == SUBSCRIPTION_NATIONAL:
        return sub, RESOURCE_NATIONAL, 'usa'
    return sub, rt, rid


def _scope_clause(sub_type: str, rt: str | None, rid: str | None) -> tuple[str, list[Any]]:
    clause = ''
    params: list[Any] = []
    if sub_type == SUBSCRIPTION_FACILITY:
        clause = ' AND s.resource_type = ? AND s.resource_id = ?'
        params.extend([RESOURCE_FACILITY, rid])
    elif sub_type == SUBSCRIPTION_STATE:
        clause = ' AND s.resource_type = ? AND s.resource_id = ?'
        params.extend([RESOURCE_STATE, rid])
    elif sub_type == SUBSCRIPTION_NATIONAL:
        clause = ' AND s.resource_type = ? AND s.resource_id = ?'
        params.extend([RESOURCE_NATIONAL, 'usa'])
    return clause, params


def _fetch_eligible_recipients(
    conn: Any,
    sub_type: str,
    rt: str | None,
    rid: str | None,
) -> list[Any]:
    scope, scope_params = _scope_clause(sub_type, rt, rid)
    q = f'''
        SELECT c.id AS contact_id, c.email, s.id AS subscription_id
        FROM contacts c
        JOIN subscriptions s ON s.contact_id = c.id
        WHERE s.subscription_type = ? AND s.status = ?{scope}
        ORDER BY c.id
    '''
    params: list[Any] = [sub_type, SUBSCRIPTION_STATUS_ACTIVE, *scope_params]
    rows = conn.execute(q, tuple(params)).fetchall()
    seen_emails: set[str] = set()
    out: list[Any] = []
    for row in rows:
        email_key = (row['email'] or '').strip().lower()
        if not email_key or email_key in seen_emails:
            continue
        seen_emails.add(email_key)
        out.append(row)
    return out


def _count_excluded_unsubscribed(
    conn: Any,
    sub_type: str,
    rt: str | None,
    rid: str | None,
) -> int:
    scope, scope_params = _scope_clause(sub_type, rt, rid)
    row = conn.execute(
        f'''
        SELECT COUNT(DISTINCT c.id) AS n
        FROM contacts c
        JOIN subscriptions s ON s.contact_id = c.id
        WHERE s.subscription_type = ? AND s.status = ?{scope}
        ''',
        tuple([sub_type, SUBSCRIPTION_STATUS_UNSUBSCRIBED, *scope_params]),
    ).fetchone()
    return int(row['n'] if row else 0)


def preview_recipients(
    subscription_type: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> dict[str, Any]:
    """Count eligible active subscribers; never returns email addresses."""
    try:
        sub, rt, rid = validate_campaign_scope(
            subscription_type, resource_type=resource_type, resource_id=resource_id,
        )
    except CampaignScopeError as exc:
        return {'ok': False, 'error': exc.code}
    init_db()
    with db_session() as conn:
        eligible = _fetch_eligible_recipients(conn, sub, rt, rid)
        excluded = _count_excluded_unsubscribed(conn, sub, rt, rid)
    return {
        'ok': True,
        'subscriptionType': sub,
        'resourceType': rt,
        'resourceId': rid,
        'eligibleCount': len(eligible),
        'excludedUnsubscribedCount': excluded,
    }


def create_campaign_draft(
    name: str,
    subscription_type: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    subject: str = '',
    body_preview: str = '',
    test_mode: bool = False,
) -> dict[str, Any]:
    try:
        sub, rt, rid = validate_campaign_scope(
            subscription_type, resource_type=resource_type, resource_id=resource_id,
        )
    except CampaignScopeError as exc:
        return {'ok': False, 'error': exc.code}
    preview = preview_recipients(sub, resource_type=rt, resource_id=rid)
    if not preview.get('ok'):
        return preview
    provider = (os.environ.get('PBJ_AUDIENCE_EMAIL_PROVIDER') or 'loops').strip().lower()[:32]
    init_db()
    with db_session() as conn:
        cur = execute_with_retry(
            conn,
            '''
            INSERT INTO campaigns (
                name, subscription_type, resource_type, resource_id,
                subject, body_preview, provider, status, recipient_count,
                excluded_count, test_mode, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            ''',
            (
                name[:200],
                sub,
                rt,
                rid,
                subject[:300],
                body_preview[:8000],
                provider,
                preview['eligibleCount'],
                preview.get('excludedUnsubscribedCount', 0),
                1 if test_mode else 0,
                str(uuid.uuid4()),
            ),
        )
        campaign_id = int(cur.lastrowid)
    return {'ok': True, 'campaignId': campaign_id, **preview}


def list_campaigns(*, limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with db_session() as conn:
        rows = conn.execute(
            '''
            SELECT id, name, subscription_type, resource_type, resource_id,
                   subject, status, recipient_count, excluded_count,
                   successful_count, failed_count, test_mode,
                   provider, provider_campaign_id, frozen_at,
                   created_at, sent_at, error_message
            FROM campaigns ORDER BY created_at DESC LIMIT ?
            ''',
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_campaign_audit(campaign_id: int) -> dict[str, Any] | None:
    init_db()
    with db_session() as conn:
        camp = conn.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
        if not camp:
            return None
        frozen = conn.execute(
            'SELECT COUNT(*) AS n FROM campaign_audience WHERE campaign_id = ?',
            (campaign_id,),
        ).fetchone()
        sends = conn.execute(
            '''
            SELECT status, COUNT(*) AS n FROM campaign_sends
            WHERE campaign_id = ? AND COALESCE(is_test, 0) = 0
            GROUP BY status
            ''',
            (campaign_id,),
        ).fetchall()
        tests = conn.execute(
            'SELECT COUNT(*) AS n FROM campaign_sends WHERE campaign_id = ? AND is_test = 1',
            (campaign_id,),
        ).fetchone()
    return {
        'campaignId': campaign_id,
        'subscriptionType': camp['subscription_type'],
        'resourceType': camp['resource_type'],
        'resourceId': camp['resource_id'],
        'subject': camp['subject'],
        'status': camp['status'],
        'audienceCount': camp['recipient_count'],
        'excludedCount': camp['excluded_count'],
        'frozenAudienceCount': int(frozen['n'] if frozen else 0),
        'successfulRecipients': camp['successful_count'],
        'failedRecipients': camp['failed_count'],
        'testSends': int(tests['n'] if tests else 0),
        'provider': camp['provider'],
        'providerCampaignId': camp['provider_campaign_id'],
        'createdAt': camp['created_at'],
        'frozenAt': camp['frozen_at'],
        'sentAt': camp['sent_at'],
        'sendStatuses': {r['status']: int(r['n']) for r in sends},
        'errorMessage': camp['error_message'],
    }


def _provider_configured(provider: str) -> bool:
    provider = (provider or '').strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        return False
    if provider == 'loops':
        return bool(os.environ.get('PBJ_AUDIENCE_LOOPS_API_KEY', '').strip())
    return False


def _freeze_campaign_audience(conn: Any, campaign_id: int, camp: Any) -> list[Any]:
    existing = conn.execute(
        'SELECT contact_id, subscription_id FROM campaign_audience WHERE campaign_id = ?',
        (campaign_id,),
    ).fetchall()
    if existing:
        ids = [int(r['contact_id']) for r in existing]
        placeholders = ','.join('?' * len(ids))
        return conn.execute(
            f'''
            SELECT c.id AS contact_id, c.email, ca.subscription_id AS subscription_id
            FROM campaign_audience ca
            JOIN contacts c ON c.id = ca.contact_id
            WHERE ca.campaign_id = ? AND c.id IN ({placeholders})
            ORDER BY c.id
            ''',
            (campaign_id, *ids),
        ).fetchall()

    recipients = _fetch_eligible_recipients(
        conn, camp['subscription_type'], camp['resource_type'], camp['resource_id'],
    )
    for row in recipients:
        execute_with_retry(
            conn,
            '''
            INSERT OR IGNORE INTO campaign_audience (campaign_id, contact_id, subscription_id)
            VALUES (?, ?, ?)
            ''',
            (campaign_id, row['contact_id'], row['subscription_id']),
        )
    execute_with_retry(
        conn,
        '''
        UPDATE campaigns SET frozen_at = datetime('now'), recipient_count = ?
        WHERE id = ?
        ''',
        (len(recipients), campaign_id),
    )
    return recipients


def send_campaign(
    campaign_id: int,
    *,
    test_email: str | None = None,
    retry_failed_only: bool = False,
) -> dict[str, Any]:
    """
    Send or test-send a campaign.
    Preview uses live counts; production send freezes audience before provider dispatch.
    """
    init_db()
    test_email_norm = (test_email or '').strip().lower() or None

    with _send_lock:
        with db_session() as conn:
            camp = conn.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
            if not camp:
                return {'ok': False, 'error': 'campaign_not_found'}

            if test_email_norm:
                return _send_test(conn, camp, test_email_norm)

            if retry_failed_only:
                return _retry_failed(conn, camp)

            if camp['status'] not in ('draft',):
                return {'ok': False, 'error': 'invalid_status', 'status': camp['status']}

            provider = (camp['provider'] or 'loops').strip().lower()
            if not _provider_configured(provider):
                return {'ok': False, 'error': 'provider_not_configured'}

            locked = execute_with_retry(
                conn,
                '''
                UPDATE campaigns SET status = 'sending', send_started_at = datetime('now')
                WHERE id = ? AND status = 'draft'
                ''',
                (campaign_id,),
            )
            if locked.rowcount == 0:
                return {'ok': False, 'error': 'send_already_in_progress_or_completed'}

            recipients = _freeze_campaign_audience(conn, campaign_id, camp)
            return _dispatch_to_recipients(conn, camp, recipients, is_test=False)


def _send_test(conn: Any, camp: Any, test_email: str) -> dict[str, Any]:
    """Test send to one address; does not mark campaign as sent or mutate frozen audience."""
    provider = (camp['provider'] or 'loops').strip().lower()
    if not _provider_configured(provider):
        return {'ok': False, 'error': 'provider_not_configured'}
    row = conn.execute(
        'SELECT id, email FROM contacts WHERE email = ? COLLATE NOCASE', (test_email,),
    ).fetchone()
    contact_id = int(row['id']) if row else None
    if contact_id is None:
        cur = execute_with_retry(
            conn,
            'INSERT INTO contacts (email) VALUES (?)',
            (test_email,),
        )
        contact_id = int(cur.lastrowid)
    try:
        if provider == 'loops':
            _send_via_loops(
                os.environ.get('PBJ_AUDIENCE_LOOPS_API_KEY', '').strip(),
                test_email,
                camp,
                idempotency_key=f'test-{camp["id"]}-{contact_id}-{uuid.uuid4().hex[:8]}',
            )
        execute_with_retry(
            conn,
            '''
            INSERT INTO campaign_sends (
                campaign_id, contact_id, subscription_id, status, is_test, sent_at
            ) VALUES (?, ?, NULL, 'sent', 1, datetime('now'))
            ''',
            (int(camp['id']), contact_id),
        )
        _log.info(
            'Campaign test send recorded campaign_id=%s contact_id=%s',
            camp['id'], contact_id,
        )
        return {
            'ok': True,
            'campaignId': int(camp['id']),
            'testMode': True,
            'sent': 1,
            'failed': 0,
            'campaignStatus': camp['status'],
        }
    except Exception as exc:
        _log.warning('Campaign test send failed campaign_id=%s: %s', camp['id'], type(exc).__name__)
        execute_with_retry(
            conn,
            '''
            INSERT INTO campaign_sends (
                campaign_id, contact_id, subscription_id, status, is_test, error_message
            ) VALUES (?, ?, NULL, 'failed', 1, ?)
            ''',
            (int(camp['id']), contact_id, type(exc).__name__),
        )
        return {'ok': False, 'error': 'test_send_failed', 'campaignId': int(camp['id'])}


def _retry_failed(conn: Any, camp: Any) -> dict[str, Any]:
    if camp['status'] not in ('partial', 'failed'):
        return {'ok': False, 'error': 'invalid_status_for_retry', 'status': camp['status']}
    provider = (camp['provider'] or 'loops').strip().lower()
    if not _provider_configured(provider):
        return {'ok': False, 'error': 'provider_not_configured'}
    rows = conn.execute(
        '''
        SELECT cs.contact_id, cs.subscription_id, c.email
        FROM campaign_sends cs
        JOIN contacts c ON c.id = cs.contact_id
        WHERE cs.campaign_id = ? AND cs.status = 'failed' AND COALESCE(cs.is_test, 0) = 0
        ''',
        (int(camp['id']),),
    ).fetchall()
    if not rows:
        return {'ok': False, 'error': 'no_failed_recipients'}
    recipient_rows = [
        {'contact_id': r['contact_id'], 'email': r['email'], 'subscription_id': r['subscription_id']}
        for r in rows
    ]
    return _dispatch_to_recipients(conn, camp, recipient_rows, is_test=False, retry_mode=True)


def _dispatch_to_recipients(
    conn: Any,
    camp: Any,
    recipients: list[Any],
    *,
    is_test: bool,
    retry_mode: bool = False,
) -> dict[str, Any]:
    campaign_id = int(camp['id'])
    provider = (camp['provider'] or 'loops').strip().lower()
    api_key = os.environ.get('PBJ_AUDIENCE_LOOPS_API_KEY', '').strip()
    sent = 0
    failed = 0
    skipped = 0

    for row in recipients:
        contact_id = int(row['contact_id'])
        sub_id = row['subscription_id'] if 'subscription_id' in row.keys() else None
        email = row['email']

        existing = conn.execute(
            '''
            SELECT status FROM campaign_sends
            WHERE campaign_id = ? AND contact_id = ? AND COALESCE(is_test, 0) = 0
            ''',
            (campaign_id, contact_id),
        ).fetchone()
        if existing and existing['status'] == 'sent' and not retry_mode:
            skipped += 1
            continue

        execute_with_retry(
            conn,
            '''
            INSERT INTO campaign_sends (campaign_id, contact_id, subscription_id, status, is_test)
            VALUES (?, ?, ?, 'pending', 0)
            ON CONFLICT(campaign_id, contact_id) DO UPDATE SET
                status = CASE WHEN campaign_sends.status = 'sent' THEN 'sent' ELSE 'pending' END
            ''',
            (campaign_id, contact_id, sub_id),
        )

        idempotency_key = f'camp-{campaign_id}-contact-{contact_id}'
        try:
            if provider == 'loops' and api_key:
                msg_id = _send_via_loops(api_key, email, camp, idempotency_key=idempotency_key)
            else:
                raise RuntimeError('provider_not_configured')
            execute_with_retry(
                conn,
                '''
                UPDATE campaign_sends
                SET status = 'sent', sent_at = datetime('now'),
                    provider_message_id = ?, error_message = NULL, idempotency_key = ?
                WHERE campaign_id = ? AND contact_id = ? AND COALESCE(is_test, 0) = 0
                ''',
                (msg_id, idempotency_key, campaign_id, contact_id),
            )
            sent += 1
        except Exception as exc:
            failed += 1
            _log.warning(
                'Campaign send failed campaign_id=%s contact_id=%s err=%s',
                campaign_id, contact_id, type(exc).__name__,
            )
            execute_with_retry(
                conn,
                '''
                UPDATE campaign_sends
                SET status = 'failed', error_message = ?, idempotency_key = ?
                WHERE campaign_id = ? AND contact_id = ? AND COALESCE(is_test, 0) = 0
                ''',
                (type(exc).__name__, idempotency_key, campaign_id, contact_id),
            )

    if is_test:
        status = camp['status']
    elif failed == 0 and sent > 0:
        status = 'sent'
    elif sent > 0:
        status = 'partial'
    else:
        status = 'failed'

    if not is_test:
        execute_with_retry(
            conn,
            '''
            UPDATE campaigns
            SET status = ?, sent_at = datetime('now'),
                successful_count = COALESCE(successful_count, 0) + ?,
                failed_count = (
                    SELECT COUNT(*) FROM campaign_sends
                    WHERE campaign_id = ? AND status = 'failed' AND COALESCE(is_test, 0) = 0
                ),
                error_message = ?
            WHERE id = ?
            ''',
            (
                status,
                sent,
                campaign_id,
                f'{failed} failed' if failed else None,
                campaign_id,
            ),
        )

    return {
        'ok': True,
        'campaignId': campaign_id,
        'sent': sent,
        'failed': failed,
        'skipped': skipped,
        'testMode': is_test,
        'status': status if not is_test else camp['status'],
        'retryMode': retry_mode,
    }


def _send_via_loops(
    api_key: str,
    email: str,
    camp: Any,
    *,
    idempotency_key: str,
) -> str:
    import urllib.error
    import urllib.request

    payload = {
        'email': email,
        'subject': camp['subject'],
        'dataVariables': {'body': camp['body_preview']},
        'idempotencyKey': idempotency_key,
    }
    req = urllib.request.Request(
        'https://app.loops.so/api/v1/transactional',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotency_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            data = json.loads(body) if body else {}
            return str(data.get('id') or idempotency_key)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'loops_http_{exc.code}') from exc
