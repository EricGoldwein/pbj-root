"""
Role-aware public taxonomy for /owners/{pac} presentation (not route rename).

Mutually exclusive publication segments from CMS SNF All Owners role categories
(+ CHOW / enrollment profile_kind). Presentation and SEO only — durable routes
remain /owners/{pac}/{slug}.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

PublicationSegment = Literal[
    "ownership_interest_only",
    "mixed_ownership_plus_other",
    "control_managerial_no_ownership",
    "governance_only",
    "administrative_enrollment_style",
    "financial_only",
    "other_or_unclassified",
    "chow_enrollment_party",
    "unknown_placeholder",
]

_CATEGORY_OWNERSHIP = "ownership_interest"
_CATEGORY_CONTROL = "operational_control"
_CATEGORY_GOVERNANCE = "corporate_governance"
_CATEGORY_ADMIN = "administrative_disclosure"
_CATEGORY_FINANCIAL = "financial_interest"
_CATEGORY_OTHER = "other"

# Title suffix after em dash (before | PBJ320)
_TITLE_SUFFIX: dict[str, str] = {
    "ownership_interest_only": "Nursing Home Ownership Interest",
    "mixed_ownership_plus_other": "Nursing Home Ownership Interest",
    "control_managerial_no_ownership": "Nursing Home Managing & Control Role",
    "governance_only": "Nursing Home Officer/Director",
    "administrative_enrollment_style": "CMS Nursing Home Enrollment Associate",
    "financial_only": "Nursing Home Financial Interest",
    "other_or_unclassified": "CMS Nursing Home Associate",
    "chow_enrollment_party": "CMS CHOW Enrollment Party",
    "unknown_placeholder": "CMS Nursing Home Associate",
}

_DESCRIPTOR: dict[str, str] = {
    "ownership_interest_only": "Ownership interest",
    "mixed_ownership_plus_other": "Mixed CMS roles",
    "control_managerial_no_ownership": "Managing / control",
    "governance_only": "Officer / director",
    "administrative_enrollment_style": "Enrollment entity",
    "financial_only": "Financial interest",
    "other_or_unclassified": "CMS associate",
    "chow_enrollment_party": "CHOW party",
    "unknown_placeholder": "CMS associate",
}

_FACILITY_SECTION: dict[str, str] = {
    "ownership_interest_only": "Ownership-interest facilities",
    # Mixed/control/enrollment: do not imply every row is ownership-interest-only.
    "mixed_ownership_plus_other": "Linked facilities",
    "control_managerial_no_ownership": "Linked facilities",
    "governance_only": "Linked facilities",
    "administrative_enrollment_style": "Linked facilities",
    "financial_only": "Linked facilities",
    "other_or_unclassified": "Linked facilities",
    "chow_enrollment_party": "Linked facilities",
    "unknown_placeholder": "Linked facilities",
}

_KNOWN_SEGMENTS: frozenset[str] = frozenset(_TITLE_SUFFIX.keys())


def collect_role_categories(profile: dict[str, Any] | None) -> set[str]:
    """Role categories present on this profile's facility / party rows."""
    if not profile:
        return set()
    cats: set[str] = set()
    for fac in profile.get("facilities") or []:
        c = str(fac.get("role_category") or "").strip()
        if c:
            cats.add(c)
    ow = profile.get("owner_control_section")
    if isinstance(ow, dict):
        for fac in ow.get("facilities") or []:
            c = str(fac.get("role_category") or "").strip()
            if c:
                cats.add(c)
    for party in profile.get("control_parties") or []:
        c = str(party.get("role_category") or "").strip()
        if c:
            cats.add(c)
    return cats


