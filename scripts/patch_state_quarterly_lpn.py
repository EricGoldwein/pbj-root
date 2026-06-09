#!/usr/bin/env python3
"""
Add LPN_HPRD and LPN_Care_HPRD to quarterly aggregate CSVs from facility_quarterly_metrics.csv.

Patches (weighted by total_resident_days, same as PBJapp RN_HPRD):
  - state_quarterly_metrics.csv   (per STATE, CY_Qtr)
  - national_quarterly_metrics.csv (per CY_Qtr)
  - cms_region_quarterly_metrics.csv (per REGION, CY_Qtr)

Run after syncing facility_quarterly_metrics.csv from PBJapp:
  python scripts/patch_state_quarterly_lpn.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

STATE_CSV = ROOT / "state_quarterly_metrics.csv"
NATIONAL_CSV = ROOT / "national_quarterly_metrics.csv"
REGION_CSV = ROOT / "cms_region_quarterly_metrics.csv"
REGION_MAP_CSV = ROOT / "cms_region_state_mapping.csv"
FACILITY_CSV = ROOT / "facility_quarterly_metrics.csv"

LPN_COLS = ("LPN_HPRD", "LPN_Care_HPRD")


def _weighted_hprd(group: pd.DataFrame, hours_col: str) -> float:
    trd = pd.to_numeric(group["total_resident_days"], errors="coerce").sum()
    hrs = pd.to_numeric(group[hours_col], errors="coerce").sum()
    if not trd or pd.isna(trd) or trd <= 0:
        return float("nan")
    return float(hrs / trd)


def _weighted_hprd_from_state_rows(states: pd.DataFrame, hprd_col: str) -> float:
    """Weighted average of state HPRD using total_resident_days."""
    if states.empty or hprd_col not in states.columns:
        return float("nan")
    trd = pd.to_numeric(states["total_resident_days"], errors="coerce").sum()
    if not trd or pd.isna(trd) or trd <= 0:
        return float("nan")
    hrs = (
        pd.to_numeric(states[hprd_col], errors="coerce")
        * pd.to_numeric(states["total_resident_days"], errors="coerce")
    ).sum()
    return float(hrs / trd)


def compute_grouped_lpn(fq: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Return group_cols + LPN_HPRD, LPN_Care_HPRD."""
    fq = fq.copy()
    if "STATE" in fq.columns:
        fq["STATE"] = fq["STATE"].astype(str).str.strip().str.upper()
    fq["CY_Qtr"] = fq["CY_Qtr"].astype(str).str.strip()
    rows = []
    for keys, group in fq.groupby(group_cols, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        lpn = _weighted_hprd(group, "Total_LPN_Hours") if "Total_LPN_Hours" in group.columns else float("nan")
        lpn_care = (
            _weighted_hprd(group, "Total_LPN_Care_Hours")
            if "Total_LPN_Care_Hours" in group.columns
            else float("nan")
        )
        if pd.isna(lpn) and "LPN_HPRD" in group.columns:
            lpn = float(pd.to_numeric(group["LPN_HPRD"], errors="coerce").mean())
        if pd.isna(lpn_care) and "LPN_Care_HPRD" in group.columns:
            lpn_care = float(pd.to_numeric(group["LPN_Care_HPRD"], errors="coerce").mean())
        row = dict(zip(group_cols, keys))
        row["LPN_HPRD"] = lpn
        row["LPN_Care_HPRD"] = lpn_care
        rows.append(row)
    return pd.DataFrame(rows)


def _insert_after(cols: list[str], after: str, new_cols: tuple[str, ...]) -> list[str]:
    out = [c for c in cols if c not in new_cols]
    if after in out:
        idx = out.index(after) + 1
        for col in new_cols:
            out.insert(idx, col)
            idx += 1
    else:
        out.extend(new_cols)
    return out


def _write_csv(df: pd.DataFrame, path: Path, backup_prefix: str) -> None:
    import shutil

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}.{backup_prefix}_{ts}{path.suffix}")
    if path.is_file() and not backup.is_file():
        shutil.copy2(path, backup)
        print(f"  Backup: {backup.name}")
    tmp = path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
    print(f"  Wrote {path.name} ({len(df):,} rows)")


