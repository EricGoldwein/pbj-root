"""Sunny Pastures — admin-only synthetic Florida provider fixture.

Facility-level values are invented. State/national comparisons are computed at
render time against the real Florida PBJ population (this ID is never inserted).

History length matches typical public PBJ provider pages: 2017Q1 through the
site canonical quarter (~37 quarters). The last four quarters carry the
calibrated deterioration narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SUNNY_PASTURES_ID = 'DEMO-FL-SUNNY'
SUNNY_PASTURES_PATH = '/admin/sample/sunny-pastures'
SUNNY_PASTURES_LOCAL_PATH = '/sunny-pastures'
SUNNY_PASTURES_NAME = 'Sunny Pastures'
_DEFAULT_ANCHOR_QUARTER = '2026Q1'
_HISTORY_START = '2017Q1'

# Last four quarters (oldest → newest). Latest total is calibrated against real
# FL 2026Q1 HPRD lists via get_facility_state_percentile (~18th percentile).
# Steps are uneven on purpose — real low-HPRD FL homes plateau and bounce.
_TAIL_STORY: tuple[dict[str, float], ...] = (
    {
        'census': 97.0,
        'total_hprd': 3.58,
        'rn_hprd': 0.56,
        'lpn_hprd': 0.84,
        'na_hprd': 2.04,
        'nurse_care_hprd': 3.34,
        'rn_care_hprd': 0.49,
        'lpn_care_hprd': 0.81,
        'contract_pct': 2.8,
    },
    {
        'census': 99.0,
        'total_hprd': 3.62,
        'rn_hprd': 0.59,
        'lpn_hprd': 0.81,
        'na_hprd': 2.08,
        'nurse_care_hprd': 3.38,
        'rn_care_hprd': 0.52,
        'lpn_care_hprd': 0.78,
        'contract_pct': 3.4,
    },
    {
        'census': 107.0,
        'total_hprd': 3.46,
        'rn_hprd': 0.47,
        'lpn_hprd': 0.83,
        'na_hprd': 2.02,
        'nurse_care_hprd': 3.22,
        'rn_care_hprd': 0.40,
        'lpn_care_hprd': 0.80,
        'contract_pct': 7.1,
    },
    {
        'census': 113.0,
        'total_hprd': 3.40,
        'rn_hprd': 0.44,
        'lpn_hprd': 0.80,
        'na_hprd': 2.01,
        'nurse_care_hprd': 3.16,
        'rn_care_hprd': 0.38,
        'lpn_care_hprd': 0.77,
        'contract_pct': 9.0,
    },
)


@dataclass(frozen=True)
class DemoProviderPayload:
    """Same inputs ``generate_provider_page_html`` expects for a real CCN."""

    provider_id: str
    facility_df: Any
    provider_info_row: dict[str, Any]


def is_demo_provider_id(value: object) -> bool:
    raw = str(value or '').strip().upper()
    return raw == SUNNY_PASTURES_ID


def _parse_cy_qtr(q: str) -> tuple[int, int] | None:
    s = str(q or '').strip().upper()
    if len(s) < 6 or s[4] != 'Q':
        return None
    try:
        year = int(s[:4])
        qn = int(s[5])
    except ValueError:
        return None
    if qn < 1 or qn > 4:
        return None
    return year, qn


def _prior_cy_qtr(q: str) -> str | None:
    parsed = _parse_cy_qtr(q)
    if not parsed:
        return None
    year, qn = parsed
    if qn == 1:
        return f'{year - 1}Q4'
    return f'{year}Q{qn - 1}'


def _next_cy_qtr(q: str) -> str | None:
    parsed = _parse_cy_qtr(q)
    if not parsed:
        return None
    year, qn = parsed
    if qn == 4:
        return f'{year + 1}Q1'
    return f'{year}Q{qn + 1}'


def quarters_ending_at(anchor_qtr: str | None, n: int | None = None) -> list[str]:
    """Chronological CY_Qtr list ending at ``anchor_qtr`` (inclusive).

    If ``n`` is None, span ``_HISTORY_START`` through the anchor (full PBJ window).
    """
    q = str(anchor_qtr or _DEFAULT_ANCHOR_QUARTER).strip().upper()
    if not q:
        q = _DEFAULT_ANCHOR_QUARTER
    if n is None:
        return _quarter_span(_HISTORY_START, q)
    trail: list[str] = []
    cur: str | None = q
    for _ in range(max(1, n)):
        if not cur:
            break
        trail.append(cur)
        cur = _prior_cy_qtr(cur)
    trail.reverse()
    return trail


def _quarter_span(start: str, end: str) -> list[str]:
    if not _parse_cy_qtr(start) or not _parse_cy_qtr(end):
        return []
    if start > end:
        return []
    out = [start]
    cur: str | None = start
    while cur != end:
        cur = _next_cy_qtr(cur)
        if not cur:
            break
        out.append(cur)
        if len(out) > 80:
            break
    return out


def _round2(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def _metric_row(
    *,
    census: float,
    total_hprd: float,
    rn_hprd: float,
    lpn_hprd: float,
    contract_pct: float,
) -> dict[str, float]:
    """Keep role splits internally consistent with Total / Direct / RN / LPN / NA."""
    total_hprd = _round2(total_hprd)
    rn_hprd = _round2(rn_hprd)
    lpn_hprd = _round2(lpn_hprd)
    admin = 0.24
    nurse_care = _round2(total_hprd - admin)
    rn_care = _round2(max(0.05, rn_hprd - 0.07))
    lpn_care = _round2(max(0.05, lpn_hprd - 0.03))
    na_hprd = _round2(max(0.5, nurse_care - rn_care - lpn_care))
    return {
        'census': _round2(census),
        'total_hprd': total_hprd,
        'rn_hprd': rn_hprd,
        'lpn_hprd': lpn_hprd,
        'na_hprd': na_hprd,
        'nurse_care_hprd': nurse_care,
        'rn_care_hprd': rn_care,
        'lpn_care_hprd': lpn_care,
        'contract_pct': _round2(contract_pct),
    }


def _u01(seed: str) -> float:
    """Stable 0–1 hash. Not cryptographic — fixture texture only."""
    h = 2166136261
    for ch in seed:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return (h % 10000) / 10000.0


# Light, real-FL-shaped nudges (plateaus, COVID occupancy dip, 2022 softening,
# one 2024 dip-and-recover). Texture checked against FL homes near 3.40 HPRD
# in 2026Q1 (e.g. 105258 / 105884); values are invented, not copied.
_EPISODES: dict[str, dict[str, float]] = {
    '2020Q2': {'census': -3.5, 'total': 0.05, 'rn': 0.05, 'contract': 0.8},
    '2020Q3': {'census': -2.0, 'total': 0.02, 'rn': 0.03},
    '2020Q4': {'census': -1.0, 'total': 0.07, 'contract': 1.4},
    '2021Q1': {'census': -2.0, 'contract': 3.6},
    '2021Q2': {'contract': 4.1, 'total': 0.04},
    '2022Q2': {'total': -0.11, 'rn': -0.07, 'lpn': 0.06},
    '2022Q3': {'total': -0.09, 'rn': -0.08, 'lpn': 0.07},
    '2024Q3': {'total': -0.14, 'rn': -0.09},
    '2024Q4': {'total': 0.09, 'rn': 0.05},
}


def _pre_tail_stories(quarters: list[str]) -> list[dict[str, float]]:
    """Random-walk around a weak-FL band: plateaus, small reversals, no ramp."""
    total, rn, lpn, census, contract = 3.87, 0.62, 0.88, 91.0, 1.8
    prev_dt = 0.0
    rows: list[dict[str, float]] = []
    for qtr in quarters:
        parsed = _parse_cy_qtr(qtr) or (2017, 1)
        year, _qn = parsed
        u = _u01(qtr)
        if u < 0.30:
            dt = 0.0
        elif u < 0.50 and prev_dt:
            dt = -0.6 * prev_dt
        else:
            dt = (_u01(qtr + 't') - 0.50) * 0.20
        dt += (3.74 - total) * 0.10
        if year >= 2022:
            dt -= 0.012
        ep = _EPISODES.get(qtr, {})
        dt += ep.get('total', 0.0)
        total = max(3.42, min(4.12, total + dt))
        prev_dt = dt

        ru = _u01(qtr + 'rn')
        drn = 0.0 if ru < 0.32 else (ru - 0.50) * 0.16
        drn += ep.get('rn', 0.0)
        rn = max(0.42, min(0.76, rn + drn + (0.60 - rn) * 0.14))

        lpn += ep.get('lpn', 0.0) - 0.30 * drn + (_u01(qtr + 'lpn') - 0.50) * 0.07
        lpn = max(0.68, min(1.08, lpn))

        dc = 0.0 if _u01(qtr + 'cp') < 0.28 else (_u01(qtr + 'c') - 0.50) * 3.6
        dc += ep.get('census', 0.0)
        target_c = 90.0 if year < 2021 else (88.0 if year < 2024 else 94.0)
        census = max(82.0, min(102.0, census + dc + (target_c - census) * 0.18))

        if qtr in _EPISODES and 'contract' in ep:
            contract = max(0.4, ep['contract'])
        elif _u01(qtr + 'k') < 0.10:
            contract = 0.6 + _u01(qtr + 'kv') * 3.2
        else:
            contract = 0.5 + _u01(qtr + 'kb') * 2.0

        rows.append(
            _metric_row(
                census=census,
                total_hprd=total,
                rn_hprd=rn,
                lpn_hprd=lpn,
                contract_pct=contract,
            )
        )
    return rows


def _story_for_quarters(quarters: list[str]) -> list[dict[str, float]]:
    n = len(quarters)
    tail_n = len(_TAIL_STORY)
    if n < tail_n:
        return [dict(row) for row in _TAIL_STORY[-n:]]
    head = _pre_tail_stories(quarters[:-tail_n])
    tail = [dict(row) for row in _TAIL_STORY]
    return head + tail


def load_sunny_pastures_provider(canonical_quarter: str | None = None) -> DemoProviderPayload:
    """Build facility_df + provider_info_row for the public provider renderer.

    Verified from: facility_provider_indexes.REQUIRED_PROVIDER_DF_CSV_COLUMNS
    plus Nurse_Care_HPRD / RN_Care_HPRD / LPN_Care_HPRD / COUNTY_NAME / PROVNAME
    read by generate_provider_page_html and _provider_charts_chartjs_data.
    Real FL pages typically span 2017Q1 through the canonical quarter (~37 rows).
    """
    import pandas as pd

    quarters = quarters_ending_at(canonical_quarter)
    if len(quarters) < 8:
        quarters = quarters_ending_at(_DEFAULT_ANCHOR_QUARTER)
    latest_q = quarters[-1]
    stories = _story_for_quarters(quarters)
    rows = []
    for qtr, story in zip(quarters, stories):
        rows.append(
            {
                'PROVNUM': SUNNY_PASTURES_ID,
                'CY_Qtr': qtr,
                'PROVNAME': 'SUNNY PASTURES',
                'STATE': 'FL',
                'COUNTY_NAME': 'Miami-Dade',
                'Total_Nurse_HPRD': story['total_hprd'],
                'RN_HPRD': story['rn_hprd'],
                'LPN_HPRD': story['lpn_hprd'],
                'Nurse_Assistant_HPRD': story['na_hprd'],
                'Nurse_Care_HPRD': story['nurse_care_hprd'],
                'RN_Care_HPRD': story['rn_care_hprd'],
                'LPN_Care_HPRD': story['lpn_care_hprd'],
                'Contract_Percentage': story['contract_pct'],
                'avg_daily_census': story['census'],
            }
        )
    latest = stories[-1]
    provider_info_row: dict[str, Any] = {
        'is_demo': True,
        'demo_page_path': SUNNY_PASTURES_PATH,
        'ccn': SUNNY_PASTURES_ID,
        'provider_name': SUNNY_PASTURES_NAME,
        'city': 'Miami',
        'state': 'FL',
        'ownership_type': 'For profit - Corporation',
        'entity_id': None,
        'entity_name': '',
        'overall_rating': 2,
        'staffing_rating': 2,
        'health_inspection_rating': 2,
        'qm_rating': 4,
        'quality_measure_rating': 4,
        'abuse_icon': '',
        'has_abuse_icon': '',
        'sff_status': '',
        'certified_beds': 120,
        'number_of_certified_beds': 120,
        'avg_residents_per_day': latest['census'],
        'urban': 'Urban',
        'CY_Qtr': latest_q,
        'case_mix_total_nurse_hrs_per_resident_per_day': 3.82,
        'case_mix_rn_hrs_per_resident_per_day': 0.61,
        'case_mix_lpn_hrs_per_resident_per_day': 0.87,
        'case_mix_na_hrs_per_resident_per_day': 2.34,
        'nursing_case_mix_index': 1.27,
        'nursing_case_mix_index_ratio': 1.08,
        'staffing_rating_footnote': '',
        'reported_staffing_footnote': '',
    }
    return DemoProviderPayload(
        provider_id=SUNNY_PASTURES_ID,
        facility_df=pd.DataFrame(rows),
        provider_info_row=provider_info_row,
    )
