"""
One-off: Check FEC API for MAGA Inc. (C00892471) and see if Benjamin Landa appears.
Run from repo root: python -m donor.check_maga_api_landa
"""
import os
import sys
import requests
from pathlib import Path

# Ensure donor is on path and .env is loaded
donor_dir = Path(__file__).resolve().parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import query_donations_by_committee, FEC_API_KEY, FEC_API_BASE_URL, _rate_limit

def main():
    committee_id = "C00892471"  # MAGA Inc.
    print("FEC API check: MAGA Inc. (C00892471) – looking for LANDA/Benjamin Landa")
    print("FEC_API_KEY set:", bool(FEC_API_KEY and FEC_API_KEY != "YOUR_API_KEY_HERE"))
    if not FEC_API_KEY or FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set FEC_API_KEY in donor/.env or environment to use the API.")
        return 1

    # First: one raw request to see pagination structure
    _rate_limit()
    r = requests.get(
        f"{FEC_API_BASE_URL}/schedules/schedule_a",
        params={"api_key": FEC_API_KEY, "committee_id": committee_id, "per_page": 100, "page": 1, "sort": "-contribution_receipt_date"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    print("\nRaw API response keys:", list(data.keys()))
    pagination = data.get("pagination") or data.get("pagination_info") or {}
    print("Pagination object:", pagination)
    print("Results on page 1:", len(data.get("results", [])))

    # Fetch ALL pages (no max_pages) to see total and whether Landa is on a later page
    print("\nFetching ALL pages (100 per page)...")
    try:
        raw = query_donations_by_committee(committee_id, per_page=100, max_pages=None)
    except Exception as e:
        print("API error:", e)
        return 1

    print(f"Total contributions returned: {len(raw)}")
    if not raw:
        print("No results. Committee may have no data in API or different ID.")
        return 0

    # API returns list of dicts; check structure of first result
    first = raw[0]
    name_keys = [k for k in first.keys() if "name" in k.lower() or "contributor" in k.lower()]
    print("Sample keys (name-related):", name_keys)
    # OpenFEC schedule_a often returns contributor_name at top level
    contributor_name_key = "contributor_name" if "contributor_name" in first else (name_keys[0] if name_keys else None)
    if contributor_name_key:
        print(f"Using field: {contributor_name_key!r}")
    else:
        print("First record keys:", list(first.keys())[:15])

    # Search for LANDA
    landa_records = []
    for i, r in enumerate(raw):
        name = (r.get("contributor_name") or r.get("contributor_name_1") or "").strip()
        if not name:
            continue
        if "landa" in name.lower() or "benjamin" in name.lower():
            landa_records.append((i, name, r.get("contribution_receipt_amount"), r.get("contribution_receipt_date")))

    if landa_records:
        print(f"\nFound {len(landa_records)} record(s) with LANDA/Benjamin:")
        for idx, name, amt, date in landa_records:
            print(f"  Row {idx}: {name!r}  amount={amt}  date={date}")
    else:
        print("\nNo contributor with 'LANDA' or 'BENJAMIN' in name in the API response.")
        print("First 5 contributor names (API order):")
        for i, r in enumerate(raw[:5]):
            n = r.get("contributor_name") or r.get("contributor_name_1") or "(no name key)"
            a = r.get("contribution_receipt_amount")
            d = r.get("contribution_receipt_date")
            print(f"  {i}: {n!r}  amount={a}  date={d}")
        print("\nConclusion: The OpenFEC API returns only this set of contributions for MAGA Inc.")
        print("Benjamin Landa is in bulk data (indiv26.parquet) but NOT in the API response.")
        print("To show Landa on the website, use local bulk data (donor/FEC data/indiv26.parquet).")

    return 0

if __name__ == "__main__":
    sys.exit(main())
