"""
Convert FEC Committee Master (pipe-delimited .txt) to CSV.
Source: https://www.fec.gov/campaign-finance-data/committee-master-file-description/
Files: cm26.zip (2025-2026), cm24.zip (2023-2024), etc. — reads directly from .zip.
Usage: python fec_committee_master_to_csv.py
         → processes all cm*.zip in script directory
       python fec_committee_master_to_csv.py path/to/cm26.zip [-o output/cm26.csv]
       python fec_committee_master_to_csv.py path/to/dir
         → processes all cm*.zip in that directory
"""
import csv
import sys
import zipfile
from pathlib import Path

# FEC Committee master file columns (pipe-delimited, 15 fields)
# https://www.fec.gov/campaign-finance-data/committee-master-file-description/
COMMITTEE_MASTER_COLUMNS = [
    "CMTE_ID",           # 1  Committee identification (e.g. C00100005)
    "CMTE_NM",           # 2  Committee name
    "TRES_NM",           # 3  Treasurer's name
    "CMTE_ST1",          # 4  Street one
    "CMTE_ST2",          # 5  Street two
    "CMTE_CITY",         # 6  City or town
    "CMTE_ST",           # 7  State
    "CMTE_ZIP",          # 8  ZIP code
    "CMTE_DSGN",         # 9  Committee designation (A/B/D/J/P/U)
    "CMTE_TP",           # 10 Committee type (H/S/P/etc.)
    "CMTE_PTY_AFFILIATION",  # 11 Committee party
    "CMTE_FILING_FREQ",  # 12 Filing frequency (A/D/M/Q/T/W)
    "ORG_TP",            # 13 Interest group category (C/L/M/T/V/W/H/I)
    "CONNECTED_ORG_NM",  # 14 Connected organization's name
    "CAND_ID",           # 15 Candidate identification (when CMTE_TP is H, S, or P)
]


def read_txt_from_path(path: Path):
    """Yield lines from path; if path is .zip, read first .txt inside."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as z:
            for name in z.namelist():
                if name.lower().endswith(".txt"):
                    with z.open(name) as f:
                        for line in f:
                            yield line.decode("utf-8", errors="replace").rstrip("\r\n")
                    return
        raise ValueError(f"No .txt file found in zip: {path}")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            yield line.rstrip("\r\n")


def parse_committee_master(in_path: Path, out_path: Path = None):
    """Parse pipe-delimited committee master; write CSV. Returns row count."""
    out_path = out_path or in_path.with_suffix(".csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with open(out_path, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=COMMITTEE_MASTER_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for line in read_txt_from_path(in_path):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            while len(parts) < len(COMMITTEE_MASTER_COLUMNS):
                parts.append("")
            row = dict(zip(COMMITTEE_MASTER_COLUMNS, parts[: len(COMMITTEE_MASTER_COLUMNS)]))
            w.writerow(row)
            rows += 1
    return rows


def main():
    script_dir = Path(__file__).resolve().parent

    if len(sys.argv) < 2:
        # No args: process all cm*.zip in script directory
        inputs = sorted(script_dir.glob("cm*.zip"))
        if not inputs:
            print(f"No cm*.zip files found in {script_dir}")
            sys.exit(1)
        print(f"Processing {len(inputs)} files: {[p.name for p in inputs]}")
        for in_path in inputs:
            n = parse_committee_master(in_path)
            out_file = in_path.with_suffix(".csv")
            print(f"  Wrote {n:,} rows to {out_file.name}")
        return

    in_path = Path(sys.argv[1])
    if "-o" in sys.argv:
        i = sys.argv.index("-o")
        out_path = Path(sys.argv[i + 1]) if i + 1 < len(sys.argv) else None
    else:
        out_path = None

    if in_path.is_dir():
        # Directory: process all cm*.zip inside
        inputs = sorted(in_path.glob("cm*.zip"))
        if not inputs:
            print(f"No cm*.zip files found in {in_path}")
            sys.exit(1)
        print(f"Processing {len(inputs)} files in {in_path}")
        for p in inputs:
            n = parse_committee_master(p)
            print(f"  Wrote {n:,} rows to {p.with_suffix('.csv').name}")
    else:
        n = parse_committee_master(in_path, out_path)
        out_file = out_path or in_path.with_suffix(".csv")
        print(f"Wrote {n:,} rows to {out_file}")


if __name__ == "__main__":
    main()
