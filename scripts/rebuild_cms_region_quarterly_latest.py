#!/usr/bin/env python3
"""Rebuild cms_region_quarterly_metrics.csv for the latest quarter in state_quarterly_metrics.csv.

Uses state aggregates for weighted HPRD and facility_quarterly_metrics.csv for medians.
Does not require facility_lite_metrics.csv (which may lag the canonical quarter).
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def _median(values, exclude_zeros=False):
    if exclude_zeros:
        vals = sorted(v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v)) and v > 0)
    else:
        vals = sorted(v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v)))
    if not vals:
        return np.nan
    mid = len(vals) // 2
    if len(vals) % 2 == 0:
        return (vals[mid - 1] + vals[mid]) / 2
    return vals[mid]


def main() -> int:
    state_df = pd.read_csv('state_quarterly_metrics.csv', low_memory=False)
    region_map = pd.read_csv('cms_region_state_mapping.csv')
    quarters = sorted(state_df['CY_Qtr'].dropna().astype(str).unique().tolist())
    if not quarters:
        print('ERROR: no quarters in state_quarterly_metrics.csv', file=sys.stderr)
        return 1
    # Wrapped needs current + prior slots (q2 + q1); emit the last two quarters when available.
    target_quarters = quarters[-2:] if len(quarters) >= 2 else quarters[-1:]
    print(f'Rebuilding cms_region_quarterly_metrics.csv for {target_quarters}')

    state_to_region = {}
    for _, row in region_map.iterrows():
        state_abbr = str(row['State_Code']).strip().upper()
        state_to_region[state_abbr] = {
            'regionNumber': int(row['CMS_Region_Number']),
            'regionName': str(row['CMS_Region_Name']).strip(),
            'regionFull': str(row['CMS_Region_Full']).strip(),
        }

    region_states = defaultdict(list)
    region_info_map = {}
    for state_abbr, info in state_to_region.items():
        region_states[info['regionFull']].append(state_abbr)
        region_info_map[info['regionFull']] = info

    usecols = [
        'STATE', 'CY_Qtr', 'Total_Nurse_HPRD', 'RN_HPRD', 'Nurse_Care_HPRD',
        'RN_Care_HPRD', 'Nurse_Assistant_HPRD', 'Contract_Percentage',
    ]
    fac_all = pd.read_csv(
        'facility_quarterly_metrics.csv',
        usecols=lambda c: c in usecols or c in ('STATE', 'CY_Qtr'),
        low_memory=False,
        dtype={'STATE': str, 'CY_Qtr': str},
    )
    fac_all['STATE'] = fac_all['STATE'].astype(str).str.strip().str.upper()
    fac_all = fac_all[fac_all['CY_Qtr'].astype(str).isin(target_quarters)]
    print(f'Facility rows for {target_quarters}: {len(fac_all):,}')

    rows = []
    for quarter in target_quarters:
        print(f'  quarter {quarter}...')
        fac = fac_all[fac_all['CY_Qtr'].astype(str) == quarter]
        quarter_state = state_df[state_df['CY_Qtr'].astype(str) == quarter].copy()
        quarter_state['STATE'] = quarter_state['STATE'].astype(str).str.strip().str.upper()

        for region_full, states in region_states.items():
            region_state_data = quarter_state[quarter_state['STATE'].isin(states)]
            if region_state_data.empty:
                continue
            region_facilities = fac[fac['STATE'].isin(states)]
            info = region_info_map[region_full]

            facility_count = float(region_state_data['facility_count'].sum()) if 'facility_count' in region_state_data else float(len(region_facilities))
            total_resident_days = float(region_state_data['total_resident_days'].sum()) if 'total_resident_days' in region_state_data else 0.0
            avg_days_reported = float(region_state_data['avg_days_reported'].max()) if 'avg_days_reported' in region_state_data else 0.0
            avg_daily_census = (
                total_resident_days / (facility_count * avg_days_reported)
                if facility_count > 0 and avg_days_reported > 0 else 0.0
            )
            MDScensus = float(region_state_data['MDScensus'].sum()) if 'MDScensus' in region_state_data.columns else 0.0

            total_nurse_hours = float((region_state_data['Total_Nurse_HPRD'] * region_state_data['total_resident_days']).sum())
            total_rn_hours = float((region_state_data['RN_HPRD'] * region_state_data['total_resident_days']).sum())
            total_nurse_care_hours = float((region_state_data['Nurse_Care_HPRD'] * region_state_data['total_resident_days']).sum())
            total_rn_care_hours = float((region_state_data['RN_Care_HPRD'] * region_state_data['total_resident_days']).sum())
            total_nurse_assistant_hours = float((region_state_data['Nurse_Assistant_HPRD'] * region_state_data['total_resident_days']).sum())
            total_contract_hours = (
                float(region_state_data['Total_Contract_Hours'].sum())
                if 'Total_Contract_Hours' in region_state_data.columns else 0.0
            )

            def _hprd(hours):
                return hours / total_resident_days if total_resident_days > 0 else np.nan

            total_nurse_hprd = _hprd(total_nurse_hours)
            rn_hprd = _hprd(total_rn_hours)
            nurse_care_hprd = _hprd(total_nurse_care_hours)
            rn_care_hprd = _hprd(total_rn_care_hours)
            nurse_assistant_hprd = _hprd(total_nurse_assistant_hours)
            contract_percentage = (
                total_contract_hours / total_nurse_hours * 100 if total_nurse_hours > 0 else np.nan
            )
            direct_care_percentage = (
                total_nurse_care_hours / total_nurse_hours * 100 if total_nurse_hours > 0 else np.nan
            )
            total_rn_percentage = (
                total_rn_hours / total_nurse_hours * 100 if total_nurse_hours > 0 else np.nan
            )
            nurse_aide_percentage = (
                total_nurse_assistant_hours / total_nurse_hours * 100 if total_nurse_hours > 0 else np.nan
            )

            def _col_list(col):
                if col not in region_facilities.columns or region_facilities.empty:
                    return []
                return pd.to_numeric(region_facilities[col], errors='coerce').dropna().tolist()

            medians = {
                'Total_Nurse_HPRD_Median': _median(_col_list('Total_Nurse_HPRD'), exclude_zeros=True),
                'RN_HPRD_Median': _median(_col_list('RN_HPRD'), exclude_zeros=True),
                'Nurse_Care_HPRD_Median': _median(_col_list('Nurse_Care_HPRD'), exclude_zeros=True),
                'RN_Care_HPRD_Median': _median(_col_list('RN_Care_HPRD'), exclude_zeros=True),
                'Nurse_Assistant_HPRD_Median': _median(_col_list('Nurse_Assistant_HPRD'), exclude_zeros=True),
                'Contract_Percentage_Median': _median(_col_list('Contract_Percentage'), exclude_zeros=False),
            }

            # LPN columns when present on state aggregates
            lpn_hprd = np.nan
            lpn_care_hprd = np.nan
            if 'LPN_HPRD' in region_state_data.columns and total_resident_days > 0:
                lpn_hprd = float((region_state_data['LPN_HPRD'] * region_state_data['total_resident_days']).sum() / total_resident_days)
            if 'LPN_Care_HPRD' in region_state_data.columns and total_resident_days > 0:
                lpn_care_hprd = float((region_state_data['LPN_Care_HPRD'] * region_state_data['total_resident_days']).sum() / total_resident_days)

            rows.append({
                'REGION': region_full,
                'REGION_NUMBER': info['regionNumber'],
                'REGION_NAME': info['regionName'],
                'CY_Qtr': quarter,
                'facility_count': facility_count,
                'avg_days_reported': avg_days_reported,
                'total_resident_days': total_resident_days,
                'avg_daily_census': avg_daily_census,
                'MDScensus': MDScensus,
                'Total_Nurse_Hours': total_nurse_hours,
                'Total_RN_Hours': total_rn_hours,
                'Total_Nurse_Care_Hours': total_nurse_care_hours,
                'Total_RN_Care_Hours': total_rn_care_hours,
                'Total_Nurse_Assistant_Hours': total_nurse_assistant_hours,
                'Total_Contract_Hours': total_contract_hours,
                'Total_Nurse_HPRD': total_nurse_hprd,
                'RN_HPRD': rn_hprd,
                'Nurse_Care_HPRD': nurse_care_hprd,
                'RN_Care_HPRD': rn_care_hprd,
                'Nurse_Assistant_HPRD': nurse_assistant_hprd,
                'Contract_Percentage': contract_percentage,
                'Direct_Care_Percentage': direct_care_percentage,
                'Total_RN_Percentage': total_rn_percentage,
                'Nurse_Aide_Percentage': nurse_aide_percentage,
                'LPN_HPRD': lpn_hprd,
                'LPN_Care_HPRD': lpn_care_hprd,
                **medians,
            })

    if not rows:
        print('ERROR: no region rows produced', file=sys.stderr)
        return 1

    out = pd.DataFrame(rows)
    out_path = 'cms_region_quarterly_metrics.csv'
    out.to_csv(out_path, index=False)
    print(f'Wrote {len(out)} rows to {out_path} for CY_Qtr in {sorted(out["CY_Qtr"].unique().tolist())}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
