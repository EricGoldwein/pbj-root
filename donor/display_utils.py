"""
Shared display formatting for donor/ownership UI.
Title-case for committee names, recipient names, etc.
"""


# Acronyms that display all caps when they appear as words (e.g. MAGA Inc. not Maga Inc.; RNC, DNC, DSCC)
ACRONYM_WORDS = frozenset(
    "maga rnc dnc dscc nrcc dccc nrsc hmp pac".split()
)
# 2–3 letter nonwords that display all caps: USA, US, state codes (handled below), FEC, CMS, etc.
CAPS_2_3_LETTER = frozenset(
    "usa us fec cms irs fda cdc gop dhs doj hhs osha".split()
)


def title_case_committee(name: str) -> str:
    """
    First letter cap; WinRed/ActBlue as-is; MAGA/RNC/DNC/DSCC etc. as all caps; the/and/at/of lowercase when not first word.
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
    # Whole string is a single acronym or 2–3 letter abbrev -> all caps
    if lower in ACRONYM_WORDS or lower in CAPS_2_3_LETTER:
        return s.upper()
    small = {"the", "and", "at", "of", "a", "an", "in", "on", "for", "to", "with"}
    state_abbrevs = frozenset(
        "al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy dc".split()
    )
    words = s.split()
    out = []
    for i, w in enumerate(words):
        w = w.strip()
        if not w:
            continue
        w_clean = w.lower().replace(".", "")
        if w_clean in ACRONYM_WORDS:
            out.append(w_clean.upper())
        elif w_clean in CAPS_2_3_LETTER:
            out.append(w_clean.upper())
        elif len(w_clean) == 2 and w_clean in state_abbrevs:
            out.append(w_clean.upper())
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
