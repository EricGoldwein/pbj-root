#!/usr/bin/env python3
"""Build donor/output/owners_database.csv from policy-selected SNF_All_Owners*.csv (Render build step)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ownership.ownership_release_policy import (  # noqa: E402
    OwnershipReleasePolicyError,
    resolve_ownership_source_path,
)

OUT = REPO / "donor" / "output" / "owners_database.csv"


def main() -> int:
    if OUT.is_file() and OUT.stat().st_size > 10_000:
        print(f"[build_owners_database] OK existing {OUT.name} ({OUT.stat().st_size // 1024} KB)")
        return 0
    try:
        snf = resolve_ownership_source_path(REPO, verify_checksum=False)
    except OwnershipReleasePolicyError as exc:
        print(f"[build_owners_database] FAIL: {exc}", file=sys.stderr)
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
