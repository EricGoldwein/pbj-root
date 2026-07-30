"""Centralized contextual CTA resolution (server-side mirror of pbj-audience.js resolver)."""

from __future__ import annotations

from typing import Any

from audience.constants import (
    SUBSCRIPTION_FACILITY,
    SUBSCRIPTION_NATIONAL,
    SUBSCRIPTION_PBJ320_INSIGHTS,
    SUBSCRIPTION_STATE,
    SUBSCRIPTION_APP_EARLY_ACCESS,
    SUBSCRIPTION_ATTORNEY_RESOURCES,
)

# Ownership-scoped subscriptions require send workflow support — disabled until implemented.
CHAIN_SUBSCRIPTIONS_ENABLED = False


def _ctx_get(ctx: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in ctx and ctx[k] not in (None, ''):
            return ctx[k]
    return default


def resolve_cta(
    ctx: dict[str, Any] | None = None,
    *,
    explicit_variant: str | None = None,
    existing_subscriptions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Return CTA spec: variant, primary, title, description, submitLabel, secondary, preferenceDefaults.
    Verified from: user prompt priority order (facility > state > search > homepage > insights).
    """
    ctx = dict(ctx or {})
    subs = set(existing_subscriptions or [])
    page_type = (_ctx_get(ctx, 'pageType', 'page_type', 'kind') or 'fallback').lower()
    facility_name = (_ctx_get(ctx, 'facilityName', 'facility_name') or '').strip()
    state_name = (_ctx_get(ctx, 'stateName', 'state_name') or _ctx_get(ctx, 'recentStateName', 'continueStateName') or '').strip()
    state_abbr = (_ctx_get(ctx, 'stateAbbr', 'state_abbr', 'state') or _ctx_get(ctx, 'recentStateAbbr', 'continueStateAbbr') or '').strip().upper()
    ccn = (_ctx_get(ctx, 'ccn', 'resourceId') or '').strip()
    chain_name = (_ctx_get(ctx, 'chainName', 'ownerName', 'entityName') or '').strip()
    search_states = _ctx_get(ctx, 'searchStateFilters', 'search_states') or []
    if isinstance(search_states, str):
        search_states = [s.strip().upper() for s in search_states.split(',') if s.strip()]
    else:
        search_states = [str(s).strip().upper() for s in search_states if str(s).strip()]

    if explicit_variant:
        variant = explicit_variant
    elif page_type == 'provider' or page_type == 'facility':
        variant = 'facility_follow'
    elif page_type == 'state' and state_abbr and state_abbr != 'USA':
        variant = 'state_follow'
    elif page_type == 'search' or _ctx_get(ctx, 'fromSearch'):
        if len(search_states) == 1:
            variant = 'search_state'
            state_abbr = state_abbr or search_states[0]
        elif len(search_states) > 1:
            variant = 'search_national'
        else:
            variant = 'search_national'
    elif page_type in ('ownership', 'chain') and CHAIN_SUBSCRIPTIONS_ENABLED and chain_name:
        variant = 'ownership_follow'
    elif page_type in ('ownership', 'chain'):
        variant = 'state_follow' if state_abbr else 'national_updates'
    elif page_type == 'insights' or page_type == 'insights_article':
        variant = 'insights_article'
    elif page_type in ('attorney', 'premium', 'attorneys'):
        variant = 'attorney_updates'
    elif page_type == 'homepage' and _ctx_get(ctx, 'recentStateAbbr', 'continueStateAbbr'):
        variant = 'homepage_continue_state'
        state_abbr = state_abbr or str(_ctx_get(ctx, 'recentStateAbbr', 'continueStateAbbr')).upper()
        state_name = state_name or str(_ctx_get(ctx, 'recentStateName', 'continueStateName') or state_abbr)
    else:
        variant = 'homepage_insights'

    spec = _copy_for_variant(variant, facility_name, state_name, state_abbr, chain_name)
    primary = spec['primary']
    spec['suppressed'] = primary in subs
    spec['context'] = {
        'pageType': page_type,
        'ccn': ccn or None,
        'facilityName': facility_name or None,
        'stateAbbr': state_abbr or None,
        'stateName': state_name or None,
        'chainName': chain_name or None,
    }
    return spec


def _copy_for_variant(
    variant: str,
    facility_name: str,
    state_name: str,
    state_abbr: str,
    chain_name: str,
) -> dict[str, Any]:
    if variant == 'facility_follow':
        label = f'Updates · {facility_name}' if facility_name else 'Facility updates'
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_FACILITY,
            'label': label,
            'title': label,
            'description': 'Staffing and ownership notes when PBJ320 has something new on this facility.',
            'submitLabel': 'Subscribe',
            'secondary': None,
            'preferenceDefaults': [SUBSCRIPTION_FACILITY],
            'preferenceTitle': 'Add other update types',
        }
    if variant in ('state_follow', 'search_state', 'homepage_continue_state'):
        sn = state_name or state_abbr or 'your state'
        label = f'{sn} staffing updates' if variant != 'homepage_continue_state' else f'{sn} updates'
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_STATE,
            'label': label,
            'title': label,
            'description': 'Notes when new CMS staffing data or PBJ320 state analysis publishes.',
            'submitLabel': 'Subscribe',
            'secondary': None,
            'preferenceDefaults': [SUBSCRIPTION_STATE],
            'preferenceTitle': 'Add other update types',
        }
    if variant in ('national_updates', 'search_national'):
        label = 'National staffing updates'
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_NATIONAL,
            'label': label,
            'title': label,
            'description': 'Occasional notes on CMS staffing releases and national PBJ320 findings.',
            'submitLabel': 'Subscribe',
            'secondary': None,
            'preferenceDefaults': [SUBSCRIPTION_NATIONAL],
            'preferenceTitle': 'Add other update types',
        }
    if variant == 'ownership_follow' and chain_name:
        label = f'Updates · {chain_name}'
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_FACILITY,
            'label': label,
            'title': label,
            'description': 'Staffing and ownership notes related to this ownership group.',
            'submitLabel': 'Subscribe',
            'secondary': None,
            'preferenceDefaults': [SUBSCRIPTION_FACILITY],
            'preferenceTitle': 'Add other update types',
        }
    if variant == 'insights_article':
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_PBJ320_INSIGHTS,
            'label': 'PBJ320 Insights',
            'title': 'PBJ320 Insights',
            'description': 'Analysis by email when we publish on PBJ320.',
            'submitLabel': 'Subscribe',
            'secondary': {'type': 'eric_substack', 'label': 'Eric\'s Substack'},
            'preferenceDefaults': [SUBSCRIPTION_PBJ320_INSIGHTS],
            'preferenceTitle': 'Add other update types',
        }
    if variant == 'attorney_updates':
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_ATTORNEY_RESOURCES,
            'label': 'Professional updates',
            'title': 'Professional updates',
            'description': 'Research tools and staffing analysis for attorneys and experts.',
            'submitLabel': 'Subscribe',
            'secondary': None,
            'preferenceDefaults': [SUBSCRIPTION_ATTORNEY_RESOURCES],
            'preferenceTitle': 'Add other update types',
        }
    if variant == 'homepage_app':
        return {
            'variant': variant,
            'primary': SUBSCRIPTION_APP_EARLY_ACCESS,
            'label': 'PBJ320 app',
            'title': 'PBJ320 app',
            'description': 'Product notes and an invitation when early access opens.',
            'submitLabel': 'Subscribe',
            'secondary': None,
            'preferenceDefaults': [SUBSCRIPTION_APP_EARLY_ACCESS],
            'preferenceTitle': 'Add other update types',
        }
    label = 'PBJ320 updates'
    return {
        'variant': variant if variant != 'homepage_continue_state' else 'homepage_insights',
        'primary': SUBSCRIPTION_PBJ320_INSIGHTS,
        'label': label,
        'title': label,
        'description': 'Occasional analysis and staffing notes by email.',
        'submitLabel': 'Subscribe',
        'secondary': None,
        'preferenceDefaults': [SUBSCRIPTION_PBJ320_INSIGHTS],
        'preferenceTitle': 'Add other update types',
    }
