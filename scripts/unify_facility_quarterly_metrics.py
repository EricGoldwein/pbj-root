#!/usr/bin/env python3
"""
Upgrade facility_quarterly_metrics.csv to the unified schema (legacy + LPN columns).

Safe: legacy columns are unchanged; extra LPN columns are added or merged from the
deprecated facility_quarterly_metrics_with_lpn.csv sidecar. Creates a timestamped backup
before overwriting.

Run from repo root:
  python scripts/unify_facility_quarterly_metrics.py
  python scripts/unify_facility_quarterly_metrics.py --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_CSV = REPO_ROOT / 'facility_quarterly_metrics.csv'
SIDECAR_CSV = REPO_ROOT / 'facility_quarterly_metrics_with_lpn.csv'

LEGACY_COLS = (
    'PROVNUM',
    'PROVNAME',
    'STATE',
    'COUNTY_NAME',
    'CY_Qtr',
    'days_reported',
    'total_resident_days',
    'avg_daily_census',
    'MDScensus',
    'Total_Nurse_Hours',
    'Total_RN_Hours',
    'Total_Nurse_Care_Hours',
    'Total_RN_Care_Hours',
    'Total_Nurse_Assistant_Hours',
    'Total_Contract_Hours',
    'Total_Nurse_HPRD',
    'RN_HPRD',
    'Nurse_Care_HPRD',
    'RN_Care_HPRD',
    'Nurse_Assistant_HPRD',
    'Contract_Percentage',
)
LPN_COLS = (
    'Total_LPN_Hours',
    'Total_LPN_Care_Hours',
    'Total_LPN_Admin_Hours',
    'Total_LPN_Contract_Hours',
    'LPN_HPRD',
    'LPN_Care_HPRD',
    'LPN_Admin_HPRD',
)
ALL_COLS = LEGACY_COLS + LPN_COLS


def _format_provnum(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.lower().str.split('e', n=1, expand=True)[0].str.split('.', n=1, expand=True)[0]
    return out.str.zfill(6)


def _unified_from_paths(main: Path, sidecar: Path | None) -> pd.DataFrame:
    if not main.is_file():
        raise FileNotFoundError(f'Missing {main}')
    raw = pd.read_csv(main, low_memory=False)
    missing = [c for c in LEGACY_COLS if c not in raw.columns]
    if missing:
        raise ValueError(f'{main.name} missing legacy columns: {missing}')
    if 'LPN_HPRD' in raw.columns:
        unified = raw.reindex(columns=list(ALL_COLS), copy=True)
    elif sidecar and sidecar.is_file():
        ext = pd.read_csv(sidecar, low_memory=False)
        miss_x = [c for c in ALL_COLS if c not in ext.columns]
        if miss_x:
            raise ValueError(f'{sidecar.name} missing columns: {miss_x}')
        unified = raw.merge(
            ext[['PROVNUM', 'CY_Qtr'] + list(LPN_COLS)],
            on=['PROVNUM', 'CY_Qtr'],
            how='left',
        )
        unified = unified.reindex(columns=list(ALL_COLS), copy=True)
    else:
        unified = raw.reindex(columns=list(ALL_COLS), copy=True)
        for c in LPN_COLS:
            unified[c] = float('nan')
    unified['PROVNUM'] = _format_provnum(unified['PROVNUM'])
    unified['CY_Qtr'] = unified['CY_Qtr'].astype(str).str.strip()
    unified = unified.drop_duplicates(subset=['PROVNUM', 'CY_Qtr'], keep='last')
    return unified


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', action='store_true', help='Report only; do not write')
    args = p.parse_args()

    unified = _unified_from_paths(MAIN_CSV, SIDECAR_CSV if SIDECAR_CSV.is_file() else None)
    lpn_nn = int(pd.to_numeric(unified['LPN_HPRD'], errors='coerce').notna().sum())
    print(f'Rows: {len(unified):,}; LPN_HPRD non-null: {lpn_nn:,}')
    if 'LPN_HPRD' in pd.read_csv(MAIN_CSV, nrows=0).columns:
        print(f'{MAIN_CSV.name} already has LPN_HPRD column.')
    if args.dry_run:
        print('[dry-run] Would write unified schema to', MAIN_CSV)
        return 0

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = MAIN_CSV.with_name(f'facility_quarterly_metrics.pre_unify_{ts}.csv')
    shutil.copy2(MAIN_CSV, backup)
    print(f'Backup: {backup}')
    unified[list(ALL_COLS)].to_csv(MAIN_CSV, index=False)
    print(f'Wrote unified {MAIN_CSV}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
