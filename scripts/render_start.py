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
    # On Render, CSV/index work belongs in buildCommand only. Running ensure_deploy_csvs
    # at start delays or prevents Gunicorn bind → health check "connection refused".
    if os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'):
        return False
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


def _resync_provider_index_meta() -> None:
    """Align meta.json mtime with on-disk CSV so cold /provider uses SQLite, not full CSV scans."""
    try:
        sys.path.insert(0, APP_ROOT)
        import facility_provider_indexes as fpi

        for name in ('facility_quarterly_metrics.csv', 'facility_quarterly_metrics_latest.csv'):
            csv_path = os.path.join(APP_ROOT, name)
            if os.path.isfile(csv_path) and not _is_lfs_pointer(csv_path):
                if fpi.try_resync_meta_mtime(csv_path):
                    _log(f'provider index meta resynced for {name}')
                break
    except Exception as e:
        _log(f'provider index meta resync skipped: {e}')


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

    _resync_provider_index_meta()

    port = (os.environ.get('PORT') or '10000').strip()
    try:
        port = str(int(port))
    except (ValueError, TypeError):
        port = '10000'
    bind = f'0.0.0.0:{port}'
    _log(
        f'gunicorn launch bind={bind} PORT={port} '
        f'elapsed_since_start_s={time.time() - t_cmd:.2f}'
    )

    gunicorn_argv = [
        'gunicorn',
        'app:app',
        '-c',
        'gunicorn_config.py',
        '--bind',
        bind,
    ]
    try:
        os.execvp(gunicorn_argv[0], gunicorn_argv)
    except FileNotFoundError:
        _log('FATAL: gunicorn not found on PATH — pip install -r requirements.txt')
        return 127
    except OSError as e:
        _log(f'FATAL: could not exec gunicorn: {e}')
        return 127
    return 127


if __name__ == '__main__':
    raise SystemExit(main())