def classify_publication_segment(profile: dict[str, Any] | None) -> PublicationSegment:
    """Mutually exclusive public segment for SEO / UI framing."""
    from ownership.owner_indexability import is_suppress_owner_name

    if not profile:
        return "other_or_unclassified"
    name = str(profile.get("display_name") or "").strip()
    if is_suppress_owner_name(name):
        return "unknown_placeholder"

    kind = str(profile.get("profile_kind") or "").strip()
    if kind == "chow_only" or profile.get("is_chow_only"):
        return "chow_enrollment_party"
    if kind == "enrollment" and not (profile.get("owner_control_section") or {}).get("facilities"):
        # Pure enrollment PAC profile with no owner/control rows
        cats = collect_role_categories(profile)
        if not cats or cats <= {_CATEGORY_ADMIN, _CATEGORY_OTHER}:
            return "administrative_enrollment_style"

    roles = collect_role_categories(profile)
    has_o = _CATEGORY_OWNERSHIP in roles
    has_c = _CATEGORY_CONTROL in roles
    has_g = _CATEGORY_GOVERNANCE in roles
    has_a = _CATEGORY_ADMIN in roles
    has_f = _CATEGORY_FINANCIAL in roles

    if has_o and (has_c or has_g or has_a or has_f or (_CATEGORY_OTHER in roles)):
        return "mixed_ownership_plus_other"
    if has_o:
        return "ownership_interest_only"
    if has_c:
        return "control_managerial_no_ownership"
    if has_g:
        return "governance_only"
    if has_f and not has_a:
        return "financial_only"
    if has_a:
        return "administrative_enrollment_style"
    if kind in ("enrollment",):
        return "administrative_enrollment_style"
    return "other_or_unclassified"


