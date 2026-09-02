"""Eligibility and safety checks for the feature-flagged facility popup."""

from __future__ import annotations

from pathlib import Path

import pytest

from audience.constants import ANALYTICS_EVENTS
from audience.prompt_config import (
    facility_popup_eligibility,
    prompt_config_payload,
)
from audience.service import sanitize_analytics_metadata


ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / 'pbj-audience.js'


def _eligible_signals(**overrides):
    signals = {
        'pageType': 'provider',
        'pageviewCount': 4,
        'pageSeconds': 20,
        'distinctFacilityViews': 3,
        'sessionCount': 1,
        'alreadyFollowing': False,
        'promptShownThisSession': False,
        'dismissedWithin30Days': False,
        'manualModalOpened': False,
        'inlineInteracted': False,
        'inlineVisible': False,
    }
    signals.update(overrides)
    return signals


def test_popup_default_off_and_feedback_stays_off(monkeypatch):
    monkeypatch.delenv('PBJ_AUDIENCE_ENGAGEMENT_PROMPTS', raising=False)
    monkeypatch.delenv('PBJ_AUDIENCE_FEEDBACK_PROMPTS', raising=False)
    config = prompt_config_payload()
    assert config['engagementPromptsEnabled'] is False
    assert config['feedbackPromptsEnabled'] is False
    assert config['minFacilityPageSeconds'] == 20
    assert config['noExitIntent'] is True


def test_no_popup_on_first_pageview():
    assert facility_popup_eligibility(
        _eligible_signals(pageviewCount=1)
    ) == (False, 'first_pageview')


def test_no_popup_before_20_seconds():
    assert facility_popup_eligibility(
        _eligible_signals(pageSeconds=19.99)
    ) == (False, 'before_minimum_time')


def test_eligible_after_three_distinct_facility_views():
    assert facility_popup_eligibility(
        _eligible_signals(distinctFacilityViews=3)
    ) == (True, 'distinct_facility_pages_3plus')


def test_eligible_on_return_session():
    assert facility_popup_eligibility(
        _eligible_signals(distinctFacilityViews=1, sessionCount=2)
    ) == (True, 'repeat_session')


@pytest.mark.parametrize(
    ('field', 'reason'),
    [
        ('alreadyFollowing', 'already_following'),
        ('inlineVisible', 'inline_cta_visible'),
        ('inlineInteracted', 'inline_cta_interacted'),
        ('promptShownThisSession', 'prompt_already_shown'),
        ('dismissedWithin30Days', 'dismissed_30_days'),
        ('manualModalOpened', 'manual_modal_opened'),
    ],
)
def test_popup_suppression_reasons(field, reason):
    assert facility_popup_eligibility(
        _eligible_signals(**{field: True})
    ) == (False, reason)


def test_popup_success_is_one_sentence_and_has_no_preferences():
    js = JS_PATH.read_text(encoding='utf-8')
    popup = js.split('function showFacilityPopup', 1)[1].split(
        'function schedulePopupRetry', 1
    )[0]
    assert "successMessage: 'You\\u2019re following this facility.'" in popup
    assert popup.count('successMessage:') == 1
    assert 'preference' not in popup.lower()
    assert 'name="role"' not in popup.lower()
    assert 'name="organization"' not in popup.lower()


def test_popup_analytics_events_and_metadata_exclude_email():
    expected = {
        'popup_eligible',
        'popup_shown',
        'popup_dismissed',
        'popup_submitted',
        'popup_error',
        'popup_suppressed',
    }
    assert expected <= ANALYTICS_EVENTS
    metadata = sanitize_analytics_metadata({
        'facility_ccn': '335513',
        'facility_view_count': 3,
        'session_count': 2,
        'trigger_reason': 'repeat_session',
        'email': 'private@example.com',
        'csrfToken': 'secret',
    })
    assert metadata['facility_ccn'] == '335513'
    assert 'email' not in metadata
    assert all('token' not in key.lower() for key in metadata)
