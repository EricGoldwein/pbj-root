#!/usr/bin/env python3
"""Build the compact historical Provider Info runtime artifact.

Reproducible, deterministic build: raw monthly ``ProviderInfoNorm_YYYY_MM.csv``
snapshots (one per CMS processing month, one uniform ``quarter``/``processing_date``
per file -- see app.py's ``_provider_snapshot_quarter_and_processing_date``) in,
one compact Parquet file out.

Grain: one row per (ccn, pbj_quarter) -- the CANONICAL snapshot for that quarter.
When multiple monthly files self-tag the same PBJ quarter (CMS's normal
recurring publication pattern), the file with the LATEST processing_date wins.
This is the exact same tie-break as app.py's ``_provider_snapshot_quarter_registry``
/ ``resolve_provider_info_snapshot_path_for_quarter`` (verified against PBJapp's
``pbj_case_mix_cmi.coalesce_provider_quarter_snapshots``) -- this script does not
invent a different rule. Collapsing to one row per (ccn, quarter) at build time
(rather than keeping every monthly row) is safe *because* processing_date is
uniform across every row in a given source file: the canonical-file choice does
not vary by CCN, so build-time collapse and query-time resolution are provably
identical. That invariant is validated below (``--source-dir`` files with a
non-uniform processing_date abort the build).

Never manually edited: this artifact is build output. To update it, add new
source months and re-run this script -- do not hand-edit the Parquet or the
manifest.

Usage:
    python scripts/build_provider_info_history.py --source-dir <path to ProviderInfoNorm_*.csv folder>

Source directory resolution order when --source-dir is omitted:
    1. $PBJ_PROVIDER_INFO_HISTORY_SOURCE env var
    2. ./provider_info/ (this repo's own tracked monthly snapshots -- shallow,
       currently ~9 months; always available, always safe)
This script does NOT reach into another repo's working tree by default --
a deeper archive (e.g. PBJapp's provider_info_normalized/) must be pointed to
explicitly via --source-dir or the env var. That data is untracked/gitignored
local build output in PBJapp, not something pbj-root depends on being present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PARQUET = APP_ROOT / "data" / "derived" / "provider_info_history.parquet"
DEFAULT_OUTPUT_MANIFEST = APP_ROOT / "data" / "derived" / "provider_info_history_manifest.json"

# Compact column set -- PERIOD-SENSITIVE fields only (see PROVIDER_INFO_FIELD_SEMANTICS.md).
# Deliberately excludes current-identity fields (name/address/phone/lat-long/footnote
# text, chain/affiliated-entity identity) -- those remain served by the existing
# current-snapshot path and would roughly double artifact size for no historical value.
VALUE_COLUMNS = [
    "certified_beds",
    "avg_residents_per_day",
    "nursing_case_mix_index",
    "nursing_case_mix_index_ratio",
    "case_mix_total_nurse_hrs_per_resident_per_day",
    "case_mix_rn_hrs_per_resident_per_day",
    "case_mix_lpn_hrs_per_resident_per_day",
    "case_mix_na_hrs_per_resident_per_day",
    "case_mix_weekend_total_nurse_hrs_per_resident_per_day",
    "adjusted_total_nurse_hrs_per_resident_per_day",
    "overall_rating",
    "staffing_rating",
    "qm_rating",
    "health_inspection_rating",
    "sff_status",
    "abuse_icon",
    "provider_changed_ownership_in_last_12_months",
    "state",
]
KEY_COLUMNS = ["ccn", "pbj_quarter", "processing_date", "source_filename"]
ALL_OUTPUT_COLUMNS = KEY_COLUMNS + VALUE_COLUMNS

# Small row groups (data is sorted by ccn just before write, below) so a runtime
# per-CCN predicate-pushdown read (app.py's _load_provider_info_history_rows_for_ccn,
# filters=[('ccn','==',ccn)]) can skip row groups outside that CCN's contiguous range
# instead of decoding the whole ~484k-row file. Measured: a single row group (pyarrow's
# default for a file this size) forces a full-file decode even with filters= (~200MB+
# transient per lookup); row_group_size=2000 (~240 groups for the current archive) cuts
# a single-CCN filtered read to a ~30-50MB transient, no permanent resident growth.
PARQUET_ROW_GROUP_SIZE = 2000

_QUARTER_DISPLAY_RE = re.compile(r"^Q([1-4])\s*(\d{4})$", re.IGNORECASE)
_QUARTER_CY_RE = re.compile(r"^(\d{4})Q([1-4])$")


def _quarter_display_to_cy(raw: str) -> str | None:
    raw = str(raw or "").strip()
    if _QUARTER_CY_RE.match(raw):
        return raw
    m = _QUARTER_DISPLAY_RE.match(raw)
    if m:
        return f"{m.group(2)}Q{m.group(1)}"
    return None


def _quarter_sort_key(q_cy: str) -> tuple[int, int]:
    m = _QUARTER_CY_RE.match(q_cy)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_source_dir(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value)
    env_value = os.environ.get("PBJ_PROVIDER_INFO_HISTORY_SOURCE")
    if env_value:
        return Path(env_value)
    return APP_ROOT / "provider_info"


def _candidate_files(source_dir: Path) -> list[Path]:
    return sorted(
        p for p in source_dir.glob("ProviderInfoNorm_*.csv") if p.is_file()
    )


def _file_quarter_and_processing_date(path: Path) -> tuple[str | None, pd.Timestamp | None, bool]:
    """Return (pbj_quarter, processing_date, is_uniform).

    ``is_uniform`` is False when the file's processing_date column is not a
    single value across every row -- that would break the build-time
    (ccn, quarter) collapse's equivalence to query-time resolution (see module
    docstring), so the caller must abort rather than silently pick a mode.
    """
    df = pd.read_csv(path, usecols=lambda c: c in ("quarter", "processing_date"), low_memory=False)
    if "quarter" not in df.columns:
        return None, None, True
    q_vals = df["quarter"].dropna().astype(str).str.strip()
    q_vals = q_vals[q_vals != ""]
    if q_vals.empty:
        return None, None, True
    q_cy = _quarter_display_to_cy(q_vals.mode().iat[0])
    proc_dt = None
    is_uniform = True
    if "processing_date" in df.columns:
        proc_vals = pd.to_datetime(df["processing_date"], errors="coerce").dropna()
        if not proc_vals.empty:
            proc_dt = proc_vals.mode().iat[0]
            is_uniform = proc_vals.nunique() == 1
    return q_cy, proc_dt, is_uniform


def _canonical_files_by_quarter(files: list[Path]) -> dict[str, dict]:
    """Group files by self-tagged PBJ quarter; pick the latest-processing_date file per quarter."""
    by_quarter: dict[str, list[tuple]] = {}
    for path in files:
        q_cy, proc_dt, is_uniform = _file_quarter_and_processing_date(path)
        if not q_cy or not _QUARTER_CY_RE.match(q_cy):
            print(f"  skip (no usable quarter tag): {path.name}")
            continue
        if not is_uniform:
            raise SystemExit(
                f"ABORT: {path.name} has more than one distinct processing_date value. "
                "Build-time (ccn, quarter) collapse assumes one uniform processing_date "
                "per source file (see module docstring) -- this file violates that "
                "invariant and must be fixed upstream before this script can trust it."
            )
        by_quarter.setdefault(q_cy, []).append((proc_dt, path))

    canonical: dict[str, dict] = {}
    for q_cy, entries in by_quarter.items():
        dated = [(dt, p) for dt, p in entries if dt is not None]
        if dated:
            dated.sort(key=lambda t: t[0])
            proc_dt, path = dated[-1]
        else:
            entries_sorted = sorted(entries, key=lambda t: t[1].name, reverse=True)
            proc_dt, path = None, entries_sorted[0][1]
        canonical[q_cy] = {"path": path, "processing_date": proc_dt}
    return canonical


def build(source_dir: Path, output_parquet: Path, output_manifest: Path) -> dict:
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory not found: {source_dir}")
    files = _candidate_files(source_dir)
    if not files:
        raise SystemExit(f"No ProviderInfoNorm_*.csv files found under {source_dir}")

    print(f"Scanning {len(files)} candidate source files under {source_dir} ...")
    canonical = _canonical_files_by_quarter(files)
    if not canonical:
        raise SystemExit("No source file produced a usable (quarter, processing_date) tag.")

    frames = []
    source_manifest_entries = []
    for q_cy in sorted(canonical, key=_quarter_sort_key):
        entry = canonical[q_cy]
        path: Path = entry["path"]
        proc_dt = entry["processing_date"]
        print(f"  {q_cy}: canonical -> {path.name} (processing_date={proc_dt})")
        header_cols = set(pd.read_csv(path, nrows=0).columns)
        usecols = ["ccn"] + [c for c in VALUE_COLUMNS if c in header_cols]
        df = pd.read_csv(path, usecols=usecols, low_memory=False)
        df["ccn"] = (
            df["ccn"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(6)
        )
        df = df[df["ccn"].str.len() == 6]
        df["pbj_quarter"] = q_cy
        df["processing_date"] = proc_dt.strftime("%Y-%m-%d") if proc_dt is not None else None
        df["source_filename"] = path.name
        for col in VALUE_COLUMNS:
            if col not in df.columns:
                df[col] = None
        frames.append(df[ALL_OUTPUT_COLUMNS])
        source_manifest_entries.append(
            {
                "pbj_quarter": q_cy,
                "source_filename": path.name,
                "processing_date": proc_dt.strftime("%Y-%m-%d") if proc_dt is not None else None,
                "sha256": _sha256(path),
                "row_count": int(len(df)),
            }
        )

    combined = pd.concat(frames, ignore_index=True)

    # Validation: uniqueness of (ccn, pbj_quarter).
    dup_mask = combined.duplicated(subset=["ccn", "pbj_quarter"], keep=False)
    if dup_mask.any():
        dupes = combined.loc[dup_mask, ["ccn", "pbj_quarter"]].drop_duplicates()
        raise SystemExit(
            f"ABORT: {len(dupes)} (ccn, pbj_quarter) pairs are not unique after build -- "
            "canonical-file selection should make this impossible. Sample:\n"
            f"{dupes.head(10).to_string(index=False)}"
        )

    # Validation: processing_date parses and is within a sane bound.
    proc_parsed = pd.to_datetime(combined["processing_date"], errors="coerce")
    if proc_parsed.isna().any():
        raise SystemExit("ABORT: some rows have an unparseable processing_date.")
    if (proc_parsed.dt.year < 2015).any() or (proc_parsed.dt.year > 2035).any():
        raise SystemExit("ABORT: a processing_date falls outside the sane 2015-2035 bound.")

    combined = combined.sort_values(["ccn", "pbj_quarter"]).reset_index(drop=True)

    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(
        output_parquet,
        engine="pyarrow",
        compression="snappy",
        index=False,
        row_group_size=PARQUET_ROW_GROUP_SIZE,
    )

    quarters_covered = sorted(combined["pbj_quarter"].unique().tolist(), key=_quarter_sort_key)
    manifest = {
        "artifact": "provider_info_history.parquet",
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "build_script": "scripts/build_provider_info_history.py",
        "source_dir": str(source_dir),
        "source_files_considered": len(files),
        "source_files_used": len(source_manifest_entries),
        "row_count": int(len(combined)),
        "unique_ccn_count": int(combined["ccn"].nunique()),
        "quarter_coverage": {
            "min": quarters_covered[0] if quarters_covered else None,
            "max": quarters_covered[-1] if quarters_covered else None,
            "count": len(quarters_covered),
            "all": quarters_covered,
        },
        "grain": "one row per (ccn, pbj_quarter) -- the canonical (latest processing_date "
        "among same-quarter-tagged source files) snapshot for that quarter",
        "columns": ALL_OUTPUT_COLUMNS,
        "sources": source_manifest_entries,
        "validation": {
            "unique_ccn_quarter_pairs": True,
            "processing_date_parseable": True,
            "processing_date_within_bounds": True,
        },
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    parquet_mb = output_parquet.stat().st_size / 1e6
    print(f"\nWrote {output_parquet} ({parquet_mb:.2f} MB), {len(combined)} rows, "
          f"{manifest['unique_ccn_count']} CCNs, quarters {manifest['quarter_coverage']['min']}"
          f"..{manifest['quarter_coverage']['max']}")
    print(f"Wrote {output_manifest}")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-dir", default=None, help="Folder of ProviderInfoNorm_YYYY_MM.csv files")
    ap.add_argument("--output-parquet", default=str(DEFAULT_OUTPUT_PARQUET))
    ap.add_argument("--output-manifest", default=str(DEFAULT_OUTPUT_MANIFEST))
    args = ap.parse_args()

    source_dir = _resolve_source_dir(args.source_dir)
    build(source_dir, Path(args.output_parquet), Path(args.output_manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
