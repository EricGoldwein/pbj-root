"""
Test MAGA Inc. (C00892471) committee fetch: chunked path (what dashboard uses) and Landa presence.
Run from repo root: python -m donor.test_maga_landa
Exits 0 if Landa found; 1 if API key missing or Landa not found.
"""
import sys
from pathlib import Path

donor_dir = Path(__file__).resolve().parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import (
    query_donations_by_committee_chunked,
    query_donations_by_committee,
    FEC_API_KEY,
)


def find_landa(records):
    """Return list of (index, name, amount, date) for records with LANDA in contributor name (Benjamin Landa)."""
    out = []
    for i, r in enumerate(records):
        name = (r.get("contributor_name") or r.get("contributor_name_1") or "").strip()
        if not name:
            continue
        if "landa" in name.lower():
            out.append((i, name, r.get("contribution_receipt_amount"), r.get("contribution_receipt_date")))
    return out


def main():
    committee_id = "C00892471"  # MAGA Inc.
    print("=" * 60)
    print("MAGA Inc. / Landa test (dashboard path)")
    print("=" * 60)
    if not FEC_API_KEY or FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set FEC_API_KEY in donor/.env or environment.")
        return 1

    # 1) Chunked path — exactly what the dashboard uses for MAGA Inc.
    print("\n1. Chunked by year (dashboard path): max_pages_per_period=3, years=[2026, 2025, 2024]")
    try:
        raw_chunked, years_included = query_donations_by_committee_chunked(
            committee_id, max_pages_per_period=3, years=[2026, 2025, 2024]
        )
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1
    print(f"   Total records: {len(raw_chunked)}")
    print(f"   Years included: {years_included}")

    landa_chunked = find_landa(raw_chunked)
    if landa_chunked:
        print(f"   Landa found: YES ({len(landa_chunked)} record(s))")
        for idx, name, amt, date in landa_chunked:
            print(f"      {name!r}  amount={amt}  date={date}")
    else:
        print("   Landa found: NO")

    # 2) Single multi-page path (cursor) — 10 pages, no year filter
    print("\n2. Single multi-page (cursor): max_pages=10")
    try:
        raw_single = query_donations_by_committee(
            committee_id, per_page=100, max_pages=10, timeout=120
        )
    except Exception as e:
        print(f"   FAIL: {e}")
        return 1
    print(f"   Total records: {len(raw_single)}")

    landa_single = find_landa(raw_single)
    if landa_single:
        print(f"   Landa found: YES ({len(landa_single)} record(s))")
        for idx, name, amt, date in landa_single:
            print(f"      {name!r}  amount={amt}  date={date}")
    else:
        print("   Landa found: NO")

    # Pass if Landa appears in either path
    if landa_chunked or landa_single:
        print("\n" + "=" * 60)
        print("PASS: Benjamin Landa appears in at least one path.")
        print("=" * 60)
        return 0
    print("\n" + "=" * 60)
    print("FAIL: Benjamin Landa not found in chunked or single path.")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
