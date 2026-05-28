"""Precomputed facility/provider lookup artifacts (SQLite + pickle) for fast /provider cold path."""

from __future__ import annotations

import json
import os
import pickle
import re
import sqlite3
import threading
import time
from typing import Any

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(APP_ROOT, 'data', 'provider_indexes')
SQLITE_PATH = os.path.join(INDEX_DIR, 'facility_quarterly_provider.sqlite')
META_PATH = os.path.join(INDEX_DIR, 'meta.json')
PERCENTILE_PKL = os.path.join(INDEX_DIR, 'state_percentile_hprd.pkl')
CONTRACT_PKL = os.path.join(INDEX_DIR, 'state_contract_median.pkl')

# Single schema contract: build renames CSV -> sqlite; load must restore CSV names for app.py/charts.
CSV_TO_SQLITE_COLUMNS: dict[str, str] = {
    'PROVNUM': 'provnum',
    'CY_Qtr': 'cy_qtr',
    'PROVNAME': 'provname',
    'STATE': 'state',
    'COUNTY_NAME': 'county_name',
    'Total_Nurse_HPRD': 'total_nurse_hprd',
    'RN_HPRD': 'rn_hprd',
    'Nurse_Assistant_HPRD': 'nurse_assistant_hprd',
    'Nurse_Care_HPRD': 'nurse_care_hprd',
    'RN_Care_HPRD': 'rn_care_hprd',
    'Contract_Percentage': 'contract_percentage',
    'LPN_HPRD': 'lpn_hprd',
    'LPN_Care_HPRD': 'lpn_care_hprd',
    'Total_LPN_Hours': 'total_lpn_hours',
}

SQLITE_TO_CSV_COLUMNS: dict[str, str] = {v: k for k, v in CSV_TO_SQLITE_COLUMNS.items() if k != v}

# Columns app.py / chart builders read from facility_df (must exist after load_ccn_longitudinal_df).
REQUIRED_PROVIDER_DF_CSV_COLUMNS: tuple[str, ...] = (
    'PROVNUM',
    'CY_Qtr',
    'Total_Nurse_HPRD',
    'RN_HPRD',
    'Nurse_Assistant_HPRD',
    'LPN_HPRD',
    'Contract_Percentage',
    'avg_daily_census',
)

_DEFAULT_VALIDATION_CCNS: tuple[str, ...] = ('676230', '035297', '335513')

_SQLITE_CONN: sqlite3.Connection | None = None
_SQLITE_LOCK = threading.Lock()
_META_CACHE: dict[str, Any] | None = None
_CCN_ALLOWED_RE = re.compile(r'^[A-Z0-9]{1,6}$')


def _norm_ccn(raw: Any) -> str:
    s = str(raw or '').strip().upper()
    if '.' in s:
        s = s.split('.')[0]
    if not s or not _CCN_ALLOWED_RE.fullmatch(s):
        return ''
    return s.zfill(6)


def csv_rename_map_for_build() -> dict[str, str]:
    """Pass to DataFrame.rename when writing facility_quarterly SQLite table."""
    return dict(CSV_TO_SQLITE_COLUMNS)


def _restore_csv_column_names(df):
    """Copy sqlite metric columns to uppercase CSV names expected by app.py."""
    if df is None or getattr(df, 'empty', True):
        return df
    for sqlite_col, csv_col in SQLITE_TO_CSV_COLUMNS.items():
        if sqlite_col in df.columns and csv_col not in df.columns:
            df[csv_col] = df[sqlite_col]
    return df


def provider_df_schema_errors(df, *, ccn: str = '') -> list[str]:
    """Return list of schema violations (empty list = OK for page render)."""
    if df is None or getattr(df, 'empty', True):
        return ['empty_dataframe']
    missing = [c for c in REQUIRED_PROVIDER_DF_CSV_COLUMNS if c not in df.columns]
    if missing:
        return [f'missing_csv_columns:{",".join(missing)}']
    if ccn and 'PROVNUM' in df.columns:
        got = _norm_ccn(df['PROVNUM'].iloc[-1])
        if got != _norm_ccn(ccn):
            return [f'provnum_mismatch:{got}!={ccn}']
    return []


