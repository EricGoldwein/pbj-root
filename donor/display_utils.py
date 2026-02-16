"""
Shared display formatting for donor/ownership UI.
Title-case for committee names, recipient names, etc.
"""


def title_case_committee(name: str) -> str:
    """
    First letter cap; WinRed/ActBlue as-is; the/and/at/of lowercase when not first word.
    Used for FEC committee names, recipient names, etc. across top page and ownership search.
    """
    if not name or not isinstance(name, str):
        return name or ""
    s = name.strip()
    lower = s.lower()
    if lower == "winred":
        return "WinRed"
    if lower == "actblue":
        return "ActBlue"
    # Acronyms that stay all caps
    if lower in ("nrsc", "dscc", "pac", "maga", "dnc", "rnc", "hmp"):
        return s.upper()
    small = {"the", "and", "at", "of", "a", "an", "in", "on", "for", "to", "with"}
    acronym_words = {"usa"}  # words that stay all caps (e.g. "usa" or "u.s.a." -> USA)
    state_abbrevs = frozenset(
        "al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy dc".split()
    )
    words = s.split()
    out = []
    for i, w in enumerate(words):
        w = w.strip()
        if not w:
            continue
        w_lower = w.lower().replace(".", "")
        if w_lower in acronym_words:
            out.append("USA")
        elif len(w_lower) == 2 and w_lower in state_abbrevs:
            out.append(w_lower.upper())
        elif "-" in w:
            out.append("-".join(p.capitalize() for p in w.split("-")))
        elif i == 0 or w.lower() not in small:
            out.append(w.capitalize())
        else:
            out.append(w.lower())
    return " ".join(out)


def format_top_recipients(raw: str) -> str:
    """Format 'NAME $X; NAME $Y' with title-case on committee names."""
    if not raw or not isinstance(raw, str):
        return raw or ""
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    out = []
    for p in parts:
        if " $" in p:
            name, _, amount = p.rpartition(" $")
            out.append(f"{title_case_committee(name.strip())} ${amount.strip()}")
        else:
            out.append(title_case_committee(p))
    return "; ".join(out)
