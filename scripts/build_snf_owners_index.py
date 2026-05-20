#!/usr/bin/env python3
"""Build SQLite + org-name index from the newest SNF_All_Owners*.csv (Render build step)."""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path

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


if __name__ == "__main__":
    build()
