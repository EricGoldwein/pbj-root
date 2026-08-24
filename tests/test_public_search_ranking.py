"""Tests for public search ranking policy (national scope, gentle state boost)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_LIMIT = 8
MAX_BOOST_STATE_IN_RESULTS = 3


def _match_query(value: str, q: str) -> bool:
    return q.lower() in (value or '').lower()


def _text_match_score(
    value: str,
    q: str,
    exact: int,
    prefix: int,
    word_prefix: int,
    substring: int,
) -> int:
    text = (value or '').strip().lower()
    query = (q or '').strip().lower()
    if not text or not query:
        return 0
    if text == query:
        return exact
    if text.startswith(query):
        return prefix
    words = [word for word in re.split(r'[^a-z0-9]+', text) if word]
    if any(word.startswith(query) for word in words):
        return word_prefix
    return substring if query in text else 0


def facility_base_score(row: dict, q: str) -> int:
    """Mirror public-search.js facilityBaseScore — verified from: public-search.js."""
    score = _text_match_score(str(row.get('c') or ''), q, 1000, 800, 0, 0)
    score += _text_match_score(str(row.get('n') or ''), q, 600, 500, 300, 100)
    score += _text_match_score(str(row.get('y') or ''), q, 90, 70, 55, 35)
    score += _text_match_score(str(row.get('s') or ''), q, 50, 40, 30, 20)
    return score


def top_facilities(q: str, boost_abbr: str | None, limit: int = RESULT_LIMIT) -> list[dict]:
    """Mirror public-search.js buildFacilityResults selection logic."""
    path = REPO_ROOT / 'search_index.json'
    if not path.exists():
        pytest.skip('search_index.json not present locally')
    data = json.loads(path.read_text(encoding='utf-8'))
    hits = []
    for row in data.get('f', []):
        if not row or not row.get('c'):
            continue
        base = facility_base_score(row, q)
        if base:
            hits.append({'row': row, 'base': base})
    hits.sort(key=lambda item: (-item['base'], str(item['row'].get('n') or '')))

    max_in_state = (
        min(MAX_BOOST_STATE_IN_RESULTS, max(1, limit - 1)) if boost_abbr else 0
    )
    in_state_hits = [h for h in hits if boost_abbr and (h['row'].get('s') or '') == boost_abbr]
    other_hits = [h for h in hits if not (boost_abbr and (h['row'].get('s') or '') == boost_abbr)]

    selected: list[dict] = []
    used: set[str] = set()

    for hit in in_state_hits:
        if len(selected) >= max_in_state:
            break
        key = str(hit['row'].get('c') or '')
        if key in used:
            continue
        used.add(key)
        selected.append(hit)

    for hit in other_hits:
        if len(selected) >= limit:
            break
        key = str(hit['row'].get('c') or '')
        if key in used:
            continue
        used.add(key)
        selected.append(hit)

    if len(selected) < limit:
        for hit in in_state_hits:
            if len(selected) >= limit:
                break
            key = str(hit['row'].get('c') or '')
            if key in used:
                continue
            used.add(key)
            selected.append(hit)

    def _sort_key(item: dict) -> tuple:
        row = item['row']
        in_boost = 1 if boost_abbr and (row.get('s') or '') == boost_abbr else 0
        return (-item['base'], -in_boost, str(row.get('n') or ''))

    selected.sort(key=_sort_key)
    return [item['row'] for item in selected[:limit]]


def test_fa_on_ny_page_includes_non_ny_matches():
    """NY provider context must not exclude other states from top results."""
    results = top_facilities('fa', 'NY')
    states = {(r.get('s') or '') for r in results}
    assert len(results) == RESULT_LIMIT
    assert 'NY' in states
    assert len(states) > 1, f'expected mixed states, got only {states}'
    assert sum(1 for r in results if r.get('s') == 'NY') <= MAX_BOOST_STATE_IN_RESULTS


def test_ccn_prefix_match_scores_highest():
    row = {'n': 'Example', 'c': '335513', 'y': 'NYC', 's': 'NY'}
    assert facility_base_score(row, '3355') == 800


def test_name_prefix_beats_word_prefix_and_incidental_location_match():
    direct = {'n': 'HANCEVILLE NURSING & REHAB CENTER', 'c': '015073', 'y': 'HANCEVILLE', 's': 'AL'}
    later_word = {'n': 'APERION CARE HANOVER', 'c': '145333', 'y': 'CHICAGO', 's': 'IL'}
    city_only = {'n': 'BRICKYARD HEALTHCARE', 'c': '155000', 'y': 'HARTFORD CITY', 's': 'IN'}
    assert facility_base_score(direct, 'ha') > facility_base_score(later_word, 'ha')
    assert facility_base_score(later_word, 'ha') > facility_base_score(city_only, 'ha')


def test_ha_results_begin_with_direct_name_prefixes():
    results = top_facilities('ha', None)
    assert results
    assert all(str(row.get('n') or '').lower().startswith('ha') for row in results[:3])
