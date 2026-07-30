"""Engagement prompt eligibility and frequency rules (feature-flagged)."""

from __future__ import annotations

import os
from typing import Any

# Verified from: docs/audience-system-developer.md — env-gated prompts.
PROMPT_DISMISS_DAYS = 30
MIN_FACILITY_PAGES_FOR_HEAVY = 3
MIN_FACILITY_PAGE_SECONDS = 20


def engagement_prompts_enabled() -> bool:
    return os.environ.get('PBJ_AUDIENCE_ENGAGEMENT_PROMPTS', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


def feedback_prompts_enabled() -> bool:
    return os.environ.get('PBJ_AUDIENCE_FEEDBACK_PROMPTS', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


def prompt_config_payload() -> dict[str, Any]:
    """Client-readable prompt rules (no secrets)."""
    return {
        'engagementPromptsEnabled': engagement_prompts_enabled(),
        'feedbackPromptsEnabled': feedback_prompts_enabled(),
        'dismissSuppressDays': PROMPT_DISMISS_DAYS,
        'minFacilityPagesForHeavy': MIN_FACILITY_PAGES_FOR_HEAVY,
        'minFacilityPageSeconds': MIN_FACILITY_PAGE_SECONDS,
        'neverOnFirstPageview': True,
        'maxPromptsPerSession': 1,
        'noExitIntent': True,
        'promptType': 'facility_follow_popup',
    }


def is_heavy_user_signals(signals: dict[str, Any] | None) -> tuple[bool, str | None]:
    """Return facility-popup heavy-user eligibility and trigger reason."""
    if not signals:
        return False, None
    facility_views = int(
        signals.get('distinctFacilityViews')
        or signals.get('facilityPageViews')
        or 0
    )
    if facility_views >= MIN_FACILITY_PAGES_FOR_HEAVY:
        return True, 'distinct_facility_pages_3plus'
    if signals.get('repeatSession') or int(signals.get('sessionCount') or 0) > 1:
        return True, 'repeat_session'
    return False, None


def facility_popup_eligibility(signals: dict[str, Any] | None) -> tuple[bool, str]:
    """Evaluate the client-visible facility popup rules without side effects."""
    data = signals or {}
    if data.get('pageType') not in ('provider', 'facility'):
        return False, 'not_facility_page'
    if int(data.get('pageviewCount') or 0) <= 1:
        return False, 'first_pageview'
    if float(data.get('pageSeconds') or 0) < MIN_FACILITY_PAGE_SECONDS:
        return False, 'before_minimum_time'
    if data.get('alreadyFollowing'):
        return False, 'already_following'
    if data.get('promptShownThisSession'):
        return False, 'prompt_already_shown'
    if data.get('dismissedWithin30Days'):
        return False, 'dismissed_30_days'
    if data.get('manualModalOpened'):
        return False, 'manual_modal_opened'
    if data.get('inlineInteracted'):
        return False, 'inline_cta_interacted'
    if data.get('inlineVisible'):
        return False, 'inline_cta_visible'
    heavy, trigger = is_heavy_user_signals(data)
    if not heavy:
        return False, 'not_heavy_user'
    return True, trigger or 'eligible'
