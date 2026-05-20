#!/usr/bin/env python3
"""CLI check: public facility trend exports follow the case-mix export rule."""
from __future__ import annotations

import argparse
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault('PBJ_SKIP_HEAVY_INIT', '1')


def _integration_check(ccn: str) -> None:
    from app import _build_facility_quarterly_trend_csv_rows, load_facility_quarterly_for_provider
    from pbj_format import format_metric_value, format_quarter_display
    from pbj_ai_support import verify_public_facility_trend_case_mix_export

    fq = load_facility_quarterly_for_provider(ccn)
    if fq is None or getattr(fq, 'empty', True):
        raise SystemExit(f'[SKIP] no PBJ rows for CCN {ccn}')
    rows = _build_facility_quarterly_trend_csv_rows(
        ccn,
        fq,
        'Test Facility',
        'CT',
        'Connecticut',
        'https://www.pbj320.com',
        format_metric_value,
        format_quarter_display,
    )
    verify_public_facility_trend_case_mix_export(rows, ccn=ccn)
    cm_rows = sum(
        1
        for r in rows
        if any(str(r.get(c) or '').strip() not in ('', '—') for c in (
            'case_mix_index', 'case_mix_index_ratio', 'cms_case_mix_total_nurse_hprd'
        ))
    )
    print(f'[PASS] CCN {ccn}: {len(rows)} trend rows, case-mix on {cm_rows} quarter(s)')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ccn', default='075388', help='CCN to verify (default: 075388)')
    parser.add_argument('--unit-only', action='store_true', help='Skip live facility integration')
    args = parser.parse_args()

    from test_public_case_mix_export import PublicCaseMixExportRuleTests  # noqa: WPS433

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(PublicCaseMixExportRuleTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1

    if args.unit_only:
        return 0

    try:
        _integration_check(args.ccn.zfill(6)[-6:])
    except SystemExit as exc:
        code = exc.code
        if code == 0 or str(code) == '0':
            return 0
        print(exc, file=sys.stderr)
        return 1 if code is None else int(code)
    except Exception as exc:
        print(f'[FAIL] integration: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
