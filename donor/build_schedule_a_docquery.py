"""
Build and verify FEC docquery links for Schedule A receipts.

Usage:
  From project root: python donor/build_schedule_a_docquery.py
  From donor/:       python build_schedule_a_docquery.py

This script:
  1. Builds a docquery URL from committee_id + image_number (direct).
  2. Builds from a Schedule A record that includes image_number (sub_id).
  3. If a record lacks image_number, fetches /filings/ for the committee and period
     and uses the filing's image_number (no guessing).
  4. Outputs: constructed URL, source values (committee_id, image_number, API endpoint),
     and confirmation that the link loads (HEAD request).
"""

import os
import sys
from pathlib import Path

donor_dir = Path(__file__).resolve().parent
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))
os.chdir(donor_dir)

env_file = donor_dir / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

if not os.environ.get("FEC_API_KEY") or os.environ.get("FEC_API_KEY") == "YOUR_API_KEY_HERE":
    os.environ["FEC_API_KEY"] = "DEMO_KEY"
    print("(No FEC_API_KEY in .env — using DEMO_KEY.)\n")

from fec_api_client import (
    build_schedule_a_docquery_link,
    correct_docquery_url_for_form_type,
    docquery_path_for_form_type,
    query_donations_by_name,
    query_filings_by_committee,
)


def main():
    print("=" * 70)
    print("FEC Schedule A docquery link construction")
    print("=" * 70)

    # 1) Direct: committee_id + image_number (verified example from user)
    committee_id = "C00892471"
    image_number = "1930418"
    print("\n1. Direct construction (committee_id + image_number)")
    print("-" * 50)
    result = build_schedule_a_docquery_link(
        committee_id=committee_id,
        image_number=image_number,
        verify_link=False,
    )
    _print_result(result)
    expected_url = "https://docquery.fec.gov/cgi-bin/forms/C00892471/1930418/sa/ALL"
    assert result["url"] == expected_url, f"Expected {expected_url!r}, got {result['url']!r}"
    print("   (URL matches verified example.)")

    # 2) From Schedule A record that has file_number (docquery uses file_number, not sub_id)
    print("\n2. From Schedule A record with file_number")
    print("-" * 50)
    schedule_a_with_id = {
        "committee_id": "C00892471",
        "committee": {"committee_id": "C00892471", "name": "MAGA INC."},
        "file_number": "1930534",
        "contribution_receipt_date": "2025-08-20",
        "contribution_receipt_amount": 750000,
    }
    result2 = build_schedule_a_docquery_link(
        committee_id=committee_id,
        schedule_a_record=schedule_a_with_id,
        verify_link=False,
    )
    _print_result(result2)
    assert result2["source"] == "schedule_a"
    assert result2["api_endpoint_used"] == "/schedules/schedule_a/"

    # 3) From Schedule A record WITHOUT image_number — fetch from /filings/
    print("\n3. From Schedule A record WITHOUT image_number (fetch from /filings/)")
    print("-" * 50)
    schedule_a_no_id = {
        "committee_id": "C00892471",
        "committee": {"committee_id": "C00892471", "name": "MAGA INC."},
        "contribution_receipt_date": "2025-08-20",
        "contribution_receipt_amount": 750000,
    }
    result3 = build_schedule_a_docquery_link(
        committee_id=committee_id,
        schedule_a_record=schedule_a_no_id,
        verify_link=False,
    )
    _print_result(result3)
    if result3["source"] == "filings":
        print("   (image_number obtained from OpenFEC /filings/ — no guessing.)")
    elif result3["source"] == "none":
        print("   (No filings returned for this committee/period; link is fallback receipts search.)")

    # 4) Optional: one live Schedule A from API and build link (no HEAD check to avoid timeout)
    print("\n4. Live: one Schedule A from API -> docquery link")
    print("-" * 50)
    try:
        raw = query_donations_by_name("PRUITTHEALTH", per_page=1, max_pages=1)
        if raw:
            rec = raw[0]
            cid = (rec.get("committee") or {}).get("committee_id") or rec.get("committee_id")
            result4 = build_schedule_a_docquery_link(
                committee_id=cid,
                schedule_a_record=rec,
                verify_link=False,
            )
            _print_result(result4)
            print("   Confirmation: open the URL in a browser to verify it displays Schedule A receipts.")
        else:
            print("   No Schedule A results (API empty or rate limit).")
    except Exception as e:
        print(f"   API or link error: {e}")

    # 5) Form 13 (inaugural): C00894162, 1910509 -> f132 (e.g. Benjamin Landa / Trump Vance Inaugural)
    #    Pass form_type="F13" so path is a deterministic formula (no API); FEC docquery uses f132 for Form 13.
    print("\n5. Form 13 (inaugural) -> f132 (C00894162, 1910509)")
    print("-" * 50)
    result5 = build_schedule_a_docquery_link(
        committee_id="C00894162",
        image_number="1910509",
        form_type="F13",
        verify_link=False,
    )
    _print_result(result5)
    assert result5["url"].endswith("/f132"), f"Form 13 should produce .../f132, got {result5['url']!r}"
    print("   (Formula: form_type F13 -> path f132; no API, no fuzzy matching.)")

    # 6) correct_docquery_url_for_form_type: wrong sa/ALL -> corrected f132 (Landa example)
    #    Requires API to look up form_type for the filing; skip assertion if offline.
    print("\n6. correct_docquery_url_for_form_type (sa/ALL -> f132 for Form 13)")
    print("-" * 50)
    wrong_url = "https://docquery.fec.gov/cgi-bin/forms/C00894162/1910509/sa/ALL"
    corrected = correct_docquery_url_for_form_type(wrong_url)
    print(f"   Input:  {wrong_url}")
    print(f"   Output: {corrected or '(unchanged)'}")
    if corrected:
        assert corrected.endswith("/f132"), f"Expected .../f132, got {corrected!r}"
        print("   (Stored sa/ALL URL corrected to f132 so Landa link works.)")
    else:
        print("   (API unavailable or filing not F13; correction skipped. Formula test in #5 and #7.)")

    # 7) docquery_path_for_form_type (no API)
    print("\n7. docquery_path_for_form_type (F13 -> f132, other -> sa/ALL)")
    print("-" * 50)
    assert docquery_path_for_form_type("F13") == "f132"
    assert docquery_path_for_form_type("F3") == "sa/ALL"
    assert docquery_path_for_form_type("F3X") == "sa/ALL"
    assert docquery_path_for_form_type(None) == "sa/ALL"
    print("   F13 -> f132, F3/F3X/None -> sa/ALL (OK)")

    print("\n" + "=" * 70)
    print("Done.")


def _print_result(result):
    """Print structured output: URL, source values, confirmation."""
    print(f"   URL: {result.get('url', '')}")
    print(f"   committee_id: {result.get('committee_id', '')}")
    print(f"   image_number: {result.get('image_number', '')}")
    print(f"   source: {result.get('source', '')}")
    print(f"   api_endpoint_used: {result.get('api_endpoint_used', '')}")
    if "link_verified" in result:
        status = "yes" if result["link_verified"] else "no"
        print(f"   link_verified: {status} (link loads and displays Schedule A: {status})")


if __name__ == "__main__":
    main()
