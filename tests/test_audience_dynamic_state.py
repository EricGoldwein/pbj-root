"""Dynamic state / search integration tests for audience CTA behavior."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from audience import db as audience_db
from audience.cta_resolver import resolve_cta
from audience.service import get_contact_subscriptions, record_engagement_event, sanitize_analytics_metadata, signup


@pytest.fixture()
def audience_db_path(monkeypatch):
    fd, path = tempfile.mkstemp(suffix='.sqlite')
    os.close(fd)
    monkeypatch.setenv('SUBSCRIBERS_DB_PATH', path)
    monkeypatch.delenv('RENDER', raising=False)
    audience_db._path_logged = False
    audience_db._production_checked = False
    audience_db.init_db()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def test_pa_facility_without_state_landing_page_cta():
    """Pennsylvania has no dedicated /state/pennsylvania requirement for facility CTA."""
    spec = resolve_cta({
        'pageType': 'provider',
        'ccn': '395001',
        'facilityName': 'Example Pennsylvania NH',
        'stateAbbr': 'PA',
        'stateName': 'Pennsylvania',
    })
    assert spec['variant'] == 'facility_follow'
    assert 'Example Pennsylvania NH' in spec['title']
    assert spec['context']['stateAbbr'] == 'PA'
    assert '/state/' not in json.dumps(spec)


def test_pa_facility_signup_stores_normalized_state_abbr(audience_db_path):
    spec = resolve_cta({
        'pageType': 'provider',
        'ccn': '395001',
        'facilityName': 'Example Pennsylvania NH',
        'stateAbbr': 'PA',
        'stateName': 'Pennsylvania',
    })
    signup(
        'pa-fac@example.com',
        cta_variant=spec['variant'],
        context=spec['context'],
        preferences=['facility'],
    )
    with audience_db.db_session() as conn:
        row = conn.execute(
            '''
            SELECT s.resource_id, sc.state_abbr
            FROM subscriptions s
            JOIN contacts c ON c.id = s.contact_id
            LEFT JOIN signup_context sc ON sc.contact_id = c.id
            WHERE c.email = ? AND s.subscription_type = 'facility'
            ''',
            ('pa-fac@example.com',),
        ).fetchone()
    assert row['resource_id'] == '395001'
    assert row['state_abbr'] == 'PA'


def test_preference_step_not_in_initial_resolver_copy():
    spec = resolve_cta({
        'pageType': 'provider',
        'ccn': '395001',
        'facilityName': 'Example NH',
        'stateAbbr': 'PA',
        'stateName': 'Pennsylvania',
    })
    assert spec['secondary'] is None
    assert spec['submitLabel'] == 'Subscribe'


def test_existing_state_subscription_suppresses_redundant_primary(audience_db_path):
    signup(
        'pa-state@example.com',
        cta_variant='search_state',
        context={'stateAbbr': 'PA', 'stateName': 'Pennsylvania'},
        preferences=['state'],
    )
    spec = resolve_cta(
        {'pageType': 'state', 'stateAbbr': 'PA', 'stateName': 'Pennsylvania'},
        existing_subscriptions=['state'],
    )
    assert spec['suppressed'] is True


def test_analytics_use_state_abbr_not_email(audience_db_path):
    meta = sanitize_analytics_metadata({
        'stateAbbr': 'PA',
        'email': 'user@example.com',
        'pageType': 'provider',
    })
    assert meta.get('stateAbbr') == 'PA'
    assert 'email' not in meta
    record_engagement_event(
        visitor_key='visitor-abc',
        event_name='state_followed',
        page_type='provider',
        resource_id='PA',
        metadata=meta,
    )
    with audience_db.db_session() as conn:
        row = conn.execute(
            'SELECT metadata, resource_id FROM engagement_events ORDER BY id DESC LIMIT 1',
        ).fetchone()
    stored = json.loads(row['metadata'] or '{}')
    assert 'email' not in stored
    assert row['resource_id'] == 'PA'


def test_single_state_search_resolves_state_cta():
    spec = resolve_cta({'pageType': 'search', 'fromSearch': True, 'searchStateFilters': ['PA']})
    assert spec['variant'] == 'search_state'
    assert spec['primary'] == 'state'


def test_multi_state_search_resolves_national_cta():
    spec = resolve_cta({'pageType': 'search', 'searchStateFilters': ['PA', 'NY']})
    assert spec['variant'] == 'search_national'
    assert spec['primary'] == 'national'


def test_missing_state_context_falls_back_to_general_cta():
    spec = resolve_cta({'pageType': 'fallback'})
    assert spec['variant'] == 'homepage_insights'
    assert spec['primary'] == 'pbj320_insights'
    assert 'Texas' not in spec['title']
    assert 'Pennsylvania' not in spec['title']


def test_invalid_state_abbr_not_used_in_cta_copy():
    spec = resolve_cta({'pageType': 'provider', 'stateAbbr': 'XX', 'facilityName': 'Test NH', 'ccn': '123456'})
    assert spec['variant'] == 'facility_follow'
    secondary = spec.get('secondary')
    if secondary:
        assert 'XX' not in secondary.get('label', '')


def test_flask_resolve_cta_api_single_state_search():
    from app import app

    client = app.test_client()
    resp = client.post(
        '/api/audience/resolve-cta',
        json={'context': {'pageType': 'search', 'searchStateFilters': ['PA']}},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['cta']['variant'] == 'search_state'


def test_flask_signup_status_after_pa_facility(audience_db_path):
    from app import app

    client = app.test_client()
    csrf = client.get('/api/subscribe/csrf').get_json()['csrf_token']
    resp = client.post(
        '/api/audience/signup',
        json={
            'email': 'integration@example.com',
            'ctaVariant': 'facility_follow',
            'context': {'ccn': '395001', 'stateAbbr': 'PA', 'stateName': 'Pennsylvania', 'pageType': 'provider'},
            'preferences': ['facility'],
            'csrfToken': csrf,
        },
        headers={'X-CSRF-Token': csrf},
    )
    assert resp.status_code == 200
    status = get_contact_subscriptions('integration@example.com')
    assert 'facility' in status['activeTypes']
