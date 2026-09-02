"""Admin-only Sunny Pastures demo provider — reuses the public provider renderer."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from audience.admin_auth import SESSION_KEY, _session_token
from demo_data.sunny_pastures import (
    SUNNY_PASTURES_ID,
    SUNNY_PASTURES_LOCAL_PATH,
    SUNNY_PASTURES_PATH,
    is_demo_provider_id,
    load_sunny_pastures_provider,
)
from facility_provider_indexes import REQUIRED_PROVIDER_DF_CSV_COLUMNS
from site_public_config import sitemap_loc_is_allowed

REPO_ROOT = Path(__file__).resolve().parents[1]

_PROVIDER_UI_MARKERS = (
    'id="pbj-takeaway"',
    'class="pbj-takeaway',
    'pbj-casemix-card',
    'data-pbj-casemix-ui="14-split-7"',
    'pbj-chart-container',
    'pbj-page-overview',
    'pbj-page-summary',
    'pbj-metric--ratings',
    'How these figures are calculated',
    'chartTotalHprd',
    'chartRN',
    'chartCensus',
    'chartContract',
)


@pytest.fixture()
def admin_key(monkeypatch):
    monkeypatch.setenv('ADMIN_VIEW_KEY', 'secret-admin-key')
    monkeypatch.delenv('PBJ_ADMIN_KEY', raising=False)


@pytest.fixture()
def client(admin_key):
    from app import app

    app.config['SECRET_KEY'] = 'test-secret-key'
    return app.test_client()


def _auth_headers():
    return {'Authorization': 'Bearer secret-admin-key'}


def test_demo_id_is_not_a_cms_ccn():
    assert SUNNY_PASTURES_ID == 'DEMO-FL-SUNNY'
    assert is_demo_provider_id(SUNNY_PASTURES_ID)
    assert not is_demo_provider_id('105502')
    from app import normalize_ccn

    assert normalize_ccn(SUNNY_PASTURES_ID) == ''


def test_fixture_matches_provider_page_schema():
    payload = load_sunny_pastures_provider(canonical_quarter='2026Q1')
    df = payload.facility_df
    missing = [c for c in REQUIRED_PROVIDER_DF_CSV_COLUMNS if c not in df.columns]
    assert missing == [], missing
    quarters = [str(v) for v in df['CY_Qtr']]
    assert len(quarters) >= 36
    assert quarters[0] == '2017Q1'
    assert quarters[-1] == '2026Q1'
    assert quarters[-4:] == ['2025Q2', '2025Q3', '2025Q4', '2026Q1']
    latest = df.iloc[-1]
    assert float(latest['Total_Nurse_HPRD']) == pytest.approx(3.40)
    assert float(latest['RN_HPRD']) == pytest.approx(0.44)
    assert float(latest['avg_daily_census']) == pytest.approx(113.0)
    assert float(latest['Contract_Percentage']) == pytest.approx(9.0)
    tail = df.iloc[-4:]
    totals = [float(v) for v in tail['Total_Nurse_HPRD']]
    rns = [float(v) for v in tail['RN_HPRD']]
    census = [float(v) for v in tail['avg_daily_census']]
    contracts = [float(v) for v in tail['Contract_Percentage']]
    assert totals[0] > totals[-1]
    assert rns[0] > rns[-1]
    assert census[-1] > census[0]
    assert contracts[-1] > contracts[0]
    # Last four are not an even staircase.
    assert len(set(round(totals[i] - totals[i + 1], 2) for i in range(3))) > 1
    hist_totals = [float(v) for v in df['Total_Nurse_HPRD'].iloc[:-4]]
    ups = sum(1 for i in range(1, len(hist_totals)) if hist_totals[i] > hist_totals[i - 1])
    downs = sum(1 for i in range(1, len(hist_totals)) if hist_totals[i] < hist_totals[i - 1])
    assert ups >= 4 and downs >= 4
    row = payload.provider_info_row
    assert row['is_demo'] is True
    assert row['provider_name'] == 'Sunny Pastures'
    assert row['city'] == 'Miami'
    assert row['state'] == 'FL'
    assert row['overall_rating'] == 2
    assert row['staffing_rating'] == 2
    assert row['health_inspection_rating'] == 2
    assert row['qm_rating'] == 4
    assert 3.7 <= float(row['case_mix_total_nurse_hrs_per_resident_per_day']) <= 3.9
    assert not row.get('entity_id')
    assert not row.get('abuse_icon')
    assert not row.get('sff_status')


def test_admin_sample_requires_auth(client):
    resp = client.get(SUNNY_PASTURES_PATH)
    assert resp.status_code in (302, 303)
    location = resp.headers.get('Location') or ''
    assert '/admin/audience/login' in location
    assert resp.headers.get('X-Robots-Tag') == 'noindex, nofollow'


def test_admin_sample_rejects_query_string_key(client):
    resp = client.get(f'{SUNNY_PASTURES_PATH}?key=secret-admin-key')
    assert resp.status_code in (302, 303)
    assert '/admin/audience/login' in (resp.headers.get('Location') or '')


def test_public_provider_url_does_not_serve_demo(client):
    resp = client.get(f'/provider/{SUNNY_PASTURES_ID}')
    assert resp.status_code == 404


def test_demo_not_in_search_index_or_sitemap():
    idx_path = REPO_ROOT / 'search_index.json'
    if idx_path.is_file():
        text = idx_path.read_text(encoding='utf-8')
        assert SUNNY_PASTURES_ID not in text
        assert 'Sunny Pastures' not in text
    loc = f'https://www.pbj320.com{SUNNY_PASTURES_PATH}'
    assert sitemap_loc_is_allowed(loc) is False
    assert sitemap_loc_is_allowed(f'https://www.pbj320.com{SUNNY_PASTURES_LOCAL_PATH}') is False


def test_local_preview_is_ungated_on_loopback(client):
    resp = client.get(SUNNY_PASTURES_LOCAL_PATH)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Sunny Pastures' in html
    assert '2017Q1' in html
    assert '3.40' in html
    assert resp.headers.get('X-Robots-Tag') == 'noindex, nofollow'


def test_local_preview_is_404_on_render(client, monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    resp = client.get(SUNNY_PASTURES_LOCAL_PATH)
    assert resp.status_code == 404


def test_authenticated_demo_page_reuses_provider_ui(client):
    resp = client.get(SUNNY_PASTURES_PATH, headers=_auth_headers())
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Sunny Pastures' in html
    assert 'DEMO' in html
    assert 'Synthetic facility data' in html
    assert 'Florida comparisons use actual PBJ data' in html
    assert 'noindex, nofollow' in html.lower()
    assert resp.headers.get('X-Robots-Tag') == 'noindex, nofollow'
    assert 'no-store' in (resp.headers.get('Cache-Control') or '')
    assert 'medicare.gov/care-compare' not in html
    assert 'application/ld+json' not in html
    assert 'Golden Girls' in html
    assert 'Sophia' in html
    for marker in _PROVIDER_UI_MARKERS:
        assert marker in html, f'missing provider UI marker: {marker}'
    assert re.search(r'reported <strong>\d+\.\d+ HPRD</strong>', html)
    assert 'N/A HPRD' not in html
    assert '3.40' in html
    assert '3.82' in html
    assert '2017Q1' in html
    assert html.count('2017Q1') >= 1
    assert '2026Q1' in html
    assert 'For Profit' in html
    assert 'Miami' in html
    assert SUNNY_PASTURES_ID in html
    assert 'SFF Candidate' not in html
    assert '>SFF</span>' not in html
    assert '1★ Staffing' not in html
    assert '1-star staffing' not in html.lower()


def test_florida_percentile_uses_real_population_not_fixture():
    from app import get_facility_state_percentile, get_canonical_latest_quarter

    payload = load_sunny_pastures_provider(
        canonical_quarter=get_canonical_latest_quarter() or '2026Q1'
    )
    latest = payload.facility_df.iloc[-1]
    q = str(latest['CY_Qtr'])
    hprd = float(latest['Total_Nurse_HPRD'])
    rn = float(latest['RN_HPRD'])
    pct_total, pct_rn = get_facility_state_percentile(
        payload.provider_id, 'FL', q, hprd, rn
    )
    if pct_total is None:
        pytest.skip('Florida percentile index not available in this environment')
    assert 10 <= int(pct_total) <= 25
    if pct_rn is not None:
        assert 10 <= int(pct_rn) <= 30
    from app import format_percentile_phrase

    phrase = format_percentile_phrase(pct_total, 'Florida')
    assert phrase
    assert 'Florida' in phrase
    assert 'bottom 5%' not in phrase
    # Fixture ID must not be required for the rank (CCN is ignored).
    pct2, _ = get_facility_state_percentile('999999', 'FL', q, hprd, rn)
    assert pct2 == pct_total


def test_demo_html_matches_real_florida_provider_structure(client):
    demo = client.get(SUNNY_PASTURES_PATH, headers=_auth_headers())
    assert demo.status_code == 200
    demo_html = demo.get_data(as_text=True)

    fl_ccn = _first_florida_ccn()
    if not fl_ccn:
        pytest.skip('No Florida CCN available for structural comparison')
    real = client.get(f'/provider/{fl_ccn}')
    if real.status_code != 200:
        pytest.skip(f'Florida provider {fl_ccn} returned {real.status_code}')
    real_html = real.get_data(as_text=True)
    for marker in _PROVIDER_UI_MARKERS:
        assert marker in demo_html, f'demo missing {marker}'
        assert marker in real_html, f'real FL provider missing {marker}'
    assert demo_html.count('pbj-chart-container') >= 4
    assert real_html.count('pbj-chart-container') >= 4
    assert 'pbj-page-summary-identity' in demo_html
    assert 'pbj-page-summary-identity' in real_html
    assert 'id="pbj-takeaway"' in demo_html
    assert 'id="pbj-takeaway"' in real_html


def _first_florida_ccn() -> str:
    idx_path = REPO_ROOT / 'search_index.json'
    if not idx_path.is_file():
        return ''
    import json

    data = json.loads(idx_path.read_text(encoding='utf-8'))
    for row in data.get('f') or []:
        if str(row.get('s') or '').strip().upper() == 'FL':
            ccn = str(row.get('c') or '').strip()
            if ccn and ccn.isdigit():
                return ccn.zfill(6)
    return ''