def get_stored_publication_segment(
    pac: str, *, db_path: Path | None = None
) -> PublicationSegment | None:
    """Read canonical segment from pac_publication_taxonomy when present."""
    digits = "".join(ch for ch in str(pac or "") if ch.isdigit())
    if len(digits) == 9:
        digits = digits.zfill(10)
    pac_n = digits if len(digits) == 10 else ""
    if len(pac_n) != 10:
        return None
    try:
        from ownership.canonical_store import DB_PATH, PAC_TAX_TABLE, connect

        path = db_path or DB_PATH
        if not path.is_file():
            return None
        conn = connect(path)
        try:
            row = conn.execute(
                f'SELECT segment FROM "{PAC_TAX_TABLE}" WHERE pac=?',
                (pac_n,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        seg = str(row["segment"] or "").strip()
        if seg in _KNOWN_SEGMENTS:
            return seg  # type: ignore[return-value]
    except Exception:
        return None
    return None


def segment_for_profile(profile: dict[str, Any] | None) -> PublicationSegment:
    """Prefer already-attached publication_segment; else classify from live profile."""
    if profile:
        attached = str(profile.get("publication_segment") or "").strip()
        if attached in _KNOWN_SEGMENTS:
            return attached  # type: ignore[return-value]
    return classify_publication_segment(profile)


def has_ownership_interest(profile: dict[str, Any] | None) -> bool:
    seg = segment_for_profile(profile)
    return seg in ("ownership_interest_only", "mixed_ownership_plus_other")


def _normalize_pct_token(raw: str) -> str:
    s = str(raw or "").strip()
    if not s or s in ("—", "-", "n/a", "N/A", "nan"):
        return ""
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        val = float(s.replace(",", ""))
    except ValueError:
        return str(raw).strip()
    if abs(val - round(val)) < 1e-9:
        return f"{int(round(val))}%"
    text = f"{val:.4f}".rstrip("0").rstrip(".")
    return f"{text}%"


def ownership_pct_headline(profile: dict[str, Any] | None) -> tuple[str, str]:
    """Compact OI % chip: ('48.5%', help) uniform, ('up to 48.5%', help) vary, or ('', '')."""
    if not profile or not has_ownership_interest(profile):
        return "", ""
    values: list[float] = []
    display_tokens: list[str] = []
    for fac in list(profile.get("facilities") or []):
        if str(fac.get("role_category") or "") != _CATEGORY_OWNERSHIP:
            continue
        token = _normalize_pct_token(str(fac.get("pct") or ""))
        if not token:
            continue
        display_tokens.append(token)
        try:
            values.append(float(token.rstrip("%").replace(",", "")))
        except ValueError:
            continue
    ow = profile.get("owner_control_section")
    if not values and isinstance(ow, dict):
        return ownership_pct_headline(ow)
    if not values:
        return "", ""
    unique = {round(v, 4) for v in values}
    max_tok = _normalize_pct_token(str(max(values)))
    help_body = (
        "CMS-reported ownership-interest percentages on individual facility rows. "
        "Values can differ by facility; this line summarizes those row-level figures only."
    )
    if len(unique) == 1:
        return display_tokens[0], help_body
    return f"up to {max_tok}", help_body + " When percentages vary, the headline shows the maximum."


def publication_descriptor(profile: dict[str, Any] | None) -> str:
    seg = segment_for_profile(profile)
    base = _DESCRIPTOR.get(seg, _DESCRIPTOR["other_or_unclassified"])
    if seg in ("ownership_interest_only", "mixed_ownership_plus_other") and profile:
        pct_chip, _help = ownership_pct_headline(profile)
        if pct_chip:
            return f"{base} · {pct_chip}"
    # CHOW: short buyer/seller chip when unambiguous
    if seg == "chow_enrollment_party" and profile:
        roles = {
            str(r.get("chow_role") or r.get("role") or "").strip().lower()
            for r in (profile.get("chow_transactions") or [])
        }
        if "buyer" in roles and "seller" not in roles:
            return "CHOW buyer"
        if "seller" in roles and "buyer" not in roles:
            return "CHOW seller"
    return base


def publication_title_suffix(profile: dict[str, Any] | None) -> str:
    seg = segment_for_profile(profile)
    return _TITLE_SUFFIX.get(seg, _TITLE_SUFFIX["other_or_unclassified"])


def facility_section_label(profile: dict[str, Any] | None) -> str:
    seg = segment_for_profile(profile)
    return _FACILITY_SECTION.get(seg, _FACILITY_SECTION["other_or_unclassified"])


def uses_ownership_portfolio_language(profile: dict[str, Any] | None) -> bool:
    return segment_for_profile(profile) in (
        "ownership_interest_only",
        "mixed_ownership_plus_other",
    )


def schema_org_type(profile: dict[str, Any] | None) -> str:
    """Person vs Organization for JSON-LD."""
    ot = str((profile or {}).get("owner_type") or "").strip().lower()
    if "individual" in ot or ot in ("person", "i"):
        return "Person"
    # Heuristic: no org tokens and short multi-word name
    name = str((profile or {}).get("display_name") or "").strip()
    if ot.startswith("ind"):
        return "Person"
    # Explicit party type fields used elsewhere
    for fac in (profile or {}).get("facilities") or []:
        break
    if "organization" in ot or "org" in ot or "provider" in ot or "llc" in name.lower():
        return "Organization"
    if "individual" in ot:
        return "Person"
    # Default: Organization for PAC pages unless Individual
    if ot == "individual":
        return "Person"
    return "Organization"


def meta_relationship_phrase(profile: dict[str, Any] | None) -> str:
    seg = segment_for_profile(profile)
    return {
        "ownership_interest_only": "CMS-disclosed ownership interest",
        "mixed_ownership_plus_other": "CMS-disclosed ownership interest and other roles",
        "control_managerial_no_ownership": "CMS-disclosed managing/control role",
        "governance_only": "CMS-disclosed officer/director role",
        "administrative_enrollment_style": "CMS enrollment association",
        "financial_only": "CMS-disclosed financial interest",
        "other_or_unclassified": "CMS-disclosed associate relationship",
        "chow_enrollment_party": "CMS CHOW enrollment transaction party",
        "unknown_placeholder": "CMS-disclosed associate relationship",
    }.get(seg, "CMS-disclosed associate relationship")


def _primary_ownership_pct(profile: dict[str, Any]) -> str:
    """Uniform OI % or empty when percentages vary / missing (legacy helper)."""
    chip, _help = ownership_pct_headline(profile)
    if chip.startswith("up to "):
        return ""
    return chip


def attach_publication_taxonomy(profile: dict[str, Any]) -> dict[str, Any]:
    """Annotate profile with publication segment + labels (mutates and returns).

    Prefer pac_publication_taxonomy.segment from snf_owners_lookup.sqlite when
    present for this PAC so title/meta/descriptor stay aligned with the store.
    Fall back to classify_publication_segment(profile) when no store row.
    """
    pac = str(profile.get("associate_id") or "").strip()
    stored = get_stored_publication_segment(pac) if pac else None
    if stored:
        seg: PublicationSegment = stored
        profile["publication_segment_source"] = "store"
    else:
        seg = classify_publication_segment(profile)
        profile["publication_segment_source"] = "live"
    profile["publication_segment"] = seg
    # Helpers read profile["publication_segment"] via segment_for_profile.
    profile["publication_descriptor"] = publication_descriptor(profile)
    profile["publication_title_suffix"] = publication_title_suffix(profile)
    profile["facility_section_label"] = facility_section_label(profile)
    profile["uses_ownership_portfolio_language"] = uses_ownership_portfolio_language(profile)
    profile["schema_org_type"] = schema_org_type(profile)
    profile["meta_relationship_phrase"] = meta_relationship_phrase(profile)
    return profile
