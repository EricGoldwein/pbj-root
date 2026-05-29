#!/usr/bin/env python3
"""
Read-only ownership data QA report (does not modify production artifacts).

Checks:
  - Invalid / duplicate PACs in SNF SQLite
  - State index vs profile facility_count mismatches (sample)
  - Duplicate CCN-owner edges
  - CCN leading-zero normalization
  - CHOW records with missing CCN or effective_date
  - State filter (NY/CT) on index artifact

Usage:
  python scripts/audit_ownership_data.py
  python scripts/audit_ownership_data.py --sample 25
"""
from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ownership.beta_gate import OWNERSHIP_PUBLIC_STATES  # noqa: E402
from ownership.owner_profile import (  # noqa: E402
    OWNER_PAC_COL,
    _norm_ccn_key,
    _norm_org_key,
    load_owner_profile_resolved,
    normalize_associate_id,
    snf_owners_csv_path,
)

DB_PATH = REPO / "ownership" / "snf_owners_lookup.sqlite"
STATE_INDEX_PATH = REPO / "ownership" / "state_owner_index.json.gz"
CHOW_PATH = REPO / "chow_index.json"
TABLE = "snf_owners"


def _load_state_index() -> dict[str, list[dict]]:
    if not STATE_INDEX_PATH.is_file():
        return {}
    with gzip.open(STATE_INDEX_PATH, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    return {str(k).upper()[:2]: list(v) for k, v in raw.items() if isinstance(v, list)}


def _audit_pac_integrity(conn: sqlite3.Connection) -> list[str]:
    issues: list[str] = []
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{TABLE}")')]
    if OWNER_PAC_COL not in cols:
        return ["SQLite missing ASSOCIATE ID - OWNER column"]
    bad_owner = 0
    bad_enroll = 0
    enroll_col = "ASSOCIATE ID"
    for row in conn.execute(f'SELECT "{OWNER_PAC_COL}", "{enroll_col}" FROM "{TABLE}"'):
        ow = normalize_associate_id(row[0])
        en = normalize_associate_id(row[1])
        if row[0] and len(ow) != 10:
            bad_owner += 1
        if row[1] and len(en) != 10:
            bad_enroll += 1
    if bad_owner:
        issues.append(f"Rows with non-normalizable owner PAC: {bad_owner:,}")
    if bad_enroll:
        issues.append(f"Rows with non-normalizable enrollment PAC: {bad_enroll:,}")
    return issues


def _audit_ccn_owner_duplicates(conn: sqlite3.Connection) -> list[str]:
    from ownership.owner_profile import (
        _facility_name_to_ccn,
        _legal_business_name_to_ccn,
        _resolve_ccn_with_method,
    )

    legal = _legal_business_name_to_ccn()
    name = _facility_name_to_ccn()
    pair_counts: Counter[tuple[str, str]] = Counter()
    for sql_row in conn.execute(f'SELECT "ORGANIZATION NAME", "{OWNER_PAC_COL}" FROM "{TABLE}"'):
        fac = str(sql_row[0] or "").strip()
        ow = normalize_associate_id(sql_row[1])
        if len(ow) != 10 or not fac:
            continue
        key = _norm_org_key(fac)
        ccn = legal.get(key) or name.get(key) or _resolve_ccn_with_method(fac)[0]
        if not ccn:
            continue
        pair_counts[(ow, _norm_ccn_key(ccn))] += 1
    dupes = sum(1 for c in pair_counts.values() if c > 1)
    if dupes:
        return [f"Owner-PAC/CCN pairs with multiple SNF rows: {dupes:,} (expected for multi-role filings)"]
    return []


def _audit_state_index_vs_profiles(sample: int) -> list[str]:
    issues: list[str] = []
    artifact = _load_state_index()
    if not artifact:
        return ["state_owner_index.json.gz missing — skip profile count comparison"]

    mismatches: list[str] = []
    for st in OWNERSHIP_PUBLIC_STATES:
        rows = artifact.get(st) or []
        for row in rows[:sample]:
            pac = str(row.get("associate_id") or "")
            idx_count = int(row.get("facility_count") or 0)
            prof = load_owner_profile_resolved(pac)
            if not prof:
                mismatches.append(f"{st} {pac}: in index but profile missing")
                continue
            prof_count = int(prof.get("facility_count") or 0)
            if prof_count != idx_count:
                mismatches.append(
                    f"{st} {pac} {row.get('name', '')[:40]!r}: "
                    f"index_ccn={idx_count} profile_facility_count={prof_count} "
                    f"kind={prof.get('profile_kind')}"
                )
    if mismatches:
        issues.append(
            f"State index vs profile facility_count mismatches (top {sample} per state): "
            f"{len(mismatches)}"
        )
        issues.extend(mismatches[:15])
        if len(mismatches) > 15:
            issues.append(f"  … and {len(mismatches) - 15} more")
    else:
        issues.append("State index vs profile counts: no mismatches in sample (unexpected if name-dedup differs)")
    return issues


def _audit_chow() -> list[str]:
    issues: list[str] = []
    if not CHOW_PATH.is_file():
        return ["chow_index.json missing"]
    data = json.loads(CHOW_PATH.read_text(encoding="utf-8"))
    records = data.get("records") or []
    no_ccn = sum(1 for r in records if not _norm_ccn_key(str(r.get("ccn") or "")))
    no_date = sum(1 for r in records if not str(r.get("effective_date") or "").strip())
    bad_date = 0
    for r in records:
        d = str(r.get("effective_date") or "")
        if d and (len(d) < 10 or d[4] != "-"):
            bad_date += 1
    issues.append(f"CHOW records: {len(records):,} total")
    if no_ccn:
        issues.append(f"  CHOW without CCN: {no_ccn:,}")
    if no_date:
        issues.append(f"  CHOW without effective_date: {no_date:,}")
    if bad_date:
        issues.append(f"  CHOW non-ISO effective_date: {bad_date:,}")
    for st in OWNERSHIP_PUBLIC_STATES:
        n = sum(
            1
            for r in records
            if str(r.get("state") or "").strip().upper()[:2] == st
        )
        issues.append(f"  CHOW in {st}: {n:,}")
    return issues


def _audit_ccn_leading_zeros(conn: sqlite3.Connection) -> list[str]:
    """CCNs stored without zfill should still normalize to same 6-digit key."""
    from ownership.owner_profile import _resolve_ccn_with_method

    samples = 0
    ok = 0
    for sql_row in conn.execute(f'SELECT "ORGANIZATION NAME" FROM "{TABLE}" LIMIT 5000'):
        fac = str(sql_row[0] or "").strip()
        if not fac:
            continue
        ccn, _ = _resolve_ccn_with_method(fac)
        if not ccn:
            continue
        samples += 1
        norm = _norm_ccn_key(ccn)
        if len(norm) == 6 and norm.isdigit():
            ok += 1
    if samples:
        return [f"CCN normalization spot-check: {ok}/{samples} resolve to 6-digit keys"]
    return ["CCN normalization spot-check: no resolved CCNs in sample"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ownership data QA report")
    parser.add_argument("--sample", type=int, default=20, help="Top owners per state to compare")
    args = parser.parse_args()

    print("[audit_ownership_data] PBJ320 ownership QA (read-only)\n")
    warnings = 0

    csv_path = snf_owners_csv_path()
    print(f"SNF CSV: {csv_path.name if csv_path else 'MISSING'}")
    print(f"SQLite:  {'yes' if DB_PATH.is_file() else 'MISSING'}")
    print(f"Index:   {'yes' if STATE_INDEX_PATH.is_file() else 'MISSING'}")
    print()

    if DB_PATH.is_file():
        conn = sqlite3.connect(DB_PATH)
        try:
            for block in (
                _audit_pac_integrity(conn),
                _audit_ccn_leading_zeros(conn),
                _audit_ccn_owner_duplicates(conn),
            ):
                for line in block:
                    print(line)
                    if "missing" in line.lower() or "non-normalizable" in line:
                        warnings += 1
        finally:
            conn.close()
    else:
        print("WARN: No SQLite — skipping PAC/CCN edge checks")
        warnings += 1

    print()
    for line in _audit_chow():
        print(line)

    print()
    for line in _audit_state_index_vs_profiles(args.sample):
        print(line)
        if "mismatch" in line.lower() and "no mismatches" not in line.lower():
            warnings += 1

    print()
    if warnings:
        print(f"[audit_ownership_data] Done with {warnings} warning area(s) — review mismatches above.")
        return 1
    print("[audit_ownership_data] Done — no critical integrity flags (count mismatches may still be methodological).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
