"""
Fetch one Schedule A per form type (F3, F3P, F3X, F3L) from the FEC API and print
the docquery URL we derive. Uses file_number from schedule_a (same as production)
so docquery accepts the report id; /filings file_number often gives Invalid Report Id.

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
    query_donations_by_committee,
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

# Known committees that file each form type; we use schedule_a from these so file_number = docquery report id.
# F3 = House/Senate, F3P = Presidential, F3X = PAC/party, F3L = Lobbyist bundling.
KNOWN_COMMITTEE_BY_FORM = {
    "F3": "C00541474",    # Committee to Elect Shawn Pinkston (House)
    "F3P": "C00890079",   # Conservative American Middle Eastern PAC (Form 3P)
    "F3X": "C00892471",   # MAGA Inc. (PAC)
    "F3L": "C00573949",   # Josh Gottheimer for Congress (F3L; 1943222 works)
}


def _rate_limit():
    time.sleep(0.6)


def fetch_one_schedule_a_by_form_type(form_type: str):
    """Get one schedule_a record for the form_type; use its file_number (docquery accepts this). Returns (committee_id, file_number, form_type) or None."""
    # Prefer schedule_a: file_number from the filing that contains that Schedule A is what docquery expects (avoids Invalid Report Id from /filings).
    cid = KNOWN_COMMITTEE_BY_FORM.get(form_type)
    if cid:
        _rate_limit()
        try:
            records = query_donations_by_committee(cid, per_page=10, max_pages=1)
            for rec in records:
                fn = rec.get("file_number")
                ft = (rec.get("form_type") or "").strip() or form_type
                if fn is not None and _is_valid_filing_image_id(fn):
                    return (cid, str(fn).strip().lstrip("FEC-"), ft)
        except Exception:
            pass
    # Fallback: get committee from /filings?form_type=, then schedule_a for that committee.
    api_key = os.environ.get("FEC_API_KEY", "DEMO_KEY")
    _rate_limit()
    try:
        r = requests.get(
            f"{FEC_API_BASE_URL}/filings",
            params={"api_key": api_key, "form_type": form_type, "per_page": 5, "sort": "-receipt_date"},
            timeout=30,
        )
        r.raise_for_status()
        results = (r.json() or {}).get("results") or []
        for f in results:
            cid = (f.get("committee") or {}).get("committee_id") or f.get("committee_id") or ""
            if not cid:
                continue
            _rate_limit()
            try:
                records = query_donations_by_committee(cid, per_page=5, max_pages=1)
                for rec in records:
                    fn = rec.get("file_number")
                    ft = (rec.get("form_type") or "").strip() or form_type
                    if fn is not None and _is_valid_filing_image_id(fn):
                        return (str(cid).strip(), str(fn).strip().lstrip("FEC-"), ft)
            except Exception:
                continue
    except Exception:
        pass
    return None


def main():
    print("=" * 70)
    print("FEC docquery URLs from schedule_a (same id source as production)")
    print("=" * 70)
    print("file_number from schedule_a = docquery report id; /filings often gives Invalid Report Id.\n")

    for form_type in ("F3", "F3P", "F3X", "F3L"):
        row = fetch_one_schedule_a_by_form_type(form_type)
        if not row:
            print(f"{form_type}: No schedule_a record found (add committee to KNOWN_COMMITTEE_BY_FORM).\n")
            continue
        committee_id, file_number, resolved_form = row
        path = docquery_path_for_form_type(resolved_form)
        url = f"{DOCQUERY_BASE_URL}/{committee_id}/{file_number}/{path}"
        print(f"Form type: {resolved_form}")
        print(f"  committee_id: {committee_id}")
        print(f"  file_number:  {file_number} (from schedule_a)")
        print(f"  path:         {path}")
        print(f"  URL:          {url}")
        print()

    print("=" * 70)
    print("Open each URL in a browser; you should see Schedule A itemized receipts.")
    print("=" * 70)


if __name__ == "__main__":
    main()
