"""Runtime loader for facility-quarter staffing compliance deploy bundle (public site).

Bundle layout (under data/compliance/):
- staffing_compliance_manifest.json
- staffing_compliance_summary.csv.gz  (committed for Render)
- staffing_compliance_summary.csv       (materialized at deploy)
- staffing_compliance_index.sqlite      (built at deploy for O(1) ccn+quarter lookup)
- staffing_compliance_thresholds.json   (config copy for labels / future states)

Premium flagged calendar days stay in PBJapp only (not shipped to pbj-root).
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sqlite3
import threading
from typing import Any, Mapping

BUNDLE_SCHEMA_VERSION = 1
DEFAULT_REL_DIR = os.path.join('data', 'compliance')
MANIFEST_NAME = 'staffing_compliance_manifest.json'
SUMMARY_GZ_NAME = 'staffing_compliance_summary.csv.gz'
SUMMARY_CSV_NAME = 'staffing_compliance_summary.csv'
INDEX_NAME = 'staffing_compliance_index.sqlite'
THRESHOLDS_NAME = 'staffing_compliance_thresholds.json'

_PUBLIC_COLUMNS = (
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

_MANIFEST_CACHE: dict[str, Any] | None = None
_MANIFEST_MTIME: float = 0.0
_THRESHOLDS_CACHE: dict[str, Any] | None = None
_THRESHOLDS_MTIME: float = 0.0
_LOOKUP_CACHE_MAX = max(64, int(os.environ.get('PBJ_COMPLIANCE_LOOKUP_CACHE_MAX', '512')))
_LOOKUP_CACHE: dict[tuple[str, str], dict[str, Any] | None] = {}
_LOOKUP_CACHE_ORDER: list[tuple[str, str]] = []
_LOOKUP_LOCK = threading.Lock()
_SQLITE_CONN: sqlite3.Connection | None = None
_SQLITE_LOCK = threading.Lock()


def _bundle_dir(app_root: str) -> str:
    override = (os.environ.get('PBJ_STAFFING_COMPLIANCE_DIR') or '').strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(app_root, override.replace('/', os.sep))
    return os.path.join(app_root, DEFAULT_REL_DIR)


def _file_mtime(path: str | None) -> float:
    if not path or not os.path.isfile(path):
        return 0.0
    try:
        return float(os.path.getmtime(path))
    except OSError:
        return 0.0


def manifest_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), MANIFEST_NAME)


def summary_gzip_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), SUMMARY_GZ_NAME)


def summary_csv_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), SUMMARY_CSV_NAME)


def index_sqlite_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), INDEX_NAME)


def thresholds_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), THRESHOLDS_NAME)


def normalize_ccn(raw: Any) -> str:
    s = str(raw or '').strip().upper()
    if '.' in s:
        s = s.split('.')[0]
    return s.zfill(6) if s else ''


def normalize_quarter(raw: Any) -> str:
    s = str(raw or '').strip().upper().replace(' ', '')
    if s.startswith('CY'):
        s = s[2:]
    m = re.match(r'^(\d{4})Q([1-4])$', s)
    if m:
        return f'CY{m.group(1)}Q{m.group(2)}'
    return str(raw or '').strip()


def load_manifest(app_root: str, *, force: bool = False) -> dict[str, Any] | None:
    global _MANIFEST_CACHE, _MANIFEST_MTIME
    path = manifest_path(app_root)
    mtime = _file_mtime(path)
    if not force and _MANIFEST_CACHE is not None and mtime == _MANIFEST_MTIME:
        return _MANIFEST_CACHE
    if not os.path.isfile(path):
        _MANIFEST_CACHE = None
        _MANIFEST_MTIME = 0.0
        return None
    try:
        data = json.loads(open(path, encoding='utf-8').read())
    except Exception as exc:
        print(f'[staffing_compliance_bundle] manifest load failed: {exc}', flush=True)
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get('bundle_schema_version', 0)) != BUNDLE_SCHEMA_VERSION:
        print('[staffing_compliance_bundle] manifest schema version mismatch', flush=True)
        return None
    _MANIFEST_CACHE = data
    _MANIFEST_MTIME = mtime
    return data


def bundle_available(app_root: str) -> bool:
    root = _bundle_dir(app_root)
    gz = os.path.join(root, SUMMARY_GZ_NAME)
    manifest = os.path.join(root, MANIFEST_NAME)
    return os.path.isfile(gz) and os.path.isfile(manifest)


def states_with_thresholds(app_root: str) -> list[str]:
    m = load_manifest(app_root) or {}
    states = m.get('states_with_thresholds') or []
    return [str(s).upper() for s in states]


def load_state_threshold_config(app_root: str, state_code: str) -> dict[str, Any] | None:
    """Row from staffing_compliance_thresholds.json for a configured state (CT, NY, …)."""
    global _THRESHOLDS_CACHE, _THRESHOLDS_MTIME
    st = str(state_code or '').strip().upper()[:2]
    if not st:
        return None
    path = thresholds_path(app_root)
    mtime = _file_mtime(path)
    if _THRESHOLDS_CACHE is None or mtime != _THRESHOLDS_MTIME:
        try:
            raw = json.loads(open(path, encoding='utf-8').read())
        except OSError:
            return None
        rows = raw.get('state_thresholds') or raw.get('thresholds') or []
        _THRESHOLDS_CACHE = {
            str(r.get('state', '')).upper(): r for r in rows if r.get('enabled', True)
        }
        _THRESHOLDS_MTIME = mtime
    row = (_THRESHOLDS_CACHE or {}).get(st)
    return dict(row) if row else None


def state_threshold_modal_note(app_root: str, state_code: str) -> str:
    """Optional accuracy/context line for Details modal (statute vs PBJ metric)."""
    row = load_state_threshold_config(app_root, state_code) or {}
    note = str(row.get('notes') or '').strip()
    return note


def quarters_in_bundle(app_root: str) -> list[str]:
    m = load_manifest(app_root) or {}
    return [normalize_quarter(q) for q in (m.get('quarters_in_bundle') or [])]


def materialize_summary_csv(app_root: str) -> str | None:
    """Decompress summary gzip to CSV if needed (Render deploy)."""
    gz = summary_gzip_path(app_root)
    csv = summary_csv_path(app_root)
    if os.path.isfile(csv) and _file_mtime(csv) >= _file_mtime(gz):
        return csv
    if not os.path.isfile(gz):
        return csv if os.path.isfile(csv) else None
    os.makedirs(os.path.dirname(csv) or app_root, exist_ok=True)
    with gzip.open(gz, 'rb') as f_in, open(csv, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    return csv


def _sqlite_connect(app_root: str) -> sqlite3.Connection | None:
    global _SQLITE_CONN
    db_path = index_sqlite_path(app_root)
    if not os.path.isfile(db_path):
        return None
    with _SQLITE_LOCK:
        if _SQLITE_CONN is None:
            _SQLITE_CONN = sqlite3.connect(db_path, check_same_thread=False)
            _SQLITE_CONN.row_factory = sqlite3.Row
        return _SQLITE_CONN


def _lookup_cache_set(key: tuple[str, str], value: dict[str, Any] | None) -> None:
    with _LOOKUP_LOCK:
        if key in _LOOKUP_CACHE:
            try:
                _LOOKUP_CACHE_ORDER.remove(key)
            except ValueError:
                pass
        _LOOKUP_CACHE[key] = value
        _LOOKUP_CACHE_ORDER.append(key)
        while len(_LOOKUP_CACHE_ORDER) > _LOOKUP_CACHE_MAX:
            old = _LOOKUP_CACHE_ORDER.pop(0)
            _LOOKUP_CACHE.pop(old, None)


def lookup_cache_stats() -> dict[str, int]:
    with _LOOKUP_LOCK:
        return {'entries': len(_LOOKUP_CACHE), 'max_entries': _LOOKUP_CACHE_MAX}


def lookup_public_summary(app_root: str, ccn: str, quarter: str) -> dict[str, Any] | None:
    """Return public-safe compliance counts for facility × quarter, or None."""
    prov = normalize_ccn(ccn)
    q = normalize_quarter(quarter)
    if not prov or not q:
        return None
    key = (prov, q)
    with _LOOKUP_LOCK:
        if key in _LOOKUP_CACHE:
            hit = _LOOKUP_CACHE[key]
            try:
                _LOOKUP_CACHE_ORDER.remove(key)
                _LOOKUP_CACHE_ORDER.append(key)
            except ValueError:
                pass
            return hit

    conn = _sqlite_connect(app_root)
    row_dict: dict[str, Any] | None = None
    if conn is not None:
        cur = conn.execute(
            'SELECT * FROM compliance_summary WHERE ccn = ? AND quarter = ? LIMIT 1',
            (prov, q),
        )
        row = cur.fetchone()
        if row is not None:
            row_dict = {k: row[k] for k in row.keys()}

    if row_dict is None:
        # Fallback: duckdb/pandas not required; skip if no index
        row_dict = None

    if row_dict is not None:
        out = {k: row_dict.get(k) for k in _PUBLIC_COLUMNS}
        out['ccn'] = prov
        out['quarter'] = q
        _lookup_cache_set(key, out)
        return out

    _lookup_cache_set(key, None)
    return None


def format_public_summary_sentences(summary: Mapping[str, Any]) -> list[str]:
    """Human-readable count lines for provider page (no flagged dates)."""
    if not summary:
        return []
    lines: list[str] = []
    total = summary.get('total_days_reported')
    try:
        total_i = int(total) if total is not None else 0
    except (TypeError, ValueError):
        total_i = 0

    def _day_word(n: int) -> str:
        return 'day' if n == 1 else 'days'

    rn8 = summary.get('rn_below_8hr_days_count')
    if rn8 is not None and not (isinstance(rn8, float) and rn8 != rn8):
        try:
            n = int(rn8)
            if n > 0:
                lines.append(f'{n} {_day_word(n)} with total RN hours under 8 reported')
        except (TypeError, ValueError):
            pass

    rn0 = summary.get('rn_0_days_count')
    if rn0 is not None and not (isinstance(rn0, float) and rn0 != rn0):
        try:
            n = int(rn0)
            if n > 0:
                lines.append(f'{n} {_day_word(n)} with zero total RN hours reported')
        except (TypeError, ValueError):
            pass

    below = summary.get('below_state_min_days_count')
    label = (summary.get('state_min_label') or '').strip()
    if below is not None and not (isinstance(below, float) and below != below):
        try:
            n = int(below)
            if n > 0:
                if label:
                    lines.append(f'{n} {_day_word(n)} below state staffing threshold ({label})')
                else:
                    lines.append(f'{n} {_day_word(n)} below state staffing threshold')
        except (TypeError, ValueError):
            pass

    if not lines and total_i > 0:
        return []
    return lines


def invalidate_caches() -> None:
    global _MANIFEST_CACHE, _MANIFEST_MTIME, _SQLITE_CONN
    with _LOOKUP_LOCK:
        _LOOKUP_CACHE.clear()
        _LOOKUP_CACHE_ORDER.clear()
    _MANIFEST_CACHE = None
    _MANIFEST_MTIME = 0.0
    with _SQLITE_LOCK:
        if _SQLITE_CONN is not None:
            try:
                _SQLITE_CONN.close()
            except Exception:
                pass
            _SQLITE_CONN = None
