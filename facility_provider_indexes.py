"""Precomputed facility/provider lookup artifacts (SQLite + pickle) for fast /provider cold path."""

from __future__ import annotations

import json
import os
import pickle
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

_SQLITE_CONN: sqlite3.Connection | None = None
_SQLITE_LOCK = threading.Lock()
_META_CACHE: dict[str, Any] | None = None


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
        'ok': bool(csv_path) and sqlite_exists() and meta_exists() and matches,
        'index_dir': INDEX_DIR,
        'sqlite_exists': sqlite_exists(),
        'meta_exists': meta_exists(),
        'percentile_pkl_exists': os.path.isfile(PERCENTILE_PKL),
        'contract_pkl_exists': os.path.isfile(CONTRACT_PKL),
        'meta_matches_csv': matches,
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
        cur = conn.execute(
            'SELECT * FROM facility_quarterly WHERE provnum = ? ORDER BY cy_qtr',
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
        return df
    except sqlite3.Error as e:
        log_index_event('sqlite_error', ccn=prov, error=str(e)[:200])
        return None


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
            ccn = str(row[0] or '').strip().zfill(6)
            if len(ccn) != 6:
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
