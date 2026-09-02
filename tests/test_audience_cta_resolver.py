"""Tests for centralized audience CTA resolver."""

from __future__ import annotations

from audience.cta_resolver import resolve_cta


def test_facility_page_resolves_facility_and_state_context():
    spec = resolve_cta({
        'pageType': 'provider',
        'ccn': '335513',
        'facilityName': 'Seagate Rehabilitation',
        'stateAbbr': 'NY',
        'stateName': 'New York',
    })
    assert spec['variant'] == 'facility_follow'
    assert spec['primary'] == 'facility'
    assert 'Seagate' in spec['title']
    assert spec['submitLabel'] == 'Subscribe'
    assert spec['secondary'] is None


def test_state_cta_without_state_landing_page():
    """Facility-derived state works when user never visited /state/pennsylvania."""
    spec = resolve_cta({
        'pageType': 'provider',
        'ccn': '395001',
        'facilityName': 'Example NH',
        'stateAbbr': 'PA',
        'stateName': 'Pennsylvania',
    })
    assert spec['primary'] == 'facility'
    assert spec['context']['stateAbbr'] == 'PA'


def test_state_page_primary():
    spec = resolve_cta({'pageType': 'state', 'stateAbbr': 'TX', 'stateName': 'Texas'})
    assert spec['variant'] == 'state_follow'
    assert 'Texas' in spec['label']


def test_search_single_state_filter():
    spec = resolve_cta({'pageType': 'search', 'fromSearch': True, 'searchStateFilters': ['PA']})
    assert spec['variant'] == 'search_state'
    assert spec['primary'] == 'state'


def test_search_multi_state_national():
    spec = resolve_cta({'pageType': 'search', 'searchStateFilters': ['PA', 'NY', 'TX']})
    assert spec['variant'] == 'search_national'
    assert spec['primary'] == 'national'
    assert 'National' in spec['label']


def test_insights_article_separate_from_substack():
    spec = resolve_cta({'pageType': 'insights_article'})
    assert spec['primary'] == 'pbj320_insights'
    assert spec['secondary']['type'] == 'eric_substack'


def test_homepage_continue_state_for_returning_visitor():
    spec = resolve_cta({
        'pageType': 'homepage',
        'recentStateAbbr': 'PA',
        'recentStateName': 'Pennsylvania',
    }, explicit_variant='homepage_continue_state')
    assert 'Pennsylvania' in spec['label']


def test_existing_subscription_suppressed_flag():
    spec = resolve_cta({'pageType': 'homepage'}, existing_subscriptions=['pbj320_insights'])
    assert spec['suppressed'] is True
