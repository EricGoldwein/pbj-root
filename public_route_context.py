"""Resolve public-page route context for global header search (server + client JSON bootstrap)."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from ownership.state_owner_index import STATE_OWNER_INDEX_SLUGS

_STATE_NAME_TO_CODE: dict[str, str] = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
    'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
    'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
    'district of columbia': 'DC', 'puerto rico': 'PR',
}

_STATE_CODE_TO_NAME: dict[str, str] = {v: k.title() for k, v in _STATE_NAME_TO_CODE.items()}
_USA_SLUGS = frozenset({'usa', 'us', 'national', 'united-states', 'united states'})

_PROVIDER_RE = re.compile(r'^/provider/(\d{6})$')
_STATE_RE = re.compile(r'^/state/([^/]+)$')
_ENTITY_RE = re.compile(r'^/entity/(\d+)$')
_OWNERS_PAC_RE = re.compile(r'^/owners/(\d{10})$')

_SLUG_TO_STATE_CODE: dict[str, str] = {'usa': 'USA'}
for _name_lower, _code in _STATE_NAME_TO_CODE.items():
    _slug = _STATE_CODE_TO_NAME.get(_code, _code).lower().replace(' ', '-')
    _SLUG_TO_STATE_CODE[_slug] = _code


def _canonical_slug(state_code: str) -> str:
    """Verified from: app.py get_canonical_slug."""
    code = (state_code or '').strip().upper()
    if code == 'USA':
        return 'usa'
    state_name = _STATE_CODE_TO_NAME.get(code, '')
    if not state_name:
        return code.lower()
    return state_name.lower().replace(' ', '-')


for _name_lower, _code in _STATE_NAME_TO_CODE.items():
    _SLUG_TO_STATE_CODE[_canonical_slug(_code)] = _code


def _empty_context() -> dict[str, Any]:
    return {
        'kind': 'fallback',
        'stateAbbr': None,
        'stateName': None,
        'stateSlug': None,
        'ccn': None,
        'entityId': None,
        'ownershipStateSlug': None,
    }


def _state_fields_from_slug(slug: str) -> tuple[str | None, str | None, str | None]:
    """Return (stateSlug, stateAbbr, stateName) for a /state/<slug> segment."""
    key = (slug or '').strip().lower()
    if key in _USA_SLUGS or key == 'usa':
        return 'usa', 'USA', 'United States'
    code = _SLUG_TO_STATE_CODE.get(key)
    if code:
        return key, code, _STATE_CODE_TO_NAME.get(code, code)
    return key or None, None, None


def resolve_public_route_context(path: str, *, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve page kind and identifiers from a URL path (no query string)."""
    raw = (path or '/').split('?')[0].split('#')[0].strip() or '/'
    normalized = raw.rstrip('/') or '/'

    ctx = _empty_context()

    if normalized == '/':
        ctx['kind'] = 'homepage'
    elif m := _PROVIDER_RE.match(normalized):
        ctx['kind'] = 'provider'
        ctx['ccn'] = m.group(1)
    elif m := _STATE_RE.match(normalized):
        ctx['kind'] = 'state'
        slug, abbr, name = _state_fields_from_slug(m.group(1))
        ctx['stateSlug'] = slug
        ctx['stateAbbr'] = abbr
        ctx['stateName'] = name
    elif m := _ENTITY_RE.match(normalized):
        ctx['kind'] = 'entity'
        ctx['entityId'] = int(m.group(1))
    elif normalized == '/owners' or normalized.startswith('/owners/'):
        ctx['kind'] = 'ownership'
        segment = normalized[len('/owners/'):] if normalized != '/owners' else ''
        if segment:
            if _OWNERS_PAC_RE.match(normalized):
                pass
            elif segment.lower() in STATE_OWNER_INDEX_SLUGS:
                ctx['ownershipStateSlug'] = segment.lower()
                st_code = STATE_OWNER_INDEX_SLUGS[segment.lower()]
                ctx['stateAbbr'] = st_code
                ctx['stateName'] = _STATE_CODE_TO_NAME.get(st_code, st_code)
    else:
        ctx['kind'] = 'fallback'

    if overrides:
        for key, value in overrides.items():
            if value is not None or key in ctx:
                ctx[key] = value
    return ctx


def search_ui_config(context: dict[str, Any]) -> dict[str, Any]:
    """UI copy and ranking hints for the public search overlay."""
    boost = (context.get('stateAbbr') or '').strip().upper() or None
    if boost == 'USA':
        boost = None
    return {
        'placeholder': 'Find a nursing home',
        'boostStateAbbr': boost,
    }


def public_route_context_payload(
    path: str,
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full bootstrap payload for client search (context + ui config)."""
    ctx = resolve_public_route_context(path, overrides=overrides)
    return {
        'context': ctx,
        'search': search_ui_config(ctx),
    }


def public_route_context_json_script_tag(
    path: str,
    *,
    overrides: dict[str, Any] | None = None,
) -> str:
    """Embed route context in page head for client-side search."""
    payload = public_route_context_payload(path, overrides=overrides)
    data = json.dumps(payload, separators=(',', ':'))
    return (
        f'<script type="application/json" id="pbj-route-context">'
        f'{html.escape(data, quote=False)}</script>'
    )
