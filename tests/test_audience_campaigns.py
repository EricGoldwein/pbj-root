"""Campaign safety tests — no real provider sends."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from audience import db as audience_db
from audience.campaigns import (
    create_campaign_draft,
    get_campaign_audit,
    preview_recipients,
    send_campaign,
)
from audience.constants import SUBSCRIPTION_STATUS_UNSUBSCRIBED
from audience.service import signup


@pytest.fixture()
def audience_db_path(monkeypatch):
    fd, path = tempfile.mkstemp(suffix='.sqlite')
    os.close(fd)
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', path)
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.delenv('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', raising=False)
    monkeypatch.delenv('PBJ_AUDIENCE_LOOPS_API_KEY', raising=False)
    audience_db._path_logged = False
    audience_db._production_checked = False
    audience_db.init_db()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def _seed_facility(email: str, ccn: str = '395001'):
    signup(
        email,
        cta_variant='facility_follow',
        context={'ccn': ccn, 'stateAbbr': 'PA', 'stateName': 'Pennsylvania'},
        preferences=['facility'],
    )


def _seed_state(email: str, abbr: str = 'PA'):
    signup(
        email,
        cta_variant='search_state',
        context={'stateAbbr': abbr, 'stateName': 'Pennsylvania'},
        preferences=['state'],
    )


def _seed_national(email: str):
    signup(
        email,
        cta_variant='search_national',
        preferences=['national'],
    )


def test_invalid_facility_scope_requires_ccn():
    result = preview_recipients('facility', resource_type='facility', resource_id='bad')
    assert result['ok'] is False
    assert result['error'] == 'facility_ccn_required'


def test_invalid_state_scope_requires_abbr():
    result = preview_recipients('state', resource_type='state', resource_id='Pennsylvania')
    assert result['ok'] is False
    assert result['error'] == 'state_abbr_required'


def test_topic_unsubscribe_excluded_from_recipients(audience_db_path):
    _seed_state('active@example.com', 'PA')
    _seed_state('gone@example.com', 'PA')
    with audience_db.db_session() as conn:
        conn.execute(
            '''
            UPDATE subscriptions SET status = ?
            WHERE contact_id = (SELECT id FROM contacts WHERE email = ?)
            ''',
            (SUBSCRIPTION_STATUS_UNSUBSCRIBED, 'gone@example.com'),
        )
    preview = preview_recipients('state', resource_type='state', resource_id='PA')
    assert preview['eligibleCount'] == 1
    assert preview['excludedUnsubscribedCount'] == 1


def test_duplicate_email_deduplicated(audience_db_path):
    _seed_state('dup@example.com', 'PA')
    preview = preview_recipients('state', resource_type='state', resource_id='PA')
    assert preview['eligibleCount'] == 1


def test_national_does_not_include_facility_only(audience_db_path):
    _seed_facility('fac-only@example.com')
    _seed_national('nat@example.com')
    preview = preview_recipients('national', resource_type='national', resource_id='usa')
    assert preview['eligibleCount'] == 1


def test_missing_provider_fails_closed(audience_db_path):
    _seed_national('nat@example.com')
    draft = create_campaign_draft('Nat update', 'national', subject='Hello', body_preview='Body')
    result = send_campaign(draft['campaignId'])
    assert result['ok'] is False
    assert result['error'] == 'provider_not_configured'
    audit = get_campaign_audit(draft['campaignId'])
    assert audit['status'] == 'draft'


def test_test_send_does_not_mark_campaign_sent(audience_db_path, monkeypatch):
    monkeypatch.setenv('PBJ_AUDIENCE_LOOPS_API_KEY', 'test-key')
    _seed_national('prod@example.com')
    draft = create_campaign_draft('Nat update', 'national', subject='Hello', body_preview='Body')
    with patch('audience.campaigns._send_via_loops', return_value='msg-1'):
        result = send_campaign(draft['campaignId'], test_email='test@example.com')
    assert result['ok'] is True
    assert result['testMode'] is True
    audit = get_campaign_audit(draft['campaignId'])
    assert audit['status'] == 'draft'
    assert audit['testSends'] == 1
    assert audit['frozenAudienceCount'] == 0


def test_production_send_freezes_audience(audience_db_path, monkeypatch):
    monkeypatch.setenv('PBJ_AUDIENCE_LOOPS_API_KEY', 'test-key')
    _seed_national('a@example.com')
    _seed_national('b@example.com')
    draft = create_campaign_draft('Nat update', 'national', subject='Hello', body_preview='Body')
    with patch('audience.campaigns._send_via_loops', return_value='msg-1'):
        result = send_campaign(draft['campaignId'])
    assert result['ok'] is True
    assert result['sent'] == 2
    audit = get_campaign_audit(draft['campaignId'])
    assert audit['frozenAudienceCount'] == 2
    assert audit['status'] == 'sent'


def test_repeated_send_request_rejected(audience_db_path, monkeypatch):
    monkeypatch.setenv('PBJ_AUDIENCE_LOOPS_API_KEY', 'test-key')
    _seed_national('a@example.com')
    draft = create_campaign_draft('Nat update', 'national', subject='Hello', body_preview='Body')
    with patch('audience.campaigns._send_via_loops', return_value='msg-1'):
        first = send_campaign(draft['campaignId'])
        second = send_campaign(draft['campaignId'])
    assert first['ok'] is True
    assert second['ok'] is False
    assert second['error'] == 'invalid_status'


def test_partial_failure_and_retry_only_failed(audience_db_path, monkeypatch):
    monkeypatch.setenv('PBJ_AUDIENCE_LOOPS_API_KEY', 'test-key')
    _seed_national('ok@example.com')
    _seed_national('fail@example.com')
    draft = create_campaign_draft('Nat update', 'national', subject='Hello', body_preview='Body')

    def _side_effect(api_key, email, camp, *, idempotency_key):
        if email == 'fail@example.com':
            raise RuntimeError('loops_http_500')
        return 'msg-ok'

    with patch('audience.campaigns._send_via_loops', side_effect=_side_effect):
        result = send_campaign(draft['campaignId'])
    assert result['sent'] == 1
    assert result['failed'] == 1
    audit = get_campaign_audit(draft['campaignId'])
    assert audit['status'] == 'partial'

    with patch('audience.campaigns._send_via_loops', return_value='msg-retry'):
        retry = send_campaign(draft['campaignId'], retry_failed_only=True)
    assert retry['ok'] is True
    assert retry['sent'] == 1
    audit2 = get_campaign_audit(draft['campaignId'])
    assert audit2['successfulRecipients'] >= 2


def test_preview_never_returns_emails(audience_db_path):
    _seed_national('secret@example.com')
    preview = preview_recipients('national', resource_type='national', resource_id='usa')
    assert 'email' not in str(preview).lower() or preview.get('eligibleCount') == 1
    assert 'secret@example.com' not in str(preview)
