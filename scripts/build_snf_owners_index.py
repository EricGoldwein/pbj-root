#!/usr/bin/env python3
"""Build SQLite + org-name index from the newest SNF_All_Owners*.csv (Render build step)."""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ownership.owner_profile import (  # noqa: E402
    ENROLLMENT_PAC_COL,
    OWNER_PAC_COL,
    _CCN_MATCH_METHOD_RANK,
    _CSV_USECOLS,
    _norm_org_key,
    _resolve_ccn_with_method,
    normalize_associate_id,
    snf_owners_csv_path,
)

OWNERSHIP_DIR = REPO / "ownership"
DB_PATH = OWNERSHIP_DIR / "snf_owners_lookup.sqlite"
DB_BUILD_PATH = OWNERSHIP_DIR / "snf_owners_lookup.build.sqlite"
ORG_INDEX_PATH = OWNERSHIP_DIR / "snf_owners_org_index.json.gz"
CCN_INDEX_PATH = OWNERSHIP_DIR / "snf_owners_ccn_index.json.gz"
STATE_TOP_OWNERS_PATH = OWNERSHIP_DIR / "state_top_owners.json.gz"
STATE_OWNER_INDEX_PATH = OWNERSHIP_DIR / "state_owner_index.json.gz"
TABLE = "snf_owners"
CHUNK = 100_000


