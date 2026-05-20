"""Display formatting for CMS org names and role text."""
from __future__ import annotations

import re

_ORG_UPPER = frozenset({"llc", "llp", "lp", "inc", "corp", "ltd", "pllc", "dba", "snf", "adp"})
_SMALL_WORDS = frozenset({"at", "of", "in", "on", "to", "by", "for", "the", "and", "or", "a", "an"})
_ROLE_ACRONYMS = frozenset({"adp", "snf", "rn", "lpn", "cna", "ceo", "cfo", "coo", "pac", "llc", "llp"})
_ROMAN_NUMERALS = frozenset({
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv",
    "xvi", "xvii", "xviii", "xix", "xx",
})


def _is_roman_numeral_token(core: str) -> bool:
    low = core.lower()
    if low in _ROMAN_NUMERALS:
        return True
    return bool(re.fullmatch(r"[ivxlcdm]+", low)) and len(low) <= 6


def _format_word_token(w: str, *, is_first: bool) -> str:
    if not w or not w.strip():
        return w
    lead = ""
    trail = ""
    core = w
    while core and not core[0].isalnum():
        lead += core[0]
        core = core[1:]
    while core and not core[-1].isalnum():
        trail = core[-1] + trail
        core = core[:-1]
    if not core:
        return w
    low = core.lower()
    if low in _ORG_UPPER:
        if low in ("llc", "llp", "lp", "dba", "snf", "adp"):
            out = low.upper()
        else:
            out = low.title()
    elif not is_first and low in _SMALL_WORDS:
        out = low
    elif _is_roman_numeral_token(core):
        out = core.upper()
    elif core.isalpha():
        out = core.capitalize()
    else:
        out = core
    return lead + out + trail


def _apply_roman_numeral_tokens(s: str) -> str:
    """Uppercase Roman numeral tokens (e.g. Xii → XII) without changing other words."""
    parts = re.split(r"(\s+)", s)
    out: list[str] = []
    for part in parts:
        if not part.strip():
            out.append(part)
            continue
        lead = ""
        trail = ""
        core = part
        while core and not core[0].isalnum():
            lead += core[0]
            core = core[1:]
        while core and not core[-1].isalnum():
            trail = core[-1] + trail
            core = core[:-1]
        if core and _is_roman_numeral_token(core):
            out.append(lead + core.upper() + trail)
        else:
            out.append(part)
    return "".join(out)


def _org_name_needs_title_case(s: str) -> bool:
    if len(s) <= 4:
        return False
    if s == s.upper() and re.search(r"[A-Z]", s):
        return True
    words = re.findall(r"[A-Za-z]{2,}", s)
    return any(w.isupper() for w in words)


def format_org_display(name: str) -> str:
    if not name:
        return name
    s = str(name).strip()
    if not _org_name_needs_title_case(s):
        return _apply_roman_numeral_tokens(s)
    parts = re.split(r"(\s+|,|\.|;)", s)
    out: list[str] = []
    word_idx = 0
    for part in parts:
        if not part or re.fullmatch(r"[\s,\.;]+", part):
            out.append(part)
            continue
        out.append(_format_word_token(part, is_first=word_idx == 0))
        word_idx += 1
    formatted = re.sub(r",(?!\s)", ", ", "".join(out))
    return _apply_roman_numeral_tokens(formatted)


def _format_role_segment(seg: str) -> str:
    seg = seg.strip()
    if not seg:
        return seg
    if seg != seg.upper() or len(seg) <= 4:
        return seg
    parts = re.split(r"(\s+|/)", seg)
    out: list[str] = []
    word_idx = 0
    for part in parts:
        if not part.strip() or part == "/":
            out.append(part)
            continue
        low = part.lower().strip(".,;:")
        punct = part[len(part.rstrip(".,;:")) :] if part.rstrip(".,;:") != part else ""
        core = part.strip(".,;:")
        if low in _ROLE_ACRONYMS:
            out.append(core.upper() + punct)
        elif word_idx > 0 and low in _SMALL_WORDS:
            out.append(low + punct)
        else:
            out.append(core.capitalize() + punct)
        word_idx += 1
    return "".join(out)


