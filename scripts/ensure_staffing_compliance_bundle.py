#!/usr/bin/env python3
"""Materialize staffing compliance summary CSV from committed gzip (Render deploy)."""

from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import staffing_compliance_bundle as scb  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    os.chdir(REPO)
    if os.environ.get('PBJ_SKIP_STAFFING_COMPLIANCE_BUNDLE', '').strip().lower() in ('1', 'true', 'yes'):
        _log('ensure_staffing_compliance_bundle: skipped (PBJ_SKIP_STAFFING_COMPLIANCE_BUNDLE)')
        return 0

    if not scb.bundle_available(REPO):
        _log('ensure_staffing_compliance_bundle: no bundle in repo; skip (optional artifact)')
        return 0

    csv_path = scb.materialize_summary_csv(REPO)
    if not csv_path or not os.path.isfile(csv_path):
        _log('ensure_staffing_compliance_bundle: ERROR could not materialize summary CSV')
        return 1

    manifest = scb.load_manifest(REPO, force=True) or {}
    quarters = manifest.get('quarters_in_bundle') or []
    states = manifest.get('states_with_thresholds') or []
    _log(
        f'ensure_staffing_compliance_bundle: OK rows~manifest={manifest.get("row_count")} '
        f'quarters={len(quarters)} states={states}'
    )

    # Patch manifest with deploy csv mtime for staleness checks
    meta_path = scb.manifest_path(REPO)
    try:
        manifest['sources'] = manifest.get('sources') or {}
        manifest['sources']['summary_csv'] = {
            'path': scb.SUMMARY_CSV_NAME,
            'mtime': os.path.getmtime(csv_path),
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
    except OSError as exc:
        _log(f'ensure_staffing_compliance_bundle: WARN could not update manifest: {exc}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