def _write_gzip_json(path: Path, data: Any) -> None:
    """Atomic gzip JSON write (avoids Windows lock/Errno 22 on in-place open)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _write_org_keys(org_map: dict[str, str], row: pd.Series) -> None:
    pac = normalize_associate_id(str(row.get(ENROLLMENT_PAC_COL) or ""))
    if len(pac) != 10:
        return
    for col in ("ORGANIZATION NAME", "DOING BUSINESS AS NAME - OWNER"):
        key = _norm_org_key(str(row.get(col) or ""))
        if key and key not in org_map:
            org_map[key] = pac


def _write_ccn_key(
    ccn_map: dict[str, dict[str, str]],
    seen_enrollment_pacs: set[str],
    row: pd.Series,
) -> None:
    pac = normalize_associate_id(str(row.get(ENROLLMENT_PAC_COL) or ""))
    if len(pac) != 10 or pac in seen_enrollment_pacs:
        return
    seen_enrollment_pacs.add(pac)
    org_name = str(row.get("ORGANIZATION NAME") or "")
    ccn, method = _resolve_ccn_with_method(org_name)
    if not ccn:
        return
    rank = _CCN_MATCH_METHOD_RANK.get(method or "", 0)
    prev = ccn_map.get(ccn)
    prev_rank = _CCN_MATCH_METHOD_RANK.get((prev or {}).get("method") or "", 0)
    if prev is None or rank > prev_rank:
        ccn_map[ccn] = {"pac": pac, "method": method or ""}


def promote_build_db() -> bool:
    """Replace live SQLite with the sidecar build. Returns False when live DB is locked (e.g. app.py)."""
    if not DB_BUILD_PATH.is_file():
        print(f"[build_snf_owners_index] No build DB at {DB_BUILD_PATH.name}")
        return False
    try:
        if DB_PATH.is_file():
            DB_PATH.unlink()
        DB_BUILD_PATH.replace(DB_PATH)
        print(f"[build_snf_owners_index] Promoted {DB_BUILD_PATH.name} -> {DB_PATH.name}")
        return True
    except PermissionError:
        print(
            f"[build_snf_owners_index] Live DB locked; kept {DB_BUILD_PATH.name}. "
            f"Stop app.py, then run: python scripts/build_snf_owners_index.py --promote-db"
        )
        return False


def build_derived_indexes(*, db_path: Path | None = None) -> None:
    """Gzip state indexes + search catalog from an existing SQLite owners DB."""
    db = db_path or DB_PATH
    if not db.is_file():
        print(f"[build_snf_owners_index] Skip derived indexes: missing {db.name}")
        sys.exit(1)
    print(f"[build_snf_owners_index] Derived indexes from {db.name}")
    build_state_top_owners(db_path=db)
    build_state_owner_index_lists(db_path=db)
    from ownership.owner_profile import write_public_owner_search_catalog_file  # noqa: E402

    n_ct = write_public_owner_search_catalog_file()
    print(f"[build_snf_owners_index] ct_owner_search_catalog: {n_ct:,} rows")
    from ownership.owner_indexability import refresh_owner_indexability_cache  # noqa: E402

    refresh_owner_indexability_cache()


def build_sqlite_from_csv(*, out_path: Path) -> None:
    csv_path = snf_owners_csv_path()
    if not csv_path or not csv_path.is_file():
        print(f"[build_snf_owners_index] No SNF owners CSV found under {OWNERSHIP_DIR}")
        sys.exit(1)

    print(f"[build_snf_owners_index] Source: {csv_path.name} -> {out_path.name}")
    if out_path.is_file():
        out_path.unlink()
    ORG_INDEX_PATH.unlink(missing_ok=True)
    CCN_INDEX_PATH.unlink(missing_ok=True)

    header = pd.read_csv(csv_path, nrows=0, encoding="latin-1").columns.tolist()
    cols = [c for c in _CSV_USECOLS if c in header]
    if ENROLLMENT_PAC_COL not in cols:
        print("[build_snf_owners_index] Missing enrollment PAC column in CSV")
        sys.exit(1)

    conn = sqlite3.connect(out_path)
    org_map: dict[str, str] = {}
    ccn_map: dict[str, dict[str, str]] = {}
    seen_enrollment_pacs: set[str] = set()
    total = 0
    try:
        for i, chunk in enumerate(
            pd.read_csv(
                csv_path,
                dtype=str,
                encoding="latin-1",
                low_memory=False,
                usecols=cols,
                chunksize=CHUNK,
            )
        ):
            chunk.to_sql(TABLE, conn, if_exists="append", index=False)
            for _, row in chunk.iterrows():
                _write_org_keys(org_map, row)
                _write_ccn_key(ccn_map, seen_enrollment_pacs, row)
            total += len(chunk)
            print(f"[build_snf_owners_index] rows {total:,}")
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_enrollment_pac ON "{TABLE}" ("{ENROLLMENT_PAC_COL}")'
        )
        if OWNER_PAC_COL in cols:
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS idx_owner_pac ON "{TABLE}" ("{OWNER_PAC_COL}")'
            )
        conn.commit()
    finally:
        conn.close()

    with gzip.open(ORG_INDEX_PATH, "wt", encoding="utf-8") as f:
        json.dump(org_map, f, separators=(",", ":"))

    with gzip.open(CCN_INDEX_PATH, "wt", encoding="utf-8") as f:
        json.dump(ccn_map, f, separators=(",", ":"))

    print(
        f"[build_snf_owners_index] Done: {out_path.name} ({out_path.stat().st_size // 1024 // 1024} MB), "
        f"{len(org_map):,} org keys -> {ORG_INDEX_PATH.name}, "
        f"{len(ccn_map):,} CCN keys -> {CCN_INDEX_PATH.name}"
    )


def build() -> None:
    build_sqlite_from_csv(out_path=DB_BUILD_PATH)
    build_derived_indexes(db_path=DB_BUILD_PATH)
    promote_build_db()


def build_state_top_owners(*, db_path: Path | None = None) -> None:
    """Precompute per-state top owner/control orgs (avoids full SQLite scan on each state page)."""
    from ownership.owner_profile import (  # noqa: E402
        OWNER_PAC_COL,
        _ccn_to_state_from_search_index,
        _facility_name_to_ccn,
        _legal_business_name_to_ccn,
        _norm_ccn_key,
        _norm_org_key,
        _owner_display_name,
        _resolve_ccn_with_method,
        _sqlite_row_to_dict,
        associate_profile_url,
        normalize_associate_id,
    )

    db = db_path or DB_PATH
    if not db.is_file():
        print("[build_snf_owners_index] Skip state_top_owners: no SQLite DB")
        return

    ccn_state = _ccn_to_state_from_search_index()
    legal_ccn = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()
    from ownership.role_classification import (  # noqa: E402
        accumulate_facility_link,
        facility_link_counts_from_buckets,
    )

    owner_link_buckets: dict[str, dict[str, set[str]]] = {}
    by_state: dict[str, dict[str, set[str]]] = {}
    meta: dict[str, dict[str, Any]] = {}

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{TABLE}")')]
        if OWNER_PAC_COL not in cols:
            print("[build_snf_owners_index] Skip state_top_owners: no owner PAC column")
            return
        for sql_row in conn.execute(f'SELECT * FROM "{TABLE}"'):
            row = _sqlite_row_to_dict(sql_row)
            fac = str(row.get("ORGANIZATION NAME") or "").strip()
            if not fac:
                continue
            key = _norm_org_key(fac)
            ccn = legal_ccn.get(key) or name_ccn.get(key) or _resolve_ccn_with_method(fac)[0]
            if not ccn:
                continue
            ccn_norm = _norm_ccn_key(ccn)
            fac_st = ccn_state.get(ccn_norm) or ""
            if not fac_st:
                continue
            ow_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
            if len(ow_pac) != 10:
                continue
            accumulate_facility_link(owner_link_buckets, ow_pac, ccn_norm, row)
            by_state.setdefault(fac_st, {}).setdefault(ow_pac, set()).add(ccn_norm)
            if ow_pac not in meta:
                meta[ow_pac] = {
                    "associate_id": ow_pac,
                    "name": _owner_display_name(row),
                    "profile_url": associate_profile_url(ow_pac),
                }
    finally:
        conn.close()

    out: dict[str, list[dict[str, Any]]] = {}
    for st, owners in sorted(by_state.items()):
        rows: list[dict[str, Any]] = []
        for pac, ccns in owners.items():
            m = meta.get(pac) or {}
            buckets = owner_link_buckets.get(pac) or {"any": ccns}
            counts = facility_link_counts_from_buckets(buckets)
            counts["facility_count"] = len(ccns)
            rows.append(
                {
                    "associate_id": pac,
                    "name": m.get("name") or pac,
                    "profile_url": m.get("profile_url") or associate_profile_url(pac),
                    **counts,
                }
            )
        rows.sort(key=lambda x: (-int(x.get("facility_count") or 0), str(x.get("name") or "")))
        out[st] = rows[:8]

    _write_gzip_json(STATE_TOP_OWNERS_PATH, out)

    ct = len(out.get("CT") or [])
    print(f"[build_snf_owners_index] state_top_owners: {len(out)} states, CT has {ct} rows -> {STATE_TOP_OWNERS_PATH.name}")


def build_state_owner_index_lists(*, db_path: Path | None = None) -> None:
    """Full owner/control org lists for state index pages (NY/CT public; FL draft)."""
    from ownership.state_owner_index import STATE_OWNER_INDEX_STATES  # noqa: E402
    from ownership.owner_profile import (  # noqa: E402
        OWNER_PAC_COL,
        _ccn_to_state_from_search_index,
        _facility_name_to_ccn,
        _legal_business_name_to_ccn,
        _norm_ccn_key,
        _norm_org_key,
        _owner_display_name,
        _resolve_ccn_with_method,
        _sqlite_row_to_dict,
        associate_profile_url,
        normalize_associate_id,
    )

    db = db_path or DB_PATH
    if not db.is_file():
        print("[build_snf_owners_index] Skip state_owner_index: no SQLite DB")
        return

    ccn_state = _ccn_to_state_from_search_index()
    legal_ccn = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()
    from ownership.role_classification import (  # noqa: E402
        accumulate_facility_link,
        facility_link_counts_from_buckets,
    )

    owner_link_buckets: dict[str, dict[str, set[str]]] = {}
    by_state: dict[str, dict[str, set[str]]] = {st: {} for st in STATE_OWNER_INDEX_STATES}
    total_by_pac: dict[str, set[str]] = {}
    meta: dict[str, dict[str, Any]] = {}

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{TABLE}")')]
        if OWNER_PAC_COL not in cols:
            print("[build_snf_owners_index] Skip state_owner_index: no owner PAC column")
            return
        for sql_row in conn.execute(f'SELECT * FROM "{TABLE}"'):
            row = _sqlite_row_to_dict(sql_row)
            fac = str(row.get("ORGANIZATION NAME") or "").strip()
            if not fac:
                continue
            key = _norm_org_key(fac)
            ccn = legal_ccn.get(key) or name_ccn.get(key) or _resolve_ccn_with_method(fac)[0]
            if not ccn:
                continue
            ccn_norm = _norm_ccn_key(ccn)
            fac_st = ccn_state.get(ccn_norm) or ""
            ow_pac = normalize_associate_id(row.get(OWNER_PAC_COL))
            if len(ow_pac) != 10:
                continue
            if fac_st:
                total_by_pac.setdefault(ow_pac, set()).add(ccn_norm)
            if fac_st not in STATE_OWNER_INDEX_STATES:
                continue
            accumulate_facility_link(owner_link_buckets, ow_pac, ccn_norm, row)
            by_state[fac_st].setdefault(ow_pac, set()).add(ccn_norm)
            if ow_pac not in meta:
                meta[ow_pac] = {
                    "associate_id": ow_pac,
                    "name": _owner_display_name(row),
                    "profile_url": associate_profile_url(ow_pac),
                }
    finally:
        conn.close()

    out: dict[str, list[dict[str, Any]]] = {}
    for st in sorted(STATE_OWNER_INDEX_STATES):
        owners = by_state.get(st) or {}
        rows: list[dict[str, Any]] = []
        for pac, ccns in owners.items():
            m = meta.get(pac) or {}
            buckets = owner_link_buckets.get(pac) or {"any": ccns}
            counts = facility_link_counts_from_buckets(buckets)
            counts["facility_count"] = len(ccns)
            rows.append(
                {
                    "associate_id": pac,
                    "name": m.get("name") or pac,
                    "profile_url": m.get("profile_url") or associate_profile_url(pac),
                    "facility_count_total": len(total_by_pac.get(pac) or set()),
                    **counts,
                }
            )
        rows.sort(key=lambda x: (-int(x.get("facility_count") or 0), str(x.get("name") or "")))
        out[st] = rows

    _write_gzip_json(STATE_OWNER_INDEX_PATH, out)

    counts = ", ".join(
        f"{st} {len(out.get(st) or []):,}" for st in sorted(STATE_OWNER_INDEX_STATES)
    )
    print(f"[build_snf_owners_index] state_owner_index: {counts} -> {STATE_OWNER_INDEX_PATH.name}")


if __name__ == "__main__":
    if "--index-only" in sys.argv:
        build_derived_indexes()
    elif "--promote-db" in sys.argv:
        if not promote_build_db():
            sys.exit(1)
    else:
        build()
