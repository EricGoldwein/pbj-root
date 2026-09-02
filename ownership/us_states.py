"""US state codes and names for ownership surfaces (50 states + DC; excludes PR).

Verified from: app.py STATE_NAME_TO_CODE / STATES_FOR_RANKING (PR excluded from rankings).
"""
from __future__ import annotations

# Lowercase full name -> USPS code (same keys as app.py STATE_NAME_TO_CODE minus PR).
_STATE_NAME_TO_CODE: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    "district of columbia": "DC",
}

US_STATE_CODE_TO_NAME: dict[str, str] = {
    code: name.title() for name, code in _STATE_NAME_TO_CODE.items()
}

US_STATE_CODES: frozenset[str] = frozenset(US_STATE_CODE_TO_NAME.keys())


def state_page_slug(state_code: str, state_name: str | None = None) -> str:
    """Canonical /state/<slug> segment (matches app.get_canonical_slug)."""
    st = (state_code or "").strip().upper()[:2]
    name = (state_name or US_STATE_CODE_TO_NAME.get(st) or st).strip()
    return name.lower().replace(" ", "-")


def owner_index_slug(state_code: str) -> str:
    """Two-letter slug for /owners/<slug> routes."""
    return (state_code or "").strip().lower()[:2]


def public_owner_states_coverage_phrase() -> str:
    """Hub / SEO copy for nationwide ownership index coverage."""
    return "all 50 states and D.C."