def validate_built_sqlite_against_csv(
    csv_path: str,
    *,
    sample_ccns: tuple[str, ...] | None = None,
    canonical_quarter: str | None = None,
    rtol: float = 1e-5,
) -> list[str]:
    """
    Post-build gate: load CCNs from SQLite via load_ccn_longitudinal_df and compare to CSV.
    Returns human-readable errors (empty = pass).
    """
    import pandas as pd

    errors: list[str] = []
    if not sqlite_available() or not os.path.isfile(csv_path):
        return ['artifacts_or_csv_missing']

    close_sqlite()
    global _META_CACHE  # noqa: PLW0603
    _META_CACHE = None

    ccns = list(sample_ccns or _DEFAULT_VALIDATION_CCNS)
    latest_q = (canonical_quarter or _read_meta().get('canonical_quarter') or '').strip()

    for prov in ccns:
        prov = _norm_ccn(prov)
        if not prov:
            errors.append(f'{prov}:invalid_ccn')
            continue
        df = load_ccn_longitudinal_df(prov, pd)
        schema_err = provider_df_schema_errors(df, ccn=prov)
        if schema_err:
            errors.append(f'{prov}:{";".join(schema_err)}')
            continue
        if not latest_q or 'CY_Qtr' not in df.columns:
            errors.append(f'{prov}:no_canonical_quarter')
            continue
        sub = df[df['CY_Qtr'].astype(str).str.strip() == latest_q]
        if sub.empty:
            errors.append(f'{prov}:no_rows_for_{latest_q}')
            continue
        fast_hprd = sub.iloc[0].get('Total_Nurse_HPRD')
        csv_hprd = None
        for chunk in pd.read_csv(csv_path, low_memory=False, chunksize=100000):
            if 'PROVNUM' not in chunk.columns:
                continue
            chunk['PROVNUM'] = chunk['PROVNUM'].astype(str).str.strip().str.upper().str.zfill(6)
            m = chunk[(chunk['PROVNUM'] == prov) & (chunk['CY_Qtr'].astype(str).str.strip() == latest_q)]
            if not m.empty:
                csv_hprd = m.iloc[0].get('Total_Nurse_HPRD')
                break
        if csv_hprd is None or (isinstance(csv_hprd, float) and pd.isna(csv_hprd)):
            continue
        try:
            a, b = float(fast_hprd), float(csv_hprd)
        except (TypeError, ValueError):
            errors.append(f'{prov}:hprd_not_numeric fast={fast_hprd} csv={csv_hprd}')
            continue
        if pd.isna(a) and pd.isna(b):
            continue
        if pd.isna(a) != pd.isna(b) or (not pd.isna(a) and abs(a - b) > rtol * max(abs(b), 1e-9)):
            errors.append(f'{prov}:hprd_mismatch fast={a} csv={b} q={latest_q}')

    return errors


def log_index_event(event: str, **fields: Any) -> None:
    """Structured ops log: [PBJ_PROVIDER_INDEX] {json}."""
    payload = {'event': event, **fields}
    print(
        '[PBJ_PROVIDER_INDEX] ' + json.dumps(payload, separators=(',', ':'), sort_keys=True),
        flush=True,
    )


def index_dir() -> str:
    return INDEX_DIR


def sqlite_path() -> str:
    return SQLITE_PATH


def sqlite_exists() -> bool:
    return os.path.isfile(SQLITE_PATH)


def meta_exists() -> bool:
    return os.path.isfile(META_PATH)


def sqlite_available() -> bool:
    return sqlite_exists() and meta_exists()


def close_sqlite() -> None:
    """Release SQLite handle (e.g. before moving artifact files on Windows)."""
    global _SQLITE_CONN
    with _SQLITE_LOCK:
        if _SQLITE_CONN is not None:
            try:
                _SQLITE_CONN.close()
            except Exception:
                pass
            _SQLITE_CONN = None


def _read_meta() -> dict[str, Any]:
    global _META_CACHE
    if _META_CACHE is not None:
        return _META_CACHE
    try:
        with open(META_PATH, encoding='utf-8') as f:
            _META_CACHE = json.load(f)
    except (OSError, json.JSONDecodeError):
        _META_CACHE = {}
    return _META_CACHE


def meta_matches_csv(csv_path: str | None) -> bool:
    if not csv_path or not sqlite_available():
        return False
    meta = _read_meta()
    try:
        mtime = int(os.path.getmtime(csv_path))
    except OSError:
        return False
    return (
        os.path.basename(csv_path) == meta.get('source_basename')
        and mtime == int(meta.get('source_mtime') or -1)
    )


