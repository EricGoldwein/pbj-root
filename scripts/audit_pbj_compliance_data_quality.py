#!/usr/bin/env python3
"""
Read-only pre-export QA: COALESCE impact, duplicate facility-days, implausible
values for NY/CT PBJ daily compliance inputs (same files as bundle build).

Does not change production calculation logic, bundles, or public outputs.
Documented in docs/data_quality_and_fallbacks_audit.md and
docs/staffing_minimums_methodology.md (QA before publish).

Run before publishing new compliance bundles or adding states. Flag:
  - null/blank hour fields, duplicate CCN+WorkDate, negative hours/census
  - extreme HPRD; impact on below-threshold, 0 RN, RN<8 counts

Usage:
  python scripts/audit_pbj_compliance_data_quality.py
  python scripts/audit_pbj_compliance_data_quality.py --quarters CY2025Q4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBJAPP = ROOT.parent / "PBJapp"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PBJAPP) not in sys.path:
    sys.path.insert(0, str(PBJAPP))

import duckdb  # noqa: E402

RN_COLS = ["Hrs_RNDON", "Hrs_RNadmin", "Hrs_RN"]
NURSE_COLS = RN_COLS + ["Hrs_LPNadmin", "Hrs_LPN", "Hrs_CNA", "Hrs_NAtrn", "Hrs_MedAide"]
THRESHOLDS = {"NY": 3.56, "CT": 3.06}
HPRD_HIGH = 12.0
RN_HPRD_HIGH = 8.0


def _coalesce_sum(cols: list[str]) -> str:
    return " + ".join(f"COALESCE({c}, 0)" for c in cols)


def _strict_sum(cols: list[str]) -> str:
    """NULL if any column NULL, else sum."""
    null_checks = " OR ".join(f"{c} IS NULL" for c in cols)
    raw_sum = " + ".join(cols)
    return f"CASE WHEN ({null_checks}) THEN NULL ELSE ({raw_sum}) END"


def _any_null(cols: list[str]) -> str:
    return " OR ".join(f"{c} IS NULL" for c in cols)


def audit_quarter(conn: duckdb.DuckDBPyConnection, csv_path: Path, quarter: str) -> dict:
    rn_co = _coalesce_sum(RN_COLS)
    nurse_co = _coalesce_sum(NURSE_COLS)
    rn_strict = _strict_sum(RN_COLS)
    nurse_strict = _strict_sum(NURSE_COLS)
    any_null = _any_null(NURSE_COLS)

    q = quarter.replace("CY", "") if quarter.startswith("CY") else quarter
    sql = f"""
    WITH raw AS (
      SELECT
        LPAD(CAST(PROVNUM AS VARCHAR), 6, '0') AS ccn,
        UPPER(TRIM(STATE)) AS state,
        CAST(WorkDate AS VARCHAR) AS work_date,
        MDScensus AS census,
        {', '.join(NURSE_COLS)},
        ({rn_co}) AS rn_hours_coalesce,
        ({nurse_co}) AS nurse_hours_coalesce,
        {rn_strict} AS rn_hours_strict,
        {nurse_strict} AS nurse_hours_strict,
        ({any_null}) AS any_hour_null
      FROM read_csv_auto(?, header=True, ignore_errors=True, types={{'PROVNUM': 'VARCHAR'}})
      WHERE UPPER(TRIM(STATE)) IN ('NY', 'CT')
    ),
    valid AS (
      SELECT *,
        nurse_hours_coalesce * 1.0 / census AS nurse_hprd_coalesce,
        CASE WHEN nurse_hours_strict IS NULL THEN NULL
             ELSE nurse_hours_strict * 1.0 / census END AS nurse_hprd_strict,
        rn_hours_coalesce * 1.0 / census AS rn_hprd_coalesce,
        CASE WHEN census > 0 THEN 1 ELSE 0 END AS is_valid_census
      FROM raw
    ),
    flagged AS (
      SELECT *,
        CASE WHEN state = 'NY' THEN 3.56 WHEN state = 'CT' THEN 3.06 END AS thresh,
        CASE WHEN is_valid_census = 1 AND rn_hours_coalesce = 0 THEN 1 ELSE 0 END AS rn0_coalesce,
        CASE WHEN is_valid_census = 1 AND rn_hours_strict = 0 THEN 1 ELSE 0 END AS rn0_strict,
        CASE WHEN is_valid_census = 1 AND rn_hours_coalesce < 8 THEN 1 ELSE 0 END AS rn8_coalesce,
        CASE WHEN is_valid_census = 1 AND rn_hours_strict IS NOT NULL AND rn_hours_strict < 8 THEN 1 ELSE 0 END AS rn8_strict,
        CASE WHEN is_valid_census = 1 AND nurse_hprd_coalesce < (
          CASE WHEN state = 'NY' THEN 3.56 WHEN state = 'CT' THEN 3.06 END
        ) THEN 1 ELSE 0 END AS below_coalesce,
        CASE WHEN is_valid_census = 1 AND nurse_hprd_strict IS NOT NULL AND nurse_hprd_strict < (
          CASE WHEN state = 'NY' THEN 3.56 WHEN state = 'CT' THEN 3.06 END
        ) THEN 1 ELSE 0 END AS below_strict,
        CASE WHEN census < 0 THEN 1 ELSE 0 END AS neg_census,
        CASE WHEN {' OR '.join(f'{c} < 0' for c in NURSE_COLS)} THEN 1 ELSE 0 END AS neg_hours,
        CASE WHEN is_valid_census = 1 AND nurse_hprd_coalesce > {HPRD_HIGH} THEN 1 ELSE 0 END AS high_nurse_hprd,
        CASE WHEN is_valid_census = 1 AND rn_hprd_coalesce > {RN_HPRD_HIGH} THEN 1 ELSE 0 END AS high_rn_hprd
      FROM valid
    )
    SELECT * FROM flagged
    """
    return conn.execute(sql, [str(csv_path)]).df()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pbj-dir",
        type=Path,
        default=PBJAPP / "standardized_PBJ",
    )
    ap.add_argument(
        "--quarters",
        nargs="*",
        default=["CY2025Q1", "CY2025Q2", "CY2025Q3", "CY2025Q4"],
    )
    ap.add_argument("--top-n", type=int, default=15)
    args = ap.parse_args()

    import pandas as pd

    conn = duckdb.connect()
    all_parts: list[pd.DataFrame] = []

    for quarter in args.quarters:
        csv_path = args.pbj_dir / f"PBJ_dailynursestaffing_{quarter}.csv"
        if not csv_path.is_file():
            print(f"SKIP missing {csv_path}")
            continue
        print(f"Loading {quarter} ...", flush=True)
        df = audit_quarter(conn, csv_path, quarter)
        df["quarter"] = quarter
        all_parts.append(df)

    if not all_parts:
        print("No quarter files loaded", file=sys.stderr)
        return 2

    df = pd.concat(all_parts, ignore_index=True)
    valid = df[df["census"] > 0].copy()
    n_valid = len(valid)
    n_all = len(df)

    print("\n" + "=" * 72)
    print("SCOPE: NY + CT, quarters:", ", ".join(args.quarters))
    print(f"Total rows (NY+CT): {n_all:,}  |  census>0 facility-days: {n_valid:,}")
    print("=" * 72)

    # --- A: COALESCE / missing hours ---
    print("\n## A. COALESCE(hours, 0) vs treat missing hours as incomplete\n")

    any_null = valid["any_hour_null"].astype(bool)
    n_any_null = int(any_null.sum())
    pct_null = 100.0 * n_any_null / n_valid if n_valid else 0

    # per-column null rates
    print("Missing/null by column (census>0 days):")
    for c in NURSE_COLS:
        n = int(valid[c].isna().sum())
        print(f"  {c}: {n:,} ({100*n/n_valid:.4f}%)")

    print(f"\nAny of 8 hour columns null: {n_any_null:,} ({pct_null:.4f}%) of valid facility-days")

    # all-null vs partial-null
    all_null = valid[NURSE_COLS].isna().all(axis=1)
    partial_null = any_null & ~all_null
    print(f"  All 8 hours null (census>0): {int(all_null.sum()):,}")
    print(f"  Partial null (some cols): {int(partial_null.sum()):,}")

    # rows where coalesce=0 but strict is NULL (would be excluded)
    would_exclude = valid[any_null]
    n_exclude = len(would_exclude)

    sub = valid[any_null]
    rn0_drop = int((sub["rn0_coalesce"] == 1).sum()) - int((sub["rn0_strict"] == 1).sum())
    below_drop = int((sub["below_coalesce"] == 1).sum()) - int((sub["below_strict"] == 1).sum())
    rn8_drop = int((sub["rn8_coalesce"] == 1).sum()) - int((sub["rn8_strict"] == 1).sum())

    rn0_before = int(valid["rn0_coalesce"].sum())
    rn0_after = int(valid.loc[~any_null, "rn0_strict"].sum()) if (~any_null).any() else 0
    below_before = int(valid["below_coalesce"].sum())
    below_after = int(valid.loc[~any_null, "below_strict"].sum()) if (~any_null).any() else 0
    rn8_before = int(valid["rn8_coalesce"].sum())
    rn8_after = int(valid.loc[~any_null, "rn8_strict"].sum()) if (~any_null).any() else 0

    print("\nIf missing-hour days excluded (strict sum) vs current COALESCE:")
    print(f"  Facility-days excluded from denominator: {n_exclude:,}")
    print(f"  0 RN days:        {rn0_before:,} -> {rn0_after:,}  (delta {rn0_after - rn0_before:+,})")
    print(f"  RN <8 hr days:    {rn8_before:,} -> {rn8_after:,}  (delta {rn8_after - rn8_before:+,})")
    print(f"  Below threshold:  {below_before:,} -> {below_after:,}  (delta {below_after - below_before:+,})")
    print(f"  (Of excluded days, COALESCE-only flags: rn0~{int(sub['rn0_coalesce'].sum())}, below~{int(sub['below_coalesce'].sum())})")

    # true zero heuristic: all cols present and all == 0
    present_all = ~any_null
    true_zero = present_all & (valid[NURSE_COLS].fillna(0).sum(axis=1) == 0)
    coerced_zero = any_null & (valid["rn_hours_coalesce"] == 0)
    print("\nMissing vs true zero (heuristic, census>0):")
    print(f"  All fields present and all hours = 0: {int(true_zero.sum()):,}")
    print(f"  Any null but COALESCE total RN hours = 0: {int(coerced_zero.sum()):,} (likely data gap, counted as 0 today)")

    # top facilities by null days
    top_null = (
        valid[any_null]
        .groupby(["state", "ccn"], as_index=False)
        .size()
        .rename(columns={"size": "null_hour_days"})
        .sort_values("null_hour_days", ascending=False)
        .head(args.top_n)
    )
    print(f"\nTop {args.top_n} CCNs by facility-days with any null hour field:")
    for _, r in top_null.iterrows():
        print(f"  {r['ccn']} {r['state']}: {int(r['null_hour_days'])} days")

    # --- B: duplicates ---
    print("\n## B. Duplicate provnum + WorkDate rows\n")

    dup_keys = (
        valid.groupby(["quarter", "ccn", "work_date"])
        .size()
        .reset_index(name="n")
    )
    dups = dup_keys[dup_keys["n"] > 1]
    n_dup_keys = len(dups)
    extra_rows = int((dups["n"] - 1).sum()) if not dups.empty else 0
    print(f"Duplicate facility-days (census>0, unique ccn+date with n>1): {n_dup_keys:,}")
    print(f"Extra rows beyond first per day: {extra_rows:,}")

    if not dups.empty:
        dup_ccns = dups["ccn"].nunique()
        print(f"Affected CCNs (at least one dup day): {dup_ccns:,}")

        # sample conflict check on duplicate groups
        dup_mask = valid.set_index(["quarter", "ccn", "work_date"]).index.isin(
            set(zip(dups["quarter"], dups["ccn"], dups["work_date"]))
        )
        dup_rows = valid[dup_mask]
        grp = dup_rows.groupby(["quarter", "ccn", "work_date"])
        identical_census = 0
        conflicting_census = 0
        identical_nurse = 0
        conflicting_nurse = 0
        for _, g in grp:
            if g["census"].nunique() <= 1:
                identical_census += 1
            else:
                conflicting_census += 1
            if g["nurse_hours_coalesce"].nunique() <= 1:
                identical_nurse += 1
            else:
                conflicting_nurse += 1
        n_dup_groups = len(grp)
        print(f"Duplicate groups: {n_dup_groups:,}")
        print(f"  Identical census across dup rows: {identical_census:,} | Conflicting: {conflicting_census:,}")
        print(f"  Identical COALESCE nurse hours: {identical_nurse:,} | Conflicting: {conflicting_nurse:,}")
        print("Current build: len(group) counts each row as a day (can double-count days and flags).")

        # impact: deduped by max vs sum
        dedup_first = valid.sort_values("work_date").drop_duplicates(
            subset=["quarter", "ccn", "work_date"], keep="first"
        )
        dedup_sum_hours = (
            valid.groupby(["quarter", "ccn", "work_date", "state"], as_index=False)
            .agg(
                census=("census", "first"),
                nurse_hours_coalesce=("nurse_hours_coalesce", "sum"),
                rn_hours_coalesce=("rn_hours_coalesce", "sum"),
            )
        )
        # recompute flags on deduped first vs current
        def _flags(frame: pd.DataFrame, label: str) -> dict:
            f = frame[frame["census"] > 0].copy()
            f["below"] = f.apply(
                lambda r: r["nurse_hours_coalesce"] / r["census"] < THRESHOLDS[r["state"]],
                axis=1,
            )
            return {
                "label": label,
                "days": len(f),
                "rn0": int((f["rn_hours_coalesce"] == 0).sum()),
                "rn8": int((f["rn_hours_coalesce"] < 8).sum()),
                "below": int(f["below"].sum()),
            }

        cur = _flags(valid, "current (all rows)")
        d1 = _flags(dedup_first, "dedupe keep first")
        dsum2 = (
            valid.groupby(["quarter", "ccn", "work_date", "state"], as_index=False)
            .agg(
                census=("census", "first"),
                nurse_hours_coalesce=("nurse_hours_coalesce", "sum"),
                rn_hours_coalesce=("rn_hours_coalesce", "sum"),
            )
        )
        dsum2 = dsum2[dsum2["census"] > 0]
        dsum2["below"] = dsum2.apply(
            lambda r: r["nurse_hours_coalesce"] / r["census"] < THRESHOLDS[r["state"]],
            axis=1,
        )
        print("\nFlag totals — current vs dedupe keep-first vs dedupe sum-hours:")
        print(f"  Current rows (census>0): days={cur['days']:,} rn0={cur['rn0']:,} rn8={cur['rn8']:,} below={cur['below']:,}")
        print(f"  Dedupe first:            days={d1['days']:,} rn0={d1['rn0']:,} rn8={d1['rn8']:,} below={d1['below']:,}")
        print(
            f"  Dedupe sum hours:        days={len(dsum2):,} rn0={int((dsum2['rn_hours_coalesce']==0).sum()):,} "
            f"rn8={int((dsum2['rn_hours_coalesce']<8).sum()):,} below={int(dsum2['below'].sum()):,}"
        )

        top_dup = (
            dups.groupby("ccn", as_index=False)["n"]
            .sum()
            .rename(columns={"n": "dup_day_rows"})
            .sort_values("dup_day_rows", ascending=False)
            .head(args.top_n)
        )
        print(f"\nTop {args.top_n} CCNs by duplicate facility-day row count:")
        for _, r in top_dup.iterrows():
            print(f"  {r['ccn']}: {int(r['dup_day_rows'])} extra dup rows")

    # --- C: implausible ---
    print("\n## C. Implausible / invalid values (census>0 unless noted)\n")

    neg_census_all = int((df["census"] < 0).sum())
    zero_census = int((df["census"] == 0).sum())
    neg_hours = int(valid["neg_hours"].sum()) if "neg_hours" in valid.columns else 0
    high_nurse = int(valid["high_nurse_hprd"].sum())
    high_rn = int(valid["high_rn_hprd"].sum())

    print(f"Negative census rows (all NY+CT rows): {neg_census_all:,}")
    print(f"Zero census rows (excluded from compliance denominator): {zero_census:,}")
    print(f"Negative any hour (census>0): {neg_hours:,}")
    print(f"Total nursing HPRD > {HPRD_HIGH} (census>0): {high_nurse:,}")
    print(f"RN HPRD > {RN_HPRD_HIGH} (census>0): {high_rn:,}")

    extreme = valid[(valid["high_nurse_hprd"] == 1) | (valid["high_rn_hprd"] == 1) | (valid["neg_hours"] == 1)]
    below_extreme = int(extreme["below_coalesce"].sum())
    rn0_extreme = int(extreme["rn0_coalesce"].sum())
    print(f"\nExtreme-value days that are also below threshold: {below_extreme:,}")
    print(f"Extreme-value days counted as 0 RN: {rn0_extreme:,}")

    if high_nurse:
        top_high = (
            valid[valid["high_nurse_hprd"] == 1]
            .nlargest(args.top_n, "nurse_hprd_coalesce")[["quarter", "ccn", "state", "work_date", "nurse_hprd_coalesce", "census"]]
        )
        print(f"\nTop {args.top_n} highest total nursing HPRD days:")
        for _, r in top_high.iterrows():
            print(
                f"  {r['quarter']} {r['ccn']} {r['state']} {r['work_date']}: "
                f"HPRD={r['nurse_hprd_coalesce']:.2f} census={r['census']}"
            )

    # bundle impact note
    print("\n## Bundle alignment note")
    print("Public bundle uses same COALESCE logic and row-level day counts as build.")
    print("Compare facility-quarter totals via scripts/audit_staffing_thresholds.py if needed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
