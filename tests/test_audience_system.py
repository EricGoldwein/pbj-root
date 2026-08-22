"""Extended audience system tests — product model, security, analytics."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from audience import db as audience_db
from audience.admin_auth import verify_admin_request
from audience.constants import normalize_subscription_type
from audience.cta_resolver import resolve_cta
from audience.db import ensure_production_db_config, is_production_environment
from audience.service import (
    add_preferences,
    admin_export_csv_rows,
    csv_safe_cell,
    format_admin_signup_notification,
    get_contact_subscriptions,
    has_active_subscription,
    is_prompt_suppressed,
    normalize_email,
    record_prompt_dismissal,
    sanitize_analytics_metadata,
    signup,
    substack_outbound_url,
    unsubscribe_by_token,
    unsubscribe_token,
)


@pytest.fixture()
def audience_db_path(monkeypatch):
    fd, path = tempfile.mkstemp(suffix='.sqlite')
    os.close(fd)
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', path)
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.delenv('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', raising=False)
    audience_db._path_logged = False
    audience_db._production_checked = False
    audience_db.init_db()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def test_pbj320_insights_not_substack(audience_db_path):
    result = signup(
        'insights@example.com',
        cta_variant='homepage_insights',
        preferences=['pbj320_insights'],
    )
    assert 'substackUrl' not in result
    status = get_contact_subscriptions('insights@example.com')
    assert 'pbj320_insights' in status['activeTypes']


def test_legacy_insights_alias_normalizes():
    assert normalize_subscription_type('insights') == 'pbj320_insights'
    assert normalize_subscription_type('eric_substack') is None


def test_substack_url_uses_eric_substack_campaign():
    url = substack_outbound_url(cta_variant='insights_article', page_type='insights')
    assert 'utm_campaign=eric_substack' in url


def test_duplicate_contact_upsert(audience_db_path):
    r1 = signup('user@example.com', cta_variant='homepage_insights', preferences=['pbj320_insights'])
    r2 = signup('User@example.com', cta_variant='facility_follow', context={'ccn': '015009'}, preferences=['facility'])
    assert r1['contactCreated'] is True
    assert r2['contactCreated'] is False
    assert r1['contactId'] == r2['contactId']


def test_multiple_subscriptions(audience_db_path):
    signup('multi@example.com', cta_variant='facility_follow', context={'ccn': '015009', 'stateAbbr': 'AL'}, preferences=['facility'])
    add_preferences('multi@example.com', ['pbj320_insights', 'app_early_access'], context={'stateAbbr': 'AL'})
    status = get_contact_subscriptions('multi@example.com')
    types = {s['subscription_type'] for s in status['subscriptions']}
    assert 'facility' in types
    assert 'app_early_access' in types


def test_context_capture_signup_context_table(audience_db_path):
    signup(
        'ctx@example.com',
        cta_variant='facility_follow',
        context={
            'sourceUrl': 'https://www.pbj320.com/provider/335513',
            'pageType': 'provider',
            'ccn': '335513',
            'facilityName': 'Seagate',
            'stateAbbr': 'NY',
            'stateName': 'New York',
            'utmSource': 'google',
            'deviceCategory': 'mobile',
            'visitorKey': 'anon-123',
        },
        preferences=['facility'],
    )
    with audience_db.db_session() as conn:
        row = conn.execute(
            'SELECT facility_ccn, state_abbr, device_category FROM signup_context ORDER BY id DESC LIMIT 1'
        ).fetchone()
    assert row['facility_ccn'] == '335513'
    assert row['state_abbr'] == 'NY'
    assert row['device_category'] == 'mobile'


def test_facility_state_from_provider_without_state_page(audience_db_path):
    spec = resolve_cta({'pageType': 'provider', 'stateAbbr': 'PA', 'stateName': 'Pennsylvania', 'ccn': '123456'})
    assert spec['primary'] == 'facility'
    signup('pa@example.com', cta_variant=spec['variant'], context=spec['context'], preferences=['facility'])
    with audience_db.db_session() as conn:
        row = conn.execute(
            '''
            SELECT resource_id FROM subscriptions s JOIN contacts c ON c.id = s.contact_id
            WHERE c.email = ? AND s.subscription_type = 'facility'
            ''',
            ('pa@example.com',),
        ).fetchone()
    assert row['resource_id'] == '123456'


def test_consent_version_recorded(audience_db_path):
    signup('consent@example.com', cta_variant='homepage_insights', preferences=['pbj320_insights'])
    with audience_db.db_session() as conn:
        row = conn.execute(
            'SELECT consent_copy_version FROM consent_events ORDER BY id DESC LIMIT 1'
        ).fetchone()
    assert row['consent_copy_version'] == '2026-07-12-v2'


def test_unsubscribe_scoped(audience_db_path):
    signup('unsub@example.com', cta_variant='homepage_app', preferences=['app_early_access'])
    cid = signup('unsub@example.com', cta_variant='homepage_insights', preferences=['pbj320_insights'])['contactId']
    token = unsubscribe_token(cid, 'app_early_access', None, None)
    unsubscribe_by_token(token)
    assert has_active_subscription('unsub@example.com', 'app_early_access') is False
    assert has_active_subscription('unsub@example.com', 'pbj320_insights') is True


def test_prompt_suppression_30_days(audience_db_path):
    visitor = 'v-key-abc'
    prompt_type = 'facility_follow_popup'
    assert is_prompt_suppressed(visitor, prompt_type) is False
    record_prompt_dismissal(visitor, prompt_type)
    assert is_prompt_suppressed(visitor, prompt_type) is True


def test_analytics_strips_email_and_tokens():
    meta = sanitize_analytics_metadata({'email': 'a@b.com', 'token': 'secret', 'page_type': 'provider'})
    assert 'email' not in meta
    assert 'token' not in meta
    assert meta['page_type'] == 'provider'


def test_csv_formula_injection_escape():
    assert csv_safe_cell('=cmd|').startswith("'")
    assert csv_safe_cell('normal@example.com') == 'normal@example.com'


def test_admin_rejects_query_string_key(monkeypatch):
    from flask import Flask, request

    monkeypatch.setenv('ADMIN_VIEW_KEY', 'secret-admin-key')
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    with app.test_request_context('/admin/audience?key=secret-admin-key'):
        assert verify_admin_request(request) is False
    with app.test_request_context('/admin/audience', headers={'Authorization': 'Bearer secret-admin-key'}):
        assert verify_admin_request(request) is True
    with app.test_request_context('/admin/audience', headers={'X-PBJ-Admin-Key': 'secret-admin-key'}):
        assert verify_admin_request(request) is True


def test_admin_session_auth(monkeypatch):
    from flask import Flask, request

    from audience.admin_auth import establish_admin_session, verify_admin_request

    monkeypatch.setenv('ADMIN_VIEW_KEY', 'secret-admin-key')
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-secret'
    with app.test_request_context('/admin/audience'):
        establish_admin_session()
        assert verify_admin_request(request) is True


def test_production_requires_persistent_db(monkeypatch):
    monkeypatch.setenv('PBJ_REQUIRE_PERSISTENT_AUDIENCE_DB', '1')
    monkeypatch.delenv('SUBSCRIBERS_DB_PATH', raising=False)
    audience_db._production_checked = False
    with pytest.raises(RuntimeError, match='SUBSCRIBERS_DB_PATH'):
        ensure_production_db_config()


def test_csv_export_rows(audience_db_path):
    signup('csv@example.com', cta_variant='homepage_insights', preferences=['pbj320_insights'])
    rows = admin_export_csv_rows()
    assert rows[0][0] == 'email'
    assert any(r[0] == 'csv@example.com' for r in rows[1:])


def test_national_subscription(audience_db_path):
    signup('nat@example.com', cta_variant='search_national', preferences=['national'])
    assert has_active_subscription('nat@example.com', 'national', resource_type='national', resource_id='usa')


def test_admin_signup_notification_includes_subscriber_identity():
    subject, body = format_admin_signup_notification(
        'subscriber@example.com',
        'facility_follow',
        [{
            'subscriptionType': 'facility',
            'result': 'created',
            'resourceType': 'facility',
            'resourceId': '015009',
        }],
        context={
            'facilityName': 'Example Nursing Home',
            'ccn': '015009',
            'stateAbbr': 'AL',
            'pageType': 'provider',
            'sourceUrl': 'https://www.pbj320.com/provider/015009',
        },
        contact_created=True,
    )
    assert subject == 'PBJ320 audience signup: subscriber@example.com'
    assert 'Email: subscriber@example.com' in body
    assert 'CTA: facility_follow' in body
    assert 'facility (facility: 015009)' in body
    assert 'Facility: Example Nursing Home' in body
    assert 'Source URL: https://www.pbj320.com/provider/015009' in body
    assert 'New contact: yes' in body
