#!/usr/bin/env python3
"""Backfill empty ``urban`` on ProviderInfoNorm_* from matching NH_ProviderInfo_* snapshot."""
from __future__ import annotations

import os
import sys

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)

import pandas as pd

from utils.date_utils import _parse_provider_filename


def _norm_paths_newest_first():
    provider_dir = os.path.join(APP_ROOT, 'provider_info')
    paths = []
    for name in os.listdir(provider_dir):
        if name.startswith('ProviderInfoNorm_') and name.lower().endswith('.csv'):
            paths.append(os.path.join(provider_dir, name))
    paths.sort(
        key=lambda p: _parse_provider_filename(__import__('pathlib').Path(p)) or (0, 0),
        reverse=True,
    )
    return paths


def _nh_path_for_norm(norm_path: str) -> str | None:
    parsed = _parse_provider_filename(__import__('pathlib').Path(norm_path))
    if not parsed:
        return None
    year, month = parsed
    provider_dir = os.path.join(APP_ROOT, 'provider_info')
    month_names = (
        '', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    )
    if month < 1 or month > 12:
        return None
    candidates = [
        os.path.join(provider_dir, f'NH_ProviderInfo_{month_names[month]}{year}.csv'),
        os.path.join(provider_dir, f'NH_ProviderInfo_{month_names[month]}_{year}.csv'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def backfill_norm_urban(norm_path: str, nh_path: str) -> int:
    norm = pd.read_csv(norm_path, low_memory=False)
    if 'ccn' not in norm.columns or 'urban' not in norm.columns:
        raise SystemExit(f'{norm_path}: missing ccn or urban column')
    nh = pd.read_csv(nh_path, low_memory=False)
    ccn_col = next(
        (c for c in nh.columns if str(c).lower() in ('ccn',) or 'ccn' in str(c).lower()),
        None,
    )
    urban_col = next(
        (c for c in nh.columns if str(c).lower() == 'urban'),
        None,
    )
    if not ccn_col or not urban_col:
        raise SystemExit(f'{nh_path}: missing CCN or Urban column')
    nh_map = nh[[ccn_col, urban_col]].copy()
    nh_map[ccn_col] = (
        nh_map[ccn_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(6)
    )
    nh_map = nh_map.rename(columns={ccn_col: 'ccn', urban_col: 'urban_src'})
    nh_map = nh_map.dropna(subset=['ccn']).drop_duplicates('ccn', keep='last')
    norm['ccn_key'] = norm['ccn'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(6)
    merged = norm.merge(nh_map, left_on='ccn_key', right_on='ccn', how='left', suffixes=('', '_nh'))
    missing_before = merged['urban'].isna().sum()
    merged['urban'] = merged['urban'].where(merged['urban'].notna(), merged['urban_src'])
    filled = int(missing_before - merged['urban'].isna().sum())
    out_cols = [c for c in norm.columns if c != 'ccn_key']
    merged[out_cols].to_csv(norm_path, index=False)
    return filled


def main() -> int:
    os.chdir(APP_ROOT)
    norms = _norm_paths_newest_first()
    if not norms:
        print('backfill_provider_norm_urban: no ProviderInfoNorm_*.csv found', file=sys.stderr)
        return 1
    norm_path = norms[0]
    sample = pd.read_csv(norm_path, usecols=['urban'], nrows=20000)
    if sample['urban'].notna().any():
        print(f'backfill_provider_norm_urban: OK urban already populated in {norm_path}')
        return 0
    nh_path = _nh_path_for_norm(norm_path)
    if not nh_path:
        print(f'backfill_provider_norm_urban: no NH snapshot for {norm_path}', file=sys.stderr)
        return 1
    filled = backfill_norm_urban(norm_path, nh_path)
    print(f'backfill_provider_norm_urban: filled {filled} urban values in {norm_path} from {nh_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
