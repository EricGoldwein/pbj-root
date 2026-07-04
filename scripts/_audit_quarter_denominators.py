#!/usr/bin/env python3
"""Audit quarterly denominator handling for sign-off."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs"

fq = pd.read_csv(CSV / "facility_quarter_summary.csv")
fac = pd.read_csv(CSV / "facility_summary.csv")

print("=== 1. Facility-quarter totals ===")
print("total facility-quarters:", len(fq))
print("unique facilities in fq:", fq["ccn"].nunique())

print("\n=== quarters_analyzed distribution (facility summary) ===")
for k, v in fac["quarters_analyzed"].value_counts().sort_index().items():
    print(f"  {int(k)} quarters: {int(v)} facilities")
print("sum quarters_analyzed:", int(fac["quarters_analyzed"].sum()))

print("\n=== 2. Display denominator audit ===")
bad = []
for _, row in fac.iterrows():
    qa = int(row["quarters_analyzed"])
    qb = int(row["quarters_below_350_total"])
    expected = f"{qb}/{qa}"
    disp = str(row.get("qtrs_below_350_display", ""))
    if disp != expected:
        bad.append((row["ccn"], disp, expected))
x4_bug = fac[(fac["quarters_analyzed"] < 4) & fac["qtrs_below_350_display"].astype(str).str.endswith("/4")]
print("display mismatches:", len(bad))
print("x/4 when quarters_analyzed < 4:", len(x4_bug))
if len(x4_bug):
    print(x4_bug[["ccn", "quarters_analyzed", "qtrs_below_350_display"]].head(10).to_string())

partial = fac[fac["quarters_analyzed"] < 4]
print(f"\npartial-year facilities: {len(partial)}")
if len(partial):
    print(partial[["ccn", "quarters_analyzed", "quarters_below_350_total", "qtrs_below_350_display"]].head(8).to_string())

print("\n=== 3. 284 figure definition ===")
exactly_4_below = int((fac["quarters_below_350_total"] == 4).sum())
all4_analyzed_all4_below = int(
    ((fac["quarters_analyzed"] == 4) & (fac["quarters_below_350_total"] == 4)).sum()
)
every_analyzed = int((fac["quarters_below_350_total"] == fac["quarters_analyzed"]).sum())
partial_all_below = fac[
    (fac["quarters_below_350_total"] == fac["quarters_analyzed"]) & (fac["quarters_analyzed"] < 4)
]
print("facilities with quarters_below_350_total == 4:", exactly_4_below)
print("facilities with 4 analyzed AND 4 below:", all4_analyzed_all4_below)
print("facilities below in EVERY analyzed quarter:", every_analyzed)
print("partial-year below in every analyzed quarter:", len(partial_all_below))

print("\n=== distribution facilities_by_quarters_below_350 (count of quarters below) ===")
for i in range(5):
    n = int((fac["quarters_below_350_total"] == i).sum())
    print(f"  {i} quarters below: {n} facilities")

print("\n=== facilities with 4 below but <4 analyzed ===")
weird = fac[(fac["quarters_below_350_total"] == 4) & (fac["quarters_analyzed"] < 4)]
print(len(weird))
