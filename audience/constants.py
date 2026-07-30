"""Audience subscription types, roles, consent copy, and analytics event names."""

from __future__ import annotations

# --- Product subscriptions (stored in PBJ320 DB) ---

SUBSCRIPTION_PBJ320_INSIGHTS = 'pbj320_insights'
SUBSCRIPTION_FACILITY = 'facility'
SUBSCRIPTION_STATE = 'state'
SUBSCRIPTION_NATIONAL = 'national'
SUBSCRIPTION_APP_EARLY_ACCESS = 'app_early_access'
SUBSCRIPTION_RESEARCH_TOOLS = 'research_tools'
SUBSCRIPTION_ATTORNEY_RESOURCES = 'attorney_resources'
SUBSCRIPTION_ADVOCACY = 'advocacy'

# Legacy alias accepted at API boundary and migrated in DB.
SUBSCRIPTION_INSIGHTS_LEGACY = 'insights'

SUBSCRIPTION_TYPES = frozenset({
    SUBSCRIPTION_PBJ320_INSIGHTS,
    SUBSCRIPTION_FACILITY,
    SUBSCRIPTION_STATE,
    SUBSCRIPTION_NATIONAL,
    SUBSCRIPTION_APP_EARLY_ACCESS,
    SUBSCRIPTION_RESEARCH_TOOLS,
    SUBSCRIPTION_ATTORNEY_RESOURCES,
    SUBSCRIPTION_ADVOCACY,
})

# Eric's Substack is NOT a PBJ320 subscription product — outbound link / analytics only.
ANALYTICS_ERIC_SUBSTACK = 'eric_substack'

RESOURCE_FACILITY = 'facility'
RESOURCE_STATE = 'state'
RESOURCE_CHAIN = 'chain'
RESOURCE_NATIONAL = 'national'

RESOURCE_TYPES = frozenset({RESOURCE_FACILITY, RESOURCE_STATE, RESOURCE_CHAIN, RESOURCE_NATIONAL})

SUBSCRIPTION_STATUS_ACTIVE = 'active'
SUBSCRIPTION_STATUS_UNSUBSCRIBED = 'unsubscribed'

ROLES = frozenset({
    'attorney',
    'advocate',
    'researcher',
    'nursing_home_professional',
    'resident_family',
    'government',
    'other',
})

CONSENT_COPY_VERSION = '2026-07-12-v2'

SUBSTACK_BASE_URL = 'https://320insight.substack.com/'

# Normalize legacy preference names from clients.
SUBSCRIPTION_ALIASES: dict[str, str] = {
    'insights': SUBSCRIPTION_PBJ320_INSIGHTS,
    'pbj320_insights': SUBSCRIPTION_PBJ320_INSIGHTS,
    'eric_substack': ANALYTICS_ERIC_SUBSTACK,  # never stored as subscription
}

ANALYTICS_EVENTS = frozenset({
    'signup_cta_viewed',
    'signup_started',
    'signup_completed',
    'subscription_preference_added',
    'facility_followed',
    'state_followed',
    'national_updates_subscribed',
    'pbj320_insights_subscribed',
    'substack_link_clicked',
    'app_early_access_joined',
    'popup_eligible',
    'popup_shown',
    'popup_dismissed',
    'popup_submitted',
    'popup_error',
    'popup_suppressed',
    'feedback_submitted',
    'testimonial_permission_granted',
    'unsubscribe_completed',
})

CTA_VARIANT_PRIMARY: dict[str, str] = {
    'homepage_insights': SUBSCRIPTION_PBJ320_INSIGHTS,
    'homepage_continue_state': SUBSCRIPTION_STATE,
    'homepage_app': SUBSCRIPTION_APP_EARLY_ACCESS,
    'facility_follow': SUBSCRIPTION_FACILITY,
    'state_follow': SUBSCRIPTION_STATE,
    'national_updates': SUBSCRIPTION_NATIONAL,
    'search_state': SUBSCRIPTION_STATE,
    'search_national': SUBSCRIPTION_NATIONAL,
    'insights_article': SUBSCRIPTION_PBJ320_INSIGHTS,
    'attorney_updates': SUBSCRIPTION_ATTORNEY_RESOURCES,
    'email_updates_modal': SUBSCRIPTION_PBJ320_INSIGHTS,
    'footer_modal': SUBSCRIPTION_PBJ320_INSIGHTS,
    'legacy_subscribe': SUBSCRIPTION_PBJ320_INSIGHTS,
    'engagement_prompt': SUBSCRIPTION_FACILITY,
}


def normalize_subscription_type(raw: str | None) -> str | None:
    """Map client/legacy names to canonical subscription types. Returns None for non-subscribable values."""
    key = (raw or '').strip().lower()
    if not key:
        return None
    if key == ANALYTICS_ERIC_SUBSTACK:
        return None
    if key in SUBSCRIPTION_ALIASES:
        mapped = SUBSCRIPTION_ALIASES[key]
        return mapped if mapped in SUBSCRIPTION_TYPES else None
    return key if key in SUBSCRIPTION_TYPES else None
