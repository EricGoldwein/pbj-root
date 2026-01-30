"""
Internal test: verify we can fetch FEC API and build docquery links for a Pruitt Health donation.
Run from project root: python donor/test_fec_link.py
Or from donor/: python test_fec_link.py
"""
import os
import sys
from pathlib import Path

# Ensure donor/ is on path and .env is loadable
donor_dir = Path(__file__).resolve().parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))
os.chdir(donor_dir)

# Load .env before importing fec_api_client
env_file = donor_dir / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Use DEMO_KEY for test if no key set (so test can run without .env)
if not os.environ.get("FEC_API_KEY") or os.environ.get("FEC_API_KEY") == "YOUR_API_KEY_HERE":
    os.environ["FEC_API_KEY"] = "DEMO_KEY"
    print("(No FEC_API_KEY in .env — using DEMO_KEY for this test.)")

from fec_api_client import query_donations_by_name, normalize_fec_donation, FEC_API_KEY

def main():
    print("=" * 60)
    print("FEC link internal test (Pruitt Health donation)")
    print("=" * 60)

    # Query a few donations by Pruitt Health
    name = "PRUITTHEALTH"
    print(f"\n1. Querying FEC API for contributor_name={name!r} (per_page=5, max_pages=1)...")
    raw = None
    try:
        raw = query_donations_by_name(name, per_page=5, max_pages=1)
    except Exception as e:
        print(f"   API failed: {e}")
        print("   Using sample data to verify link-building logic.")
    if not raw:
        # Fallback: sample FEC-style record (MAGA INC donation) so we still verify URL logic
        raw = [{
            "contributor_name": "PRUITTHEALTH CONSULTING SERVICES INC",
            "contribution_receipt_amount": 750000,
            "contribution_receipt_date": "2025-08-20",
            "committee_id": "C00892471",
            "sub_id": "1930534",
            "committee": {"committee_id": "C00892471", "name": "MAGA INC."},
        }]
        print("   No results (timeout or empty). Using sample record to verify link logic.")
    print(f"   Got {len(raw)} record(s).")

    # Inspect first raw record keys
    first = raw[0]
    print(f"\n2. First raw record keys: {sorted(first.keys())}")
    committee = first.get("committee")
    if committee is not None:
        print(f"   committee (type {type(committee).__name__}): {committee if isinstance(committee, dict) else 'not a dict'}")
        if isinstance(committee, dict):
            print(f"   committee keys: {sorted(committee.keys())}")
            print(f"   committee_id = {committee.get('committee_id')!r}, name = {committee.get('name')!r}")
    print(f"   Top-level committee_id = {first.get('committee_id')!r}")
    print(f"   sub_id = {first.get('sub_id')!r}")
    print(f"   image_number = {first.get('image_number')!r}")
    print(f"   contribution_receipt_amount = {first.get('contribution_receipt_amount')!r}")
    print(f"   contribution_receipt_date = {first.get('contribution_receipt_date')!r}")

    # Normalize and show link fields
    print("\n3. Normalized records (committee_id, FEC id/sub_id, fec_docquery_url):")
    for i, rec in enumerate(raw[:5], 1):
        norm = normalize_fec_donation(rec)
        cid = norm.get("committee_id") or ""
        cname = norm.get("committee_name") or ""
        fid = norm.get("fec_record_id") or ""
        url = norm.get("fec_docquery_url") or ""
        amt = norm.get("donation_amount")
        date = norm.get("donation_date")
        print(f"   [{i}] Committee: {cname!r} (committee_id={cid!r})")
        print(f"       FEC id (sub_id) = {fid!r}")
        print(f"       Amount = {amt}, Date = {date}")
        print(f"       fec_docquery_url = {url}")

    # Verify first link (HEAD request, short timeout)
    url = normalize_fec_donation(raw[0]).get("fec_docquery_url")
    if url:
        print("\n4. Checking first link (HEAD request, 5s timeout)...")
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "PBJ320-FEC-Link-Test/1.0")
            with urllib.request.urlopen(req, timeout=5) as r:
                print(f"   OK {r.status} — link is reachable")
        except Exception as e:
            print(f"   HEAD failed (link may still work in browser): {e}")
    else:
        print("\n4. No docquery URL to check (missing committee_id or sub_id).")

    print("\n" + "=" * 60)
    print("Done.")

if __name__ == "__main__":
    main()
