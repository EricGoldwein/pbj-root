#!/usr/bin/env python3
"""Compare rebuilt facility_quarterly_metrics.csv vs pre-rebuild backup (legacy cols only)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

LEGACY_COLS = (
    "PROVNUM",
    "PROVNAME",
    "STATE",
    "COUNTY_NAME",
    "CY_Qtr",
    "days_reported",
    "total_resident_days",
    "avg_daily_census",
    "MDScensus",
    "Total_Nurse_Hours",
    "Total_RN_Hours",
    "Total_Nurse_Care_Hours",
    "Total_RN_Care_Hours",
    "Total_Nurse_Assistant_Hours",
    "Total_Contract_Hours",
    "Total_Nurse_HPRD",
    "RN_HPRD",
    "Nurse_Care_HPRD",
    "RN_Care_HPRD",
    "Nurse_Assistant_HPRD",
    "Contract_Percentage",
)


def _zprov(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.lower()
    out = out.str.split("e", n=1, expand=True)[0].str.split(".", n=1, expand=True)[0]
    return out.str.zfill(6)


def _load(path: Path, cols: tuple[str, ...]) -> pd.DataFrame:
    hdr = pd.read_csv(path, nrows=0).columns
    use = [c for c in cols if c in hdr]
    df = pd.read_csv(path, usecols=use, low_memory=False)
    df["PROVNUM"] = _zprov(df["PROVNUM"])
    df["CY_Qtr"] = df["CY_Qtr"].astype(str).str.strip()
    return df


def compare(new_path: Path, old_path: Path, rtol: float, atol: float) -> int:
    print(f"NEW: {new_path}")
    print(f"OLD: {old_path}")
    new = _load(new_path, LEGACY_COLS)
    old = _load(old_path, LEGACY_COLS)
    dup_new = int(new.duplicated(subset=["PROVNUM", "CY_Qtr"]).sum())
    if dup_new:
        print(f"  WARNING: new file has {dup_new:,} duplicate PROVNUM+CY_Qtr rows — comparing deduped (keep=last)")
        new = new.drop_duplicates(subset=["PROVNUM", "CY_Qtr"], keep="last")
    print(f"  rows: new={len(new):,}  old={len(old):,}")

    merged = new.merge(old, on=["PROVNUM", "CY_Qtr"], how="outer", indicator=True)
    both = int((merged["_merge"] == "both").sum())
    only_new = int((merged["_merge"] == "left_only").sum())
    only_old = int((merged["_merge"] == "right_only").sum())
    print(f"  keys in both: {both:,}  only in new: {only_new:,}  only in old: {only_old:,}")

    if only_new:
        print("  sample only-in-new:")
        print(merged.loc[merged["_merge"] == "left_only", ["PROVNUM", "CY_Qtr"]].head(5).to_string(index=False))
    if only_old:
        print("  sample only-in-old:")
        print(merged.loc[merged["_merge"] == "right_only", ["PROVNUM", "CY_Qtr"]].head(5).to_string(index=False))

    m = new.merge(old, on=["PROVNUM", "CY_Qtr"], suffixes=("_n", "_o"))
    failed = False
    for col in LEGACY_COLS:
        if col in ("PROVNUM", "CY_Qtr"):
            continue
        a, b = m[f"{col}_n"], m[f"{col}_o"]
        if col in ("PROVNAME", "STATE", "COUNTY_NAME"):
            ok = a.astype(str).str.strip() == b.astype(str).str.strip()
        else:
            an = pd.to_numeric(a, errors="coerce")
            bn = pd.to_numeric(b, errors="coerce")
            ok = (np.abs(an - bn) <= atol + rtol * np.abs(bn)) | (an.isna() & bn.isna())
        bad = int((~ok).sum())
        if bad:
            failed = True
            print(f"  DIFF {col}: {bad:,} rows")
            print(m.loc[~ok, ["PROVNUM", "CY_Qtr", f"{col}_n", f"{col}_o"]].head(2).to_string(index=False))

    if not failed:
        print("  legacy columns: ALL MATCH on overlapping keys")
    for col in ("Total_Nurse_HPRD", "RN_HPRD", "Nurse_Assistant_HPRD"):
        d = (
            pd.to_numeric(m[f"{col}_n"], errors="coerce")
            - pd.to_numeric(m[f"{col}_o"], errors="coerce")
        ).abs()
        print(f"  max |delta| {col}: {float(d.max()):.6g}")
    return 1 if failed or only_old else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--new", type=Path, default=REPO_ROOT / "facility_quarterly_metrics.csv")
    p.add_argument(
        "--old",
        type=Path,
        default=REPO_ROOT / "facility_quarterly_metrics.pre_unify_20260520_194654.csv",
    )
    p.add_argument("--rtol", type=float, default=1e-6)
    p.add_argument("--atol", type=float, default=1e-4)
    args = p.parse_args()
    if not args.new.is_file() or not args.old.is_file():
        print("ERROR: missing new or old file", file=sys.stderr)
        return 2
    return compare(args.new, args.old, args.rtol, args.atol)


if __name__ == "__main__":
    raise SystemExit(main())
