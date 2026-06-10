#!/usr/bin/env python3
"""
Render deploy: materialize full longitudinal CSVs from committed archives (no LFS checkout).

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


def _log(msg: str) -> None:
    print(msg, flush=True)


def _is_lfs_pointer(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            head = f.read(120)
    except OSError:
        return False
    return head.startswith(b'version https://git-lfs.github.com/spec/v1')


def _header_has_cy_qtr(path: str) -> bool:
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return bool(reader.fieldnames and 'CY_Qtr' in reader.fieldnames)
    except OSError:
        return False


def _count_cy_qtr(path: str) -> tuple[int, list[str]]:
    quarters: set[str] = set()
    rows = 0
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or 'CY_Qtr' not in reader.fieldnames:
            return 0, []
        for row in reader:
            rows += 1
            if rows % 100000 == 0:
                _log(f'ensure_deploy_csvs: verifying rows={rows:,} quarters_so_far={len(quarters)}')
            q = (row.get('CY_Qtr') or '').strip()
            if q:
                quarters.add(q)
    return rows, sorted(quarters)


def _link_or_copy(src: str, dest: str) -> None:
    if os.path.isfile(dest):
        os.remove(dest)
    try:
        os.link(src, dest)
        _log(f'ensure_deploy_csvs: hard-linked -> {dest}')
    except OSError:
        _log(f'ensure_deploy_csvs: copying 190MB -> {dest} (may take 1-2 min)...')
        shutil.copy2(src, dest)
        _log(f'ensure_deploy_csvs: copied -> {dest}')


def _gunzip_facility_metrics(*, verify_rows: bool = True) -> None:
    gz_path = os.path.join(APP_ROOT, FACILITY_GZIP)
    out_path = os.path.join(APP_ROOT, FACILITY_CSV)
    if os.path.isfile(out_path) and not _is_lfs_pointer(out_path):
        if not verify_rows:
            if not _header_has_cy_qtr(out_path):
                _log(f'ensure_deploy_csvs: ERROR {FACILITY_CSV} missing CY_Qtr column')
                sys.exit(1)
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            _log(
                f'ensure_deploy_csvs: quick OK {FACILITY_CSV} present '
                f'size_mb={size_mb:.1f} (skipped row scan; use --full or RUN_DEPLOY_CSV_CHECK=1)'
            )
            _link_or_copy(out_path, os.path.join(APP_ROOT, FACILITY_LATEST))
            return
        rows, quarters = _count_cy_qtr(out_path)
        if len(quarters) >= MIN_FACILITY_QUARTERS:
            _log(
                f'ensure_deploy_csvs: {FACILITY_CSV} already present '
                f'rows={rows} quarters={len(quarters)} range={quarters[0]}..{quarters[-1]}'
            )
            _link_or_copy(out_path, os.path.join(APP_ROOT, FACILITY_LATEST))
            return
    if not os.path.isfile(gz_path):
        _log(f'ensure_deploy_csvs: ERROR missing {FACILITY_GZIP}')
        sys.exit(1)
    if _is_lfs_pointer(gz_path):
        _log(f'ensure_deploy_csvs: ERROR {FACILITY_GZIP} is LFS pointer')
        sys.exit(1)
    gz_mb = os.path.getsize(gz_path) / (1024 * 1024)
    _log(f'ensure_deploy_csvs: decompressing {FACILITY_GZIP} ({gz_mb:.1f} MB) -> {FACILITY_CSV} (~2 min)...')
    with gzip.open(gz_path, 'rb') as f_in, open(out_path, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    _log('ensure_deploy_csvs: decompress done; verifying quarters...')
    rows, quarters = _count_cy_qtr(out_path)
    if len(quarters) < MIN_FACILITY_QUARTERS:
        _log(
            f'ensure_deploy_csvs: ERROR only {len(quarters)} quarters '
            f'(need >={MIN_FACILITY_QUARTERS}): {quarters}'
        )
        sys.exit(1)
    _log(
        f'ensure_deploy_csvs: {FACILITY_CSV} rows={rows} '
        f'quarters={len(quarters)} range={quarters[0]}..{quarters[-1]}'
    )
    _link_or_copy(out_path, os.path.join(APP_ROOT, FACILITY_LATEST))


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
        _log('ensure_deploy_csvs: WARN provider_info_combined_latest.csv missing')
        return
    if _is_lfs_pointer(path):
        _log('ensure_deploy_csvs: ERROR provider_info_combined_latest.csv is LFS pointer')
        sys.exit(1)
    _log('ensure_deploy_csvs: OK provider_info_combined_latest.csv')


STATE_LPN_COLUMNS = ('LPN_HPRD', 'LPN_Care_HPRD')
NATIONAL_LPN_COLUMNS = STATE_LPN_COLUMNS
REGION_LPN_COLUMNS = STATE_LPN_COLUMNS

STATE_MEDIAN_COLUMNS = (
    'Total_Nurse_HPRD_Median',
    'RN_HPRD_Median',
    'Nurse_Care_HPRD_Median',
    'RN_Care_HPRD_Median',
    'LPN_HPRD_Median',
    'LPN_Care_HPRD_Median',
    'Nurse_Assistant_HPRD_Median',
    'Contract_Percentage_Median',
)


def _csv_missing_columns(path: str, required: tuple[str, ...]) -> list[str]:
    try:
        with open(path, newline='', encoding='utf-8') as f:
            headers = csv.DictReader(f).fieldnames or []
    except OSError as exc:
        _log(f'ensure_deploy_csvs: WARN could not read {os.path.basename(path)} header: {exc}')
        return list(required)
    return [c for c in required if c not in headers]


def _ensure_quarterly_lpn_columns() -> None:
    """Add LPN_HPRD / LPN_Care_HPRD to state, national, and region quarterly CSVs when missing."""
    if not os.path.isfile(os.path.join(APP_ROOT, FACILITY_CSV)):
        _log('ensure_deploy_csvs: WARN facility CSV missing; skip quarterly LPN patch')
        return
    targets = (
        ('state_quarterly_metrics.csv', STATE_LPN_COLUMNS),
        ('national_quarterly_metrics.csv', NATIONAL_LPN_COLUMNS),
        ('cms_region_quarterly_metrics.csv', REGION_LPN_COLUMNS),
    )
    need_patch = False
    for rel, cols in targets:
        path = os.path.join(APP_ROOT, rel)
        if not os.path.isfile(path):
            _log(f'ensure_deploy_csvs: WARN {rel} missing; skip LPN check for that file')
            continue
        missing = _csv_missing_columns(path, cols)
        if missing:
            need_patch = True
            _log(f'ensure_deploy_csvs: {rel} missing LPN columns: {", ".join(missing)}')
        else:
            _log(f'ensure_deploy_csvs: OK {rel} has LPN columns')
    if not need_patch:
        return
    patch_script = os.path.join(APP_ROOT, 'scripts', 'patch_state_quarterly_lpn.py')
    if not os.path.isfile(patch_script):
        _log('ensure_deploy_csvs: WARN missing patch_state_quarterly_lpn.py')
        return
    import subprocess

    rc = subprocess.call([sys.executable, patch_script], cwd=APP_ROOT)
    if rc != 0:
        _log(f'ensure_deploy_csvs: WARN patch_state_quarterly_lpn.py exited {rc}')
    else:
        _log('ensure_deploy_csvs: OK quarterly LPN columns patched (state/national/region)')


def _ensure_state_quarterly_median_columns() -> None:
    """Add *_Median columns to state_quarterly_metrics.csv when missing (/report map toggle)."""
    state_csv = os.path.join(APP_ROOT, 'state_quarterly_metrics.csv')
    if not os.path.isfile(state_csv):
        _log('ensure_deploy_csvs: WARN state_quarterly_metrics.csv missing; skip median patch')
        return
    if not os.path.isfile(os.path.join(APP_ROOT, FACILITY_CSV)):
        _log('ensure_deploy_csvs: WARN facility CSV missing; skip state median patch')
        return
    try:
        with open(state_csv, newline='', encoding='utf-8') as f:
            headers = csv.DictReader(f).fieldnames or []
    except OSError as exc:
        _log(f'ensure_deploy_csvs: WARN could not read state_quarterly_metrics header: {exc}')
        return
    missing = [c for c in STATE_MEDIAN_COLUMNS if c not in headers]
    if not missing:
        _log('ensure_deploy_csvs: OK state_quarterly_metrics.csv has *_Median columns')
        return
    patch_script = os.path.join(APP_ROOT, 'scripts', 'patch_state_quarterly_medians.py')
    if not os.path.isfile(patch_script):
        _log('ensure_deploy_csvs: WARN missing patch_state_quarterly_medians.py')
        return
    _log(
        'ensure_deploy_csvs: patching state_quarterly_metrics medians (missing: '
        + ', '.join(missing)
        + ')'
    )
    import subprocess

    rc = subprocess.call([sys.executable, patch_script], cwd=APP_ROOT)
    if rc != 0:
        _log(f'ensure_deploy_csvs: WARN patch_state_quarterly_medians.py exited {rc}')
    else:
        _log('ensure_deploy_csvs: OK state_quarterly_metrics.csv medians patched')


def main() -> int:
    os.chdir(APP_ROOT)
    import time as _time

    t_main = _time.perf_counter()
    argv = set(sys.argv[1:])
    quick = '--quick' in argv
    force_full = (
        '--full' in argv
        or (os.environ.get('RUN_DEPLOY_CSV_CHECK') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    )
    verify_rows = force_full or not quick
    _log(f'ensure_deploy_csvs: begin verify_rows={verify_rows} quick={quick}')
    t_fac = _time.perf_counter()
    _gunzip_facility_metrics(verify_rows=verify_rows)
    _log(f'ensure_deploy_csvs: facility step elapsed_s={_time.perf_counter() - t_fac:.2f}')
    norm = _newest_provider_norm_rel()
    if not norm:
        _log('ensure_deploy_csvs: ERROR no ProviderInfoNorm_*.csv')
        return 1
    _log(f'ensure_deploy_csvs: OK {norm}')
    backfill_script = os.path.join(APP_ROOT, 'scripts', 'backfill_provider_norm_urban.py')
    validate_norm_script = os.path.join(APP_ROOT, 'scripts', 'validate_provider_norm_snapshot.py')
    import subprocess
    if os.path.isfile(backfill_script):
        subprocess.call([sys.executable, backfill_script], cwd=APP_ROOT)
    if os.path.isfile(validate_norm_script):
        rc_norm = subprocess.call([sys.executable, validate_norm_script], cwd=APP_ROOT)
        if rc_norm != 0:
            _log('ensure_deploy_csvs: ERROR ProviderInfoNorm failed parity validation')
            return 1
    _check_provider_combined()
    _ensure_quarterly_lpn_columns()
    _ensure_state_quarterly_median_columns()
    scb_script = os.path.join(APP_ROOT, 'scripts', 'ensure_staffing_compliance_bundle.py')
    if os.path.isfile(scb_script):
        import subprocess

        rc_scb = subprocess.call([sys.executable, scb_script], cwd=APP_ROOT)
        if rc_scb != 0:
            _log(f'ensure_deploy_csvs: WARN ensure_staffing_compliance_bundle exited {rc_scb}')
        idx_script = os.path.join(APP_ROOT, 'scripts', 'build_staffing_compliance_runtime_index.py')
        if os.path.isfile(idx_script) and rc_scb == 0:
            rc_idx = subprocess.call([sys.executable, idx_script], cwd=APP_ROOT)
            if rc_idx != 0:
                _log(f'ensure_deploy_csvs: WARN build_staffing_compliance_runtime_index exited {rc_idx}')
    if os.environ.get('PBJ_SKIP_BUILD_PROVIDER_INDEXES', '').strip().lower() not in ('1', 'true', 'yes'):
        _log('ensure_deploy_csvs: building provider lookup indexes...')
        import subprocess
        idx_script = os.path.join(APP_ROOT, 'scripts', 'build_facility_provider_indexes.py')
        rc = subprocess.call([sys.executable, idx_script], cwd=APP_ROOT)
        if rc != 0:
            _log('ensure_deploy_csvs: WARN provider index build failed (cold path will use CSV streams)')
    spa_script = os.path.join(APP_ROOT, 'scripts', 'ensure_state_page_aggregates_bundle.py')
    if os.path.isfile(spa_script):
        import subprocess

        rc_spa = subprocess.call([sys.executable, spa_script], cwd=APP_ROOT)
        if rc_spa != 0:
            _log('ensure_deploy_csvs: ERROR state page aggregates bundle required for /state speed')
            return 1
    _log(f'ensure_deploy_csvs: done total_elapsed_s={_time.perf_counter() - t_main:.2f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
