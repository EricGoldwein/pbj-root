"""Facility page JSON-LD — same quarterly rows and page context as the public provider page."""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Mapping, Sequence

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
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clean_metric_display(val: str | None) -> str | None:
    s = (val or '').strip()
    if not s or s in ('—', 'N/A', 'n/a', '-'):
        return None
    return s


def build_facility_quarter_json_ld_properties(
    facility_df,
    *,
    format_quarter_display,
    format_metric_value,
    census_display_for_row: Callable[[Any], str | None] | None = None,
    max_quarters: int = 4,
) -> list[dict[str, Any]]:
    """
    Last N PBJ quarters as schema.org PropertyValue entries.
    Uses facility_quarterly_metrics rows only (same source as charts/CSV trends).
    """
    if not HAS_PANDAS or facility_df is None or facility_df.empty:
        return []

    try:
        sorted_df = facility_df.sort_values('CY_Qtr')
    except Exception:
        sorted_df = facility_df

    tail = sorted_df.tail(max_quarters)
    props: list[dict[str, Any]] = []

    for _, row in tail.iterrows():
        q_raw = str(row.get('CY_Qtr', '') or '').strip()
        if not q_raw:
            continue
        q_disp = format_quarter_display(q_raw)
        if not q_disp or q_disp == 'N/A':
            continue

        parts: list[str] = []
        if census_display_for_row:
            census = _clean_metric_display(census_display_for_row(row))
            if census:
                parts.append(f'average resident census {census}')

        total = _clean_metric_display(
            format_metric_value(_row_float(row, 'Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')
        )
        rn = _clean_metric_display(
            format_metric_value(_row_float(row, 'RN_HPRD'), 'RN_HPRD', 'N/A')
        )
        na_raw = _row_float(row, 'Nurse_Assistant_HPRD')
        na = _clean_metric_display(
            format_metric_value(na_raw, 'Nurse_Assistant_HPRD', 'N/A') if na_raw is not None else None
        )
        contract_raw = _row_float(row, 'Contract_Percentage')
        contract = (
            _clean_metric_display(
                format_metric_value(contract_raw, 'Contract_Percentage', 'N/A')
            )
            if contract_raw is not None
            else None
        )

        if total:
            parts.append(f'total nurse HPRD {total}')
        if rn:
            parts.append(f'RN HPRD {rn}')
        if na:
            # Nurse_Assistant_HPRD = CMS PBJ nurse aide bucket (CNA + NAtrn + MedAide), not RN/LPN.
            parts.append(f'nurse aide HPRD {na}')
        if contract:
            parts.append(f'contract staff {contract}%')

        if not parts:
            continue

        props.append(
            {
                '@type': 'PropertyValue',
                'propertyID': f'CMS PBJ quarter {q_disp}',
                'name': f'PBJ staffing ({q_disp})',
                'value': '; '.join(parts),
                'unitText': 'CMS Payroll-Based Journal quarterly staffing',
            }
        )

    return props


def build_facility_location_json_ld_properties(
    *,
    ccn: str = '',
    city: str = '',
    county: str = '',
    state_code: str = '',
    state_name: str = '',
) -> list[dict[str, Any]]:
    """CCN and geography — listed before quarterly PBJ rows."""
    props: list[dict[str, Any]] = []

    norm_ccn = (ccn or '').strip().zfill(6) if (ccn or '').strip() else ''
    if norm_ccn:
        props.append(
            {
                '@type': 'PropertyValue',
                'propertyID': 'CMS CCN',
                'name': 'CMS Certification Number (CCN)',
                'value': norm_ccn,
            }
        )

    city_s = (city or '').strip()
    if city_s and city_s != '—':
        props.append({'@type': 'PropertyValue', 'name': 'City', 'value': city_s})

    county_s = (county or '').strip()
    if county_s and county_s not in ('—', 'N/A', 'n/a'):
        props.append({'@type': 'PropertyValue', 'name': 'County', 'value': county_s})

    st_code = (state_code or '').strip().upper()[:2]
    st_name = (state_name or '').strip()
    if st_code:
        props.append(
            {
                '@type': 'PropertyValue',
                'name': 'State',
                'value': st_name if st_name else st_code,
            }
        )

    return props


def build_facility_supplemental_json_ld_properties(
    *,
    facility_flags: Sequence[str] | None = None,
    latest_cms_ratings: str = '',
    associated_entities: Sequence[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Flags, CMS stars, and entity links — after quarterly PBJ rows."""
    props: list[dict[str, Any]] = []

    flags = [f.strip() for f in (facility_flags or []) if (f or '').strip()]
    if flags:
        props.append(
            {
                '@type': 'PropertyValue',
                'propertyID': 'PBJ320 facility flags',
                'name': 'PBJ320 facility flags',
                'value': '; '.join(flags),
            }
        )

    cms_ratings = (latest_cms_ratings or '').strip()
    if cms_ratings:
        props.append(
            {
                '@type': 'PropertyValue',
                'propertyID': 'CMS ratings latest',
                'name': 'Latest CMS ratings',
                'value': cms_ratings,
            }
        )

    entities = [
        (str(n).strip(), str(u).strip())
        for n, u in (associated_entities or [])
        if str(n).strip()
    ]
    if entities:
        value_parts = []
        for name, url in entities:
            if url:
                value_parts.append(f'{name} ({url})')
            else:
                value_parts.append(name)
        props.append(
            {
                '@type': 'PropertyValue',
                'name': 'Associated ownership entities',
                'value': '; '.join(value_parts),
            }
        )

    return props


def build_facility_level_json_ld_properties(
    *,
    ccn: str = '',
    city: str = '',
    county: str = '',
    state_code: str = '',
    state_name: str = '',
    facility_flags: Sequence[str] | None = None,
    latest_cms_provider_info: str = '',
    latest_cms_ratings: str = '',
    associated_entities: Sequence[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Location + supplemental (prefer explicit location/quarter/supplemental order in app.py)."""
    ratings = (latest_cms_ratings or latest_cms_provider_info or '').strip()
    return (
        build_facility_location_json_ld_properties(
            ccn=ccn,
            city=city,
            county=county,
            state_code=state_code,
            state_name=state_name,
        )
        + build_facility_supplemental_json_ld_properties(
            facility_flags=facility_flags,
            latest_cms_ratings=ratings,
            associated_entities=associated_entities,
        )
    )
