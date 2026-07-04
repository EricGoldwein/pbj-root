"""Central registry: staffing metrics + state daily-screen rules (composed, not orphaned numbers).

Verified from: data/compliance/staffing_compliance_thresholds.json metric_definitions and
state_thresholds; MACPAC chart references are separate from daily-screen rules.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

ROOT = Path(__file__).resolve().parent
COMPLIANCE_THRESHOLDS_PATH = ROOT / 'data' / 'compliance' / 'staffing_compliance_thresholds.json'
MACPAC_STATE_STAFFING_URL = (
    'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
)

RuleType = Literal['statutory_minimum', 'benchmark', 'analytical_threshold']
Comparator = Literal['below']
ThresholdTypePublic = Literal['legal_minimum', 'benchmark', 'estimated_standard', 'proposed_standard']

RULE_TYPE_TO_PUBLIC_THRESHOLD_TYPE: dict[str, ThresholdTypePublic] = {
    'statutory_minimum': 'legal_minimum',
    'benchmark': 'benchmark',
    'analytical_threshold': 'estimated_standard',
}


class StaffingMetricDefinition(TypedDict, total=False):
    id: str
    label: str
    short_label: str
    numerator_description: str
    denominator_description: str
    included_roles: list[str]
    excluded_roles: list[str]
    methodology_text: str
    pbj_columns: list[str]


class StateStaffingRule(TypedDict, total=False):
    id: str
    state: str
    metric_id: str
    threshold: float
    comparator: Comparator
    rule_type: RuleType
    effective_date: str
    source_label: str
    source_url: str
    public_label: str
    public_methodology_text: str
    enabled: bool
    summary_label: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def load_compliance_config() -> dict[str, Any]:
    if not COMPLIANCE_THRESHOLDS_PATH.is_file():
        return {}
    return _read_json(COMPLIANCE_THRESHOLDS_PATH)


def clear_registry_cache() -> None:
    load_compliance_config.cache_clear()


def _metric_from_row(metric_id: str, row: dict[str, Any]) -> StaffingMetricDefinition:
    included = list(row.get('included_roles') or [])
    excluded = list(row.get('excluded_roles') or [])
    pbj_cols = list(row.get('pbj_columns') or [])
    if not included and pbj_cols:
        included = [c.replace('Hrs_', '') for c in pbj_cols]
    label = str(row.get('label') or row.get('short_label') or metric_id.replace('_', ' '))
    short_label = str(row.get('short_label') or label)
    num_desc = str(row.get('numerator_description') or row.get('description') or '').strip()
    den_desc = str(
        row.get('denominator_description')
        or 'MDS census for that day (facility-days with census > 0 only)'
    ).strip()
    methodology = str(row.get('methodology_text') or row.get('description') or '').strip()
    return {
        'id': metric_id,
        'label': label,
        'short_label': short_label,
        'numerator_description': num_desc,
        'denominator_description': den_desc,
        'included_roles': included,
        'excluded_roles': excluded,
        'methodology_text': methodology,
        'pbj_columns': pbj_cols,
    }


@lru_cache(maxsize=1)
def load_staffing_metric_definitions() -> dict[str, StaffingMetricDefinition]:
    cfg = load_compliance_config()
    out: dict[str, StaffingMetricDefinition] = {}
    for metric_id, row in (cfg.get('metric_definitions') or {}).items():
        if not isinstance(row, dict):
            continue
        out[str(metric_id)] = _metric_from_row(str(metric_id), row)
    return out


def get_staffing_metric(metric_id: str) -> StaffingMetricDefinition | None:
    return load_staffing_metric_definitions().get((metric_id or '').strip())


def _rule_from_row(row: dict[str, Any]) -> StateStaffingRule | None:
    state = str(row.get('state') or '').upper()[:2]
    if not state:
        return None
    metric_id = str(row.get('metric') or row.get('metric_id') or '').strip()
    if not metric_id:
        return None
    try:
        threshold = float(row['threshold'])
    except (KeyError, TypeError, ValueError):
        return None
    rule_id = str(row.get('id') or f'{state.lower()}_pbj_daily_screen')
    rule_type = str(row.get('rule_type') or 'analytical_threshold').strip()
    if rule_type not in RULE_TYPE_TO_PUBLIC_THRESHOLD_TYPE:
        rule_type = 'analytical_threshold'
    public_label = str(
        row.get('public_label')
        or row.get('label')
        or f'{state} daily staffing screen'
    ).strip()
    public_methodology = str(
        row.get('public_methodology_text') or row.get('notes') or ''
    ).strip()
    return {
        'id': rule_id,
        'state': state,
        'metric_id': metric_id,
        'threshold': threshold,
        'comparator': 'below',
        'rule_type': rule_type,  # type: ignore[typeddict-item]
        'effective_date': str(row.get('effective_date') or '').strip() or None,
        'source_label': str(row.get('source_label') or '').strip() or None,
        'source_url': str(row.get('source_url') or row.get('source_url_or_note') or '').strip() or None,
        'public_label': public_label,
        'public_methodology_text': public_methodology,
        'enabled': bool(row.get('enabled', True)),
        'summary_label': str(row.get('label') or public_label).strip(),
    }


@lru_cache(maxsize=1)
def load_state_staffing_rules() -> list[StateStaffingRule]:
    cfg = load_compliance_config()
    rules: list[StateStaffingRule] = []
    for row in cfg.get('state_thresholds') or []:
        if not isinstance(row, dict):
            continue
        rule = _rule_from_row(row)
        if rule:
            rules.append(rule)
    return rules


def daily_screen_rules(*, enabled_only: bool = True) -> list[StateStaffingRule]:
    rules = load_state_staffing_rules()
    if enabled_only:
        rules = [r for r in rules if r.get('enabled', True)]
    return sorted(rules, key=lambda r: (r.get('state') or '', r.get('id') or ''))


def get_daily_screen_rule(state_code: str) -> StateStaffingRule | None:
    st = (state_code or '').strip().upper()[:2]
    for rule in daily_screen_rules():
        if rule.get('state') == st:
            return rule
    return None


def format_threshold_value(threshold: float) -> str:
    """Display threshold without float artifacts (3.5 -> 3.50)."""
    if abs(threshold * 100 - round(threshold * 100)) < 1e-9:
        return f'{threshold:.2f}'
    return f'{threshold:g}'


def compose_rule_public_summary(rule: StateStaffingRule) -> str:
    """One-sentence public summary for a state daily-screen rule."""
    metric = get_staffing_metric(str(rule.get('metric_id') or ''))
    th_disp = format_threshold_value(float(rule.get('threshold') or 0))
    metric_label = (metric or {}).get('short_label') or (metric or {}).get('label') or 'HPRD'
    state = rule.get('state') or ''
    rule_type = rule.get('rule_type') or 'analytical_threshold'
    if rule_type == 'statutory_minimum':
        return (
            f'<strong>{state}</strong> screens use the state&rsquo;s '
            f'<strong>{th_disp}</strong> <strong>{metric_label}</strong> minimum. '
            f'{_metric_exclusion_phrase(metric)}'
        )
    macpac_link = (
        f'<a href="{MACPAC_STATE_STAFFING_URL}" rel="noopener noreferrer" target="_blank">MACPAC</a>'
    )
    return (
        f'<strong>{state}</strong> screens use <strong>{th_disp}</strong> '
        f'<strong>{metric_label}</strong>, based on {macpac_link}&rsquo;s total estimated '
        f'staffing requirement ({_metric_inclusion_phrase(metric)}).'
    )


def _metric_exclusion_phrase(metric: StaffingMetricDefinition | None) -> str:
    if not metric:
        return 'Direct-care staffing excludes administrative nursing and director-of-nursing hours where applicable.'
    excluded = metric.get('excluded_roles') or []
    if excluded:
        excl = ', '.join(excluded[:-1]) + (' and ' + excluded[-1] if len(excluded) > 1 else excluded[0])
        return (
            f'{metric.get("short_label") or "Direct-care staffing"} is '
            f'{metric.get("numerator_description") or "mapped PBJ nursing hours"} '
            f'divided by census; {excl} are excluded.'
        )
    return str(metric.get('methodology_text') or '').strip()


def _metric_inclusion_phrase(metric: StaffingMetricDefinition | None) -> str:
    if not metric:
        return 'all reported nursing roles including admin/DON, &divide; census'
    num = metric.get('numerator_description') or metric.get('label') or 'reported nursing hours'
    den = metric.get('denominator_description') or 'census'
    return f'{num} &divide; {den}'


def compose_data_sources_pbj_daily_staffing_html() -> str:
    """Full <li id="pbj-daily-staffing"> inner HTML for /data-sources."""
    rules = daily_screen_rules()
    state_bits = [compose_rule_public_summary(r) for r in rules]
    state_paragraph = ' '.join(state_bits)
    if not state_paragraph:
        state_paragraph = (
            'State-specific daily staffing screens are configured in '
            '<code>data/compliance/staffing_compliance_thresholds.json</code>.'
        )
    rn_note = (
        'PBJ320 also counts days with <strong>zero total RN hours</strong> or '
        '<strong>total RN hours under 8</strong> (RN + RN administrator + DON; '
        'facility-wide hours that day, not RN-HPRD).'
    )
    closing = (
        'PBJ320 reports PBJ-based days below threshold; it does not make legal findings '
        'of violation or noncompliance. Premium dashboards may list individual calendar '
        'dates; the free site shows quarter-level counts only.'
    )
    return (
        '<strong>PBJ daily staffing flags</strong> (facility pages, when data is available): '
        'PBJ320 screens reported daily staffing against state-specific thresholds '
        '(days with census &gt; 0). Each rule pairs a defined metric with a threshold: '
        f'{state_paragraph} '
        f'{rn_note} {closing}'
    )


def rule_to_public_threshold_entry(rule: StateStaffingRule) -> dict[str, Any]:
    """Map a daily-screen rule into public_metadata threshold registry shape."""
    state = str(rule.get('state') or '').upper()[:2]
    metric_id = str(rule.get('metric_id') or 'total_nurse_hprd')
    rule_type = str(rule.get('rule_type') or 'analytical_threshold')
    threshold_type = RULE_TYPE_TO_PUBLIC_THRESHOLD_TYPE.get(rule_type, 'estimated_standard')
    tid = f'{state.lower()}_pbj_daily_screen'
    src = str(rule.get('source_url') or '').strip() or 'data/compliance/staffing_compliance_thresholds.json'
    return {
        'state': state,
        'threshold_id': tid,
        'public_label': str(rule.get('public_label') or rule.get('summary_label') or tid),
        'value': float(rule.get('threshold') or 0),
        'unit': metric_id,
        'metric_id': metric_id,
        'threshold_type': threshold_type,
        'rule_type': rule_type,
        'short_caveat': f'Used for PBJ320 daily staffing screening on {state} facility pages.',
        'methodology_caveat': str(rule.get('public_methodology_text') or ''),
        'source_url_or_note': src,
        'show_public': True,
    }


def validate_daily_screen_rules() -> list[str]:
    """Structural checks: every rule references a defined metric; NY must not use 3.56 total."""
    issues: list[str] = []
    metrics = load_staffing_metric_definitions()
    for rule in daily_screen_rules(enabled_only=False):
        mid = str(rule.get('metric_id') or '')
        if mid not in metrics:
            issues.append(f'rule {rule.get("id")}: unknown metric_id {mid!r}')
        state = rule.get('state') or ''
        th = float(rule.get('threshold') or 0)
        if state == 'NY':
            if mid != 'direct_care_hprd':
                issues.append(f'NY daily screen must use direct_care_hprd, not {mid!r}')
            if abs(th - 3.5) > 0.001:
                issues.append(f'NY daily screen threshold must be 3.50, got {th}')
            if abs(th - 3.56) < 0.001:
                issues.append('NY daily screen must not use MACPAC 3.56 as screening threshold')
        if state == 'CT' and mid != 'total_nurse_hprd':
            issues.append(f'CT daily screen expected total_nurse_hprd, got {mid!r}')
    overrides_path = ROOT / 'data' / 'public' / 'public_threshold_overrides.json'
    if overrides_path.is_file():
        try:
            overrides = _read_json(overrides_path).get('overrides') or []
        except (OSError, json.JSONDecodeError):
            overrides = []
        for row in overrides:
            if not isinstance(row, dict):
                continue
            tid = str(row.get('threshold_id') or '')
            if tid == 'ny_pbj_daily_screen_macpac' and row.get('show_public', True):
                issues.append(
                    'public_threshold_overrides.json: remove or deprecate ny_pbj_daily_screen_macpac '
                    '(MACPAC 3.56 is chart reference only, not NY daily screen)'
                )
    return issues
