"""Regression tests for public staffing chart anomaly handling."""

import pandas as pd
import pytest

from utils.staffing_chart_anomalies import (
    apply_staffing_series_anomalies,
    is_staffing_hprd_anomaly,
)


def _load_facility_hprd_series(ccn: str) -> tuple[list[str], list, list]:
    df = pd.read_csv('facility_quarterly_metrics.csv', dtype={'PROVNUM': str})
    sub = df[df['PROVNUM'].str.zfill(6) == ccn].sort_values('CY_Qtr')
    quarters = sub['CY_Qtr'].astype(str).tolist()
    total = sub['Total_Nurse_HPRD'].tolist()
    direct = sub['Nurse_Care_HPRD'].tolist()
    return quarters, total, direct


def test_facility_056200_flags_2021q3_anomaly():
    quarters, total, direct = _load_facility_hprd_series('056200')
    idx = quarters.index('2021Q3')
    out = apply_staffing_series_anomalies(quarters, total, direct, ccn='056200')
    assert out['is_staffing_anomaly'][idx] is True
    assert out['chart_total'][idx] is None
    assert out['chart_direct'][idx] is None
    assert out['raw_total'][idx] == pytest.approx(0.083348, rel=1e-3)
    assert out['raw_direct'][idx] == pytest.approx(0.083348, rel=1e-3)
    assert out['anomaly_count'] == 1
    rec = out['anomalies'][0]
    assert rec['quarter'] == '2021Q3'
    assert rec['ccn'] == '056200'
    assert 'total_hprd below 0.25' in rec['anomaly_reason']


def test_facility_056200_chart_no_zero_plunge():
    quarters, total, direct = _load_facility_hprd_series('056200')
    out = apply_staffing_series_anomalies(quarters, total, direct, ccn='056200')
    plotted = [v for v in out['chart_total'] if v is not None]
    assert min(plotted) > 3.0
    assert 0.083 not in plotted


def test_low_but_legitimate_quarters_not_flagged():
    # 2022Q4 is lower-performing but not a data break for 056200.
    quarters, total, direct = _load_facility_hprd_series('056200')
    out = apply_staffing_series_anomalies(quarters, total, direct, ccn='056200')
    idx = quarters.index('2022Q4')
    assert out['is_staffing_anomaly'][idx] is False
    assert out['chart_total'][idx] == pytest.approx(3.893779, rel=1e-4)


def test_is_staffing_hprd_anomaly_rules():
    assert is_staffing_hprd_anomaly(0.08, 5.1, 5.3)[0] is True
    assert is_staffing_hprd_anomaly(3.9, 4.3, 4.4)[0] is False
    assert is_staffing_hprd_anomaly(None, 4.0, 4.1)[0] is False
    # Total charts no longer flag neighbor % dips alone (real quarters can move 20%+).
    assert is_staffing_hprd_anomaly(0.8, 4.0, 4.2, profile='total')[0] is False


def test_rn_direct_only_not_flagged_when_total_rn_healthy():
    """Seagate-style admin-heavy RN: total ~0.28 HPRD, direct ~0.08 — not a trend break."""
    quarters = ['2021Q3', '2021Q4', '2023Q1']
    total = [0.2757215944758318, 0.2840021984924622, 0.2281158742044178]
    direct = [0.0816848713119899, 0.0901950376884422, 0.0767012978909272]
    out = apply_staffing_series_anomalies(quarters, total, direct, ccn='335513', profile='rn')
    assert out['anomaly_count'] == 0
    assert all(v is not None for v in out['chart_total'])
    assert all(v is not None for v in out['chart_direct'])


def test_rn_stable_low_home_not_flagged_at_09():
    """Chronically ~0.09 RN HPRD is extreme but not a quarterly data break."""
    flagged, reason = is_staffing_hprd_anomaly(
        0.09, 0.088, 0.091, profile='rn', typical_level=0.09
    )
    assert flagged is False
    assert reason is None


def test_rn_abs_floor_still_catches_clear_break():
    flagged, reason = is_staffing_hprd_anomaly(0.07, 0.42, 0.44, profile='rn', typical_level=0.40)
    assert flagged is True
    assert 'below 0.08' in reason


def test_lpn_neighbor_rule_skipped_for_low_lpn_homes():
    # Typical LPN ~0.08 HPRD: neighbor dip should not trigger neighbor rule.
    assert is_staffing_hprd_anomaly(
        0.04, 0.10, 0.09, profile='lpn', typical_level=0.08
    )[0] is True  # still below abs 0.05
    assert is_staffing_hprd_anomaly(
        0.06, 0.10, 0.09, profile='lpn', typical_level=0.08
    )[0] is False
