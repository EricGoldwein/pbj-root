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
FACILITY_CSV = ROOT / "facility_quarterly_metrics.csv"

MEDIAN_COLS = [
    "Total_Nurse_HPRD_Median",
    "RN_HPRD_Median",
    "Nurse_Care_HPRD_Median",
    "RN_Care_HPRD_Median",
    "Nurse_Assistant_HPRD_Median",
    "Contract_Percentage_Median",
]

FACILITY_TO_MEDIAN = {
    "Total_Nurse_HPRD": "Total_Nurse_HPRD_Median",
    "RN_HPRD": "RN_HPRD_Median",
    "Nurse_Care_HPRD": "Nurse_Care_HPRD_Median",
    "RN_Care_HPRD": "RN_Care_HPRD_Median",
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


def main() -> None:
    if not STATE_CSV.is_file():
        print(f"ERROR: missing {STATE_CSV}", file=sys.stderr)
        sys.exit(1)
    if not FACILITY_CSV.is_file():
        print(f"ERROR: missing {FACILITY_CSV}", file=sys.stderr)
        sys.exit(1)

    print("Loading facility_quarterly_metrics.csv (usecols only)...")
    usecols = ["STATE", "CY_Qtr"] + list(FACILITY_TO_MEDIAN.keys())
    fq = pd.read_csv(FACILITY_CSV, usecols=usecols, low_memory=False)
    fq["STATE"] = fq["STATE"].astype(str).str.strip().str.upper()
    fq["CY_Qtr"] = fq["CY_Qtr"].astype(str).str.strip()

    agg: dict[str, tuple[str, object]] = {}
    for fac_col, med_col in FACILITY_TO_MEDIAN.items():
        exclude_zeros = fac_col != "Contract_Percentage"
        agg[med_col] = (fac_col, lambda s, ez=exclude_zeros: _median_series(s, exclude_zeros=ez))
    med = fq.groupby(["STATE", "CY_Qtr"], as_index=False).agg(**agg)

    print(f"Computed medians for {len(med):,} state-quarter rows")

    state_df = pd.read_csv(STATE_CSV, low_memory=False)
    state_df["STATE"] = state_df["STATE"].astype(str).str.strip().str.upper()
    state_df["CY_Qtr"] = state_df["CY_Qtr"].astype(str).str.strip()

    for col in MEDIAN_COLS:
        if col in state_df.columns:
            state_df = state_df.drop(columns=[col])

    merged = state_df.merge(med, on=["STATE", "CY_Qtr"], how="left")
    import shutil

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    backup = STATE_CSV.with_name(f"state_quarterly_metrics.pre_medians_{ts}.csv")
    if not backup.is_file():
        shutil.copy2(STATE_CSV, backup)
        print(f"Backup: {backup.name}")

    tmp = STATE_CSV.with_suffix(".csv.tmp")
    merged.to_csv(tmp, index=False)
    os.replace(tmp, STATE_CSV)
    q = merged["CY_Qtr"].max()
    sample = merged[merged["CY_Qtr"] == q].head(3)
    print(f"Wrote {STATE_CSV} ({len(merged):,} rows)")
    for _, row in sample.iterrows():
        print(
            f"  {row['STATE']} {q}: avg HPRD {row.get('Total_Nurse_HPRD', 0):.3f} "
            f"median {row.get('Total_Nurse_HPRD_Median', float('nan')):.3f}"
        )


if __name__ == "__main__":
    main()
