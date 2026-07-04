#!/usr/bin/env python3
"""
Validate public metric/threshold metadata, banned-term guardrails, and registry load.

Usage:
  python scripts/audit_public_metadata.py
  python scripts/audit_public_metadata.py --write-thresholds
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import public_metadata as pm  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description='Audit PBJ320 public metadata registries')
    ap.add_argument(
        '--write-thresholds',
        action='store_true',
        help='Regenerate data/public/public_threshold_metadata.json before validation',
    )
    args = ap.parse_args()

    if args.write_thresholds:
        path = pm.write_threshold_registry_cache()
        print(f'Wrote {path}')

    issues = pm.validate_all()
    metrics = pm.public_metrics()
    thresholds = pm.load_threshold_registry().get('thresholds') or []
    snippets = pm.load_methodology_snippets().get('snippets') or {}

    print(f'Public metadata version: {pm.PUBLIC_METADATA_VERSION}')
    print(f'Metrics (public): {len(metrics)}')
    print(f'Thresholds: {len(thresholds)}')
    print(f'Methodology snippets: {len(snippets)}')
    guard = pm.load_independence_guardrails()
    print(f'Independence guardrails: schema_version={guard.get("schema_version")} rules={len(guard.get("implementation_rules") or [])}')

    types_seen = {t.get('threshold_type') for t in thresholds}
    for required in pm.VALID_THRESHOLD_TYPES:
        if required not in types_seen:
            print(f'WARN: no threshold with threshold_type={required!r} in registry')

    if issues:
        print(f'\nFAILED: {len(issues)} issue(s)')
        for issue in issues:
            print(f'  - {issue}')
        return 1

    print('\nPASS: public metadata registries valid; independence guardrails loaded; no banned/rhetorical terms')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
