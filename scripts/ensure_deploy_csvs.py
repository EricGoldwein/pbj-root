#!/usr/bin/env python3
"""
Render deploy helper when GIT_LFS_SKIP_SMUDGE=1.

LFS pointers stay as small text files; this script ensures runtime CSVs exist
by copying non-LFS snapshots already in the repo (no LFS bandwidth).
"""
from __future__ import annotations

import csv
import os
import shutil
import sys

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_lfs_pointer(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            head = f.read(120)
    except OSError:
        return False
    return head.startswith(b'version https://git-lfs.github.com/spec/v1')


def _copy_if_pointer(target: str, source: str, label: str) -> None:
    tpath = os.path.join(APP_ROOT, target)
    spath = os.path.join(APP_ROOT, source)
    if not os.path.isfile(tpath):
        print(f'ensure_deploy_csvs: missing {target}', file=sys.stderr)
        return
    if not _is_lfs_pointer(tpath):
        print(f'ensure_deploy_csvs: {target} is real data (not LFS pointer)')
        return
    if not os.path.isfile(spath):
        print(
            f'ensure_deploy_csvs: ERROR {target} is LFS pointer but {source} missing',
            file=sys.stderr,
        )
        sys.exit(1)
    if _is_lfs_pointer(spath):
        print(
            f'ensure_deploy_csvs: ERROR {source} is also an LFS pointer; cannot deploy without LFS',
            file=sys.stderr,
        )
        sys.exit(1)
    shutil.copy2(spath, tpath)
    if _is_lfs_pointer(tpath):
        print(f'ensure_deploy_csvs: ERROR copy failed; {target} still LFS pointer', file=sys.stderr)
        sys.exit(1)
    print(f'ensure_deploy_csvs: copied {source} -> {target} ({label})')
    _log_cy_qtr_summary(tpath, target)


def _log_cy_qtr_summary(path: str, label: str) -> None:
    """Log distinct CY_Qtr values and row count without pandas (runs before pip install)."""
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or 'CY_Qtr' not in reader.fieldnames:
                print(f'ensure_deploy_csvs: WARN {label} has no CY_Qtr column', file=sys.stderr)
                return
            quarters: set[str] = set()
            rows = 0
            for row in reader:
                rows += 1
                q = (row.get('CY_Qtr') or '').strip()
                if q:
                    quarters.add(q)
        uniq = sorted(quarters)
        print(f'ensure_deploy_csvs: {label} CY_Qtr={uniq[-3:]} rows={rows}')
    except OSError as e:
        print(f'ensure_deploy_csvs: WARN could not verify {label}: {e}', file=sys.stderr)


def main() -> int:
    os.chdir(APP_ROOT)

    # App tries facility_quarterly_metrics.csv before _latest.csv; pointers must be replaced.
    _copy_if_pointer(
        'facility_quarterly_metrics.csv',
        'facility_quarterly_metrics_latest.csv',
        'facility quarterly metrics',
    )

    norm = os.path.join('provider_info', 'ProviderInfoNorm_2026_04.csv')
    if os.path.isfile(norm) and not _is_lfs_pointer(norm):
        print(f'ensure_deploy_csvs: OK {norm}')
    elif os.path.isfile(norm) and _is_lfs_pointer(norm):
        print(f'ensure_deploy_csvs: ERROR {norm} is LFS pointer', file=sys.stderr)
        return 1
    else:
        print(
            f'ensure_deploy_csvs: ERROR {norm} missing; provider pages need a non-LFS snapshot',
            file=sys.stderr,
        )
        return 1

    for name in ('provider_info_combined_latest.csv', 'provider_info_combined.csv'):
        path = os.path.join(APP_ROOT, name)
        if os.path.isfile(path) and _is_lfs_pointer(path):
            print(f'ensure_deploy_csvs: {name} is LFS pointer (OK while ProviderInfoNorm present)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
