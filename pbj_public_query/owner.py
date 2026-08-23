"""Public owner query helpers for MCP / JSON."""

from __future__ import annotations

from typing import Any

from ownership.owner_profile import (
    associate_profile_url,
    load_owner_profile_resolved,
    normalize_associate_id,
    owner_profile_canonical_path,
    search_public_owner_profiles,
)
from ownership.ownership_release_policy import active_release_date, load_policy
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def search_owners(
    *,
    query: str,
    state: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    from pbj_public_query.facility import RESULT_DEFAULT, RESULT_HARD_MAX

    try:
        lim = int(limit if limit is not None else RESULT_DEFAULT)
    except (TypeError, ValueError):
        lim = RESULT_DEFAULT
    lim = max(1, min(lim, RESULT_HARD_MAX))

    st = (state or "").strip().upper()[:2] or None
    q = (query or "").strip()
    if len(q) < 2 and len(normalize_associate_id(q)) != 10:
        return {"query": q, "count": 0, "owners": []}

    hits = search_public_owner_profiles(q, limit=lim, state_code=st)
    owners: list[dict[str, Any]] = []
    for hit in hits:
        pac = normalize_associate_id(hit.get("associate_id"))
        owners.append(
            {
                "associate_id": pac,
                "name": hit.get("name"),
                "canonical_url": hit.get("profile_url") or associate_profile_url(pac, hit.get("name") or ""),
            }
        )

    release = _ownership_release()
    return {
        "query": q,
        "state": st,
        "limit": lim,
        "count": len(owners),
        "owners": owners,
        "ownership_release": release,
    }


def get_owner_portfolio(pac: str) -> dict[str, Any] | None:
    associate = normalize_associate_id(pac)
    if len(associate) != 10:
        return None

    profile = load_owner_profile_resolved(associate)
    if not profile:
        return None

    release = _ownership_release()
    facilities: list[dict[str, Any]] = []
    states: set[str] = set()

    for fac in profile.get("facilities") or []:
        ccn = str(fac.get("ccn") or "").zfill(6)
        st = str(fac.get("state") or "").upper()[:2]
        if st:
            states.add(st)
        facilities.append(
            {
                "ccn": ccn,
                "name": fac.get("name") or fac.get("facility_name"),
                "state": st,
                "roles": fac.get("roles") or fac.get("role_labels"),
                "enrollment_pac": fac.get("enrollment_pac"),
            }
        )

    ow_section = profile.get("owner_control_section") if isinstance(profile.get("owner_control_section"), dict) else {}
    for fac in ow_section.get("facilities") or []:
        ccn = str(fac.get("ccn") or "").zfill(6)
        if any(x.get("ccn") == ccn for x in facilities):
            continue
        st = str(fac.get("state") or "").upper()[:2]
        if st:
            states.add(st)
        facilities.append(
            {
                "ccn": ccn,
                "name": fac.get("name"),
                "state": st,
                "roles": fac.get("roles"),
            }
        )

    return {
        "owner": {
            "associate_id": associate,
            "name": profile.get("display_name") or profile.get("owner_name"),
            "owner_type": profile.get("owner_type") or profile.get("entity_type"),
            "individual_or_organization": profile.get("individual_or_organization"),
        },
        "portfolio": {
            "facility_count": len(facilities),
            "states": sorted(states),
            "facilities": facilities[:120],
            "truncated": len(facilities) > 120,
        },
        "ownership_release": release,
        "canonical_url": owner_profile_canonical_path(profile),
    }


def _ownership_release() -> str:
    try:
        return active_release_date(load_policy(REPO))
    except Exception:
        return ""
