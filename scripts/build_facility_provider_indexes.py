#!/usr/bin/env python3
"""
Build provider cold-path lookup artifacts from facility_quarterly_metrics.csv.

Outputs (data/provider_indexes/):
  - facility_quarterly_provider.sqlite  (per-CCN longitudinal rows + facility_latest)
  - state_percentile_hprd.pkl
  - state_contract_median.pkl
  - meta.json

Run at deploy build (after ensure_deploy_csvs.py), not on every Gunicorn start.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_ROOT)

INDEX_DIR = os.path.join(APP_ROOT, 'data', 'provider_indexes')
SQLITE_PATH = os.path.join(INDEX_DIR, 'facility_quarterly_provider.sqlite')
META_PATH = os.path.join(INDEX_DIR, 'meta.json')


def _log(msg: str) -> None:
    print(msg, flush=True)


def _resolve_csv() -> str:
    for name in ('facility_quarterly_metrics.csv', 'facility_quarterly_metrics_latest.csv'):
        path = os.path.join(APP_ROOT, name)
        if os.path.isfile(path):
            return path
    raise FileNotFoundError('facility_quarterly_metrics.csv not found')


def main() -> int:
    os.chdir(APP_ROOT)
    csv_path = _resolve_csv()
    _log(f'build_facility_provider_indexes: source={os.path.basename(csv_path)}')

    import pandas as pd
    from app import (
        _build_state_contract_median_index_from_csv,
        _build_state_percentile_hprd_index_from_csv,
        get_canonical_latest_quarter,
    )
    from facility_provider_indexes import (
        CONTRACT_PKL,
        INDEX_DIR,
        PERCENTILE_PKL,
        csv_rename_map_for_build,
        save_pickle_index,
        validate_built_sqlite_against_csv,
    )

    os.makedirs(INDEX_DIR, exist_ok=True)
    if os.path.isfile(SQLITE_PATH):
        os.remove(SQLITE_PATH)

    rename_map = csv_rename_map_for_build()
    t0 = time.perf_counter()
    head = pd.read_csv(csv_path, nrows=0)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        row_count = 0
        latest_q = str(get_canonical_latest_quarter() or '').strip()
        for chunk in pd.read_csv(csv_path, low_memory=False, chunksize=100000):
            chunk = chunk.copy()
            chunk['PROVNUM'] = chunk['PROVNUM'].astype(str).str.strip().str.zfill(6)
            chunk['CY_Qtr'] = chunk['CY_Qtr'].astype(str).str.strip()
            chunk['STATE'] = chunk['STATE'].astype(str).str.strip().str.upper().str[:2]
            slim = chunk.rename(columns={k: v for k, v in rename_map.items() if k in chunk.columns})
            keep = [
                c for c in (
                    'provnum', 'cy_qtr', 'provname', 'state', 'county_name',
                    'total_nurse_hprd', 'rn_hprd', 'nurse_assistant_hprd',
                    'nurse_care_hprd', 'rn_care_hprd', 'contract_percentage',
                    'avg_daily_census', 'lpn_hprd', 'lpn_care_hprd', 'total_lpn_hours',
                    'days_reported', 'total_resident_days',
                )
                if c in slim.columns
            ]
            slim = slim[keep]
            slim.to_sql(
                'facility_quarterly',
                conn,
                if_exists='append',
                index=False,
                chunksize=5000,
            )
            row_count += len(slim)
            if row_count % 200000 == 0:
                _log(f'build_facility_provider_indexes: sqlite rows={row_count:,}')

        conn.execute('CREATE INDEX IF NOT EXISTS idx_fq_provnum ON facility_quarterly(provnum)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_fq_provnum_qtr ON facility_quarterly(provnum, cy_qtr)')

        if latest_q:
            conn.execute('DROP TABLE IF EXISTS facility_latest')
            conn.execute(
                '''
                CREATE TABLE facility_latest AS
                SELECT provnum, cy_qtr,
                       total_nurse_hprd, rn_hprd, contract_percentage, avg_daily_census
                FROM facility_quarterly
                WHERE cy_qtr = ?
                ''',
                (latest_q,),
            )
            conn.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS idx_facility_latest_provnum ON facility_latest(provnum)'
            )
        conn.commit()
    finally:
        conn.close()

    sqlite_ms = round((time.perf_counter() - t0) * 1000, 1)
    _log(f'build_facility_provider_indexes: sqlite rows={row_count:,} ms={sqlite_ms}')

    t_pct = time.perf_counter()
    pct_index = _build_state_percentile_hprd_index_from_csv(csv_path)
    save_pickle_index(PERCENTILE_PKL, pct_index, csv_path=csv_path)
    pct_ms = round((time.perf_counter() - t_pct) * 1000, 1)
    _log(f'build_facility_provider_indexes: percentile states={len(pct_index)} ms={pct_ms}')

    t_contract = time.perf_counter()
    contract_index = _build_state_contract_median_index_from_csv(csv_path)
    save_pickle_index(CONTRACT_PKL, contract_index, csv_path=csv_path)
    contract_ms = round((time.perf_counter() - t_contract) * 1000, 1)
    _log(f'build_facility_provider_indexes: contract states={len(contract_index)} ms={contract_ms}')

    meta = {
        'source_basename': os.path.basename(csv_path),
        'source_mtime': int(os.path.getmtime(csv_path)),
        'canonical_quarter': latest_q,
        'row_count': row_count,
        'sqlite_bytes': os.path.getsize(SQLITE_PATH),
        'built_at': time.time(),
    }
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    schema_errors = validate_built_sqlite_against_csv(csv_path, canonical_quarter=latest_q)
    if schema_errors:
        for err in schema_errors:
            _log(f'build_facility_provider_indexes: SCHEMA_FAIL {err}')
        return 1
    _log('build_facility_provider_indexes: schema_validation PASS')
    _log(f'build_facility_provider_indexes: done meta={meta}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
