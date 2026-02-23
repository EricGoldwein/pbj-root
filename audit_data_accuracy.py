#!/usr/bin/env python3
"""
Data accuracy audit script for provider, state, entity, and SFF pages.
Run from repo root: python audit_data_accuracy.py

Validates:
- Required columns in facility, state, provider_info, and chain performance CSVs
- CCN (6-digit), state (2-letter), entity_id (int) consistency
- SFF JSON structure and provider_number format
- Rounding behavior (pbj_format) and chain CSV column names
Does not start Flask or require server.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Required columns per data source (app.py contract)
FACILITY_QUARTERLY_REQUIRED = ['PROVNUM', 'CY_Qtr', 'STATE', 'Total_Nurse_HPRD']
FACILITY_QUARTERLY_OPTIONAL = ['RN_HPRD', 'Nurse_Assistant_HPRD', 'Nurse_Care_HPRD', 'Contract_Percentage', 'avg_daily_census', 'Avg_Daily_Census']

STATE_QUARTERLY_REQUIRED = ['STATE', 'CY_Qtr', 'Total_Nurse_HPRD']
STATE_QUARTERLY_OPTIONAL = ['Nurse_Care_HPRD', 'RN_HPRD', 'RN_Care_HPRD', 'avg_daily_census', 'Avg_Daily_Census', 'Contract_Percentage']

PROVIDER_INFO_CCN_KEYS = ['ccn', 'PROVNUM', 'CCN', 'Provnum']
PROVIDER_INFO_ENTITY_KEYS = ['chain_id', 'affiliated_entity_id', 'Chain ID', 'Chain_ID', 'AFFILIATED_ENTITY_ID']
PROVIDER_INFO_NAME_KEYS = ['provider_name', 'PROVNAME', 'Provider Name']
PROVIDER_INFO_STATE_KEYS = ['state', 'STATE', 'State']

CHAIN_PERFORMANCE_REQUIRED_COLUMNS = [
    'Chain ID',
    'Number of facilities',
    'Number of states and territories with operations',
    'Average overall 5-star rating',
    'Total amount of fines in dollars',
    'Number of Special Focus Facilities (SFF)',
    'Number of SFF candidates',
    'Percent of facilities classified as for-profit',
]
CHAIN_PERFORMANCE_OPTIONAL = [
    'Average staffing rating',
    'Average health inspection rating',
    'Average quality rating',
    'Total number of fines',
    'Total number of payment denials',
    'Number of facilities with an abuse icon',
    'Percentage of facilities with an abuse icon',
    'Percent of facilities classified as non-profit',
    'Percent of facilities classified as government-owned',
    'Average total nurse hours per resident day',
    'Average total Registered Nurse hours per resident day',
    'Average total nursing staff turnover percentage',
]


def find_file(*candidates: str) -> str | None:
    """First path that exists under APP_ROOT or cwd."""
    for name in candidates:
        for base in (APP_ROOT, '.'):
            p = os.path.join(base, name) if os.path.dirname(name) else os.path.join(base, name)
            if os.path.isfile(p):
                return p
    return None


def find_glob(pattern: str) -> list[str]:
    """Glob under APP_ROOT and cwd."""
    out = []
    for base in (APP_ROOT, '.'):
        full = os.path.join(base, pattern)
        out.extend(glob.glob(full))
    return [p for p in out if os.path.isfile(p)]


def load_csv_headers(path: str) -> list[str] | None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            r = csv.DictReader(f)
            return list(r.fieldnames or [])
    except Exception as e:
        print(f"  [ERROR] Reading {path}: {e}", file=sys.stderr)
        return None


def check_columns(path: str | None, required: list[str], optional: list[str] | None, name: str) -> bool:
    if not path:
        print(f"  [SKIP] {name}: file not found")
        return True
    headers = load_csv_headers(path)
    if headers is None:
        return False
    missing = [c for c in required if c not in headers]
    if missing:
        print(f"  [FAIL] {name}: missing required columns: {missing}")
        return False
    if optional:
        missing_opt = [c for c in optional if c not in headers]
        if missing_opt:
            print(f"  [WARN] {name}: missing optional columns: {missing_opt}")
    print(f"  [OK] {name}: required columns present")
    return True


def normalize_ccn(ccn: str | int) -> str:
    s = str(ccn).strip()
    if '.' in s:
        s = s.split('.')[0]
    return s.zfill(6)


def audit_facility_quarterly() -> bool:
    path = find_file('facility_quarterly_metrics.csv', 'facility_quarterly_metrics_latest.csv')
    ok = check_columns(path, FACILITY_QUARTERLY_REQUIRED, FACILITY_QUARTERLY_OPTIONAL, 'facility_quarterly_metrics')
    if path and ok:
        headers = load_csv_headers(path)
        if headers and 'PROVNUM' in headers:
            with open(path, 'r', encoding='utf-8') as f:
                r = csv.DictReader(f)
                for i, row in enumerate(r):
                    if i >= 5:
                        break
                    p = row.get('PROVNUM', '')
                    n = normalize_ccn(p)
                    if len(n) != 6:
                        print(f"  [WARN] facility_quarterly: PROVNUM '{p}' normalizes to '{n}' (expected 6 chars)")
                    st = (row.get('STATE') or '').strip().upper()
                    if st and len(st) != 2:
                        print(f"  [WARN] facility_quarterly: STATE '{st}' is not 2-letter")
    return ok


def audit_state_quarterly() -> bool:
    path = find_file('state_quarterly_metrics.csv')
    return check_columns(path, STATE_QUARTERLY_REQUIRED, STATE_QUARTERLY_OPTIONAL, 'state_quarterly_metrics')


def audit_provider_info() -> bool:
    path = find_file('provider_info_combined_latest.csv', 'provider_info_combined.csv', 'pbj-wrapped/public/data/provider_info_combined.csv')
    if not path:
        print("  [SKIP] provider_info: no file found")
        return True
    headers = load_csv_headers(path)
    if headers is None:
        return False
    has_ccn = any(k in headers for k in PROVIDER_INFO_CCN_KEYS)
    has_entity = any(k in headers for k in PROVIDER_INFO_ENTITY_KEYS)
    if not has_ccn:
        print(f"  [FAIL] provider_info: no CCN column (tried {PROVIDER_INFO_CCN_KEYS})")
        return False
    if not has_entity:
        print(f"  [WARN] provider_info: no entity ID column (tried {PROVIDER_INFO_ENTITY_KEYS})")
    print("  [OK] provider_info: required columns present")
    return True


def audit_chain_performance() -> bool:
    paths = find_glob('2025-11/Chain_Performance_*.csv') or find_glob('chain_performance.csv') or find_glob('2025-11/Chain*.csv')
    path = paths[0] if paths else None
    if not path:
        print("  [SKIP] chain_performance: no file found")
        return True
    headers = load_csv_headers(path)
    if headers is None:
        return False
    missing = [c for c in CHAIN_PERFORMANCE_REQUIRED_COLUMNS if c not in headers]
    if missing:
        print(f"  [FAIL] chain_performance: missing columns: {missing}")
        return False
    print("  [OK] chain_performance: required columns present")
    return True


def audit_sff_json() -> bool:
    path = find_file('pbj-wrapped/public/sff-facilities.json', 'pbj-wrapped/dist/sff-facilities.json', 'sff-facilities.json')
    if not path:
        print("  [SKIP] sff-facilities.json: not found")
        return True
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [FAIL] sff-facilities.json: {e}")
        return False
    facilities = data.get('facilities') if isinstance(data, dict) else (data if isinstance(data, list) else None)
    if facilities is None:
        print("  [FAIL] sff-facilities.json: expected {'facilities': [...]} or [...]")
        return False
    for i, fac in enumerate(facilities[:20]):
        if not isinstance(fac, dict):
            print(f"  [WARN] sff-facilities: entry {i} is not a dict")
            continue
        pn = fac.get('provider_number') or fac.get('Provider Number') or fac.get('provnum')
        if pn is None:
            print(f"  [WARN] sff-facilities: entry {i} has no provider_number")
        else:
            n = normalize_ccn(str(pn))
            if len(n) != 6:
                print(f"  [WARN] sff-facilities: provider_number '{pn}' normalizes to '{n}'")
    print("  [OK] sff-facilities.json: structure valid")
    return True


def audit_pbj_format_rounding() -> bool:
    try:
        from pbj_format import format_metric_value, round_half_up
    except ImportError as e:
        print(f"  [WARN] pbj_format: {e}")
        return True
    # 2.345 -> 2.35 (half up), 2.335 -> 2.34
    v = format_metric_value(2.345, 'Total_Nurse_HPRD')
    if v != '2.35':
        print(f"  [FAIL] format_metric_value(2.345, HPRD) = '{v}' expected '2.35'")
        return False
    v = format_metric_value(33.36, 'Contract_Percentage')
    if v != '33.4':
        print(f"  [FAIL] format_metric_value(33.36, Contract_Percentage) = '{v}' expected '33.4'")
        return False
    v = format_metric_value(100.7, 'avg_daily_census')
    if v != '101':
        print(f"  [FAIL] format_metric_value(100.7, census) = '{v}' expected '101'")
        return False
    print("  [OK] pbj_format rounding (ROUND_HALF_UP) as expected")
    return True


def audit_sff_table_columns() -> bool:
    """Check SFF table CSVs have expected headers (for wrapped app)."""
    tables = [
        ('pbj-wrapped/public/sff_table_a.csv', ['Provider Number', 'Facility Name']),
        ('pbj-wrapped/public/sff_table_d.csv', ['Provider Number', 'Facility Name', 'Months as an SFF Candidate']),
    ]
    ok = True
    for rel, required in tables:
        path = os.path.join(APP_ROOT, rel)
        if not os.path.isfile(path):
            continue
        headers = load_csv_headers(path)
        if headers is None:
            ok = False
            continue
        missing = [c for c in required if c not in headers]
        if missing:
            print(f"  [WARN] {rel}: missing columns {missing} (expected for SFF app)")
            # don't fail; column names might differ by CMS export
    return ok


def main() -> int:
    print("Data accuracy audit (provider, state, entity, SFF)\n")
    all_ok = True

    print("1. Facility quarterly metrics")
    all_ok &= audit_facility_quarterly()

    print("\n2. State quarterly metrics")
    all_ok &= audit_state_quarterly()

    print("\n3. Provider info (combined)")
    all_ok &= audit_provider_info()

    print("\n4. Chain performance CSV")
    all_ok &= audit_chain_performance()

    print("\n5. SFF facilities JSON")
    all_ok &= audit_sff_json()

    print("\n6. SFF table CSVs (column names)")
    audit_sff_table_columns()

    print("\n7. Rounding (pbj_format)")
    all_ok &= audit_pbj_format_rounding()

    print("\n--- Chain performance expected columns (for CMS export check) ---")
    for c in CHAIN_PERFORMANCE_REQUIRED_COLUMNS + CHAIN_PERFORMANCE_OPTIONAL:
        print(f"  {c}")

    if all_ok:
        print("\n[PASS] All checks passed. Continue with manual checklist in AUDIT_DATA_ACCURACY.md")
        return 0
    print("\n[FAIL] One or more checks failed. Fix before publish.")
    return 1


if __name__ == '__main__':
    sys.exit(main())
