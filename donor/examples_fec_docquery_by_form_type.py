"""
Fetch one filing per form type (F3, F3P, F3X, F3L) from the FEC API and print
the docquery URL we derive. Use these URLs to manually verify that sa/ALL works
for each form type.

Usage (from project root, with FEC_API_KEY in donor/.env or env):
  python donor/examples_fec_docquery_by_form_type.py

Requires network (calls api.open.fec.gov).
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
    print("(Using DEMO_KEY; add FEC_API_KEY to donor/.env for higher rate limits.)\n")

from fec_api_client import (
    DOCQUERY_BASE_URL,
    FEC_API_BASE_URL,
    docquery_path_for_form_type,
    query_filings_by_committee,
)
# Use same validity check as link builder (4-12 digit filing number; docquery rejects negative/other)
try:
    from fec_api_client import _is_valid_filing_image_id
except ImportError:
    def _is_valid_filing_image_id(val):
        if val is None:
            return False
        s = str(val).strip()
        if s.startswith("FEC-"):
            s = s[4:].strip()
        return bool(s and s.isdigit() and 4 <= len(s) <= 12)

import requests
import time

# Known committees that file each form type (for when /filings?form_type= alone returns nothing).
# F3 = House/Senate, F3P = Presidential, F3X = PAC/party, F3L = Lobbyist bundling.
KNOWN_COMMITTEE_BY_FORM = {
    "F3X": "C00892471",   # MAGA Inc. (PAC)
    "F3": "C00703975",    # Example House committee (e.g. a candidate committee)
    "F3P": "C00848793",   # Example presidential committee
    "F3L": None,          # Less common; we'll try API first
}


def _rate_limit():
    time.sleep(0.6)


def fetch_one_filing_by_form_type(form_type: str):
    """Get one filing of the given form_type with a valid file_number (4-12 digits) for docquery. Returns (committee_id, file_number, form_type) or None."""
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    # Try global filings endpoint with form_type filter; request a few pages to find valid file_number.
    _rate_limit()
    try:
        r = requests.get(
            f"{FEC_API_BASE_URL}/filings",
            params={
                "api_key": api_key,
                "form_type": form_type,
                "per_page": 20,
                "sort": "-receipt_date",
            },
            timeout=30,
        )
        r.raise_for_status()
        results = (r.json() or {}).get("results") or []
        for f in results:
            cid = (f.get("committee") or {}).get("committee_id") or f.get("committee_id") or ""
            fn = f.get("file_number") or f.get("image_number")
            ft = (f.get("form_type") or "").strip() or form_type
            if cid and fn is not None and _is_valid_filing_image_id(fn):
                return (str(cid).strip(), str(fn).strip().lstrip("FEC-"), ft)
    except Exception:
        pass
    # Fallback: use known committee for this form type.
    cid = KNOWN_COMMITTEE_BY_FORM.get(form_type)
    if not cid:
        return None
    filings = query_filings_by_committee(cid, form_type=form_type, per_page=20, max_pages=1)
    for f in filings:
        fn = f.get("file_number") or f.get("image_number")
        ft = (f.get("form_type") or "").strip() or form_type
        if fn is not None and _is_valid_filing_image_id(fn):
            return (cid, str(fn).strip().lstrip("FEC-"), ft)
    return None


def main():
    print("=" * 70)
    print("FEC docquery URLs derived from API by form type (F3, F3P, F3X, F3L)")
    print("=" * 70)
    print("Each URL is built from: committee_id + file_number from OpenFEC /filings/,")
    print("path = docquery_path_for_form_type(form_type) -> sa/ALL for these types.\n")

    for form_type in ("F3", "F3P", "F3X", "F3L"):
        row = fetch_one_filing_by_form_type(form_type)
        if not row:
            print(f"{form_type}: No filing found (skip or add committee to KNOWN_COMMITTEE_BY_FORM).\n")
            continue
        committee_id, file_number, resolved_form = row
        path = docquery_path_for_form_type(resolved_form)
        url = f"{DOCQUERY_BASE_URL}/{committee_id}/{file_number}/{path}"
        print(f"Form type: {resolved_form}")
        print(f"  committee_id: {committee_id}")
        print(f"  file_number:  {file_number}")
        print(f"  path:         {path}")
        print(f"  URL:          {url}")
        print()

    print("=" * 70)
    print("Open each URL in a browser; you should see 'SCHEDULE A - ITEMIZED RECEIPTS'.")
    print("=" * 70)


if __name__ == "__main__":
    main()
