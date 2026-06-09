#!/usr/bin/env python3
"""
Quarterly release step: add facility-level median columns to state_quarterly_metrics.csv.

Run after regenerating state_quarterly_metrics.csv from facility_quarterly_metrics.csv:
  python scripts/patch_state_quarterly_medians.py

Documented in QUARTER_RELEASE_PLAYBOOK.md (step 2). Enforced by scripts/validate_release.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

STATE_CSV = ROOT / "state_quarterly_metrics.csv"
REGION_CSV = ROOT / "cms_region_quarterly_metrics.csv"
REGION_MAP_CSV = ROOT / "cms_region_state_mapping.csv"
FACILITY_CSV = ROOT / "facility_quarterly_metrics.csv"

MEDIAN_COLS = [
    "Total_Nurse_HPRD_Median",
    "RN_HPRD_Median",
    "Nurse_Care_HPRD_Median",
    "RN_Care_HPRD_Median",
    "LPN_HPRD_Median",
    "LPN_Care_HPRD_Median",
    "Nurse_Assistant_HPRD_Median",
    "Contract_Percentage_Median",
]

FACILITY_TO_MEDIAN = {
    "Total_Nurse_HPRD": "Total_Nurse_HPRD_Median",
    "RN_HPRD": "RN_HPRD_Median",
    "Nurse_Care_HPRD": "Nurse_Care_HPRD_Median",
    "RN_Care_HPRD": "RN_Care_HPRD_Median",
    "LPN_HPRD": "LPN_HPRD_Median",
    "LPN_Care_HPRD": "LPN_Care_HPRD_Median",
    "Nurse_Assistant_HPRD": "Nurse_Assistant_HPRD_Median",
    "Contract_Percentage": "Contract_Percentage_Median",
}


def _median_series(s: pd.Series, *, exclude_zeros: bool) -> float:
    if exclude_zeros:
        vals = s[(s.notna()) & (s > 0)]
    else:
        vals = s[s.notna()]
    if vals.empty:
        return np.nan
    return float(vals.median())


def _compute_facility_medians(fq: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    agg: dict[str, tuple[str, object]] = {}
    for fac_col, med_col in FACILITY_TO_MEDIAN.items():
        if fac_col not in fq.columns:
            continue
        exclude_zeros = fac_col != "Contract_Percentage"
        agg[med_col] = (fac_col, lambda s, ez=exclude_zeros: _median_series(s, exclude_zeros=ez))
    if not agg:
        return pd.DataFrame(columns=group_cols + list(MEDIAN_COLS))
    return fq.groupby(group_cols, as_index=False).agg(**agg)


def _write_with_backup(df: pd.DataFrame, path: Path, backup_tag: str) -> None:
    import shutil

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}.{backup_tag}_{ts}{path.suffix}")
    if path.is_file() and not backup.is_file():
        shutil.copy2(path, backup)
        print(f"Backup: {backup.name}")
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def main() -> None:
    if not STATE_CSV.is_file():
        print(f"ERROR: missing {STATE_CSV}", file=sys.stderr)
        sys.exit(1)
    if not FACILITY_CSV.is_file():
        print(f"ERROR: missing {FACILITY_CSV}", file=sys.stderr)
        sys.exit(1)

    print("Loading facility_quarterly_metrics.csv (usecols only)...")
    usecols = ["STATE", "CY_Qtr"] + [c for c in FACILITY_TO_MEDIAN if c in pd.read_csv(FACILITY_CSV, nrows=0).columns]
    fq = pd.read_csv(FACILITY_CSV, usecols=usecols, low_memory=False)
    fq["STATE"] = fq["STATE"].astype(str).str.strip().str.upper()
    fq["CY_Qtr"] = fq["CY_Qtr"].astype(str).str.strip()

    med = _compute_facility_medians(fq, ["STATE", "CY_Qtr"])
    print(f"Computed medians for {len(med):,} state-quarter rows")

    state_df = pd.read_csv(STATE_CSV, low_memory=False)
    state_df["STATE"] = state_df["STATE"].astype(str).str.strip().str.upper()
    state_df["CY_Qtr"] = state_df["CY_Qtr"].astype(str).str.strip()

    for col in MEDIAN_COLS:
        if col in state_df.columns:
            state_df = state_df.drop(columns=[col])

    merged = state_df.merge(med, on=["STATE", "CY_Qtr"], how="left")
    _write_with_backup(merged, STATE_CSV, "pre_medians")
    q = merged["CY_Qtr"].max()
    sample = merged[merged["CY_Qtr"] == q].head(3)
    print(f"Wrote {STATE_CSV} ({len(merged):,} rows)")
    for _, row in sample.iterrows():
        print(
            f"  {row['STATE']} {q}: avg HPRD {row.get('Total_Nurse_HPRD', 0):.3f} "
            f"median {row.get('Total_Nurse_HPRD_Median', float('nan')):.3f} "
            f"LPN median {row.get('LPN_HPRD_Median', float('nan')):.3f}"
        )

    if REGION_CSV.is_file() and REGION_MAP_CSV.is_file():
        print("Patching cms_region_quarterly_metrics.csv medians...")
        mapping = pd.read_csv(REGION_MAP_CSV, usecols=["State_Code", "CMS_Region_Full"])
        mapping["State_Code"] = mapping["State_Code"].astype(str).str.strip().str.upper()
        fq_r = fq.merge(mapping, left_on="STATE", right_on="State_Code", how="inner")
        fq_r = fq_r.rename(columns={"CMS_Region_Full": "REGION"})
        region_med = _compute_facility_medians(fq_r, ["REGION", "CY_Qtr"])
        region_df = pd.read_csv(REGION_CSV, low_memory=False)
        region_df["REGION"] = region_df["REGION"].astype(str).str.strip()
        region_df["CY_Qtr"] = region_df["CY_Qtr"].astype(str).str.strip()
        for col in MEDIAN_COLS:
            if col in region_df.columns:
                region_df = region_df.drop(columns=[col])
        region_merged = region_df.merge(region_med, on=["REGION", "CY_Qtr"], how="left")
        _write_with_backup(region_merged, REGION_CSV, "pre_medians")
        print(f"Wrote {REGION_CSV} ({len(region_merged):,} rows)")


if __name__ == "__main__":
    main()
