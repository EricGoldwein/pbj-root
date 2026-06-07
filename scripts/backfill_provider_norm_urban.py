#!/usr/bin/env python3
"""Backfill empty Norm fields from matching NH_ProviderInfo_* snapshot.

After backfill, run ``scripts/validate_provider_norm_snapshot.py`` (also wired in ensure_deploy_csvs).

Verified from: ProviderInfoNorm_2026_05.csv vs NH_ProviderInfo_May2026.csv — May Norm
omitted ``urban``, ``nursing_case_mix_index``, and ``nursing_case_mix_index_ratio``
even though the NH file has them (Apr Norm + Apr NH match on all three).
"""
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


_NH_BACKFILL_FIELDS = (
    ('urban', 'Urban'),
    ('nursing_case_mix_index', 'Nursing Case-Mix Index'),
    ('nursing_case_mix_index_ratio', 'Nursing Case-Mix Index Ratio'),
)


def _nh_ccn_column(nh: pd.DataFrame) -> str | None:
    return next(
        (c for c in nh.columns if 'ccn' in str(c).lower()),
        None,
    )


def _norm_field_empty(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    return series.isna() | (s == '') | (s.str.lower() == 'nan')


def backfill_norm_from_nh(norm_path: str, nh_path: str) -> dict[str, int]:
    norm = pd.read_csv(norm_path, low_memory=False)
    if 'ccn' not in norm.columns:
        raise SystemExit(f'{norm_path}: missing ccn column')
    nh = pd.read_csv(nh_path, low_memory=False)
    ccn_col = _nh_ccn_column(nh)
    if not ccn_col:
        raise SystemExit(f'{nh_path}: missing CCN column')
    usecols = [ccn_col]
    rename = {ccn_col: 'ccn'}
    for norm_col, nh_col in _NH_BACKFILL_FIELDS:
        if norm_col not in norm.columns:
            continue
        if nh_col not in nh.columns:
            raise SystemExit(f'{nh_path}: missing {nh_col!r} for Norm {norm_col!r}')
        src = f'{norm_col}_src'
        usecols.append(nh_col)
        rename[nh_col] = src
    nh_map = nh[usecols].copy()
    nh_map['ccn'] = (
        nh_map[ccn_col].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(6)
    )
    nh_map = nh_map.drop(columns=[ccn_col]).rename(columns={k: v for k, v in rename.items() if k != ccn_col})
    nh_map = nh_map.dropna(subset=['ccn']).drop_duplicates('ccn', keep='last')
    norm['ccn_key'] = norm['ccn'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(6)
    merged = norm.merge(nh_map, left_on='ccn_key', right_on='ccn', how='left', suffixes=('', '_nh'))
    filled: dict[str, int] = {}
    for norm_col, _nh_col in _NH_BACKFILL_FIELDS:
        if norm_col not in norm.columns:
            continue
        src = f'{norm_col}_src'
        if src not in merged.columns:
            continue
        empty = _norm_field_empty(merged[norm_col])
        missing_before = int(empty.sum())
        merged.loc[empty, norm_col] = merged.loc[empty, src]
        filled[norm_col] = missing_before - int(_norm_field_empty(merged[norm_col]).sum())
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
    need_cols = [c for c, _ in _NH_BACKFILL_FIELDS if c in pd.read_csv(norm_path, nrows=0).columns]
    if not need_cols:
        print(f'backfill_provider_norm_urban: no backfill columns in {norm_path}')
        return 0
    sample = pd.read_csv(norm_path, usecols=need_cols, low_memory=False)
    _MIN_NORM_FILL_RATIO = 0.90
    _MIN_NH_NONEMPTY = 100

    def _needs_backfill(col: str) -> bool:
        empty = int(_norm_field_empty(sample[col]).sum())
        filled = len(sample) - empty
        if filled >= max(_MIN_NH_NONEMPTY, int(len(sample) * _MIN_NORM_FILL_RATIO)):
            return False
        return empty > 0

    cols_needing = [c for c in need_cols if _needs_backfill(c)]
    if not cols_needing:
        print(f'backfill_provider_norm_urban: OK {", ".join(need_cols)} sufficiently populated in {norm_path}')
        return 0
    nh_path = _nh_path_for_norm(norm_path)
    if not nh_path:
        print(
            f'backfill_provider_norm_urban: ERROR need NH snapshot to backfill '
            f'{", ".join(cols_needing)} in {norm_path}',
            file=sys.stderr,
        )
        return 1
    filled = backfill_norm_from_nh(norm_path, nh_path)
    parts = ', '.join(f'{k}={v}' for k, v in filled.items() if v)
    print(f'backfill_provider_norm_urban: filled in {norm_path} from {nh_path}: {parts or "none"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
