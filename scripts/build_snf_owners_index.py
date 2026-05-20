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
    _CSV_USECOLS,
    _norm_org_key,
    normalize_associate_id,
    snf_owners_csv_path,
)

OWNERSHIP_DIR = REPO / "ownership"
DB_PATH = OWNERSHIP_DIR / "snf_owners_lookup.sqlite"
ORG_INDEX_PATH = OWNERSHIP_DIR / "snf_owners_org_index.json.gz"
STATE_TOP_OWNERS_PATH = OWNERSHIP_DIR / "state_top_owners.json.gz"
TABLE = "snf_owners"
CHUNK = 100_000


def _write_org_keys(org_map: dict[str, str], row: pd.Series) -> None:
    pac = normalize_associate_id(str(row.get(ENROLLMENT_PAC_COL) or ""))
    if len(pac) != 10:
        return
    for col in ("ORGANIZATION NAME", "DOING BUSINESS AS NAME - OWNER"):
        key = _norm_org_key(str(row.get(col) or ""))
        if key and key not in org_map:
            org_map[key] = pac


def build() -> None:
    csv_path = snf_owners_csv_path()
    if not csv_path or not csv_path.is_file():
        print(f"[build_snf_owners_index] No SNF owners CSV found under {OWNERSHIP_DIR}")
        sys.exit(1)

    print(f"[build_snf_owners_index] Source: {csv_path.name}")
    if DB_PATH.is_file():
        DB_PATH.unlink()
    ORG_INDEX_PATH.unlink(missing_ok=True)

    header = pd.read_csv(csv_path, nrows=0, encoding="latin-1").columns.tolist()
    cols = [c for c in _CSV_USECOLS if c in header]
    if ENROLLMENT_PAC_COL not in cols:
        print("[build_snf_owners_index] Missing enrollment PAC column in CSV")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    org_map: dict[str, str] = {}
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

    print(
        f"[build_snf_owners_index] Done: {DB_PATH.name} ({DB_PATH.stat().st_size // 1024 // 1024} MB), "
        f"{len(org_map):,} org keys -> {ORG_INDEX_PATH.name}"
    )
    build_state_top_owners()


def build_state_top_owners() -> None:
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

    if not DB_PATH.is_file():
        print("[build_snf_owners_index] Skip state_top_owners: no SQLite DB")
        return

    ccn_state = _ccn_to_state_from_search_index()
    legal_ccn = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()
    by_state: dict[str, dict[str, set[str]]] = {}
    meta: dict[str, dict[str, Any]] = {}

    conn = sqlite3.connect(DB_PATH)
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
            rows.append(
                {
                    "associate_id": pac,
                    "name": m.get("name") or pac,
                    "facility_count": len(ccns),
                    "profile_url": m.get("profile_url") or associate_profile_url(pac),
                }
            )
        rows.sort(key=lambda x: (-int(x.get("facility_count") or 0), str(x.get("name") or "")))
        out[st] = rows[:8]

    with gzip.open(STATE_TOP_OWNERS_PATH, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))

    ct = len(out.get("CT") or [])
    print(f"[build_snf_owners_index] state_top_owners: {len(out)} states, CT has {ct} rows -> {STATE_TOP_OWNERS_PATH.name}")


if __name__ == "__main__":
    build()
