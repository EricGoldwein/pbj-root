"""
Traceback script: Find the DIRECT SOURCE of a specific donation.

Usage: python trace_donation_source.py

Traces the $1M donation to TRUMP VANCE INAUGURAL COMMITTEE (C00894162)
around Jan 9, 2025. Queries FEC API, prints raw record, and outputs the
exact docquery/filing URL that is the authoritative source.
"""

import sys
import json
from pathlib import Path

# Add donor dir to path
donor_dir = Path(__file__).resolve().parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

from fec_api_client import (
    query_donations_by_committee,
    normalize_fec_donation,
    build_schedule_a_docquery_link,
    FEC_API_KEY,
)

# Target: TRUMP VANCE INAUGURAL COMMITTEE
COMMITTEE_ID = "C00894162"
COMMITTEE_NAME = "TRUMP VANCE INAUGURAL COMMITTEE, INC."
TARGET_AMOUNT = 1_000_000
TARGET_DATE_START = "2025-01-01"
TARGET_DATE_END = "2025-01-31"


def main():
    print("=" * 80)
    print("DONATION SOURCE TRACEBACK")
    print("=" * 80)
    print(f"Committee: {COMMITTEE_NAME} ({COMMITTEE_ID})")
    print(f"Target: ~${TARGET_AMOUNT:,} contributions in {TARGET_DATE_START} to {TARGET_DATE_END}")
    print()

    if FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: FEC_API_KEY not set. Set it in donor/.env or environment.")
        print("Get a free key at: https://api.open.fec.gov/developers/")
        return 1

    print("Step 1: Query FEC API (Schedule A)...")
    print("  Endpoint: https://api.open.fec.gov/v1/schedules/schedule_a")
    print(f"  Params: committee_id={COMMITTEE_ID}, min_date={TARGET_DATE_START}, max_date={TARGET_DATE_END}")
    print()

    raw_donations = query_donations_by_committee(
        COMMITTEE_ID,
        min_date=TARGET_DATE_START,
        max_date=TARGET_DATE_END,
        per_page=100,
    )

    # Filter for $1M or high amounts
    target_records = [
        r for r in raw_donations
        if r and float(r.get("contribution_receipt_amount", 0) or 0) >= 900_000
    ]
    if not target_records:
        target_records = raw_donations[:20]  # Show first 20 if no $1M found
        print(f"  No contributions >= $900k found. Showing first {len(target_records)} records:")
    else:
        print(f"  Found {len(target_records)} contribution(s) >= $900k")
    print()

    for i, raw in enumerate(target_records):
        amt = float(raw.get("contribution_receipt_amount", 0) or 0)
        name = raw.get("contributor_name", "")
        date_val = raw.get("contribution_receipt_date", "")

        print("-" * 80)
        print(f"RECORD #{i+1}")
        print("-" * 80)
        print()
        print("RAW FEC API RESPONSE (direct from api.open.fec.gov):")
        print(json.dumps(raw, indent=2, default=str))
        print()
        print("KEY FIELDS (source of our display):")
        print(f"  contributor_name (-> donor_name):    {name!r}")
        print(f"  contribution_receipt_amount (-> amt): {amt}")
        print(f"  contribution_receipt_date (-> date):  {date_val}")
        print(f"  file_number (-> docquery URL):       {raw.get('file_number')!r}")
        print(f"  sub_id (line-item ID, NOT for URL): {raw.get('sub_id')!r}")
        print(f"  image_number (page ID):              {raw.get('image_number')!r}")
        print()

        # Normalize (what our app does)
        norm = normalize_fec_donation(raw)
        print("OUR NORMALIZED RECORD:")
        print(f"  donor_name:     {norm.get('donor_name')!r}")
        print(f"  donation_amount: {norm.get('donation_amount')}")
        print(f"  donation_date:  {norm.get('donation_date')!r}")
        print(f"  fec_docquery_url: {norm.get('fec_docquery_url')!r}")
        print()

        # Build docquery link (direct source)
        link_result = build_schedule_a_docquery_link(
            committee_id=raw.get("committee_id") or (raw.get("committee") or {}).get("committee_id") or COMMITTEE_ID,
            schedule_a_record=raw,
        )
        direct_url = link_result.get("url", "")
        file_num = link_result.get("image_number", "")
        source = link_result.get("source", "")

        print("=" * 80)
        print("DIRECT SOURCE (authoritative FEC filing):")
        print("=" * 80)
        if direct_url and "docquery" in direct_url:
            print(f"  Docquery URL: {direct_url}")
            print(f"  (Schedule A filing; file_number={file_num}, source={source})")
        else:
            print(f"  Fallback: {direct_url}")
            print("  (No file_number in API response; link goes to receipts search)")
        print()
        print("  To verify: Open the URL above in a browser to see the actual")
        print("  Schedule A form as filed with the FEC. The contributor name")
        print("  on that form is the authoritative source.")
        print()

    print("=" * 80)
    print("TRACEBACK SUMMARY")
    print("=" * 80)
    print("""
Data flow:
  1. FEC API: https://api.open.fec.gov/v1/schedules/schedule_a
     - committee_id=C00894162, min_date=2025-01-01, max_date=2025-01-31
  2. Raw record: contributor_name, contribution_receipt_amount, contribution_receipt_date, file_number
  3. Our code: fec_api_client.normalize_fec_donation() -> donor_name, donation_amount, donation_date
  4. Docquery URL: https://docquery.fec.gov/cgi-bin/forms/{committee_id}/{file_number}/sa/ALL
     - file_number comes from Schedule A API response (or /filings/ fallback)
  5. Display: owner_donor_dashboard passes fec_docquery_url as fec_link in raw_contributions

The DIRECT SOURCE is the FEC docquery URL - the actual filed Schedule A form.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
