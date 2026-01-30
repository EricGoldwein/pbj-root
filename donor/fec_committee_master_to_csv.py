"""
Convert FEC Committee Master (pipe-delimited .txt) to CSV.
Source: https://www.fec.gov/campaign-finance-data/committee-master-file-description/
Files: cm26.zip (2025-2026), cm24.zip (2023-2024), etc. — unzip to get .txt.
Usage: python fec_committee_master_to_csv.py path/to/cm26.txt
       python fec_committee_master_to_csv.py path/to/cm26.zip -o output/cm26.csv
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


# Default output: donor/data/fec_committee_master/ with cycle labels
CYCLE_LABELS = {
    "cm26": "cm26_2025_2026.csv",
    "cm24": "cm24_2023_2024.csv",
    "cm22": "cm22_2021_2022.csv",
    "cm20": "cm20_2019_2020.csv",
}


def _default_out_path(in_path: Path) -> Path:
    """Output to donor/data/fec_committee_master/ with cycle-labeled filename."""
    data_dir = Path(__file__).parent / "data" / "fec_committee_master"
    stem = in_path.stem.lower()
    if stem in CYCLE_LABELS:
        return data_dir / CYCLE_LABELS[stem]
    return data_dir / f"{stem}.csv"


def main():
    if len(sys.argv) < 2:
        print("Usage: python fec_committee_master_to_csv.py <path to cm*.txt or cm*.zip> [-o output.csv]")
        print("  Default output: donor/data/fec_committee_master/cmNN_YYYY_YYYY.csv (labeled by cycle)")
        sys.exit(1)
    in_path = Path(sys.argv[1])
    out_path = None
    if "-o" in sys.argv:
        i = sys.argv.index("-o")
        if i + 1 < len(sys.argv):
            out_path = Path(sys.argv[i + 1])
    if out_path is None:
        out_path = _default_out_path(in_path)
    n = parse_committee_master(in_path, out_path)
    print(f"Wrote {n} rows to {out_path}")


if __name__ == "__main__":
    main()
