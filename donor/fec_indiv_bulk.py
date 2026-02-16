"""
FEC individual contributions bulk data (indiv*.zip / indiv*.parquet).

Committee search can use local bulk data when available for fast lookups
instead of the FEC API (which can timeout for large committees like ActBlue).

- indiv26.zip = 2025-2026 cycle, indiv24 = 2023-2024, indiv22 = 2021-2022, indiv20 = 2019-2020.
- We use 2020 through present: indiv20, indiv22, indiv24, indiv26.
- Bulk file is pipe-delimited inside the zip (no header row in FEC bulk; use header from spec).
- Parquet: build once with build_parquet_from_indiv_zip(); then query by CMTE_ID is fast.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import json
from datetime import datetime

# Columns in FEC indiv bulk file (pipe-delimited)
INDIV_COLS = [
    "CMTE_ID", "AMNDT_IND", "RPT_TP", "TRANSACTION_PGI", "IMAGE_NUM", "TRANSACTION_TP",
    "ENTITY_TP", "NAME", "CITY", "STATE", "ZIP_CODE", "EMPLOYER", "OCCUPATION",
    "TRANSACTION_DT", "TRANSACTION_AMT", "OTHER_ID", "TRAN_ID", "FILE_NUM",
    "MEMO_CD", "MEMO_TEXT", "SUB_ID",
]


def _parse_transaction_dt(mmddyyyy: str) -> str:
    """Convert MMDDYYYY to YYYY-MM-DD. Returns '' if invalid."""
    s = (mmddyyyy or "").strip()
    if len(s) != 8 or not s.isdigit():
        return ""
    try:
        mm, dd, yyyy = int(s[:2]), int(s[2:4]), int(s[4:8])
        if 1 <= mm <= 12 and 1 <= dd <= 31 and 1970 <= yyyy <= 2030:
            return f"{yyyy}-{mm:02d}-{dd:02d}"
    except (ValueError, TypeError):
        pass
    return ""


def _bulk_row_to_api_like(row: Dict[str, Any], committee_id: str) -> Dict[str, Any]:
    """Convert one bulk indiv row to the shape expected by normalize_fec_donation (API-like)."""
    trans_dt = (row.get("TRANSACTION_DT") or "").strip()
    date_iso = _parse_transaction_dt(trans_dt)
    amt = row.get("TRANSACTION_AMT")
    try:
        amount = float(amt) if amt not in (None, "") else 0.0
    except (TypeError, ValueError):
        amount = 0.0
    cid = (row.get("CMTE_ID") or committee_id).strip()
    return {
        "contributor_name": (row.get("NAME") or "").strip(),
        "contribution_receipt_amount": amount,
        "contribution_receipt_date": date_iso or trans_dt,
        "committee_id": cid,
        "committee": {"committee_id": cid, "name": ""},
        "candidate": {},
        "contributor_city": (row.get("CITY") or "").strip(),
        "contributor_state": (row.get("STATE") or "").strip(),
        "contributor_zip": (row.get("ZIP_CODE") or "").strip(),
        "contributor_employer": (row.get("EMPLOYER") or "").strip(),
        "contributor_occupation": (row.get("OCCUPATION") or "").strip(),
        "memo_code": (row.get("MEMO_CD") or "").strip(),
        "memo_text": (row.get("MEMO_TEXT") or "").strip(),
        "file_number": row.get("FILE_NUM"),
        "sub_id": row.get("SUB_ID"),
        "image_number": row.get("IMAGE_NUM"),
    }


def get_contributions_by_committee_from_bulk(
    committee_id: str,
    data_dir: Optional[Path] = None,
    year_from: int = 2020,
    bulk_max_year: Optional[int] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], List[int], bool]:
    """
    Get contributions for a committee from local Parquet (if built).
    Returns (list of API-like raw records, years_included, used_bulk).
    If no Parquet or no data: (None, [], False).

    bulk_max_year: If set, only include parquet cycles ending on or before this year.
        Used for massive committees (ActBlue, WinRed) so we serve through 2024 only.
    """
    if not committee_id or not (committee_id or "").strip():
        return None, [], False
    try:
        import pandas as pd
    except ImportError:
        return None, [], False
    data_dir = data_dir or Path(__file__).resolve().parent / "FEC data"
    if not data_dir.exists():
        return None, [], False
    committee_id = (committee_id or "").strip()
    # Parquet files: full indiv26.parquet (2025-2026), or conduit-only indiv26_conduits.parquet
    # Per cycle: try full first; if missing, try conduit (ActBlue/WinRed only).
    cycle_specs = [
        ("indiv26.parquet", "indiv26_conduits.parquet", 2025, 2026),
        ("indiv24.parquet", "indiv24_conduits.parquet", 2023, 2024),
        ("indiv22.parquet", "indiv22_conduits.parquet", 2021, 2022),
        ("indiv20.parquet", "indiv20_conduits.parquet", 2019, 2020),
    ]
    all_rows: List[Dict[str, Any]] = []
    years_included: List[int] = []
    for full_fname, conduit_fname, y1, y2 in cycle_specs:
        if y2 < year_from:
            continue
        if bulk_max_year is not None and y2 > bulk_max_year:
            continue
        path = data_dir / full_fname
        if not path.exists():
            path = data_dir / conduit_fname
        if not path.exists():
            continue
        try:
            # PyArrow predicate pushdown: only read rows for this committee
            df = pd.read_parquet(
                path,
                columns=["CMTE_ID", "NAME", "CITY", "STATE", "ZIP_CODE", "EMPLOYER", "OCCUPATION", "TRANSACTION_DT", "TRANSACTION_AMT", "MEMO_CD", "MEMO_TEXT", "FILE_NUM", "SUB_ID", "IMAGE_NUM"],
                filters=[("CMTE_ID", "==", committee_id)],
            )
        except Exception as e:
            print(f"  [WARN] Could not read {path}: {e}")
            continue
        if df.empty:
            continue
        years_included.extend([y1, y2])
        for _, row in df.iterrows():
            r = row.to_dict()
            all_rows.append(_bulk_row_to_api_like(r, committee_id))
    years_included = sorted(set(years_included))
    if not all_rows:
        return None, [], False
    return all_rows, years_included, True


def get_bulk_manifest(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Return manifest of bulk data (parquet last_updated, row counts).
    Reads bulk_manifest.json if present; else builds from parquet file mtimes.
    """
    data_dir = data_dir or Path(__file__).resolve().parent / "FEC data"
    manifest_path = data_dir / "bulk_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    out = {"parquet": {}, "committee_csvs": {}, "last_updated": None}
    parquet_names = [
        "indiv26.parquet", "indiv26_conduits.parquet",
        "indiv24.parquet", "indiv24_conduits.parquet",
        "indiv22.parquet", "indiv22_conduits.parquet",
        "indiv20.parquet", "indiv20_conduits.parquet",
    ]
    for fname in parquet_names:
        path = data_dir / fname
        if path.exists():
            try:
                stat = path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                out["parquet"][fname] = {"last_updated": mtime.strftime("%Y-%m-%d"), "path": fname}
            except Exception:
                out["parquet"][fname] = {"last_updated": None, "path": fname}
    return out


