"""Facility Snapshot signal adapter — progressive disclosure scaffolding (not wired to production).

Builds defensible PublicStaffingSignal dicts from existing PBJ320 data shapes. Does not
perform new calculations; formats and labels observations using public_metadata registries.

Verified from: public_metadata.py, staffing_screening_registry.py,
data/compliance/staffing_compliance_thresholds.json
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

import public_metadata as pm
from staffing_screening_registry import get_daily_screen_rule

EntityType = Literal['facility', 'state', 'entity']
Direction = Literal['above', 'below', 'near', 'at', 'not_applicable']
DataQuality = Literal['complete', 'partial', 'missing', 'insufficient_sample']


class SignalComparator(TypedDict, total=False):
    kind: Literal['threshold', 'peer_average', 'percentile', 'case_mix']
    threshold_id: str | None
    value: float | None
    label: str
    threshold_type: str | None


class SignalDepthLinks(TypedDict, total=False):
    patterns_anchor: str
    evidence_anchor: str


class PublicStaffingSignal(TypedDict, total=False):
    signal_id: str
    entity_type: EntityType
    entity_id: str
    metric_id: str
    observed_value: float | int | None
    observed_display: str
    period: str
    period_display: str
    comparator: SignalComparator
    direction: Direction
    display_label: str
    explanation: str
    methodology_ref: str
    source_type: str
    evidence_tier: str
    data_quality: DataQuality
    display_priority: int
    depth_links: SignalDepthLinks


def _metric_meta(metric_id: str) -> dict[str, Any]:
    return pm.metrics_by_id().get(metric_id) or {}


def _evidence_tier(metric_id: str) -> str:
    meta = _metric_meta(metric_id)
    return pm.evidence_tier_for_source_type(str(meta.get('source_type') or 'payroll_based'))


def _classify_direction(observed: float, comparator: float, *, band: float = 0.03) -> Direction:
    if comparator == 0:
        return 'not_applicable'
    ratio = observed / comparator
    if ratio > 1 + band:
        return 'above'
    if ratio < 1 - band:
        return 'below'
    return 'near'


def _signal_id(entity_type: EntityType, entity_id: str, metric_id: str, period: str) -> str:
    return f'{entity_type}:{entity_id}:{metric_id}:{period}'


def build_hprd_vs_state_average_signal(
    *,
    ccn: str,
    period: str,
    period_display: str,
    reported_total_hprd: float | None,
    state_average_hprd: float | None,
    state_name: str,
    observed_display: str,
    state_average_display: str,
) -> PublicStaffingSignal | None:
    """Quarterly total nurse HPRD vs state average (existing ±3% band)."""
    if reported_total_hprd is None or state_average_hprd is None:
        return None
    direction = _classify_direction(float(reported_total_hprd), float(state_average_hprd))
    meta = _metric_meta('total_nurse_hprd')
    dir_phrase = {
        'above': 'above',
        'below': 'below',
        'near': 'near',
        'at': 'at',
        'not_applicable': 'compared to',
    }.get(direction, 'compared to')
    explanation = (
        f'In {period_display}, reported total nurse staffing was {dir_phrase} '
        f'the {state_name} state average ({state_average_display} HPRD). '
        f'Source: CMS PBJ payroll; quarter-level average.'
    )
    return {
        'signal_id': _signal_id('facility', ccn, 'total_nurse_hprd', period),
        'entity_type': 'facility',
        'entity_id': ccn,
        'metric_id': 'total_nurse_hprd',
        'observed_value': reported_total_hprd,
        'observed_display': observed_display,
        'period': period,
        'period_display': period_display,
        'comparator': {
            'kind': 'peer_average',
            'threshold_id': None,
            'value': state_average_hprd,
            'label': f'{state_name} state average',
            'threshold_type': 'benchmark',
        },
        'direction': direction,
        'display_label': f'Total nurse HPRD · {period_display}',
        'explanation': explanation,
        'methodology_ref': 'total_nurse_hprd',
        'source_type': str(meta.get('source_type') or 'payroll_based'),
        'evidence_tier': _evidence_tier('total_nurse_hprd'),
        'data_quality': 'complete',
        'display_priority': 1,
        'depth_links': {
            'patterns_anchor': '#patterns-total-hprd',
            'evidence_anchor': '#evidence-metric-total_nurse_hprd',
        },
    }


def build_compliance_shortfall_signal(
    *,
    ccn: str,
    period: str,
    period_display: str,
    state_code: str,
    compliance_summary: dict[str, Any],
) -> PublicStaffingSignal | None:
    """Daily screen shortfall from staffing_compliance_bundle public summary."""
    if not compliance_summary:
        return None
    try:
        total_days = int(compliance_summary.get('total_days_reported') or 0)
        below = compliance_summary.get('below_state_min_days_count')
    except (TypeError, ValueError):
        return None
    if total_days <= 0 or below is None:
        return None
    n_below = int(below)
    if n_below <= 0:
        return None

    st = (state_code or compliance_summary.get('state') or '').strip().upper()[:2]
    th_raw = compliance_summary.get('state_min_threshold_used')
    th_label = str(compliance_summary.get('state_min_label') or '').strip()
    metric_used = str(compliance_summary.get('state_min_metric_used') or 'direct_care_hprd')
    try:
        th_f = float(th_raw) if th_raw is not None else None
    except (TypeError, ValueError):
        th_f = None
    th_display = th_label or (f'{th_f:g} HPRD' if th_f is not None else 'state reference')

    rule = get_daily_screen_rule(st)
    rule_label = th_label
    if rule and str(rule.get('metric_id') or '') == metric_used:
        rule_label = str(rule.get('public_label') or rule.get('summary_label') or rule_label)

    pct = round(100.0 * n_below / total_days, 1)
    meta = _metric_meta('threshold_shortfall_rate')
    ref_phrase = rule_label or th_display or f'{st} staffing reference'
    explanation = (
        f'{n_below} of {total_days} reported PBJ days ({pct}%) were below the '
        f'{ref_phrase}. '
        f'This is a payroll-based daily screen, not a legal finding.'
    )
    return {
        'signal_id': _signal_id('facility', ccn, 'threshold_shortfall_rate', period),
        'entity_type': 'facility',
        'entity_id': ccn,
        'metric_id': 'threshold_shortfall_rate',
        'observed_value': n_below,
        'observed_display': f'{n_below} of {total_days} days',
        'period': period,
        'period_display': period_display,
        'comparator': {
            'kind': 'threshold',
            'threshold_id': f'{st.lower()}_pbj_daily_screen',
            'value': th_f,
            'label': rule_label or th_display,
            'threshold_type': 'legal_minimum' if st == 'NY' else 'estimated_standard',
        },
        'direction': 'below',
        'display_label': f'Days below reference · {period_display}',
        'explanation': explanation,
        'methodology_ref': 'threshold_shortfall_rate',
        'source_type': str(meta.get('source_type') or 'pbj320_derived'),
        'evidence_tier': _evidence_tier('threshold_shortfall_rate'),
        'data_quality': 'complete' if total_days >= 30 else 'insufficient_sample',
        'display_priority': 3,
        'depth_links': {
            'patterns_anchor': '#patterns-total-hprd',
            'evidence_anchor': '#evidence-compliance-summary',
        },
    }


def build_facility_snapshot_signals(
    *,
    ccn: str,
    period: str,
    period_display: str,
    state_code: str,
    state_name: str,
    reported_total_hprd: float | None,
    state_average_hprd: float | None,
    observed_display: str,
    state_average_display: str,
    compliance_summary: dict[str, Any] | None = None,
    max_signals: int = 4,
) -> list[PublicStaffingSignal]:
    """Compose ordered Snapshot signals (2–4) for a facility page prototype."""
    signals: list[PublicStaffingSignal] = []

    hprd_sig = build_hprd_vs_state_average_signal(
        ccn=ccn,
        period=period,
        period_display=period_display,
        reported_total_hprd=reported_total_hprd,
        state_average_hprd=state_average_hprd,
        state_name=state_name,
        observed_display=observed_display,
        state_average_display=state_average_display,
    )
    if hprd_sig:
        signals.append(hprd_sig)

    if compliance_summary and state_code.upper() in ('NY', 'CT'):
        comp_sig = build_compliance_shortfall_signal(
            ccn=ccn,
            period=period,
            period_display=period_display,
            state_code=state_code,
            compliance_summary=compliance_summary,
        )
        if comp_sig:
            signals.append(comp_sig)

    signals.sort(key=lambda s: int(s.get('display_priority') or 99))
    return signals[:max_signals]
