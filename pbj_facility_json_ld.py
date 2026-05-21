"""Facility page JSON-LD — generated from the same quarterly rows as the public provider page."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    pd = None  # type: ignore[assignment]
    HAS_PANDAS = False


def _quarter_sort_key(quarter_label: str) -> tuple[int, int]:
    s = str(quarter_label or '').strip()
    m = re.match(r'Q([1-4])\s+(\d{4})', s, re.I)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.match(r'(\d{4})Q([1-4])', s, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (0, 0)


def _row_float(row: Mapping[str, Any], key: str) -> float | None:
    if not hasattr(row, 'get'):
        return None
    v = row.get(key)
    if v is None or (HAS_PANDAS and isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _star_int(raw: Any) -> int | None:
    if raw is None or (HAS_PANDAS and isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        n = int(round(float(raw)))
        return n if 1 <= n <= 5 else None
    except (TypeError, ValueError):
        return None


def _turnover_pct_display(raw: Any) -> str | None:
    if raw is None or (HAS_PANDAS and isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        return f'{float(raw):.1f}'
    except (TypeError, ValueError):
        s = str(raw).strip()
        return s if s else None


def build_facility_quarter_json_ld_properties(
    facility_df,
    *,
    format_quarter_display,
    format_metric_value,
    provider_info_for_quarter=None,
    ccn: str = '',
    latest_raw_quarter: str = '',
    max_quarters: int = 4,
) -> list[dict[str, Any]]:
    """
    Last N PBJ quarters as schema.org PropertyValue entries.
    Uses facility_quarterly_metrics rows (same source as charts/CSV trends).
    CMS stars and turnover are added only for the latest PBJ quarter when Provider Info aligns.
    """
    if not HAS_PANDAS or facility_df is None or facility_df.empty:
        return []

    try:
        sorted_df = facility_df.sort_values('CY_Qtr')
    except Exception:
        sorted_df = facility_df

    tail = sorted_df.tail(max_quarters)
    props: list[dict[str, Any]] = []
    latest_raw = (latest_raw_quarter or '').strip()

    for _, row in tail.iterrows():
        q_raw = str(row.get('CY_Qtr', '') or '').strip()
        if not q_raw:
            continue
        q_disp = format_quarter_display(q_raw)
        if not q_disp or q_disp == 'N/A':
            continue

        total = format_metric_value(
            _row_float(row, 'Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A'
        )
        rn = format_metric_value(_row_float(row, 'RN_HPRD'), 'RN_HPRD', 'N/A')
        contract_raw = _row_float(row, 'Contract_Percentage')
        contract = (
            format_metric_value(contract_raw, 'Contract_Percentage', 'N/A')
            if contract_raw is not None
            else None
        )

        parts = [f'total nurse HPRD {total}', f'RN HPRD {rn}']
        if contract and contract != 'N/A':
            parts.append(f'contract staff {contract}%')

        if latest_raw and q_raw == latest_raw and provider_info_for_quarter and ccn:
            pi = provider_info_for_quarter(ccn, q_raw) if callable(provider_info_for_quarter) else {}
            if isinstance(pi, dict):
                overall = _star_int(pi.get('overall_rating'))
                staffing = _star_int(pi.get('staffing_rating'))
                if overall is not None:
                    parts.append(f'CMS overall Five-Star {overall} of 5')
                if staffing is not None:
                    parts.append(f'CMS staffing Five-Star {staffing} of 5')
                for key, label in (
                    ('total_nursing_staff_turnover', 'CMS total nursing staff turnover'),
                    ('registered_nurse_turnover', 'CMS RN turnover'),
                ):
                    tv = _turnover_pct_display(pi.get(key))
                    if tv and tv != 'N/A':
                        parts.append(f'{label} {tv}%')

        props.append(
            {
                '@type': 'PropertyValue',
                'propertyID': f'CMS PBJ quarter {q_disp}',
                'name': f'PBJ staffing ({q_disp})',
                'value': '; '.join(parts),
                'unitText': 'hours per resident day (HPRD) where applicable',
            }
        )

    return props
