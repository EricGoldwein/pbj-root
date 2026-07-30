"""Parse CMS SNF_All_Owners snapshot release dates from filenames."""

from __future__ import annotations

import re

_MONTH_FROM_NAME: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def parse_snf_owners_release_date(filename: str) -> str:
    """
    Return ISO date ``YYYY-MM-DD`` from an SNF_All_Owners filename, or ``""``.

  Matches pbj-root ``owner_profile._parse_snf_owners_filename`` semantics.
    """
    stem = str(filename or "").strip()
    if not stem:
        return ""
    lower = stem.lower()
    if lower.endswith(".csv"):
        lower = lower[:-4]

    m_iso = re.search(r"(\d{4})[._-](\d{1,2})(?:[._-](\d{1,2}))?", lower)
    if m_iso:
        y, mo = int(m_iso.group(1)), int(m_iso.group(2))
        day = int(m_iso.group(3)) if m_iso.group(3) else 1
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}-{day:02d}"

    m_word = re.search(r"owners[_-]?([a-z]+)[_-]?(\d{4})", lower)
    if m_word:
        mo = _MONTH_FROM_NAME.get(m_word.group(1))
        if mo:
            return f"{int(m_word.group(2)):04d}-{mo:02d}-01"

    return ""
