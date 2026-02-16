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
    words = s.split()
    out = []
    for i, w in enumerate(words):
        w = w.strip()
        if not w:
            continue
        if "-" in w:
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