def _merge_lpn_columns(target: pd.DataFrame, lpn_df: pd.DataFrame, on: list[str]) -> pd.DataFrame:
    out = target.copy()
    for col in LPN_COLS:
        if col in out.columns:
            out = out.drop(columns=[col])
    merged = out.merge(lpn_df, on=on, how="left")
    merged = merged[_insert_after(list(merged.columns), "RN_Care_HPRD", LPN_COLS)]
    return merged


def load_facility_lpn() -> pd.DataFrame:
    usecols = [
        "STATE", "CY_Qtr", "total_resident_days",
        "Total_LPN_Hours", "Total_LPN_Care_Hours", "LPN_HPRD", "LPN_Care_HPRD",
    ]
    header = pd.read_csv(FACILITY_CSV, nrows=0).columns.tolist()
    usecols = [c for c in usecols if c in header]
    if "CY_Qtr" not in usecols:
        raise ValueError("facility CSV missing CY_Qtr")
    if not any(c in usecols for c in ("Total_LPN_Hours", "LPN_HPRD")):
        raise ValueError("facility CSV has no LPN hour/HPRD columns")
    print(f"Loading {FACILITY_CSV.name} (usecols={usecols})...")
    return pd.read_csv(FACILITY_CSV, usecols=usecols, low_memory=False)


def patch_state(fq: pd.DataFrame) -> None:
    if not STATE_CSV.is_file():
        print(f"WARN: missing {STATE_CSV.name}; skip state LPN patch")
        return
    lpn_df = compute_grouped_lpn(fq, ["STATE", "CY_Qtr"])
    print(f"Computed state LPN for {len(lpn_df):,} rows")
    state_df = pd.read_csv(STATE_CSV, low_memory=False)
    state_df["STATE"] = state_df["STATE"].astype(str).str.strip().str.upper()
    state_df["CY_Qtr"] = state_df["CY_Qtr"].astype(str).str.strip()
    merged = _merge_lpn_columns(state_df, lpn_df, ["STATE", "CY_Qtr"])
    _write_csv(merged, STATE_CSV, "pre_lpn")
    q = merged["CY_Qtr"].max()
    fl = merged[(merged["STATE"] == "FL") & (merged["CY_Qtr"] == q)]
    if not fl.empty:
        row = fl.iloc[0]
        print(
            f"  FL {q}: LPN_HPRD={row.get('LPN_HPRD', float('nan')):.4f} "
            f"LPN_Care_HPRD={row.get('LPN_Care_HPRD', float('nan')):.4f}"
        )


def patch_national(fq: pd.DataFrame) -> None:
    if not NATIONAL_CSV.is_file():
        print(f"WARN: missing {NATIONAL_CSV.name}; skip national LPN patch")
        return
    lpn_df = compute_grouped_lpn(fq, ["CY_Qtr"])
    print(f"Computed national LPN for {len(lpn_df):,} quarters")
    national_df = pd.read_csv(NATIONAL_CSV, low_memory=False)
    national_df["CY_Qtr"] = national_df["CY_Qtr"].astype(str).str.strip()
    merged = _merge_lpn_columns(national_df, lpn_df, ["CY_Qtr"])
    _write_csv(merged, NATIONAL_CSV, "pre_lpn")
    q = merged["CY_Qtr"].max()
    row = merged[merged["CY_Qtr"] == q]
    if not row.empty:
        r = row.iloc[0]
        print(
            f"  National {q}: LPN_HPRD={r.get('LPN_HPRD', float('nan')):.4f} "
            f"LPN_Care_HPRD={r.get('LPN_Care_HPRD', float('nan')):.4f}"
        )


