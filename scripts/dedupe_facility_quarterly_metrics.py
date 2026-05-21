#!/usr/bin/env python3
"""Remove duplicate PROVNUM+CY_Qtr rows from facility_quarterly_metrics.csv (keep=last)."""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", type=Path, default=REPO_ROOT / "facility_quarterly_metrics.csv")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.path.is_file():
        print(f"Missing: {args.path}")
        return 2
    df = pd.read_csv(args.path, low_memory=False)
    before = len(df)
    out = df.copy()
    out["PROVNUM"] = (
        out["PROVNUM"]
        .astype(str)
        .str.lower()
        .str.split("e", n=1, expand=True)[0]
        .str.split(".", n=1, expand=True)[0]
        .str.zfill(6)
    )
    out["CY_Qtr"] = out["CY_Qtr"].astype(str).str.strip()
    out = out.drop_duplicates(subset=["PROVNUM", "CY_Qtr"], keep="last")
    dropped = before - len(out)
    print(f"Rows before: {before:,}  after: {len(out):,}  dropped: {dropped:,}")
    if dropped == 0:
        print("No duplicates — nothing to do.")
        return 0
    if args.dry_run:
        print("[dry-run] Would rewrite file.")
        return 0
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = args.path.with_name(f"{args.path.stem}.pre_dedupe_{ts}{args.path.suffix}")
    shutil.copy2(args.path, backup)
    out.to_csv(args.path, index=False)
    print(f"Backup: {backup}")
    print(f"Wrote: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
