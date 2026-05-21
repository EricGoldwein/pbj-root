#!/usr/bin/env python3
"""
Verify PBJapp -> pbj-root copies: same rows, keys, and metric values.

Copy-Item is a byte-for-byte file copy — no rounding or transforms. The site applies
ROUND_HALF_UP only when formatting for HTML/CSV export (pbj_format.format_metric_value).

Usage (from pbj-root):
  python scripts/verify_pbjapp_sync.py
  python scripts/verify_pbjapp_sync.py --source "C:/Users/egold/PycharmProjects/PBJapp"

Exit 1 if any check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_PBJAPP = Path(r"C:\Users\egold\PycharmProjects\PBJapp")

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
LPN_COLS = (
    "Total_LPN_Hours",
    "Total_LPN_Care_Hours",
    "Total_LPN_Admin_Hours",
    "Total_LPN_Contract_Hours",
    "LPN_HPRD",
    "LPN_Care_HPRD",
    "LPN_Admin_HPRD",
)
COMPARE_FILES = (
    "facility_quarterly_metrics.csv",
    "state_quarterly_metrics.csv",
    "national_quarterly_metrics.csv",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _format_provnum(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.lower().str.split("e", n=1, expand=True)[0].str.split(".", n=1, expand=True)[0]
    return out.str.zfill(6)


def _close(a: pd.Series, b: pd.Series, rtol: float, atol: float) -> pd.Series:
    return (np.abs(a - b) <= (atol + rtol * np.abs(b))) | (a.isna() & b.isna())


def _compare_facility_csv(src: Path, dst: Path, rtol: float, atol: float) -> list[str]:
    errors: list[str] = []
    if not src.is_file():
        return [f"missing source: {src}"]
    if not dst.is_file():
        return [f"missing destination: {dst}"]

    sh_src, sh_dst = _sha256(src), _sha256(dst)
    if sh_src == sh_dst:
        print(f"  [OK] {dst.name}: identical file (SHA256 match)")
        return []

    print(f"  [WARN] {dst.name}: file hash differs — comparing columns...")
    leg = pd.read_csv(src, usecols=lambda c: c in LEGACY_COLS, low_memory=False)
    dest_leg = pd.read_csv(dst, usecols=lambda c: c in LEGACY_COLS, low_memory=False)
    for label, df in (("source", leg), ("dest", dest_leg)):
        if len(df.columns) != len(LEGACY_COLS):
            errors.append(f"{label} missing legacy columns: {set(LEGACY_COLS) - set(df.columns)}")

    leg["PROVNUM"] = _format_provnum(leg["PROVNUM"])
    dest_leg["PROVNUM"] = _format_provnum(dest_leg["PROVNUM"])
    leg["CY_Qtr"] = leg["CY_Qtr"].astype(str).str.strip()
    dest_leg["CY_Qtr"] = dest_leg["CY_Qtr"].astype(str).str.strip()

    if len(leg) != len(dest_leg):
        errors.append(f"row count: source={len(leg):,} dest={len(dest_leg):,}")

    merged = leg.merge(dest_leg, on=["PROVNUM", "CY_Qtr"], how="outer", indicator=True)
    only_src = int((merged["_merge"] == "left_only").sum())
    only_dst = int((merged["_merge"] == "right_only").sum())
    if only_src or only_dst:
        errors.append(f"key mismatch: only_in_source={only_src:,} only_in_dest={only_dst:,}")

    both = leg.merge(dest_leg, on=["PROVNUM", "CY_Qtr"], suffixes=("_src", "_dst"))
    for col in LEGACY_COLS:
        if col in ("PROVNUM", "CY_Qtr"):
            continue
        a = both[f"{col}_src"]
        b = both[f"{col}_dst"]
        if col in ("PROVNAME", "STATE", "COUNTY_NAME"):
            ok = a.astype(str).str.strip() == b.astype(str).str.strip()
        else:
            ok = _close(pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce"), rtol, atol)
        bad = int((~ok).sum())
        if bad:
            errors.append(f"legacy column {col}: {bad:,} rows differ")

    # LPN columns: only compare when present on both sides
    hdr_src = pd.read_csv(src, nrows=0).columns
    hdr_dst = pd.read_csv(dst, nrows=0).columns
    lpn = [c for c in LPN_COLS if c in hdr_src and c in hdr_dst]
    if lpn:
        ext_s = pd.read_csv(src, usecols=["PROVNUM", "CY_Qtr"] + lpn, low_memory=False)
        ext_d = pd.read_csv(dst, usecols=["PROVNUM", "CY_Qtr"] + lpn, low_memory=False)
        ext_s["PROVNUM"] = _format_provnum(ext_s["PROVNUM"])
        ext_d["PROVNUM"] = _format_provnum(ext_d["PROVNUM"])
        ext_s["CY_Qtr"] = ext_s["CY_Qtr"].astype(str).str.strip()
        ext_d["CY_Qtr"] = ext_d["CY_Qtr"].astype(str).str.strip()
        m2 = ext_s.merge(ext_d, on=["PROVNUM", "CY_Qtr"], suffixes=("_src", "_dst"))
        for col in lpn:
            ok = _close(
                pd.to_numeric(m2[f"{col}_src"], errors="coerce"),
                pd.to_numeric(m2[f"{col}_dst"], errors="coerce"),
                rtol,
                atol,
            )
            bad = int((~ok).sum())
            if bad:
                errors.append(f"LPN column {col}: {bad:,} rows differ")
        nn_s = int(pd.to_numeric(ext_s["LPN_HPRD"], errors="coerce").notna().sum()) if "LPN_HPRD" in lpn else 0
        nn_d = int(pd.to_numeric(ext_d["LPN_HPRD"], errors="coerce").notna().sum()) if "LPN_HPRD" in lpn else 0
        print(f"  LPN_HPRD non-null: source={nn_s:,} dest={nn_d:,}")
    else:
        print("  LPN columns: not on both files (schema only on one side)")

    if not errors:
        print(f"  [OK] {dst.name}: legacy (+ LPN) values match within tolerance")
    return errors


def _compare_simple_file(src: Path, dst: Path) -> list[str]:
    if not src.is_file():
        return [f"missing source: {src}"]
    if not dst.is_file():
        return [f"missing destination: {dst}"]
    if _sha256(src) == _sha256(dst):
        print(f"  [OK] {dst.name}: identical file (SHA256 match)")
        return []
    return [f"{dst.name}: SHA256 mismatch (files differ)"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=DEFAULT_PBJAPP, help="PBJapp repo root")
    p.add_argument("--dest", type=Path, default=REPO_ROOT, help="pbj-root repo root")
    p.add_argument("--rtol", type=float, default=1e-9, help="Relative float tolerance if hashes differ")
    p.add_argument("--atol", type=float, default=1e-6, help="Absolute float tolerance if hashes differ")
    args = p.parse_args()

    print(f"Source (PBJapp): {args.source}")
    print(f"Dest   (pbj-root): {args.dest}")
    all_errors: list[str] = []

    for name in COMPARE_FILES:
        src = args.source / name
        dst = args.dest / name
        print(f"\n{name}:")
        if name == "facility_quarterly_metrics.csv":
            all_errors.extend(_compare_facility_csv(src, dst, args.rtol, args.atol))
        else:
            all_errors.extend(_compare_simple_file(src, dst))

    # Spot-check one CCN on facility file (display rounding is separate)
    fq = args.dest / "facility_quarterly_metrics.csv"
    if fq.is_file():
        try:
            from pbj_format import format_metric_value

            df = pd.read_csv(fq, low_memory=False)
            w = df[df["PROVNUM"].astype(str).str.zfill(6) == "075111"].sort_values("CY_Qtr")
            if not w.empty:
                row = w.iloc[-1]
                print("\nSpot check CCN 075111 (latest quarter in file):")
                print(f"  CY_Qtr: {row.get('CY_Qtr')}")
                for k in ("Total_Nurse_HPRD", "RN_HPRD", "Nurse_Assistant_HPRD", "LPN_HPRD"):
                    raw = row.get(k)
                    disp = format_metric_value(raw, k) if pd.notna(raw) else "—"
                    print(f"  {k}: raw={raw}  displayed={disp}")
        except Exception as e:
            print(f"\nSpot check skipped: {e}")

    if all_errors:
        print("\nFAILED:")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    print("\nAll sync checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
