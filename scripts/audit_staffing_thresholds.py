#!/usr/bin/env python3
"""
Read-only audit: staffing compliance bundle vs configured thresholds.

Does not rewrite production data. Optionally compares to PBJapp daily CSV
when PBJ_DAILY_DIR or ../PBJapp/standardized_PBJ is available.

Usage:
  python scripts/audit_staffing_thresholds.py
  python scripts/audit_staffing_thresholds.py --ccn 335513 --quarter CY2025Q4
  python scripts/audit_staffing_thresholds.py --state CT --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import staffing_compliance_bundle as scb  # noqa: E402

RN_COLS = ("Hrs_RNDON", "Hrs_RNadmin", "Hrs_RN")
NURSE_COLS = RN_COLS + ("Hrs_LPNadmin", "Hrs_LPN", "Hrs_CNA", "Hrs_NAtrn", "Hrs_MedAide")
IMPLAUSIBLE_HPRD_LOW = 0.0
IMPLAUSIBLE_HPRD_HIGH = 12.0


def _load_thresholds() -> dict:
    path = ROOT / "data" / "compliance" / "staffing_compliance_thresholds.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _state_threshold(cfg: dict, state: str) -> float | None:
    for row in cfg.get("state_thresholds") or []:
        if str(row.get("state", "")).upper() == state.upper() and row.get("enabled", True):
            return float(row["threshold"])
    return None


def _audit_bundle_row(app_root: str, ccn: str, quarter: str, cfg: dict) -> list[str]:
    issues: list[str] = []
    row = scb.lookup_public_summary(app_root, ccn, quarter)
    if not row:
        issues.append(f"{ccn} {quarter}: no bundle row")
        return issues

    st = str(row.get("state", "")).upper()
    th = row.get("state_min_threshold_used")
    expected_th = _state_threshold(cfg, st)
    if expected_th is not None and th is not None and float(th) != float(expected_th):
        issues.append(f"{ccn}: threshold_used={th} != config {expected_th}")

    total = int(row.get("total_days_reported") or 0)
    below = row.get("below_state_min_days_count")
    if below is not None and total and int(below) > total:
        issues.append(f"{ccn}: below_state_min_days_count > total_days_reported")

    for col in ("rn_0_days_count", "rn_below_8hr_days_count"):
        c = row.get(col)
        if c is not None and total and int(c) > total:
            issues.append(f"{ccn}: {col} > total_days_reported")

    if st in ("NY", "CT") and below is None and total > 0:
        issues.append(f"{ccn}: {st} facility missing below_state_min_days_count")

    if st == "CT" and th is not None and abs(float(th) - 3.56) < 0.001:
        issues.append(f"{ccn}: CT row uses 3.56 — expected 3.06")

    return issues


def _try_recompute_from_csv(ccn: str, quarter: str, cfg: dict) -> dict | None:
    """Recompute day counts from standardized PBJ if duckdb + file exist."""
    try:
        import duckdb  # type: ignore
    except ImportError:
        return None

    pbj_dirs = [
        ROOT.parent / "PBJapp" / "standardized_PBJ",
        Path(__file__).resolve().parents[1] / "standardized_PBJ",
    ]
    csv_path = None
    for d in pbj_dirs:
        p = d / f"PBJ_dailynursestaffing_{quarter}.csv"
        if p.is_file():
            csv_path = p
            break
    if not csv_path:
        return None

    st_row = scb.lookup_public_summary(str(ROOT), ccn, quarter)
    if not st_row:
        return None
    state = str(st_row.get("state", "")).upper()
    threshold = _state_threshold(cfg, state)
    if threshold is None:
        return None

    rn_sum = " + ".join(f"COALESCE({c}, 0)" for c in RN_COLS)
    nurse_sum = " + ".join(f"COALESCE({c}, 0)" for c in NURSE_COLS)
    sql = f"""
    SELECT
      COUNT(*) AS valid_days,
      SUM(CASE WHEN ({nurse_sum}) * 1.0 / MDScensus < {threshold} THEN 1 ELSE 0 END) AS below_state,
      SUM(CASE WHEN ({rn_sum}) = 0 THEN 1 ELSE 0 END) AS rn_0,
      SUM(CASE WHEN ({rn_sum}) < 8 THEN 1 ELSE 0 END) AS rn_below_8,
      SUM(CASE WHEN ({nurse_sum}) * 1.0 / MDScensus > {IMPLAUSIBLE_HPRD_HIGH} THEN 1 ELSE 0 END) AS high_hprd_days
    FROM read_csv_auto(?, header=True, ignore_errors=True, types={{'PROVNUM': 'VARCHAR'}})
    WHERE MDScensus > 0
      AND LPAD(CAST(PROVNUM AS VARCHAR), 6, '0') = ?
    """
    conn = duckdb.connect()
    try:
        r = conn.execute(sql, [str(csv_path), str(ccn).zfill(6)]).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {
        "valid_days": int(r[0]),
        "below_state": int(r[1]),
        "rn_0": int(r[2]),
        "rn_below_8": int(r[3]),
        "high_hprd_days": int(r[4]),
        "csv": str(csv_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit staffing compliance bundle thresholds")
    ap.add_argument("--ccn", action="append", help="CCN(s) to audit (default: sample NY/CT)")
    ap.add_argument("--quarter", default=None, help="Quarter CY2025Q4 (default: latest in manifest)")
    ap.add_argument("--state", help="Filter sample rows by state")
    ap.add_argument("--limit", type=int, default=10, help="Max facilities when sampling")
    ap.add_argument("--recompute", action="store_true", help="Compare bundle to PBJ CSV if available")
    args = ap.parse_args()

    app_root = str(ROOT)
    cfg = _load_thresholds()
    manifest = scb.load_manifest(app_root) or {}
    quarter = args.quarter or (manifest.get("quarters_in_bundle") or manifest.get("quarters") or [None])[-1]
    if not quarter:
        print("No quarter in manifest and none passed", file=sys.stderr)
        return 2

    print(f"Manifest: {manifest.get('row_count')} rows, quarters={manifest.get('quarters')}")
    print(f"Thresholds: NY={_state_threshold(cfg, 'NY')}, CT={_state_threshold(cfg, 'CT')}")
    print(f"Audit quarter: {quarter}\n")

    ccns = args.ccn
    if not ccns:
        import sqlite3

        db = scb.index_sqlite_path(app_root)
        if not Path(db).is_file():
            ccns = ["335513", "075030"]  # known NY/CT samples if index missing
        else:
            conn = sqlite3.connect(db)
            st_filter = f" AND state = '{args.state.upper()}'" if args.state else ""
            cur = conn.execute(
                f"SELECT ccn FROM compliance_summary WHERE quarter = ?{st_filter} LIMIT ?",
                (quarter, args.limit),
            )
            ccns = [str(r[0]).zfill(6) for r in cur.fetchall()]
            conn.close()
        if not ccns:
            print("No CCNs in index; pass --ccn", file=sys.stderr)
            return 1

    all_issues: list[str] = []
    for ccn in ccns:
        ccn = str(ccn).zfill(6)
        row = scb.lookup_public_summary(app_root, ccn, quarter)
        if not row:
            print(f"{ccn}: MISSING from bundle")
            all_issues.append(f"{ccn}: missing")
            continue
        print(
            f"{ccn} {row.get('state')} days={row.get('total_days_reported')} "
            f"below_state={row.get('below_state_min_days_count')} "
            f"({row.get('below_state_min_days_pct')}%) thresh={row.get('state_min_threshold_used')} "
            f"rn0={row.get('rn_0_days_count')} rn<8={row.get('rn_below_8hr_days_count')}"
        )
        all_issues.extend(_audit_bundle_row(app_root, ccn, quarter, cfg))

        if args.recompute:
            rec = _try_recompute_from_csv(ccn, quarter, cfg)
            if rec:
                b_below = row.get("below_state_min_days_count")
                if b_below is not None and int(b_below) != rec["below_state"]:
                    msg = (
                        f"{ccn}: bundle below_state={b_below} != CSV recompute {rec['below_state']} "
                        f"(valid_days bundle={row.get('total_days_reported')} csv={rec['valid_days']})"
                    )
                    all_issues.append(msg)
                    print(f"  MISMATCH: {msg}")
                else:
                    print(f"  CSV OK: below={rec['below_state']} valid={rec['valid_days']} high_hprd={rec['high_hprd_days']}")
            else:
                print("  CSV recompute skipped (no duckdb or PBJ file)")

    print()
    if all_issues:
        print(f"FAILED: {len(all_issues)} issue(s)")
        for i in all_issues:
            print(f"  - {i}")
        return 1
    print("PASS: no threshold consistency issues in sampled rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