def patch_region(fq: pd.DataFrame, state_with_lpn: pd.DataFrame | None = None) -> None:
    if not REGION_CSV.is_file():
        print(f"WARN: missing {REGION_CSV.name}; skip region LPN patch")
        return
    region_df = pd.read_csv(REGION_CSV, low_memory=False)
    region_df["CY_Qtr"] = region_df["CY_Qtr"].astype(str).str.strip()
    region_key = "REGION" if "REGION" in region_df.columns else None
    if not region_key:
        print("WARN: region CSV missing REGION column; skip")
        return

    lpn_rows = []
    if REGION_MAP_CSV.is_file() and state_with_lpn is not None:
        mapping = pd.read_csv(REGION_MAP_CSV, usecols=["State_Code", "CMS_Region_Full"])
        mapping["State_Code"] = mapping["State_Code"].astype(str).str.strip().str.upper()
        state_with_lpn = state_with_lpn.copy()
        state_with_lpn["STATE"] = state_with_lpn["STATE"].astype(str).str.strip().str.upper()
        state_with_lpn["CY_Qtr"] = state_with_lpn["CY_Qtr"].astype(str).str.strip()
        for quarter in region_df["CY_Qtr"].unique():
            st_q = state_with_lpn[state_with_lpn["CY_Qtr"] == quarter]
            if st_q.empty:
                continue
            st_q = st_q.merge(mapping, left_on="STATE", right_on="State_Code", how="inner")
            for region_full, group in st_q.groupby("CMS_Region_Full", sort=False):
                lpn_rows.append({
                    "REGION": region_full,
                    "CY_Qtr": quarter,
                    "LPN_HPRD": _weighted_hprd_from_state_rows(group, "LPN_HPRD"),
                    "LPN_Care_HPRD": _weighted_hprd_from_state_rows(group, "LPN_Care_HPRD"),
                })

    if not lpn_rows and REGION_MAP_CSV.is_file():
        mapping = pd.read_csv(REGION_MAP_CSV, usecols=["State_Code", "CMS_Region_Full"])
        mapping["State_Code"] = mapping["State_Code"].astype(str).str.strip().str.upper()
        fq_r = fq.copy()
        fq_r["STATE"] = fq_r["STATE"].astype(str).str.strip().str.upper()
        fq_r = fq_r.merge(mapping, left_on="STATE", right_on="State_Code", how="inner")
        fq_r = fq_r.rename(columns={"CMS_Region_Full": "REGION"})
        lpn_df = compute_grouped_lpn(fq_r, ["REGION", "CY_Qtr"])
        lpn_rows = lpn_df.to_dict("records")

    if not lpn_rows:
        print("WARN: could not compute region LPN; skip")
        return

    lpn_df = pd.DataFrame(lpn_rows)
    lpn_df["CY_Qtr"] = lpn_df["CY_Qtr"].astype(str).str.strip()
    lpn_df["REGION"] = lpn_df["REGION"].astype(str).str.strip()
    region_df[region_key] = region_df[region_key].astype(str).str.strip()
    merged = _merge_lpn_columns(region_df, lpn_df, [region_key, "CY_Qtr"])
    _write_csv(merged, REGION_CSV, "pre_lpn")


def main() -> None:
    if not FACILITY_CSV.is_file():
        print(f"ERROR: missing {FACILITY_CSV}", file=sys.stderr)
        sys.exit(1)

    fq = load_facility_lpn()
    print("Patching state_quarterly_metrics.csv...")
    patch_state(fq)

    state_with_lpn = None
    if STATE_CSV.is_file():
        state_with_lpn = pd.read_csv(
            STATE_CSV,
            usecols=["STATE", "CY_Qtr", "total_resident_days", "LPN_HPRD", "LPN_Care_HPRD"],
            low_memory=False,
        )

    print("Patching national_quarterly_metrics.csv...")
    patch_national(fq)

    print("Patching cms_region_quarterly_metrics.csv...")
    patch_region(fq, state_with_lpn)


if __name__ == "__main__":
    main()
