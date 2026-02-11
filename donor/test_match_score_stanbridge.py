"""Test match score for STANBRIDGE, NORMA and KAPPELER, KENDAL (no CMS location)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only the scoring helpers (no Flask/app)
from owner_donor_dashboard import (
    _compute_match_score,
    _names_same_person,
    _empty_loc,
)

def main():
    cases = [
        ("STANBRIDGE, NORMA", "NORMA STANBRIDGE", "The Woodlands", "TX", "", ""),
        ("KAPPELER, KENDAL", "KENDAL KAPPELER", "Dallas", "TX", "", ""),
        # Also test with nan string (as might come from API)
        ("STANBRIDGE, NORMA", "NORMA STANBRIDGE", "The Woodlands", "TX", "nan", "nan"),
    ]
    print("Match score test (same person, no CMS location):\n")
    for fec_name, cms_name, fec_city, fec_state, cms_city, cms_state in cases:
        same = _names_same_person(fec_name, cms_name)
        result = _compute_match_score(fec_name, cms_name, fec_city, fec_state, cms_city, cms_state)
        print(f"  FEC: {fec_name!r}  CMS: {cms_name!r}")
        print(f"  FEC loc: {fec_city!r}, {fec_state!r}  CMS loc: {cms_city!r}, {cms_state!r}")
        print(f"  _names_same_person: {same}")
        print(f"  -> match_band: {result['match_band']!r}  score: {result['match_score']}  name_score: {result['name_score']}  geo_score: {result['geo_score']}  exact_bonus: {result['exact_bonus']}")
        print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
