#!/usr/bin/env python3
"""Build donor/output/owners_database.csv from newest ownership/SNF_All_Owners*.csv (Render build step)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OWNERSHIP_DIR = REPO / "ownership"
OUT = REPO / "donor" / "output" / "owners_database.csv"


def _newest_snf_csv() -> Path | None:
    files = sorted(OWNERSHIP_DIR.glob("SNF_All_Owners*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def main() -> int:
    if OUT.is_file() and OUT.stat().st_size > 10_000:
        print(f"[build_owners_database] OK existing {OUT.name} ({OUT.stat().st_size // 1024} KB)")
        return 0
    snf = _newest_snf_csv()
    if not snf:
        print("[build_owners_database] FAIL: no SNF_All_Owners*.csv under ownership/", file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["MODE"] = "extract"
    env["CMS_OWNERSHIP_FILE"] = str(snf)
    print(f"[build_owners_database] extract from {snf.name} -> {OUT.relative_to(REPO)}")
    subprocess.run(
        [sys.executable, str(REPO / "donor" / "owner_donor.py")],
        cwd=str(REPO),
        env=env,
        check=True,
    )
    if not OUT.is_file():
        print("[build_owners_database] FAIL: owners_database.csv not created", file=sys.stderr)
        return 1
    print(f"[build_owners_database] OK {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
