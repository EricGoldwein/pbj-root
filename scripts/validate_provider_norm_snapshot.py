#!/usr/bin/env python3
"""Gate newest ProviderInfoNorm_* against its paired NH_ProviderInfo_* snapshot.

Verified from: ProviderInfoNorm_2026_05.csv vs NH_ProviderInfo_May2026.csv — May Norm
had case-mix HPRD populated but 0 nursing_case_mix_index while NH had ~14k values.

Exit 0 = OK. Exit 1 = missing files, under-filled critical columns, or spot-check failure.
"""
from __future__ import annotations

import argparse
import os
import sys

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)

import pandas as pd

from utils.date_utils import _parse_provider_filename

# Norm column → NH CMS header
_NH_PARITY_FIELDS = (
    ('nursing_case_mix_index', 'Nursing Case-Mix Index'),
    ('nursing_case_mix_index_ratio', 'Nursing Case-Mix Index Ratio'),
    ('urban', 'Urban'),
)

_MIN_NH_NONEMPTY = 100
_MIN_NORM_FILL_RATIO = 0.90
_SPOT_CCNS = ('015009',)  # Burns — AL facility with known CMI in NH May 2026


def _norm_paths_newest_first() -> list[str]:
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
    for name in (
        f'NH_ProviderInfo_{month_names[month]}{year}.csv',
        f'NH_ProviderInfo_{month_names[month]}_{year}.csv',
    ):
        path = os.path.join(provider_dir, name)
        if os.path.isfile(path):
            return path
    return None


def _nonempty_count(series: pd.Series, *, numeric: bool) -> int:
    if numeric:
        return int(pd.to_numeric(series, errors='coerce').notna().sum())
    s = series.astype(str).str.strip()
    return int(series.notna().sum() - (s == '').sum() - (s.str.lower() == 'nan').sum())


def validate_norm_snapshot(norm_path: str, nh_path: str | None = None) -> list[str]:
    errors: list[str] = []
    nh_path = nh_path or _nh_path_for_norm(norm_path)
    norm = pd.read_csv(norm_path, low_memory=False)
    if nh_path and os.path.isfile(nh_path):
        nh = pd.read_csv(nh_path, low_memory=False)
        nh.columns = [str(c).replace('\ufeff', '').strip() for c in nh.columns]
        for norm_col, nh_col in _NH_PARITY_FIELDS:
            if norm_col not in norm.columns:
                errors.append(f'{norm_path}: missing column {norm_col!r}')
                continue
            if nh_col not in nh.columns:
                errors.append(f'{nh_path}: missing NH column {nh_col!r}')
                continue
            nh_n = _nonempty_count(nh[nh_col], numeric=(norm_col != 'urban'))
            norm_n = _nonempty_count(norm[norm_col], numeric=(norm_col != 'urban'))
            if nh_n >= _MIN_NH_NONEMPTY and norm_n < int(nh_n * _MIN_NORM_FILL_RATIO):
                errors.append(
                    f'{os.path.basename(norm_path)}: {norm_col} under-filled '
                    f'({norm_n:,} vs {nh_n:,} in NH; need >={_MIN_NORM_FILL_RATIO:.0%})'
                )
    else:
        errors.append(f'no paired NH snapshot for {norm_path}')
    if 'ccn' in norm.columns:
        norm['ccn_key'] = (
            norm['ccn'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(6)
        )
        for ccn in _SPOT_CCNS:
            rows = norm[norm['ccn_key'] == ccn]
            if rows.empty:
                continue
            row = rows.iloc[-1]
            if 'nursing_case_mix_index' in norm.columns:
                cmi = pd.to_numeric(row.get('nursing_case_mix_index'), errors='coerce')
                if pd.isna(cmi):
                    errors.append(f'{os.path.basename(norm_path)}: spot CCN {ccn} missing nursing_case_mix_index')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate ProviderInfoNorm vs NH snapshot parity')
    parser.add_argument('--path', type=str, default='', help='Specific Norm CSV path')
    parser.add_argument('--all', action='store_true', help='Validate every Norm file (not only newest)')
    args = parser.parse_args()
    os.chdir(APP_ROOT)
    if args.path:
        targets = [args.path if os.path.isabs(args.path) else os.path.join(APP_ROOT, args.path)]
    elif args.all:
        targets = _norm_paths_newest_first()
    else:
        norms = _norm_paths_newest_first()
        targets = [norms[0]] if norms else []
    if not targets:
        print('validate_provider_norm_snapshot: ERROR no ProviderInfoNorm_*.csv', file=sys.stderr)
        return 1
    failed = False
    for norm_path in targets:
        errs = validate_norm_snapshot(norm_path)
        if errs:
            failed = True
            for err in errs:
                print(f'validate_provider_norm_snapshot: FAIL {err}', file=sys.stderr)
        else:
            print(f'validate_provider_norm_snapshot: OK {os.path.relpath(norm_path, APP_ROOT)}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
