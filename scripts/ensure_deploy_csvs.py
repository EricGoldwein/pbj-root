#!/usr/bin/env python3
"""
Render deploy: materialize full longitudinal CSVs from committed archives (no LFS checkout).

- facility_quarterly_metrics.csv.gz -> facility_quarterly_metrics.csv (+ _latest copy for static routes)
- provider_info_combined_latest.csv is normal git

See docs/DATA_DEPLOY.md
"""
from __future__ import annotations

import csv
import glob
import gzip
import os
import shutil
import sys

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FACILITY_GZIP = 'facility_quarterly_metrics.csv.gz'
FACILITY_CSV = 'facility_quarterly_metrics.csv'
FACILITY_LATEST = 'facility_quarterly_metrics_latest.csv'
MIN_FACILITY_QUARTERS = 12


def _is_lfs_pointer(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            head = f.read(120)
    except OSError:
        return False
    return head.startswith(b'version https://git-lfs.github.com/spec/v1')


def _count_cy_qtr(path: str) -> tuple[int, list[str]]:
    quarters: set[str] = set()
    rows = 0
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or 'CY_Qtr' not in reader.fieldnames:
            return 0, []
        for row in reader:
            rows += 1
            q = (row.get('CY_Qtr') or '').strip()
            if q:
                quarters.add(q)
    return rows, sorted(quarters)


def _gunzip_facility_metrics() -> None:
    gz_path = os.path.join(APP_ROOT, FACILITY_GZIP)
    out_path = os.path.join(APP_ROOT, FACILITY_CSV)
    if not os.path.isfile(gz_path):
        print(f'ensure_deploy_csvs: ERROR missing {FACILITY_GZIP}', file=sys.stderr)
        sys.exit(1)
    if _is_lfs_pointer(gz_path):
        print(f'ensure_deploy_csvs: ERROR {FACILITY_GZIP} is LFS pointer', file=sys.stderr)
        sys.exit(1)
    print(f'ensure_deploy_csvs: decompressing {FACILITY_GZIP} -> {FACILITY_CSV}')
    with gzip.open(gz_path, 'rb') as f_in, open(out_path, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    rows, quarters = _count_cy_qtr(out_path)
    if len(quarters) < MIN_FACILITY_QUARTERS:
        print(
            f'ensure_deploy_csvs: ERROR only {len(quarters)} quarters in {FACILITY_CSV} '
            f'(need >={MIN_FACILITY_QUARTERS}): {quarters}',
            file=sys.stderr,
        )
        sys.exit(1)
    print(
        f'ensure_deploy_csvs: {FACILITY_CSV} rows={rows} '
        f'quarters={len(quarters)} range={quarters[0]}..{quarters[-1]}'
    )
    latest_path = os.path.join(APP_ROOT, FACILITY_LATEST)
    shutil.copy2(out_path, latest_path)
    print(f'ensure_deploy_csvs: copied -> {FACILITY_LATEST}')


def _newest_provider_norm_rel() -> str | None:
    pattern = os.path.join(APP_ROOT, 'provider_info', 'ProviderInfoNorm_*.csv')
    for path in sorted(glob.glob(pattern), reverse=True):
        rel = os.path.relpath(path, APP_ROOT).replace('\\', '/')
        if os.path.isfile(path) and not _is_lfs_pointer(path):
            return rel
    return None


def _check_provider_combined() -> None:
    path = os.path.join(APP_ROOT, 'provider_info_combined_latest.csv')
    if not os.path.isfile(path):
        print('ensure_deploy_csvs: WARN provider_info_combined_latest.csv missing', file=sys.stderr)
        return
    if _is_lfs_pointer(path):
        print('ensure_deploy_csvs: ERROR provider_info_combined_latest.csv is LFS pointer', file=sys.stderr)
        sys.exit(1)
    print('ensure_deploy_csvs: OK provider_info_combined_latest.csv')


def main() -> int:
    os.chdir(APP_ROOT)
    _gunzip_facility_metrics()
    norm = _newest_provider_norm_rel()
    if not norm:
        print('ensure_deploy_csvs: ERROR no ProviderInfoNorm_*.csv', file=sys.stderr)
        return 1
    print(f'ensure_deploy_csvs: OK {norm}')
    _check_provider_combined()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