def format_role_text(role: str) -> str:
    if not role:
        return role
    s = str(role).strip()
    if ";" in s:
        return "; ".join(_format_role_segment(p.strip()) for p in s.split(";") if p.strip())
    return _format_role_segment(s)


def format_role_short(role: str) -> str:
    """Compact table label for CMS ownership roles (desktop and mobile)."""
    if not role:
        return "—"
    raw = str(role).strip()
    low = raw.lower()
    if "indirect ownership" in low and "5%" in low:
        return "≥5% indirect"
    if "direct ownership" in low and "5%" in low:
        return "≥5% direct"
    if "ownership interest" in low and "5%" in low:
        return "≥5% owner"
    if "operational" in low and "managerial" in low:
        return "Op/mgr control"
    if "managing employee" in low:
        return "Managing emp."
    if "corporate officer" in low or "corp officer" in low:
        return "Corp officer"
    if "general partner" in low:
        return "Gen. partner"
    if "limited partner" in low:
        return "LP"
    if "real property" in low:
        return "Real property"
    if "mortgage" in low and "interest" in low:
        return "Mortgage int."
    if low.startswith("officer"):
        return "Officer"
    if low.startswith("adp"):
        return "ADP"
    if "board member" in low or "board of directors" in low:
        return "Board"
    if "member" in low and len(low) < 24:
        return "Member"
    s = format_role_text(role)
    if len(s) <= 24:
        return s
    return s[:22].rstrip() + "…"


def format_cms_star_rating(val: object) -> str:
    """CMS star ratings as whole numbers 1–5, or em dash if missing."""
    if val is None:
        return "—"
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "—", "-"):
        return "—"
    try:
        f = float(s.replace(",", ""))
    except ValueError:
        return "—"
    if f != f:
        return "—"
    return str(int(round(f)))


def cms_ratings_stack_html(
    overall: object,
    staffing: object,
    qm: object = None,
    *,
    include_qm: bool = True,
) -> str:
    """Three-row Ovr / Stf / QM star display (owner profile style)."""
    ovr = format_cms_star_rating(overall)
    staff = format_cms_star_rating(staffing)
    qm_val = format_cms_star_rating(qm) if include_qm else "—"
    if ovr == "—" and staff == "—" and (qm_val == "—" or not include_qm):
        return '<span class="owner-rating-none">—</span>'
    rows: list[str] = []
    for abbrev, val in (("Ovr", ovr), ("Stf", staff)):
        rows.append(
            f'<span class="owner-rating-row">'
            f'<span class="owner-rating-k">{abbrev}</span>'
            f"{cms_rating_stars_html(val)}</span>"
        )
    if include_qm:
        rows.append(
            f'<span class="owner-rating-row">'
            f'<span class="owner-rating-k">QM</span>'
            f"{cms_rating_stars_html(qm_val)}</span>"
        )
    return f'<span class="owner-ratings-stack">{"".join(rows)}</span>'


def cms_rating_stars_html(val: object) -> str:
    """Five filled/empty star characters; 1-star uses warning color."""
    rating = format_cms_star_rating(val)
    if rating == "—":
        return '<span class="owner-rating-none">—</span>'
    n = max(0, min(5, int(rating)))
    filled = "★" * n
    empty = "☆" * (5 - n)
    on_cls = "owner-rating-stars-on"
    if n == 1:
        on_cls += " owner-rating-stars-on--low"
    return (
        f'<span class="owner-rating-stars" aria-label="{n} of 5 stars" title="{n}/5">'
        f'<span class="{on_cls}">{filled}</span>'
        f'<span class="owner-rating-stars-off">{empty}</span></span>'
    )
