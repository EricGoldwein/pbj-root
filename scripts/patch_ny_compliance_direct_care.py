#!/usr/bin/env python3
"""Recalculate NY below_state_min_* in staffing compliance bundle @ 3.50 direct care HPRD.

Verified from: PBJapp/scripts/analyze_ny_minimum_staffing.py (HRS_NY_MAPPED_TOTAL, NY_STATUTE_TOTAL_MIN_HPRD).
"""
from __future__ import annotations

import gzip
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PBJAPP = ROOT.parent / "PBJapp"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if PBJAPP.exists() and str(PBJAPP) not in sys.path:
    sys.path.insert(0, str(PBJAPP))

import staffing_compliance_bundle as scb  # noqa: E402

from scripts.analyze_ny_minimum_staffing import (  # noqa: E402
    HRS_NY_MAPPED_TOTAL,
    _parse_work_date,
    _pbj_quarter_paths,
    _sum_hours,
)

NY_THRESHOLD = 3.5
NY_LABEL = "Days below NY 3.50 direct care HPRD"
NY_METRIC = "direct_care_hprd"


def _quarter_from_date(dt: pd.Timestamp) -> str:
    return f"CY{int(dt.year)}Q{int((dt.month - 1) // 3 + 1)}"


def _load_ny_below_counts() -> pd.DataFrame:
    """Facility-quarter counts of days with NY-mapped direct care HPRD < 3.50."""
    years = {2025}
    parts: list[pd.DataFrame] = []
    usecols = ["PROVNUM", "STATE", "WorkDate", "MDScensus", *HRS_NY_MAPPED_TOTAL]

    for year in sorted(years):
        for path in _pbj_quarter_paths(year):
            for chunk in pd.read_csv(
                path,
                usecols=lambda c: c in usecols,
                dtype={"PROVNUM": str, "STATE": str},
                chunksize=250_000,
                low_memory=False,
                encoding="latin-1",
            ):
                chunk = chunk[chunk["STATE"].astype(str).str.upper() == "NY"].copy()
                if chunk.empty:
                    continue
                chunk["WorkDate"] = _parse_work_date(chunk["WorkDate"])
                chunk = chunk[chunk["WorkDate"].notna()].copy()
                census = pd.to_numeric(chunk["MDScensus"], errors="coerce")
                chunk = chunk[census > 0].copy()
                if chunk.empty:
                    continue
                census = pd.to_numeric(chunk["MDScensus"], errors="coerce")
                chunk["ccn"] = chunk["PROVNUM"].astype(str).str.strip().str.zfill(6).str[-6:]
                chunk["quarter"] = chunk["WorkDate"].map(_quarter_from_date)
                chunk["direct_care_hprd"] = _sum_hours(chunk, HRS_NY_MAPPED_TOTAL) / census
                chunk["below"] = chunk["direct_care_hprd"] < NY_THRESHOLD
                parts.append(chunk[["ccn", "quarter", "below"]])

    if not parts:
        raise FileNotFoundError("No NY PBJ daily rows found for direct-care recalculation")

    daily = pd.concat(parts, ignore_index=True)
    agg = (
        daily.groupby(["ccn", "quarter"], as_index=False)
        .agg(below_state_min_days_count=("below", "sum"))
    )
    agg["below_state_min_days_count"] = agg["below_state_min_days_count"].astype(int)
    return agg


def main() -> int:
    app_root = str(ROOT)
    csv_path = scb.materialize_summary_csv(app_root)
    if not csv_path or not Path(csv_path).is_file():
        print("[patch_ny_compliance_direct_care] missing summary CSV", file=sys.stderr)
        return 1

    below = _load_ny_below_counts()
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    ny_mask = df["state"].astype(str).str.upper() == "NY"
    if not ny_mask.any():
        print("[patch_ny_compliance_direct_care] no NY rows in summary")
        return 1

    merged = df.loc[ny_mask, ["ccn", "quarter", "total_days_reported"]].merge(
        below, on=["ccn", "quarter"], how="left"
    )
    merged["below_state_min_days_count"] = merged["below_state_min_days_count"].fillna(0).astype(int)
    total = pd.to_numeric(merged["total_days_reported"], errors="coerce").fillna(0).astype(int)
    def _pct(row: pd.Series) -> float:
        t = int(float(row.get("total_days_reported") or 0))
        if t <= 0:
            return 0.0
        return round(100.0 * int(row["below_state_min_days_count"]) / t, 2)

    merged["below_state_min_days_pct"] = merged.apply(_pct, axis=1)

    key = merged.set_index(["ccn", "quarter"])
    updated = 0
    for idx in df.index[ny_mask]:
        ccn = str(df.at[idx, "ccn"]).strip().zfill(6)[-6:]
        quarter = str(df.at[idx, "quarter"]).strip()
        if (ccn, quarter) not in key.index:
            continue
        row = key.loc[(ccn, quarter)]
        df.at[idx, "below_state_min_days_count"] = str(int(row["below_state_min_days_count"]))
        df.at[idx, "below_state_min_days_pct"] = str(row["below_state_min_days_pct"])
        df.at[idx, "state_min_threshold_used"] = str(NY_THRESHOLD)
        df.at[idx, "state_min_metric_used"] = NY_METRIC
        df.at[idx, "state_min_label"] = NY_LABEL
        updated += 1

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    df.loc[ny_mask, "generated_at"] = ts

    gz_path = scb.summary_gzip_path(app_root)
    tmp = Path(csv_path).with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(csv_path)
    with open(csv_path, "rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)

    scb.invalidate_caches()
    from scripts.build_staffing_compliance_runtime_index import main as build_index  # noqa: E402

    build_index()
    print(f"[patch_ny_compliance_direct_care] updated {updated:,} NY rows @ {NY_THRESHOLD} {NY_METRIC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
