"""Canonical URL helpers for PBJ320 owner, provider, and entity pages.

Verified from: ownership/owner_profile.py associate_profile_url / owner_display_slug;
app.py normalize_ccn; generate_search_index.json facility/entity shape.
"""

from __future__ import annotations

import re
from typing import Any

PUBLIC_CANONICAL_ORIGIN = "https://www.pbj320.com"


def slugify_name(name: str | None, *, fallback: str = "page") -> str:
    """Deterministic URL-safe slug from a display name (identity-neutral)."""
    raw = str(name or "").strip().lower()
    if not raw:
        return fallback
    slug = re.sub(r"[^a-z0-9]+", "-", raw)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or fallback


def absolute_canonical_url(path: str, origin: str = PUBLIC_CANONICAL_ORIGIN) -> str:
    """Absolute https://www.pbj320.com URL for a site path (no query string)."""
    p = (path or "").strip()
    if not p.startswith("/"):
        p = "/" + p
    return f"{origin.rstrip('/')}{p}"


def owner_url(associate_id: str, org_name: str = "") -> str:
    """Canonical CMS owner profile path (/owners/{pac}/{slug})."""
    from ownership.owner_profile import associate_profile_url

    return associate_profile_url(associate_id, org_name)


def owner_canonical_path(profile: dict[str, Any] | None) -> str:
    """Canonical /owners/{pac}/{slug} path from a loaded profile dict."""
    from ownership.owner_profile import owner_profile_canonical_path

    return owner_profile_canonical_path(profile)


def provider_url(ccn: str, name: str = "") -> str:
    """Canonical provider path: /provider/{ccn}/{slug}."""
    ccn_n = _normalize_ccn(ccn)
    if not ccn_n:
        return ""
    slug = slugify_name(name, fallback="facility")
    return f"/provider/{ccn_n}/{slug}"


def _normalize_ccn(ccn: object) -> str:
    """Local CCN normalizer (6-digit zero-padded). Avoids importing app at module load."""
    raw = str(ccn or "").strip().upper()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if len(digits) > 6:
        digits = digits[-6:]
    return digits.zfill(6)


def entity_url(entity_id: object, name: str = "") -> str:
    """Canonical entity path: /entity/{id}/{slug}."""
    try:
        eid = int(entity_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    slug = slugify_name(name, fallback="entity")
    return f"/entity/{eid}/{slug}"


def normalize_canonical_path(path: str) -> str:
    """Normalize a path for equality checks (no trailing slash, no query)."""
    p = (path or "").split("?")[0].split("#")[0].strip() or "/"
    return p.rstrip("/") or "/"


def canonical_paths_match(a: str, b: str) -> bool:
    return normalize_canonical_path(a) == normalize_canonical_path(b)


def get_facility_name_from_search_index(ccn: str, *, search_data: dict | None = None) -> str:
    """Return facility display name for a CCN from search_index.json."""
    ccn_n = _normalize_ccn(ccn)
    if not ccn_n:
        return ""
    data = search_data
    if data is None:
        try:
            from app import _get_search_index_data

            data = _get_search_index_data()
        except Exception:
            return ""
    if not data:
        return ""
    try:
        for row in data.get("f") or []:
            if str(row.get("c") or "").zfill(6)[-6:] == ccn_n:
                nm = str(row.get("n") or "").strip()
                if nm:
                    return nm
    except Exception:
        return ""
    return ""


def get_entity_name_from_search_index(entity_id: object, *, search_data: dict | None = None) -> str:
    """Return canonical entity display name from search_index.json."""
    try:
        target = int(entity_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    data = search_data
    if data is None:
        try:
            from app import _get_search_index_data

            data = _get_search_index_data()
        except Exception:
            return ""
    if not data:
        return ""
    try:
        from app import capitalize_entity_name
    except Exception:
        capitalize_entity_name = lambda s: s  # noqa: E731
    try:
        for row in data.get("e") or []:
            rid = row.get("id")
            rlink = row.get("linkId")
            if (rid is not None and int(rid) == target) or (
                rlink is not None and int(rlink) == target
            ):
                nm = str(row.get("n") or "").strip()
                if nm:
                    return capitalize_entity_name(nm)
    except Exception:
        return ""
    return ""
