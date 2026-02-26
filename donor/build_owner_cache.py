#!/usr/bin/env python3
"""
Build Parquet cache and manifest for owner dashboard (faster, stable loads).

Run when source CSVs change (e.g. after owner_donor.py extract or new quarter):
  python -m donor.build_owner_cache

Creates in donor/output/:
  - owners_database.parquet (from owners_database.csv)
  - ownership_normalized.parquet (from ownership_normalized.csv)
  - facility_name_mapping.parquet (from facility_name_mapping.csv)
  - data_manifest.json (source mtimes + built_at so dashboard can prefer Parquet when current)

Dashboard load_data() will prefer these Parquet files when they exist and are
newer than or equal to the source CSV, falling back to CSV otherwise.
Data changes are handled by re-running this script after updating the CSVs.
"""
from pathlib import Path
import json
import os
import sys

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "donor" / "output"
MANIFEST_PATH = OUTPUT_DIR / "data_manifest.json"

SOURCES = [
    ("owners_database.csv", "owners_database.parquet"),
    ("ownership_normalized.csv", "ownership_normalized.parquet"),
    ("facility_name_mapping.csv", "facility_name_mapping.parquet"),
]


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def build():
    import pandas as pd
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"sources": {}, "parquet": {}, "built_at": None}
    built_at = None
    for csv_name, parquet_name in SOURCES:
        csv_path = OUTPUT_DIR / csv_name
        parquet_path = OUTPUT_DIR / parquet_name
        if not csv_path.exists():
            print(f"[SKIP] {csv_name} not found")
            continue
        try:
            df = pd.read_csv(csv_path, dtype=str, low_memory=False, encoding="utf-8")
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(csv_path, dtype=str, low_memory=False, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, dtype=str, low_memory=False, encoding="latin-1")
        manifest["sources"][csv_name] = _mtime(csv_path)
        df.to_parquet(parquet_path, index=False)
        manifest["parquet"][parquet_name] = _mtime(parquet_path)
        if built_at is None:
            from datetime import datetime, timezone
            built_at = datetime.now(timezone.utc).isoformat()
        manifest["built_at"] = built_at
        print(f"[OK] {csv_name} -> {parquet_name} ({len(df):,} rows)")
    if manifest["built_at"]:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"[OK] Wrote {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
