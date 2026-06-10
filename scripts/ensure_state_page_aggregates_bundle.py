#!/usr/bin/env python3
"""Ensure data/state_page_aggregates.json.gz exists for fast /state pages (Render deploy).

Uses committed gzip when valid; rebuilds when missing or source signatures drift.
Fails deploy (exit 1) when no valid bundle — state pages would stay on live_fallback.
"""
from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import state_page_aggregates as spa  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _status_summary(status: dict) -> str:
    return (
        f"exists={status.get('bundle_exists')} "
        f"bytes={status.get('bundle_bytes')} "
        f"validation={status.get('validation_reason')}"
    )


def main() -> int:
    os.chdir(REPO)
    skip = (os.environ.get('PBJ_SKIP_STATE_PAGE_AGGREGATES') or '').strip().lower()
    if skip in ('1', 'true', 'yes', 'on'):
        _log('ensure_state_page_aggregates_bundle: skipped (PBJ_SKIP_STATE_PAGE_AGGREGATES)')
        return 0

    status = spa.inspect_bundle_status(REPO)
    if status.get('bundle_exists') and status.get('validation_ok'):
        _log(
            'ensure_state_page_aggregates_bundle: OK '
            f"quarter={status.get('canonical_quarter')} {_status_summary(status)}"
        )
        return 0

    if status.get('bundle_exists'):
        _log(
            'ensure_state_page_aggregates_bundle: existing bundle invalid — rebuilding '
            f"({_status_summary(status)})"
        )
    else:
        _log('ensure_state_page_aggregates_bundle: bundle missing — building')

    build_script = os.path.join(REPO, 'scripts', 'build_state_page_aggregates.py')
    if not os.path.isfile(build_script):
        _log('ensure_state_page_aggregates_bundle: ERROR build script missing')
        return 1

    rc = subprocess.call([sys.executable, build_script], cwd=REPO)
    if rc != 0:
        _log(f'ensure_state_page_aggregates_bundle: ERROR build exited {rc}')
        return 1

    status = spa.inspect_bundle_status(REPO)
    if status.get('bundle_exists') and status.get('validation_ok'):
        _log(
            'ensure_state_page_aggregates_bundle: OK after build '
            f"quarter={status.get('canonical_quarter')} bytes={status.get('bundle_bytes')}"
        )
        return 0

    _log(
        'ensure_state_page_aggregates_bundle: ERROR no valid bundle after build '
        f"({_status_summary(status)})"
    )
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
