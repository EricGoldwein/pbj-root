"""
Thorough verification: MAGA Inc. committee API vs name API.
1. List ALL donations >= $1M from committee API - is there a $5M and what name?
2. Try alternate committee_id / parameters.
3. Confirm Landa $5M only appears in name search.
Run: python -m donor.verify_maga_api_thorough
"""
import sys
from pathlib import Path

donor_dir = Path(__file__).resolve().parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import (
    query_donations_by_committee,
    query_donations_by_name,
    FEC_API_KEY,
    FEC_API_BASE_URL,
    _rate_limit,
)
import requests

def main():
    cid = "C00892471"  # MAGA Inc.
    if not FEC_API_KEY or FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("Set FEC_API_KEY")
        return 1

    print("=" * 60)
    print("1. COMMITTEE API: all contributions for C00892471 (MAGA Inc.)")
    print("=" * 60)
    raw = query_donations_by_committee(cid, per_page=100, max_pages=None)
    print("Total from committee API:", len(raw))

    # Every donation >= 500k with name and amount
    big = []
    for r in raw:
        amt = r.get("contribution_receipt_amount")
        if amt is None:
            try:
                amt = float(r.get("contribution_receipt_amount") or 0)
            except Exception:
                amt = 0
        else:
            try:
                amt = float(amt)
            except Exception:
                amt = 0
        if amt >= 500_000:
            name = (r.get("contributor_name") or "").strip()
            big.append((name, amt, r.get("contribution_receipt_date"), r.get("sub_id")))

    print("\nDonations >= $500,000 from committee API:")
    if not big:
        print("  (none)")
    else:
        for name, amt, date, sub_id in sorted(big, key=lambda x: -x[1]):
            print("  %s  $%s  date=%s  sub_id=%s" % (repr(name), amt, date, sub_id))

    # Any $5M or 5000000?
    five_mil = [x for x in raw if float(x.get("contribution_receipt_amount") or 0) in (5_000_000, 5000000.0)]
    print("\nRecords with amount exactly $5,000,000 from committee API:", len(five_mil))
    for r in five_mil:
        print("  contributor_name=%r  committee_id=%r  sub_id=%r" % (
            r.get("contributor_name"),
            r.get("committee_id"),
            r.get("sub_id"),
        ))

    print("\n" + "=" * 60)
    print("2. NAME API: query_donations_by_name('LANDA, BENJAMIN')")
    print("=" * 60)
    by_name = query_donations_by_name("LANDA, BENJAMIN", per_page=100)
    print("Total from name API:", len(by_name))
    maga_from_name = [r for r in (by_name or []) if str(r.get("committee_id") or "").strip().upper() == "C00892471"]
    print("Of those, committee_id=C00892471 (MAGA Inc.):", len(maga_from_name))
    for r in maga_from_name[:5]:
        print("  contributor_name=%r  amount=%s  date=%s  sub_id=%r" % (
            r.get("contributor_name"),
            r.get("contribution_receipt_amount"),
            r.get("contribution_receipt_date"),
            r.get("sub_id"),
        ))

    # Is that Landa's sub_id in the committee API results?
    landa_sub_ids = {str(r.get("sub_id")) for r in maga_from_name if r.get("sub_id") is not None}
    committee_sub_ids = {str(r.get("sub_id")) for r in raw if r.get("sub_id") is not None}
    overlap = landa_sub_ids & committee_sub_ids
    print("\nLanda MAGA donation sub_id(s) from name API:", landa_sub_ids)
    print("Do any of these appear in committee API results?", "YES" if overlap else "NO")

    print("\n" + "=" * 60)
    print("3. ALTERNATE committee_id / parameters")
    print("=" * 60)
    for alt_cid, label in [
        ("c00892471", "lowercase"),
        ("C00892471", "canonical"),
    ]:
        _rate_limit()
        resp = requests.get(
            f"{FEC_API_BASE_URL}/schedules/schedule_a",
            params={"api_key": FEC_API_KEY, "committee_id": alt_cid, "per_page": 10, "page": 1, "sort": "-contribution_receipt_date"},
            timeout=30,
        )
        if resp.status_code != 200:
            print("  %s: status %s" % (label, resp.status_code))
            continue
        data = resp.json()
        pag = data.get("pagination", {})
        count = pag.get("count")
        print("  committee_id=%r -> count=%s pages=%s" % (alt_cid, count, pag.get("pages")))
        if data.get("results"):
            r0 = data["results"][0]
            print("    first contributor_name=%r  amount=%s" % (r0.get("contributor_name"), r0.get("contribution_receipt_amount")))

    # Check if API has data_type or other filter we might be missing
    print("\n" + "=" * 60)
    print("4. OpenFEC schedule_a parameters (sample request)")
    print("=" * 60)
    _rate_limit()
    resp = requests.get(
        f"{FEC_API_BASE_URL}/schedules/schedule_a",
        params={"api_key": FEC_API_KEY, "committee_id": cid, "per_page": 1, "page": 1},
        timeout=30,
    )
    data = resp.json()
    if data.get("results"):
        print("Top-level keys in one result:", list(data["results"][0].keys())[:25])

    return 0

if __name__ == "__main__":
    sys.exit(main())
