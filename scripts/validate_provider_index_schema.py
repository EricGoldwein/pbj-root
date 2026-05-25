#!/usr/bin/env python3
"""Fail if deploy SQLite longitudinal load lacks CSV column names or HPRD parity."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _resolve_csv() -> str:
    import os

    for name in ('facility_quarterly_metrics.csv', 'facility_quarterly_metrics_latest.csv'):
        path = ROOT / name
        if path.is_file():
            return str(path)
    raise FileNotFoundError('facility_quarterly_metrics.csv not found')


def main() -> int:
    from facility_provider_indexes import validate_built_sqlite_against_csv

    csv_path = _resolve_csv()
    errors = validate_built_sqlite_against_csv(csv_path)
    if errors:
        print('validate_provider_index_schema: FAIL')
        for err in errors:
            print(f'  {err}')
        return 1
    print('validate_provider_index_schema: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
