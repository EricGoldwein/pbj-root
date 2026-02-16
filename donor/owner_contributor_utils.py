"""
Shared owner-matching logic for FEC donor work.
Used by top_nursing_home_contributors_2026 and fec_indiv_bulk extract-owners.
"""

import re
from typing import Dict, Any

import pandas as pd


def normalize_name(s: str) -> str:
    if pd.isna(s) or not s:
        return ""
    s = str(s).upper()
    s = re.sub(r"[^A-Z ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _collapse_middle_initials(norm: str) -> str:
    """Collapse single-letter tokens so 'MOSHE A STERN' -> 'MOSHE STERN'."""
    if not norm or len(norm) < 4:
        return norm
    parts = norm.split()
    kept = [p for p in parts if len(p) > 1]
    return " ".join(kept) if kept else norm


_LEGAL_SUFFIXES = frozenset({'INC', 'CORP', 'LLC', 'LTD', 'CO', 'CORPORATION', 'LP', 'THE'})
_SUBSTRING_BLOCKLIST = frozenset({
    'HEALTHCARE', 'HEALTH', 'SERVICES', 'SERVICE', 'CONSULTING', 'MANAGEMENT', 'CARE', 'MEDICAL',
    'NURSING', 'LIVING', 'CENTER', 'CENTERS', 'OPERATIONS', 'HOLDINGS', 'PROPERTY', 'REALTY',
    'GROUP', 'SOLUTIONS', 'INVESTMENT', 'COMPANY', 'CORPORATION', 'CORP', 'LLC', 'INC',
})


def _stem_org_name(norm_str: str, min_len: int = 6) -> str:
    if not norm_str or not isinstance(norm_str, str):
        return ""
    words = norm_str.split()
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    stem = " ".join(words).strip()
    if len(stem) < min_len or stem in _SUBSTRING_BLOCKLIST:
        return ""
    return stem


def build_owner_lookup(owners_df: pd.DataFrame) -> Dict[str, dict]:
    """Build normalized name -> owner row lookup."""
    lookup: Dict[str, dict] = {}
    for _, row in owners_df.iterrows():
        onorm = normalize_name(row.get('owner_name', ''))
        oorig = normalize_name(str(row.get('owner_name_original', '')))
        otype = (row.get('owner_type', '') or '').upper()
        for n in (onorm, oorig):
            if n:
                lookup[n] = row
                if otype == 'INDIVIDUAL':
                    collapsed = _collapse_middle_initials(n)
                    if collapsed != n and collapsed and collapsed not in lookup:
                        lookup[collapsed] = row
        for n in (onorm, oorig):
            if n:
                stem = _stem_org_name(n)
                if stem and stem not in lookup:
                    lookup[stem] = row
    return lookup


def find_owner(donor_norm: str, lookup: Dict[str, dict]) -> dict | None:
    """Match donor to owner row. FEC uses 'LAST, FIRST'; CMS has 'FIRST LAST'. Allow swap."""
    row = lookup.get(donor_norm)
    if row is not None:
        return row
    if not donor_norm or len(donor_norm) < 4:
        return None
    parts = donor_norm.split()
    if len(parts) >= 2:
        first_last = f"{parts[1]} {parts[0]}"
        row = lookup.get(first_last)
        if row is not None:
            return row
    stem = _stem_org_name(donor_norm)
    if stem:
        return lookup.get(stem)
    return None


def is_owner_contributor(name: str, lookup: Dict[str, dict]) -> bool:
    """Return True if this contributor name matches a nursing home owner."""
    norm = normalize_name(name or "")
    return find_owner(norm, lookup) is not None
