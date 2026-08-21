"""Normalized name matching for owner / organization search (no fuzzy typo matching)."""
from __future__ import annotations

import re


def _norm_search_key(name: str) -> str:
    """Uppercase key with collapsed whitespace (org substring search)."""
    return re.sub(r"\s+", " ", str(name or "").strip().upper())


def normalize_search_tokens(name: str) -> list[str]:
    """Lowercase tokens with punctuation removed and whitespace collapsed."""
    s = re.sub(r"[^\w\s]", " ", str(name or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return []
    return [t for t in s.split() if t]


_ORG_MARKERS = frozenset(
    {
        "llc",
        "inc",
        "corp",
        "ltd",
        "lp",
        "llp",
        "co",
        "company",
        "holdings",
        "group",
        "trust",
        "estate",
        "partners",
        "partnership",
        "foundation",
        "associates",
        "management",
        "services",
        "opco",
        "propco",
        "snf",
        "nursing",
        "health",
        "healthcare",
        "care",
        "center",
        "centre",
        "facility",
        "facilities",
        "homes",
        "home",
        "rehab",
        "rehabilitation",
        "hospital",
        "medical",
        "properties",
        "investments",
        "capital",
        "fund",
        "funds",
        "realty",
    }
)


def looks_like_person_name(name: str) -> bool:
    """Heuristic: multi-token name without common org tokens → person for surname rank."""
    raw = str(name or "").strip()
    tokens = normalize_search_tokens(raw)
    if len(tokens) < 2:
        return False
    # ALL-CAPS multi-token CMS org strings are not people.
    letters = [c for c in raw if c.isalpha()]
    if len(tokens) >= 3 and letters and all(c.isupper() for c in letters):
        return False
    if any(t in _ORG_MARKERS for t in tokens):
        return False
    if tokens[0] in {"estate", "trust"}:
        return False
    return True


def tokens_match_in_order(query_tokens: list[str], record_tokens: list[str]) -> bool:
    """
    True when every query token appears in record_tokens in order.
    Extra middle tokens in the record are allowed (e.g. J between Brian and Foley).
    """
    if not query_tokens or not record_tokens:
        return False
    if len(query_tokens) == 1:
        qt = query_tokens[0]
        if len(qt) < 2:
            return False
        return qt in record_tokens

    ri = 0
    for qt in query_tokens:
        if not qt:
            continue
        matched = False
        while ri < len(record_tokens):
            if record_tokens[ri] == qt:
                matched = True
                ri += 1
                break
            ri += 1
        if not matched:
            return False
    return True


def name_search_matches(query: str, record_name: str) -> bool:
    """
    Match owner/org display names: legacy uppercase substring plus ordered token match.
    """
    q = (query or "").strip()
    r = (record_name or "").strip()
    if not q or not r:
        return False

    qnorm = _norm_search_key(q)
    rnorm = _norm_search_key(r)
    if len(qnorm) >= 2 and qnorm in rnorm:
        return True

    q_tokens = normalize_search_tokens(q)
    r_tokens = normalize_search_tokens(r)
    if len(q_tokens) < 1:
        return False
    if len(q_tokens) == 1 and len(q_tokens[0]) < 2:
        return False
    return tokens_match_in_order(q_tokens, r_tokens)


def name_search_rank(query: str, record_name: str) -> int | None:
    """
    Lower rank is better. None if no match.

    Lexical ranks (exact 10-digit PAC is handled separately by the search engine):
    0 = exact normalized full-name match
    1 = exact surname match for a person (single-token query == last token)
    2 = full-name prefix (record starts with query)
    3 = exact organization / leading-token match
    4 = ordered token / prefix-token match
    5 = broader contains (substring inside a longer token/name)
    """
    if not name_search_matches(query, record_name):
        return None
    qnorm = _norm_search_key(query)
    rnorm = _norm_search_key(record_name)
    q_tokens = normalize_search_tokens(query)
    r_tokens = normalize_search_tokens(record_name)

    if qnorm == rnorm or (q_tokens and r_tokens and q_tokens == r_tokens):
        return 0

    # Exact surname for a person — not orgs; last token must equal query.
    if (
        len(q_tokens) == 1
        and len(r_tokens) >= 2
        and q_tokens[0] == r_tokens[-1]
        and looks_like_person_name(record_name)
    ):
        return 1

    if rnorm.startswith(qnorm):
        return 2

    # Multi-token query matches person with extras (Brian Foley → Brian J. Foley)
    if (
        len(q_tokens) >= 2
        and looks_like_person_name(record_name)
        and tokens_match_in_order(q_tokens, r_tokens)
    ):
        return 2 if r_tokens[0] == q_tokens[0] else 4

    # Org / leading token
    if q_tokens and r_tokens and q_tokens[0] == r_tokens[0]:
        if tokens_match_in_order(q_tokens, r_tokens):
            return 3
        return 3

    if tokens_match_in_order(q_tokens, r_tokens):
        # Single token equals an interior token (org or weak person)
        if len(q_tokens) == 1 and q_tokens[0] in r_tokens and q_tokens[0] != r_tokens[-1]:
            return 5  # e.g. LANDA inside ARLANDA tokens? actually arlanda is one token
        return 4

    # Substring contains only (LANDA ⊂ ARLANDA)
    return 5
