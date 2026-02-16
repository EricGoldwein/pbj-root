#!/usr/bin/env python3
"""Re-run top list and verify Steven Stroll appears. Uses indiv24_owners.parquet or indiv24.parquet."""
from pathlib import Path
import subprocess
import sys


def main():
    base = Path(__file__).resolve().parent
    data_dir = base / "FEC data"
    owners_24 = data_dir / "indiv24_owners.parquet"
    full_24 = data_dir / "indiv24.parquet"
    csv_path = data_dir / "top_nursing_home_contributors_2026.csv"

    if not owners_24.exists() and not full_24.exists():
        print("No indiv24 data. Build owner-extract or full parquet:")
        print('  python -m donor.fec_indiv_bulk extract-owners "donor/FEC data/indiv24.zip" --out "donor/FEC data/indiv24_owners.parquet"')
        return 1

    print("Re-running top contributors...")
    r = subprocess.run(
        [sys.executable, "-m", "donor.top_nursing_home_contributors_2026", "--top", "500"],
        cwd=base.parent,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        return 1

    if not csv_path.exists():
        print("CSV not produced:", csv_path)
        return 1

    text = csv_path.read_text(encoding="utf-8", errors="replace")
    if "STROLL" in text.upper() or "Stroll" in text:
        print("Steven Stroll FOUND on top list.")
        for line in text.splitlines():
            if "STROLL" in line.upper():
                print("  ", line[:120] + ("..." if len(line) > 120 else ""))
        return 0
    print("Steven Stroll NOT in top 500 CSV. He may be below top 500 or not in data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
