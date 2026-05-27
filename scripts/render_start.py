#!/usr/bin/env python3
"""Render start command: bind Gunicorn quickly; optional fast CSV guard (build does real work).

Use as startCommand: python scripts/render_start.py

Set PBJ_SKIP_START_CSV_ENSURE=1 (render.yaml) when buildCommand already ran ensure_deploy_csvs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log(msg: str) -> None:
    print(f'[render_start] {msg}', flush=True)


def _is_lfs_pointer(path: str) -> bool:
    try:
        with open(path, 'rb') as f:
            head = f.read(120)
    except OSError:
        return True
    return head.startswith(b'version https://git-lfs.github.com/spec/v1')


def _needs_start_ensure() -> bool:
    skip = (os.environ.get('PBJ_SKIP_START_CSV_ENSURE') or '').strip().lower()
    if skip in ('1', 'true', 'yes', 'on'):
        return False
    force = (os.environ.get('RUN_DEPLOY_CSV_CHECK') or '').strip().lower()
    if force in ('1', 'true', 'yes', 'on'):
        return True
    facility_csv = os.path.join(APP_ROOT, 'facility_quarterly_metrics.csv')
    if not os.path.isfile(facility_csv) or _is_lfs_pointer(facility_csv):
        return True
    combined = os.path.join(APP_ROOT, 'provider_info_combined_latest.csv')
    if not os.path.isfile(combined) or _is_lfs_pointer(combined):
        return True
    return False


def main() -> int:
    os.chdir(APP_ROOT)
    t_cmd = time.time()
    _log(f'start command begins pid={os.getpid()}')

    if _needs_start_ensure():
        t0 = time.perf_counter()
        _log('ensure_deploy_csvs begins (--quick; missing or forced check)')
        script = os.path.join(APP_ROOT, 'scripts', 'ensure_deploy_csvs.py')
        rc = subprocess.call([sys.executable, script, '--quick'], cwd=APP_ROOT)
        elapsed = time.perf_counter() - t0
        _log(f'ensure_deploy_csvs ends rc={rc} elapsed_s={elapsed:.2f}')
        if rc != 0:
            return rc
    else:
        _log('ensure_deploy_csvs skipped (build artifacts present; PBJ_SKIP_START_CSV_ENSURE)')

    port = (os.environ.get('PORT') or '10000').strip()
    try:
        port = str(int(port))
    except (ValueError, TypeError):
        port = '10000'
    bind = f'0.0.0.0:{port}'
    _log(f'gunicorn launch bind={bind} elapsed_since_start_s={time.time() - t_cmd:.2f}')

    gunicorn_argv = [
        'gunicorn',
        'app:app',
        '-c',
        'gunicorn_config.py',
        '--bind',
        bind,
    ]
    os.execvp(gunicorn_argv[0], gunicorn_argv)
    return 127


if __name__ == '__main__':
    raise SystemExit(main())
