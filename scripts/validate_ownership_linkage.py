#!/usr/bin/env python3
"""Deploy guard: provider ownership crosswalk + SNF owners indexes must be usable."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ownership.owner_profile import (  # noqa: E402
    _legal_business_name_to_ccn,
    lookup_cms_ownership_for_provider,
    snf_owners_csv_path,
)
from ownership.owner_portfolio_metrics import provider_info_crosswalk_paths  # noqa: E402

CCN_INDEX = REPO / "ownership" / "snf_owners_ccn_index.json.gz"
SQLITE_DB = REPO / "ownership" / "snf_owners_lookup.sqlite"

# Known-good CT enrollments (from SNF All Owners + combined provider_info legal names).
SAMPLE_CCNS = {
    "075011": "AUTUMN LAKE HEALTHCARE AT WINDSOR",
    "075389": "Apple Rehab Laurel Woods",
}


def main() -> int:
    errors: list[str] = []

    if not snf_owners_csv_path() and not SQLITE_DB.is_file():
        errors.append("Missing SNF_All_Owners CSV and snf_owners_lookup.sqlite")

    combined = [p for p in provider_info_crosswalk_paths() if "combined" in p.name.lower()]
    if not combined:
        errors.append("provider_info_combined_latest.csv missing (legal-name crosswalk)")
    else:
        import pandas as pd

        path = combined[0]
        header = pd.read_csv(path, nrows=0).columns.tolist()
        if "legal_business_name" not in [c.lower() for c in header]:
            errors.append(f"{path.name}: no legal_business_name column")
        else:
            legal_col = next(c for c in header if c.lower() == "legal_business_name")
            ccn_col = next(c for c in header if c.lower() in ("ccn", "provnum"))
            sample = pd.read_csv(path, dtype=str, usecols=[ccn_col, legal_col], nrows=20000)
            filled = sample[legal_col].fillna("").str.strip().str.lower().ne("nan") & sample[
                legal_col
            ].fillna("").str.strip().ne("")
            if int(filled.sum()) < 100:
                errors.append(
                    f"{path.name}: legal_business_name mostly empty ({filled.sum()} / {len(sample)})"
                )

    legal_map = _legal_business_name_to_ccn()
    if len(legal_map) < 500:
        errors.append(
            f"legal_business_name crosswalk too small ({len(legal_map)} keys); "
            "check provider_info_combined_latest.csv is loaded"
        )

    for ccn, dba in SAMPLE_CCNS.items():
        hit = lookup_cms_ownership_for_provider(
            {"ccn": ccn, "provider_name": dba},
            ccn=ccn,
            provider_name=dba,
        )
        parties = (hit or {}).get("control_parties") or []
        if not parties:
            errors.append(f"CCN {ccn}: no control_parties from lookup_cms_ownership_for_provider")

    if errors:
        print("[validate_ownership_linkage] FAIL", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(
        f"[validate_ownership_linkage] OK legal_keys={len(legal_map):,} "
        f"ccn_index={'yes' if CCN_INDEX.is_file() else 'no (sqlite fallback)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