def try_resync_meta_mtime(csv_path: str | None) -> bool:
    """If deploy SQLite is present but meta source_mtime drifted, refresh meta (avoids CSV stream fallback).

    Verified from: Render logs ``reason\":\"meta_mtime_stale\"`` on cold /provider renders.
    """
    global _META_CACHE
    if not csv_path or not os.path.isfile(csv_path) or not sqlite_exists() or not meta_exists():
        return False
    if meta_matches_csv(csv_path):
        return False
    meta = dict(_read_meta())
    if os.path.basename(csv_path) != meta.get('source_basename'):
        return False
    try:
        mtime = int(os.path.getmtime(csv_path))
    except OSError:
        return False
    old_mtime = int(meta.get('source_mtime') or -1)
    if mtime == old_mtime:
        return False
    meta['source_mtime'] = mtime
    meta['resynced_at'] = time.time()
    try:
        os.makedirs(os.path.dirname(META_PATH) or INDEX_DIR, exist_ok=True)
        with open(META_PATH, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
        _META_CACHE = meta
        log_index_event(
            'meta_mtime_resynced',
            path=os.path.basename(csv_path),
            old_mtime=old_mtime,
            new_mtime=mtime,
        )
        return True
    except OSError as e:
        log_index_event('meta_mtime_resync_failed', error=str(e)[:200])
        return False


def fallback_reason(csv_path: str | None, *, ccn: str | None = None) -> str:
    """Human-readable reason the fast path is unavailable."""
    if not csv_path:
        return 'facility_csv_missing'
    if not sqlite_exists():
        return 'sqlite_missing'
    if not meta_exists():
        return 'meta_missing'
    if not meta_matches_csv(csv_path):
        try:
            mtime = int(os.path.getmtime(csv_path))
        except OSError:
            return 'csv_mtime_unreadable'
        meta = _read_meta()
        if os.path.basename(csv_path) != meta.get('source_basename'):
            return 'meta_source_basename_mismatch'
        if mtime != int(meta.get('source_mtime') or -1):
            return 'meta_mtime_stale'
        return 'meta_mismatch'
    return 'sqlite_lookup_miss' if ccn else 'unknown'


def provider_index_status(
    csv_path: str | None,
    *,
    worker_hydrated: bool = False,
    percentile_warm: bool = False,
    contract_warm: bool = False,
) -> dict[str, Any]:
    """Lightweight health snapshot for CLI / protected debug route."""
    meta = _read_meta() if meta_exists() else {}
    matches = meta_matches_csv(csv_path)
    sqlite_rows = None
    latest_q = meta.get('canonical_quarter')
    latest_table_rows = None
    schema_errors: list[str] = []
    if sqlite_exists() and matches and csv_path:
        try:
            schema_errors = validate_built_sqlite_against_csv(
                csv_path,
                canonical_quarter=str(latest_q or ''),
            )
        except Exception as e:
            schema_errors = [f'validate_exception:{e}']
    if sqlite_exists():
        try:
            conn = _get_sqlite_conn()
            if conn is not None:
                sqlite_rows = conn.execute('SELECT COUNT(*) FROM facility_quarterly').fetchone()[0]
                if latest_q:
                    latest_table_rows = conn.execute(
                        'SELECT COUNT(*) FROM facility_latest WHERE cy_qtr = ?',
                        (str(latest_q),),
                    ).fetchone()[0]
        except sqlite3.Error:
            pass
    csv_mtime = None
    if csv_path and os.path.isfile(csv_path):
        try:
            csv_mtime = int(os.path.getmtime(csv_path))
        except OSError:
            pass
    return {
        'ok': bool(csv_path) and sqlite_exists() and meta_exists() and matches and not schema_errors,
        'index_dir': INDEX_DIR,
        'sqlite_exists': sqlite_exists(),
        'meta_exists': meta_exists(),
        'percentile_pkl_exists': os.path.isfile(PERCENTILE_PKL),
        'contract_pkl_exists': os.path.isfile(CONTRACT_PKL),
        'meta_matches_csv': matches,
        'schema_validation_errors': schema_errors,
        'facility_csv_path': os.path.basename(csv_path) if csv_path else None,
        'facility_csv_mtime': csv_mtime,
        'meta_source_basename': meta.get('source_basename'),
        'meta_source_mtime': meta.get('source_mtime'),
        'meta_row_count': meta.get('row_count'),
        'sqlite_row_count': sqlite_rows,
        'facility_latest_rows': latest_table_rows,
        'canonical_quarter': latest_q,
        'sqlite_bytes': os.path.getsize(SQLITE_PATH) if sqlite_exists() else 0,
        'worker_hydrated': worker_hydrated,
        'percentile_index_warm': percentile_warm,
        'contract_index_warm': contract_warm,
    }


def _get_sqlite_conn() -> sqlite3.Connection | None:
    global _SQLITE_CONN
    if not sqlite_available():
        return None
    if _SQLITE_CONN is not None:
        return _SQLITE_CONN
    with _SQLITE_LOCK:
        if _SQLITE_CONN is not None:
            return _SQLITE_CONN
        conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _SQLITE_CONN = conn
        return conn


def load_ccn_longitudinal_df(prov: str, pdm):
    """All quarterly rows for one CCN from SQLite (no CSV scan). Returns DataFrame or None."""
    if pdm is None:
        return None
    conn = _get_sqlite_conn()
    if conn is None:
        return None
    try:
        prov = _norm_ccn(prov)
        if not prov:
            return None
        cur = conn.execute(
            'SELECT * FROM facility_quarterly WHERE provnum = ? COLLATE NOCASE ORDER BY cy_qtr',
            (prov,),
        )
        rows = cur.fetchall()
        if not rows:
            return None
        data = [dict(r) for r in rows]
        df = pdm.DataFrame(data)
        if 'provnum' in df.columns and 'PROVNUM' not in df.columns:
            df['PROVNUM'] = df['provnum']
        if 'cy_qtr' in df.columns and 'CY_Qtr' not in df.columns:
            df['CY_Qtr'] = df['cy_qtr']
        if 'provname' in df.columns and 'PROVNAME' not in df.columns:
            df['PROVNAME'] = df['provname']
        if 'state' in df.columns and 'STATE' not in df.columns:
            df['STATE'] = df['state']
        if 'county_name' in df.columns and 'COUNTY_NAME' not in df.columns:
            df['COUNTY_NAME'] = df['county_name']
        df = _restore_csv_column_names(df)
        schema_err = provider_df_schema_errors(df, ccn=prov)
        if schema_err:
            log_index_event(
                'provider_df_schema_error',
                ccn=prov,
                errors=schema_err,
            )
        return df
    except sqlite3.Error as e:
        log_index_event('sqlite_error', ccn=prov, error=str(e)[:200])
        return None


def sqlite_ccn_exists(prov: str) -> bool:
    """True when a CCN exists in facility_quarterly SQLite."""
    conn = _get_sqlite_conn()
    if conn is None:
        return False
    ccn = _norm_ccn(prov)
    if not ccn:
        return False
    try:
        cur = conn.execute(
            'SELECT 1 FROM facility_quarterly WHERE provnum = ? COLLATE NOCASE LIMIT 1',
            (ccn,),
        )
        return cur.fetchone() is not None
    except sqlite3.Error as e:
        log_index_event('sqlite_error', scope='ccn_exists', ccn=ccn, error=str(e)[:200])
        return False


def load_latest_hprd_by_ccn(cy_qtr: str) -> dict[str, dict] | None:
    """Latest-quarter HPRD metrics for all CCNs from SQLite facility_latest table."""
    conn = _get_sqlite_conn()
    if conn is None:
        return None
    qtr = str(cy_qtr or '').strip()
    if not qtr:
        return None
    try:
        cur = conn.execute(
            'SELECT provnum, total_nurse_hprd, rn_hprd, contract_percentage, avg_daily_census '
            'FROM facility_latest WHERE cy_qtr = ?',
            (qtr,),
        )
        out: dict[str, dict] = {}
        for row in cur.fetchall():
            ccn = _norm_ccn(row[0])
            if not ccn:
                continue
            out[ccn] = {
                'Total_Nurse_HPRD': row[1],
                'RN_HPRD': row[2],
                'Contract_Percentage': row[3],
                'avg_daily_census': row[4],
            }
        return out
    except sqlite3.Error as e:
        log_index_event('sqlite_error', scope='facility_latest', quarter=qtr, error=str(e)[:200])
        return None


def load_pickle_index(path: str, csv_path: str | None) -> Any | None:
    if not os.path.isfile(path) or not meta_matches_csv(csv_path):
        return None
    try:
        with open(path, 'rb') as f:
            payload = pickle.load(f)
        if isinstance(payload, dict) and 'index' in payload:
            return payload['index']
        return payload
    except Exception as e:
        log_index_event('pickle_load_failed', path=os.path.basename(path), error=str(e)[:200])
        return None


def save_pickle_index(path: str, index: Any, *, csv_path: str, meta_extra: dict | None = None) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        'index': index,
        'built_at': time.time(),
        'source_basename': os.path.basename(csv_path),
        'source_mtime': int(os.path.getmtime(csv_path)),
    }
    if meta_extra:
        payload.update(meta_extra)
    with open(path, 'wb') as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
