#!/usr/bin/env python3
"""
Render deploy helper: materialize runtime CSVs without Git LFS.

facility_quarterly_metrics.csv is not in git (LFS removed); copy from _latest at build.
Provider pages use provider_info/ProviderInfoNorm_*.csv (normal git).
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


def _ensure_csv_from_source(target: str, source: str, label: str) -> None:
    tpath = os.path.join(APP_ROOT, target)
    spath = os.path.join(APP_ROOT, source)
    if not os.path.isfile(spath):
        print(f'ensure_deploy_csvs: ERROR missing {source}', file=sys.stderr)
        sys.exit(1)
    if _is_lfs_pointer(spath):
        print(f'ensure_deploy_csvs: ERROR {source} is LFS pointer', file=sys.stderr)
        sys.exit(1)
    if os.path.isfile(tpath) and not _is_lfs_pointer(tpath):
        print(f'ensure_deploy_csvs: {target} already present')
        return
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

    _ensure_csv_from_source(
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

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
