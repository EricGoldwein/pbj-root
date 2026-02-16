"""
Shared common-surname logic for top contributors. Used to flag/demote likely conflation.
"""

# Common surnames — matching may conflate different people; especially when many contributions
COMMON_SURNAMES = frozenset({
    "smith", "jones", "johnson", "williams", "brown", "davis", "miller", "rogers",
    "garcia", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez", "wilson",
    "anderson", "thomas", "taylor", "moore", "jackson", "martin", "lee", "perez",
    "thompson", "white", "harris", "sanchez", "clark", "ramirez", "lewis", "robinson",
    "walker", "young", "allen", "king", "wright", "scott", "torres", "nguyen", "hill",
    "flores", "green", "adams", "nelson", "baker", "hall", "rivera", "campbell",
    "mitchell", "carter", "roberts",
})

# Common name + this many contributions = likely conflating multiple people
LIKELY_CONFLATED_THRESHOLD = 75


def is_common_name(fec_name: str, owner_type: str = "") -> bool:
    """True if FEC name has a common surname; individuals only."""
    if (owner_type or "").upper() == "ORGANIZATION":
        return False
    if not fec_name or not isinstance(fec_name, str):
        return False
    s = fec_name.strip()
    if "," in s:
        surname = s.split(",", 1)[0].strip()
    else:
        parts = s.split()
        surname = parts[-1] if parts else ""
    return surname.lower() in COMMON_SURNAMES


def is_likely_conflated(fec_name: str, owner_type: str, num_contributions: int) -> bool:
    """True if common name with many contributions — likely conflating multiple people."""
    return (
        is_common_name(fec_name, owner_type)
        and num_contributions >= LIKELY_CONFLATED_THRESHOLD
    )
