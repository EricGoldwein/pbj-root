"""Parity: compact day_fact bundle vs PBJapp build_hprd_evidence (sample)."""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PBJAPP = REPO.parent / "PBJapp"
sys.path.insert(0, str(PBJAPP))
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402
from day_evidence_lib import METRIC_HOUR_COLUMNS, build_hprd_evidence  # noqa: E402
import staffing_evidence_bundle as seb  # noqa: E402

METRICS = list(METRIC_HOUR_COLUMNS.keys())
CSV = PBJAPP / "standardized_PBJ" / "PBJ_dailynursestaffing_CY2026Q1.csv"
DB = REPO / "data" / "evidence" / "staffing_day_evidence.sqlite"
N_FACILITIES = 12
N_DATES_PER_FACILITY = 3
SEED = 32026


def _norm_ccn(raw: object) -> str:
    s = str(raw or "").strip().upper().split(".")[0]
    return s.zfill(6) if s else ""


def _norm_date(raw: object) -> str:
    s = str(raw or "").strip().replace(".0", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s[:10] if len(s) >= 10 else s


def main() -> int:
    if not DB.is_file():
        print(f"FAIL: missing {DB}")
        return 1
    if not CSV.is_file():
        print(f"FAIL: missing {CSV}")
        return 1

    seb.invalidate_caches()
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    ccns = [r[0] for r in conn.execute("SELECT DISTINCT ccn FROM day_fact ORDER BY ccn").fetchall()]
    conn.close()
    if len(ccns) < N_FACILITIES:
        print(f"FAIL: only {len(ccns)} facilities in bundle")
        return 1

    rng = random.Random(SEED)
    sample_ccns = rng.sample(ccns, N_FACILITIES)

    # Load only sampled CCNs from source CSV
    usecols = [
        "PROVNUM",
        "WorkDate",
        "CY_Qtr",
        "MDScensus",
        "Hrs_RN",
        "Hrs_RNadmin",
        "Hrs_RNDON",
        "Hrs_LPN",
        "Hrs_CNA",
        "Hrs_NAtrn",
        "Hrs_MedAide",
        "source_file_basename",
        "source_raw_row_ordinal",
        "source_file_sha256",
    ]
    header = pd.read_csv(CSV, nrows=0).columns.tolist()
    cols = [c for c in usecols if c in header]
    want = set(sample_ccns)
    parts = []
    for chunk in pd.read_csv(CSV, usecols=cols, chunksize=200_000, low_memory=False):
        chunk["_ccn"] = chunk["PROVNUM"].astype(str).map(_norm_ccn)
        hit = chunk[chunk["_ccn"].isin(want)]
        if not hit.empty:
            parts.append(hit)
    src = pd.concat(parts, ignore_index=True)
    src["__date"] = src["WorkDate"].map(_norm_date)
    src["MDScensus"] = pd.to_numeric(src["MDScensus"], errors="coerce").fillna(0)
    src = src[src["MDScensus"] > 0]

    comparisons = 0
    mismatches: list[dict] = []
    t0 = time.perf_counter()

    for ccn in sample_ccns:
        fac = src[src["_ccn"] == ccn]
        dates = sorted(fac["__date"].unique().tolist())
        if not dates:
            mismatches.append({"ccn": ccn, "error": "no source dates"})
            continue
        pick_dates = dates if len(dates) <= N_DATES_PER_FACILITY else rng.sample(dates, N_DATES_PER_FACILITY)
        for date in pick_dates:
            row = fac[fac["__date"] == date].iloc[0]
            q = str(row.get("CY_Qtr") or "CY2026Q1")
            for metric in METRICS:
                ref = build_hprd_evidence(
                    metric=metric,
                    pbj_row=row,
                    ccn=ccn,
                    work_date=date,
                    quarter=q,
                    ein_employees=None,
                )
                got = seb.lookup_day_evidence(str(REPO), ccn, date, metric)
                comparisons += 1
                if not got:
                    mismatches.append({"ccn": ccn, "date": date, "metric": metric, "error": "missing"})
                    continue
                if abs(float(ref.get("value") or 0) - float(got.get("value") or 0)) > 1e-9:
                    mismatches.append(
                        {
                            "ccn": ccn,
                            "date": date,
                            "metric": metric,
                            "ref": ref.get("value"),
                            "got": got.get("value"),
                        }
                    )
                    continue
                if ref.get("provenance_precision") != got.get("provenance_precision"):
                    # provenance may differ if source cols absent in CSV; allow dataset_and_key vs reconstructed
                    if {ref.get("provenance_precision"), got.get("provenance_precision")} <= {
                        "exact_record",
                        "dataset_and_key",
                        "reconstructed",
                    }:
                        # Require exact match when source sha present on both
                        ref_sha = (ref.get("numerator") or {}).get("source", {}).get("source_file_sha256")
                        got_sha = (got.get("numerator") or {}).get("source", {}).get("source_file_sha256")
                        if ref_sha and got_sha and ref.get("provenance_precision") != got.get("provenance_precision"):
                            mismatches.append(
                                {
                                    "ccn": ccn,
                                    "date": date,
                                    "metric": metric,
                                    "error": "precision",
                                    "ref": ref.get("provenance_precision"),
                                    "got": got.get("provenance_precision"),
                                }
                            )
                    else:
                        mismatches.append(
                            {
                                "ccn": ccn,
                                "date": date,
                                "metric": metric,
                                "error": "precision",
                                "ref": ref.get("provenance_precision"),
                                "got": got.get("provenance_precision"),
                            }
                        )

    elapsed = time.perf_counter() - t0
    summary = {
        "ok": len(mismatches) == 0,
        "comparisons": comparisons,
        "facilities": len(sample_ccns),
        "metrics": METRICS,
        "mismatches": mismatches[:20],
        "mismatch_count": len(mismatches),
        "elapsed_s": round(elapsed, 2),
        "sample_ccns": sample_ccns,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
