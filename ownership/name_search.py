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
    0 = normalized prefix, 1 = token-aligned prefix, 2 = other token/substring match.
    """
    if not name_search_matches(query, record_name):
        return None
    qnorm = _norm_search_key(query)
    rnorm = _norm_search_key(record_name)
    if rnorm.startswith(qnorm):
        return 0
    q_tokens = normalize_search_tokens(query)
    r_tokens = normalize_search_tokens(record_name)
    if q_tokens and r_tokens and q_tokens[0] == r_tokens[0]:
        if tokens_match_in_order(q_tokens, r_tokens):
            return 1
    if len(qnorm) >= 2 and qnorm in rnorm[: max(len(qnorm) + 4, 8)]:
        return 1
    return 2
