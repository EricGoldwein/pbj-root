"""Tests for public_route_context path resolution and search UI config."""

from __future__ import annotations

import json
import re

import pytest

from public_route_context import (
    public_route_context_json_script_tag,
    public_route_context_payload,
    resolve_public_route_context,
    search_ui_config,
)


def test_homepage_kind():
    ctx = resolve_public_route_context('/')
    assert ctx['kind'] == 'homepage'


def test_provider_kind():
    ctx = resolve_public_route_context('/provider/015009')
    assert ctx['kind'] == 'provider'
    assert ctx['ccn'] == '015009'


def test_state_kind_new_york():
    ctx = resolve_public_route_context('/state/new-york')
    assert ctx['kind'] == 'state'
    assert ctx['stateAbbr'] == 'NY'
    assert ctx['stateName'] == 'New York'
    assert ctx['stateSlug'] == 'new-york'


def test_state_kind_usa():
    ctx = resolve_public_route_context('/state/usa')
    assert ctx['kind'] == 'state'
    assert ctx['stateAbbr'] == 'USA'
    assert ctx['stateSlug'] == 'usa'


def test_entity_kind():
    ctx = resolve_public_route_context('/entity/237')
    assert ctx['kind'] == 'entity'
    assert ctx['entityId'] == 237


def test_ownership_hub():
    ctx = resolve_public_route_context('/owners')
    assert ctx['kind'] == 'ownership'
    assert ctx['ownershipStateSlug'] is None


def test_ownership_state_index():
    ctx = resolve_public_route_context('/owners/ny')
    assert ctx['kind'] == 'ownership'
    assert ctx['ownershipStateSlug'] == 'ny'
    assert ctx['stateAbbr'] == 'NY'


def test_ownership_pac_profile():
    ctx = resolve_public_route_context('/owners/1234567890')
    assert ctx['kind'] == 'ownership'
    assert ctx['ownershipStateSlug'] is None


def test_fallback_report():
    ctx = resolve_public_route_context('/report')
    assert ctx['kind'] == 'fallback'


def test_overrides_merge():
    ctx = resolve_public_route_context(
        '/provider/015009',
        overrides={'stateAbbr': 'AL', 'stateName': 'Alabama', 'stateSlug': 'alabama'},
    )
    assert ctx['stateAbbr'] == 'AL'
    assert ctx['stateName'] == 'Alabama'


def test_search_ui_universal_placeholder():
    cfg = search_ui_config({'kind': 'provider'})
    assert cfg['placeholder'] == 'Find a nursing home'
    assert cfg.get('boostStateAbbr') is None


def test_search_ui_state_boosts_ranking_only():
    cfg = search_ui_config({'kind': 'state', 'stateName': 'New York', 'stateAbbr': 'NY'})
    assert cfg['placeholder'] == 'Find a nursing home'
    assert cfg['boostStateAbbr'] == 'NY'


def test_search_ui_ownership_boosts_state():
    cfg = search_ui_config({
        'kind': 'ownership',
        'stateName': 'New York',
        'stateAbbr': 'NY',
        'ownershipStateSlug': 'ny',
    })
    assert cfg['placeholder'] == 'Find a nursing home'
    assert cfg['boostStateAbbr'] == 'NY'
    assert 'categories' not in cfg


def test_json_script_tag_embeds_payload():
    tag = public_route_context_json_script_tag('/state/tennessee')
    assert 'id="pbj-route-context"' in tag
    match = re.search(r'<script[^>]*>(.+)</script>', tag, re.DOTALL)
    assert match
    payload = json.loads(match.group(1))
    assert payload['context']['kind'] == 'state'
    assert payload['context']['stateAbbr'] == 'TN'


def test_payload_structure():
    payload = public_route_context_payload('/entity/42')
    assert 'context' in payload
    assert 'search' in payload
    assert payload['context']['entityId'] == 42