# Default big committees to extract (ActBlue, WinRed). Add more IDs as needed.
DEFAULT_CONDUIT_IDS = {"C00401224", "C00694323"}

# For ActBlue, WinRed, and other massive committees: we only use bulk parquet through this year.
# Current cycle (indiv26 = 2025-2026) is excluded to keep data manageable and explicit.
# Use indiv24 (2023-2024), indiv22 (2021-2022), indiv20 (2019-2020) — or whatever parquet exists.
BULK_MASSIVE_COMMITTEE_MAX_YEAR = 2024

# Committees with >= 50k contributions in indiv26 (2025-2026); API is unsustainable for these.
# Run: python -m donor.analyze_indiv_parquet --output-ids to refresh.
MASSIVE_COMMITTEES = {
    "C00000935", "C00003418", "C00010603", "C00027466", "C00042366", "C00075820",
    "C00147512", "C00193433", "C00271338", "C00365536", "C00401224", "C00495028",
    "C00540302", "C00562983", "C00573261", "C00580068", "C00608398", "C00608695",
    "C00639591", "C00665638", "C00676395", "C00694323", "C00696526", "C00718866",
    "C00742007", "C00744946", "C00750521", "C00770941", "C00784934", "C00830679",
    "C00836403", "C00873893",
}


def build_conduits_parquet_from_indiv_zip(
    zip_path: Path,
    output_parquet_path: Path,
    committee_ids: Optional[set] = None,
    year_from: int = 2020,
    chunksize: int = 500_000,
) -> int:
    """
    Extract only specified committee(s) from an FEC indiv*.zip into a smaller parquet.
    Use this when you don't want to build full parquet (e.g. only need ActBlue/WinRed).
    committee_ids: set of CMTE_ID strings (default: ActBlue, WinRed).
    Returns number of rows written.
    """
    import zipfile
    import pandas as pd

    committee_ids = committee_ids or DEFAULT_CONDUIT_IDS
    committee_ids = {str(c).strip().upper() for c in committee_ids}
    zip_path = Path(zip_path)
    output_parquet_path = Path(output_parquet_path)
    output_parquet_path.parent.mkdir(parents=True, exist_ok=True)

    chunks_list = []
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        txt_name = next(
            (n for n in names if n.endswith(".txt") or (".txt" in n and not n.startswith("__"))),
            names[0] if names else None,
        )
        if not txt_name:
            raise FileNotFoundError(f"No .txt in zip: {zip_path}")
        print(
            f"Extracting committees {sorted(committee_ids)} from {txt_name} (chunks of {chunksize:,})...",
            flush=True,
        )
        with z.open(txt_name) as f:
            chunk_num = 0
            for chunk in pd.read_csv(
                f,
                sep="|",
                names=INDIV_COLS,
                dtype=str,
                chunksize=chunksize,
                on_bad_lines="skip",
                low_memory=False,
            ):
                chunk_num += 1
                if "CMTE_ID" not in chunk.columns:
                    continue
                chunk = chunk[chunk["CMTE_ID"].fillna("").astype(str).str.strip().str.upper().isin(committee_ids)]
                if chunk.empty:
                    continue
                if "TRANSACTION_DT" in chunk.columns:

                    def year_ok(d):
                        s = str(d)[:8]
                        if len(s) == 8 and s.isdigit():
                            y = int(s[4:8])
                            return y >= year_from
                        return True

                    chunk = chunk[chunk["TRANSACTION_DT"].apply(year_ok)]
                if chunk.empty:
                    continue
                chunks_list.append(chunk)
                total_so_far = sum(len(c) for c in chunks_list)
                print(
                    f"  Chunk {chunk_num}: kept {len(chunk):,} rows (total so far: {total_so_far:,})",
                    flush=True,
                )

    if not chunks_list:
        print("No rows matched. Wrote 0 rows.", flush=True)
        return 0
    print("Combining chunks and writing Parquet...", flush=True)
    combined = pd.concat(chunks_list, ignore_index=True)
    combined.to_parquet(output_parquet_path, engine="pyarrow", index=False)
    n = len(combined)
    data_dir = output_parquet_path.parent
    manifest_path = data_dir / "bulk_manifest.json"
    manifest = (
        get_bulk_manifest(data_dir)
        if manifest_path.exists()
        else {"parquet": {}, "committee_csvs": {}}
    )
    manifest["parquet"][output_parquet_path.name] = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "rows": n,
        "path": output_parquet_path.name,
        "conduits": sorted(committee_ids),
    }
    manifest["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"  [WARN] Could not write manifest: {e}", flush=True)
    print(f"Done. Wrote {n:,} rows to {output_parquet_path}", flush=True)
    return n


def build_owner_extract_parquet(
    zip_path: Path,
    output_parquet_path: Path,
    owners_path: Path,
    year_from: int = 2020,
    chunksize: int = 500_000,
) -> int:
    """
    Stream indiv zip and write only rows where contributor matches nursing home owners (CMS list).
    Output is small (only owner contributions across ALL committees: HMP, ActBlue, WinRed, etc.).
    Use this instead of full parquet when you only need Top Contributors / owner search.
    Returns number of rows written.
    """
    import zipfile
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    from donor.owner_contributor_utils import build_owner_lookup, is_owner_contributor

    zip_path = Path(zip_path)
    output_parquet_path = Path(output_parquet_path)
    output_parquet_path.parent.mkdir(parents=True, exist_ok=True)

    owners_df = pd.read_csv(owners_path, dtype=str, low_memory=False)
    lookup = build_owner_lookup(owners_df)
    print(f"Loaded {len(lookup):,} owner name variants from {owners_path.name}", flush=True)

    def year_ok(d):
        s = str(d)[:8]
        if len(s) == 8 and s.isdigit():
            try:
                y = int(s[4:8])
                return y >= year_from
            except (ValueError, TypeError):
                return True
        return True

    writer = None
    schema = None
    n = 0
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        txt_name = next((n for n in names if n.endswith(".txt") or (".txt" in n and not n.startswith("__"))), names[0] if names else None)
        if not txt_name:
            raise FileNotFoundError(f"No .txt in zip: {zip_path}")
        print(f"Streaming {txt_name} (chunks of {chunksize:,}), keeping owner matches...", flush=True)
        with z.open(txt_name) as f:
            chunk_num = 0
            for chunk in pd.read_csv(f, sep="|", names=INDIV_COLS, dtype=str, chunksize=chunksize, on_bad_lines="skip", low_memory=False):
                chunk_num += 1
                if "NAME" not in chunk.columns or "TRANSACTION_DT" not in chunk.columns:
                    continue
                chunk = chunk[chunk["TRANSACTION_DT"].apply(year_ok)]
                # Filter: contributor name matches owner
                mask = chunk["NAME"].fillna("").astype(str).apply(lambda x: is_owner_contributor(x, lookup))
                chunk = chunk[mask]
                if chunk.empty:
                    continue
                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(output_parquet_path, schema)
                writer.write_table(table)
                n += len(chunk)
                print(f"  Chunk {chunk_num}: kept {len(chunk):,} owner rows (total so far: {n:,})", flush=True)
    if writer is not None:
        writer.close()
    if n == 0:
        return 0
    data_dir = output_parquet_path.parent
    manifest_path = data_dir / "bulk_manifest.json"
    manifest = get_bulk_manifest(data_dir) if manifest_path.exists() else {"parquet": {}, "committee_csvs": {}}
    manifest["parquet"][output_parquet_path.name] = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "rows": n,
        "path": output_parquet_path.name,
        "owner_extract": True,
    }
    manifest["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"  [WARN] Could not write manifest: {e}", flush=True)
    print(f"Done. Wrote {n:,} owner-only rows to {output_parquet_path}", flush=True)
    return n


def build_parquet_from_indiv_zip(
    zip_path: Path,
    output_parquet_path: Path,
    year_from: int = 2020,
    chunksize: int = 500_000,
) -> int:
    """
    Build a single Parquet file from an FEC indiv*.zip (pipe-delimited inside).
    Keeps only rows with transaction year >= year_from.
    Streams chunks to parquet (no full concat) to avoid OOM on large files (50M+ rows).
    Returns number of rows written.
    Run once (e.g. python -m donor.fec_indiv_bulk) to create indiv26.parquet etc.
    """
    import zipfile
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    zip_path = Path(zip_path)
    output_parquet_path = Path(output_parquet_path)
    output_parquet_path.parent.mkdir(parents=True, exist_ok=True)

    def year_ok(d):
        s = str(d)[:8]
        if len(s) == 8 and s.isdigit():
            try:
                y = int(s[4:8])
                return y >= year_from
            except (ValueError, TypeError):
                return True
        return True

    writer = None
    schema = None
    n = 0
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        txt_name = next((n for n in names if n.endswith(".txt") or (".txt" in n and not n.startswith("__"))), names[0] if names else None)
        if not txt_name:
            raise FileNotFoundError(f"No .txt in zip: {zip_path}")
        print(f"Reading {txt_name} from zip (chunks of {chunksize:,})...", flush=True)
        with z.open(txt_name) as f:
            chunk_num = 0
            for chunk in pd.read_csv(f, sep="|", names=INDIV_COLS, dtype=str, chunksize=chunksize, on_bad_lines="skip", low_memory=False):
                chunk_num += 1
                if "TRANSACTION_DT" in chunk.columns:
                    chunk = chunk[chunk["TRANSACTION_DT"].apply(year_ok)]
                if chunk.empty:
                    continue
                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(output_parquet_path, schema)
                writer.write_table(table)
                n += len(chunk)
                print(f"  Chunk {chunk_num}: kept {len(chunk):,} rows (total so far: {n:,})", flush=True)
    if writer is not None:
        writer.close()
    if n == 0:
        return 0
    # Update manifest with last_updated and row count
    data_dir = output_parquet_path.parent
    manifest_path = data_dir / "bulk_manifest.json"
    manifest = get_bulk_manifest(data_dir) if manifest_path.exists() else {"parquet": {}, "committee_csvs": {}}
    manifest["parquet"][output_parquet_path.name] = {
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "rows": n,
        "path": output_parquet_path.name,
    }
    manifest["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"  [WARN] Could not write manifest: {e}", flush=True)
    print(f"Done. Wrote {n:,} rows.", flush=True)
    return n


def export_committee_csv(
    committee_id: str,
    label: str,
    data_dir: Optional[Path] = None,
    year_from: int = 2020,
) -> Optional[Path]:
    """
    Export one committee's contributions from parquet to CSV (for serving "download all" from our server).
    Writes committee_<id>_<label>_<date>.csv and updates bulk_manifest.json.
    Returns path to CSV or None.
    """
    import pandas as pd
    data_dir = data_dir or Path(__file__).resolve().parent / "FEC data"
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_name = f"committee_{committee_id}_{label}_{date_str}.csv"
    out_path = data_dir / out_name
    cycle_files = [("indiv26.parquet",), ("indiv24.parquet",), ("indiv22.parquet",), ("indiv20.parquet",)]
    dfs = []
    for (fname,) in cycle_files:
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(
                path,
                columns=INDIV_COLS,
                filters=[("CMTE_ID", "==", committee_id)],
            )
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            print(f"  [WARN] {path}: {e}", flush=True)
    if not dfs:
        print(f"No data for {committee_id} in parquet.", flush=True)
        return None
    combined = pd.concat(dfs, ignore_index=True)
    combined.to_csv(out_path, index=False, encoding="utf-8")
    n = len(combined)
    manifest_path = data_dir / "bulk_manifest.json"
    manifest = get_bulk_manifest(data_dir) if manifest_path.exists() else {"parquet": {}, "committee_csvs": {}}
    if "committee_csvs" not in manifest:
        manifest["committee_csvs"] = {}
    manifest["committee_csvs"][out_name] = {
        "committee_id": committee_id,
        "label": label,
        "last_updated": date_str,
        "rows": n,
    }
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"  [WARN] Could not write manifest: {e}", flush=True)
    print(f"Exported {n:,} rows to {out_path}", flush=True)
    return out_path


def get_committee_csv_path(committee_id: str, data_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Return path to a pre-built committee CSV if one exists (for serving "download all" from our server).
    Checks bulk_manifest.json first, then globs committee_<id>_*.csv and returns the latest by date in filename.
    """
    data_dir = data_dir or Path(__file__).resolve().parent / "FEC data"
    manifest = get_bulk_manifest(data_dir)
    best = None
    best_date = ""
    for name, info in (manifest.get("committee_csvs") or {}).items():
        if info.get("committee_id") != committee_id:
            continue
        p = data_dir / name
        if not p.exists():
            continue
        date_str = info.get("last_updated") or ""
        if date_str > best_date:
            best_date = date_str
            best = p
    if best:
        return best
    # Fallback: glob
    prefix = f"committee_{committee_id}_"
    candidates = list(data_dir.glob(prefix + "*.csv"))
    if not candidates:
        return None
    # Prefer by date in filename (committee_ID_label_YYYY-MM-DD.csv)
    def date_from_path(path: Path) -> str:
        stem = path.stem
        if len(stem) > len(prefix) + 10:
            return stem[-10:]  # YYYY-MM-DD
        return ""
    candidates.sort(key=date_from_path, reverse=True)
    return candidates[0] if candidates else None


if __name__ == "__main__":
    """Build Parquet from indiv zip, extract conduits, extract owners, or export committee CSVs. Usage:
      python -m donor.fec_indiv_bulk build [indiv26.zip] [--out indiv26.parquet] [--year-from 2020]
      python -m donor.fec_indiv_bulk extract-conduits [indiv26.zip] [--out indiv26_conduits.parquet] [--committees C00401224,C00694323]
      python -m donor.fec_indiv_bulk extract-owners [indiv26.zip] [--out indiv26_owners.parquet] [--owners donor/output/owners_database.csv]
      python -m donor.fec_indiv_bulk export [--committee C00401224 --label actblue] ...
    """
    import argparse
    import sys
    p = argparse.ArgumentParser(description="Build FEC indiv Parquet, extract conduits/owners, or export committee CSVs")
    p.add_argument("command_or_zip", nargs="?", default="build", help="'build' | 'extract-conduits' | 'extract-owners' | 'export' or path to zip")
    p.add_argument("zip_path", nargs="?", default=None, help="Path to indiv26.zip etc.")
    p.add_argument("--out", default=None, help="Output Parquet path")
    p.add_argument("--year-from", type=int, default=2020, help="Keep transactions from this year")
    p.add_argument("--committees", default=None, help="(extract-conduits) Comma-separated CMTE_IDs, default: C00401224,C00694323")
    p.add_argument("--owners", default=None, help="(extract-owners) Path to owners_database.csv, default: donor/output/owners_database.csv")
    p.add_argument("--committee", default=None, help="(export) Committee ID, e.g. C00401224")
    p.add_argument("--label", default="", help="(export) Label for filename, e.g. actblue")
    args = p.parse_args()
    data_dir = Path(__file__).resolve().parent / "FEC data"
    base_dir = Path(__file__).resolve().parent
    cmd = args.command_or_zip if args.command_or_zip in ("build", "export", "extract-conduits", "extract-owners") else "build"
    if cmd == "build" and args.command_or_zip and args.command_or_zip not in ("build", "export", "extract-conduits", "extract-owners"):
        zip_path = Path(args.command_or_zip)
    elif args.zip_path:
        zip_path = Path(args.zip_path)
    else:
        zip_path = data_dir / "indiv26.zip"

    if cmd == "export":
        if not args.committee:
            print("export requires --committee (e.g. C00401224)")
            sys.exit(1)
        label = (args.label or args.committee).lower().replace(" ", "_")
        export_committee_csv(args.committee, label, data_dir=data_dir, year_from=args.year_from)
        sys.exit(0)

    if cmd == "extract-conduits":
        committee_ids = None
        if args.committees:
            committee_ids = {c.strip() for c in args.committees.split(",") if c.strip()}
        out_name = (zip_path.stem + "_conduits.parquet") if zip_path.stem.startswith("indiv") else "conduits.parquet"
        out_path = Path(args.out) if args.out else (data_dir / out_name)
        if not zip_path.exists():
            print(f"Zip not found: {zip_path}")
            print("Usage: python -m donor.fec_indiv_bulk extract-conduits path/to/indiv26.zip [--out indiv26_conduits.parquet] [--committees C00401224,C00694323]")
            sys.exit(1)
        n = build_conduits_parquet_from_indiv_zip(zip_path, out_path, committee_ids=committee_ids, year_from=args.year_from)
        print(f"Wrote {n} rows to {out_path}")
        sys.exit(0)

    if cmd == "extract-owners":
        owners_path = Path(args.owners) if args.owners else (base_dir / "output" / "owners_database.csv")
        if not owners_path.exists():
            print(f"Owners file not found: {owners_path}")
            print("Run build_schedule_a_docquery.py or ensure donor/output/owners_database.csv exists.")
            sys.exit(1)
        out_name = (zip_path.stem + "_owners.parquet") if zip_path.stem.startswith("indiv") else "owners.parquet"
        out_path = Path(args.out) if args.out else (data_dir / out_name)
        if not zip_path.exists():
            print(f"Zip not found: {zip_path}")
            print("Usage: python -m donor.fec_indiv_bulk extract-owners path/to/indiv26.zip [--out indiv26_owners.parquet] [--owners donor/output/owners_database.csv]")
            sys.exit(1)
        n = build_owner_extract_parquet(zip_path, out_path, owners_path, year_from=args.year_from)
        print(f"Wrote {n} rows to {out_path}")
        sys.exit(0)

    out_path = Path(args.out) if args.out else zip_path.parent / (zip_path.stem + ".parquet")
    if not zip_path.exists():
        print(f"Zip not found: {zip_path}")
        print("Usage: python -m donor.fec_indiv_bulk build path/to/indiv26.zip [--out path/to/indiv26.parquet]")
        sys.exit(1)
    print(f"Building {out_path} from {zip_path} (year >= {args.year_from})...")
    n = build_parquet_from_indiv_zip(zip_path, out_path, year_from=args.year_from)
    print(f"Wrote {n} rows to {out_path}")
