"""
Test FEC API directly for Moshe Stern - no app, no filtering.
Run from repo root:  python donor/test_fec_moshe_stern.py
Run from donor/:    python test_fec_moshe_stern.py
Uses 15s timeout so it doesn't hang (set FEC_API_TIMEOUT=15 before import).
"""
import os
import sys

# Short timeout for this test so we don't hang
os.environ.setdefault("FEC_API_TIMEOUT", "15")

_donor_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_donor_dir)
if _donor_dir not in sys.path:
    sys.path.insert(0, _donor_dir)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    from donor.fec_api_client import query_donations_by_name, FEC_API_KEY
except ImportError:
    from fec_api_client import query_donations_by_name, FEC_API_KEY


def main():
    if FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set FEC_API_KEY in donor/.env or environment")
        return 1

    names_to_try = [
        "MOSHE STERN",
        "MOSHE A STERN",
        "STERN, MOSHE",
    ]
    print("Testing FEC API directly (15s timeout per query, no app, no filtering):\n")
    for name in names_to_try:
        print(f"  contributor_name={name!r} contributor_type=individual")
        try:
            donations = query_donations_by_name(
                contributor_name=name,
                contributor_type="IND",
                per_page=100,
                max_pages=1,
            )
            print(f"    -> {len(donations)} raw results")
            if donations:
                for i, d in enumerate(donations[:5]):
                    cn = d.get("contributor_name", "")
                    amt = d.get("contribution_receipt_amount", "")
                    dt = d.get("contribution_receipt_date", "")
                    print(f"       [{i+1}] {cn!r}  {amt}  {dt}")
        except Exception as e:
            print(f"    -> ERROR: {type(e).__name__}: {e}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
