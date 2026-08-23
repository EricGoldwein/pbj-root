"""Runtime loader for compact public staffing day-evidence bundle (read-only).

Bundle layout (under data/evidence/):
- staffing_day_evidence_manifest.json  (git — pointer + sha256)
- staffing_day_evidence.sqlite.gz      (GitHub Release — not in git)
- staffing_day_evidence.sqlite         (materialized at deploy)

Schema: day_fact — one row per (ccn, work_date) with CMS hour/census inputs
and PBJapp-precomputed HPRD floats. pbj-root assembles evidence responses from
stored fields and does not recalculate HPRD.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sqlite3
import threading
from typing import Any

BUNDLE_SCHEMA_VERSION = 2
DEFAULT_REL_DIR = os.path.join("data", "evidence")
MANIFEST_NAME = "staffing_day_evidence_manifest.json"
SQLITE_NAME = "staffing_day_evidence.sqlite"
SQLITE_GZ_NAME = "staffing_day_evidence.sqlite.gz"

_SUPPORTED_METRICS = frozenset(
    {
        "CNA_HPRD",
        "RN_HPRD",
        "LPN_HPRD",
        "Total_Nurse_Aide_HPRD",
        "Total_RN_HPRD",
    }
)

# Metric -> (stored HPRD column, CMS hour columns used for provenance display)
_METRIC_SPEC: dict[str, tuple[str, tuple[str, ...]]] = {
    "RN_HPRD": ("rn_hprd", ("Hrs_RN",)),
    "CNA_HPRD": ("cna_hprd", ("Hrs_CNA",)),
    "LPN_HPRD": ("lpn_hprd", ("Hrs_LPN",)),
    "Total_RN_HPRD": ("total_rn_hprd", ("Hrs_RN", "Hrs_RNadmin", "Hrs_RNDON")),
    "Total_Nurse_Aide_HPRD": ("total_nurse_aide_hprd", ("Hrs_CNA", "Hrs_NAtrn", "Hrs_MedAide")),
}

_HOUR_COL_TO_FIELD = {
    "Hrs_RN": "hrs_rn",
    "Hrs_RNadmin": "hrs_rnadmin",
    "Hrs_RNDON": "hrs_rndon",
    "Hrs_LPN": "hrs_lpn",
    "Hrs_LPNadmin": "hrs_lpnadmin",
    "Hrs_CNA": "hrs_cna",
    "Hrs_NAtrn": "hrs_natrn",
    "Hrs_MedAide": "hrs_medaide",
}

METRIC_DISPLAY_NAMES = {
    "CNA_HPRD": "CNA HPRD",
    "RN_HPRD": "RN HPRD",
    "LPN_HPRD": "LPN HPRD",
    "Total_Nurse_Aide_HPRD": "Total Nurse Aide HPRD",
    "Total_RN_HPRD": "Total RN HPRD",
}

_MANIFEST_CACHE: dict[str, Any] | None = None
_MANIFEST_MTIME: float = 0.0
_SQLITE_CONN: sqlite3.Connection | None = None
_SQLITE_LOCK = threading.Lock()
_LOOKUP_CACHE_MAX = max(32, int(os.environ.get("PBJ_EVIDENCE_LOOKUP_CACHE_MAX", "256")))
_LOOKUP_CACHE: dict[tuple[str, str, str], dict[str, Any] | None] = {}
_LOOKUP_ORDER: list[tuple[str, str, str]] = []
_DAY_CACHE: dict[tuple[str, str], dict[str, Any] | None] = {}
_DAY_CACHE_ORDER: list[tuple[str, str]] = []


def _bundle_dir(app_root: str) -> str:
    override = (os.environ.get("PBJ_STAFFING_EVIDENCE_DIR") or "").strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(app_root, override.replace("/", os.sep))
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


def sqlite_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), SQLITE_NAME)


def sqlite_gzip_path(app_root: str) -> str:
    return os.path.join(_bundle_dir(app_root), SQLITE_GZ_NAME)


def normalize_ccn(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if "." in s:
        s = s.split(".")[0]
    if not re.fullmatch(r"[A-Z0-9]{1,6}", s or ""):
        return ""
    return s.zfill(6)


def normalize_work_date(raw: Any) -> str:
    s = str(raw or "").strip().replace(".0", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    return ""


def normalize_metric(raw: Any) -> str:
    m = str(raw or "").strip()
    return m if m in _SUPPORTED_METRICS else ""


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
        data = json.loads(open(path, encoding="utf-8").read())
    except Exception as exc:
        print(f"[staffing_evidence_bundle] manifest load failed: {exc}", flush=True)
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("bundle_schema_version", 0)) != BUNDLE_SCHEMA_VERSION:
        print("[staffing_evidence_bundle] manifest schema version mismatch", flush=True)
        return None
    _MANIFEST_CACHE = data
    _MANIFEST_MTIME = mtime
    return data


def bundle_available(app_root: str) -> bool:
    root = _bundle_dir(app_root)
    manifest = os.path.join(root, MANIFEST_NAME)
    sqlite = os.path.join(root, SQLITE_NAME)
    gz = os.path.join(root, SQLITE_GZ_NAME)
    return os.path.isfile(manifest) and (os.path.isfile(sqlite) or os.path.isfile(gz))


def materialize_sqlite(app_root: str) -> str | None:
    gz = sqlite_gzip_path(app_root)
    db = sqlite_path(app_root)
    if os.path.isfile(db) and _file_mtime(db) >= _file_mtime(gz):
        return db
    if not os.path.isfile(gz):
        return db if os.path.isfile(db) else None
    os.makedirs(os.path.dirname(db) or app_root, exist_ok=True)
    with gzip.open(gz, "rb") as f_in, open(db, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    return db


def invalidate_caches() -> None:
    global _SQLITE_CONN, _MANIFEST_CACHE, _MANIFEST_MTIME
    with _SQLITE_LOCK:
        if _SQLITE_CONN is not None:
            try:
                _SQLITE_CONN.close()
            except Exception:
                pass
            _SQLITE_CONN = None
    _MANIFEST_CACHE = None
    _MANIFEST_MTIME = 0.0
    _LOOKUP_CACHE.clear()
    _LOOKUP_ORDER.clear()
    _DAY_CACHE.clear()
    _DAY_CACHE_ORDER.clear()


def _sqlite_connect(app_root: str) -> sqlite3.Connection | None:
    global _SQLITE_CONN
    db = materialize_sqlite(app_root)
    if not db or not os.path.isfile(db):
        return None
    with _SQLITE_LOCK:
        if _SQLITE_CONN is None:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _SQLITE_CONN = conn
        return _SQLITE_CONN


def _cache_put(key: tuple[str, str, str], val: dict[str, Any] | None) -> None:
    if key in _LOOKUP_CACHE:
        _LOOKUP_CACHE[key] = val
        return
    _LOOKUP_CACHE[key] = val
    _LOOKUP_ORDER.append(key)
    while len(_LOOKUP_ORDER) > _LOOKUP_CACHE_MAX:
        old = _LOOKUP_ORDER.pop(0)
        _LOOKUP_CACHE.pop(old, None)


def _day_cache_put(key: tuple[str, str], val: dict[str, Any] | None) -> None:
    if key in _DAY_CACHE:
        _DAY_CACHE[key] = val
        return
    _DAY_CACHE[key] = val
    _DAY_CACHE_ORDER.append(key)
    while len(_DAY_CACHE_ORDER) > _LOOKUP_CACHE_MAX:
        old = _DAY_CACHE_ORDER.pop(0)
        _DAY_CACHE.pop(old, None)


def _fetch_day_fact(app_root: str, ccn: str, work_date: str) -> dict[str, Any] | None:
    key = (ccn, work_date)
    if key in _DAY_CACHE:
        cached = _DAY_CACHE[key]
        return dict(cached) if cached else None
    conn = _sqlite_connect(app_root)
    if conn is None:
        _day_cache_put(key, None)
        return None
    try:
        row = conn.execute(
            "SELECT * FROM day_fact WHERE ccn = ? AND work_date = ?",
            (ccn, work_date),
        ).fetchone()
    except Exception as exc:
        print(f"[staffing_evidence_bundle] day_fact lookup failed: {exc}", flush=True)
        _day_cache_put(key, None)
        return None
    if not row:
        _day_cache_put(key, None)
        return None
    payload = {k: row[k] for k in row.keys()}
    _day_cache_put(key, payload)
    return dict(payload)


def _provenance_precision(row: dict[str, Any]) -> str:
    sha = row.get("source_file_sha256")
    ordinal = row.get("source_raw_row_ordinal")
    if sha and ordinal is not None:
        return "exact_record"
    if row.get("source_file_basename") or row.get("ccn"):
        return "dataset_and_key"
    return "reconstructed"


def assemble_evidence_from_day_fact(row: dict[str, Any], metric: str) -> dict[str, Any] | None:
    """Assemble public evidence payload from stored day_fact fields.

    Uses PBJapp-precomputed HPRD float for ``value``. Does not divide hours/census.
    Hour column values are CMS-published inputs used only for provenance display.
    """
    met = normalize_metric(metric)
    if not met or met not in _METRIC_SPEC:
        return None
    hprd_col, hour_cols = _METRIC_SPEC[met]
    stored_val = row.get(hprd_col)
    if stored_val is None:
        return None
    try:
        hprd = float(stored_val)
    except (TypeError, ValueError):
        return None

    census = float(row.get("mds_census") or 0)
    hour_detail: dict[str, float] = {}
    hours_total = 0.0
    for col in hour_cols:
        field = _HOUR_COL_TO_FIELD[col]
        val = round(float(row.get(field) or 0), 4)
        hour_detail[col] = val
        hours_total += val
    hours_total = round(hours_total, 4)

    ccn = str(row.get("ccn") or "")
    work_date = str(row.get("work_date") or "")
    quarter = str(row.get("quarter") or "")
    src_base = row.get("source_file_basename") or None
    src_sha = row.get("source_file_sha256") or None
    src_ord = row.get("source_raw_row_ordinal")
    try:
        src_ord_i = int(src_ord) if src_ord is not None else None
    except (TypeError, ValueError):
        src_ord_i = None
    csv_line = (src_ord_i + 2) if src_ord_i is not None else None
    precision = _provenance_precision(row)
    source_record_id = row.get("source_record_id") or None

    pbj_daily_loc = {
        "source_type": "cms_pbj_daily",
        "provenance_precision": precision,
        "dataset": "CMS PBJ Daily Nurse Staffing",
        "release": quarter,
        "ccn": ccn,
        "work_date": work_date,
        "raw_values": hour_detail,
    }
    if src_base:
        pbj_daily_loc["source_file"] = src_base
    if src_sha:
        pbj_daily_loc["source_file_sha256"] = src_sha
    if src_ord_i is not None:
        pbj_daily_loc["raw_row_ordinal"] = src_ord_i
    if csv_line is not None:
        pbj_daily_loc["csv_line_number"] = csv_line
    if source_record_id:
        pbj_daily_loc["source_record_id"] = source_record_id

    census_loc = {
        "source_type": "cms_pbj_daily",
        "provenance_precision": precision,
        "dataset": "CMS PBJ Daily Nurse Staffing",
        "release": quarter,
        "ccn": ccn,
        "work_date": work_date,
        "raw_values": {"MDScensus": round(census, 2)},
    }
    if src_base:
        census_loc["source_file"] = src_base
    if src_sha:
        census_loc["source_file_sha256"] = src_sha
    if src_ord_i is not None:
        census_loc["raw_row_ordinal"] = src_ord_i
    if csv_line is not None:
        census_loc["csv_line_number"] = csv_line
    if source_record_id:
        census_loc["source_record_id"] = source_record_id

    # Display formula uses stored CMS inputs + stored HPRD (no recomputation of value).
    formula_str = f"{hours_total} hours / {round(census, 2)} residents = {hprd} HPRD"
    precision_label = {
        "exact_record": "Source record available",
        "dataset_and_key": "Source dataset and record keys available",
        "derived": "Calculated from contributing records",
        "reconstructed": "Source dataset identified; original row not retained",
    }.get(precision, precision)

    return {
        "metric": met,
        "metric_display": METRIC_DISPLAY_NAMES.get(met, met),
        "value": hprd,
        "formula": formula_str,
        "provenance_precision": precision,
        "provenance_label": precision_label,
        "numerator": {
            "label": "Qualifying hours",
            "total": hours_total,
            "columns_used": list(hour_cols),
            "column_values": hour_detail,
            "source": pbj_daily_loc,
            "provenance_precision": precision,
        },
        "denominator": {
            "label": "MDS census (residents)",
            "value": round(census, 2),
            "column": "MDScensus",
            "source": census_loc,
            "provenance_precision": precision,
        },
        "employee_count": 0,
        "ccn": ccn,
        "work_date": work_date,
        "quarter": quarter,
        "source_record_id": source_record_id,
    }


def lookup_day_evidence(
    app_root: str,
    ccn: str,
    work_date: str,
    metric: str,
) -> dict[str, Any] | None:
    """Return assembled evidence for one facility-day metric, or None."""
    prov = normalize_ccn(ccn)
    date = normalize_work_date(work_date)
    met = normalize_metric(metric or "RN_HPRD")
    if not prov or not date or not met:
        return None
    key = (prov, date, met)
    if key in _LOOKUP_CACHE:
        cached = _LOOKUP_CACHE[key]
        return dict(cached) if cached else None

    fact = _fetch_day_fact(app_root, prov, date)
    if not fact:
        _cache_put(key, None)
        return None
    payload = assemble_evidence_from_day_fact(fact, met)
    if not payload:
        _cache_put(key, None)
        return None
    _cache_put(key, payload)
    return dict(payload)


def supported_metrics() -> frozenset[str]:
    return _SUPPORTED_METRICS
