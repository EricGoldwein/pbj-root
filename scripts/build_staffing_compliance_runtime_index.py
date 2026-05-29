#!/usr/bin/env python3
"""Build SQLite lookup index for staffing compliance summary (deploy step)."""

from __future__ import annotations

import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import staffing_compliance_bundle as scb  # noqa: E402

INDEX_COLUMNS = (
    'ccn',
    'state',
    'quarter',
    'total_days_reported',
    'rn_0_days_count',
    'rn_0_days_pct',
    'rn_below_8hr_days_count',
    'rn_below_8hr_days_pct',
    'below_state_min_days_count',
    'below_state_min_days_pct',
    'state_min_threshold_used',
    'state_min_metric_used',
    'state_min_label',
)


def _float_or_none(v: str) -> float | None:
    s = (v or '').strip()
    if not s or s.lower() in ('nan', 'none', ''):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _int_or_none(v: str) -> int | None:
    s = (v or '').strip()
    if not s or s.lower() in ('nan', 'none', ''):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def main() -> int:
    t0 = time.perf_counter()
    app_root = str(REPO)
    csv_path = scb.materialize_summary_csv(app_root)
    if not csv_path or not os.path.isfile(csv_path):
        print('[build_staffing_compliance_runtime_index] no summary CSV; skip', flush=True)
        return 0

    manifest = scb.load_manifest(app_root, force=True)
    if manifest is None:
        print('[build_staffing_compliance_runtime_index] WARN no manifest', flush=True)

    scb.invalidate_caches()
    db_path = scb.index_sqlite_path(app_root)
    os.makedirs(os.path.dirname(db_path) or app_root, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute('DROP TABLE IF EXISTS compliance_summary')
    conn.execute('DROP INDEX IF EXISTS idx_compliance_state_quarter')
    conn.execute(
        '''
        CREATE TABLE compliance_summary (
            ccn TEXT NOT NULL,
            state TEXT,
            quarter TEXT NOT NULL,
            total_days_reported INTEGER,
            rn_0_days_count INTEGER,
            rn_0_days_pct REAL,
            rn_below_8hr_days_count INTEGER,
            rn_below_8hr_days_pct REAL,
            below_state_min_days_count INTEGER,
            below_state_min_days_pct REAL,
            state_min_threshold_used REAL,
            state_min_metric_used TEXT,
            state_min_label TEXT,
            PRIMARY KEY (ccn, quarter)
        )
        '''
    )

    rows = 0
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        batch: list[tuple] = []
        for row in reader:
            batch.append(
                (
                    scb.normalize_ccn(row.get('ccn')),
                    (row.get('state') or '').strip().upper()[:2],
                    scb.normalize_quarter(row.get('quarter')),
                    _int_or_none(row.get('total_days_reported')),
                    _int_or_none(row.get('rn_0_days_count')),
                    _float_or_none(row.get('rn_0_days_pct')),
                    _int_or_none(row.get('rn_below_8hr_days_count')),
                    _float_or_none(row.get('rn_below_8hr_days_pct')),
                    _int_or_none(row.get('below_state_min_days_count')),
                    _float_or_none(row.get('below_state_min_days_pct')),
                    _float_or_none(row.get('state_min_threshold_used')),
                    (row.get('state_min_metric_used') or '').strip() or None,
                    (row.get('state_min_label') or '').strip() or None,
                )
            )
            if len(batch) >= 5000:
                conn.executemany(
                    f'INSERT INTO compliance_summary ({",".join(INDEX_COLUMNS)}) VALUES ({",".join("?" * len(INDEX_COLUMNS))})',
                    batch,
                )
                rows += len(batch)
                batch.clear()
        if batch:
            conn.executemany(
                f'INSERT INTO compliance_summary ({",".join(INDEX_COLUMNS)}) VALUES ({",".join("?" * len(INDEX_COLUMNS))})',
                batch,
            )
            rows += len(batch)

    conn.execute('CREATE INDEX IF NOT EXISTS idx_compliance_state_quarter ON compliance_summary(state, quarter)')
    conn.commit()
    conn.execute('VACUUM')
    conn.close()
    scb.invalidate_caches()

    elapsed = time.perf_counter() - t0
    print(
        f'[build_staffing_compliance_runtime_index] wrote {db_path} rows={rows} in {elapsed:.1f}s',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
