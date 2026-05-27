#!/usr/bin/env python3
"""Build snf_owners_ccn_index.json.gz (exact name matches only — finishes in seconds)."""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ownership.owner_profile import (  # noqa: E402
    ENROLLMENT_PAC_COL,
    _OWNERS_TABLE,
    _facility_name_to_ccn,
    _legal_business_name_to_ccn,
    _norm_ccn_key,
    _norm_org_key,
    normalize_associate_id,
)

DB_PATH = REPO / "ownership" / "snf_owners_lookup.sqlite"
OUT_PATH = REPO / "ownership" / "snf_owners_ccn_index.json.gz"


def main() -> None:
    if not DB_PATH.is_file():
        print(f"[build_snf_owners_ccn_index] Missing {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    legal_map = _legal_business_name_to_ccn()
    name_ccn = _facility_name_to_ccn()

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        f'SELECT DISTINCT "{ENROLLMENT_PAC_COL}", "ORGANIZATION NAME" FROM "{_OWNERS_TABLE}"'
    ).fetchall()
    conn.close()

    ccn_map: dict[str, dict[str, str]] = {}
    for pac_raw, org_name in rows:
        pac = normalize_associate_id(str(pac_raw or ""))
        if len(pac) != 10:
            continue
        key = _norm_org_key(str(org_name or ""))
        if not key:
            continue
        ccn = legal_map.get(key) or name_ccn.get(key)
        if not ccn:
            continue
        ccn_norm = _norm_ccn_key(ccn)
        if not ccn_norm:
            continue
        method = "legal_exact" if key in legal_map else "name_exact"
        prev = ccn_map.get(ccn_norm)
        prev_method = (prev or {}).get("method") or ""
        if prev is None or (method == "legal_exact" and prev_method != "legal_exact"):
            ccn_map[ccn_norm] = {"pac": pac, "method": method}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT_PATH, "wt", encoding="utf-8") as f:
        json.dump(ccn_map, f, separators=(",", ":"))

    print(
        f"[build_snf_owners_ccn_index] Wrote {len(ccn_map):,} CCN keys -> {OUT_PATH.name} "
        f"({OUT_PATH.stat().st_size // 1024} KB)"
    )


if __name__ == "__main__":
    main()
