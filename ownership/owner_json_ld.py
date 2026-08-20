"""JSON-LD helpers for /owners/{pac} profiles (Person vs Organization, role-aware)."""
from __future__ import annotations

import json
from typing import Any


def owner_profile_json_ld_docs(
    *,
    profile: dict[str, Any],
    page_url: str,
    meta_description: str,
    site_origin: str,
) -> list[dict[str, Any]]:
    display_name = str(profile.get("display_name") or "Organization").strip()
    schema_type = str(profile.get("schema_org_type") or "").strip()
    if schema_type not in ("Person", "Organization"):
        from ownership.publication_taxonomy import schema_org_type as _schema

        schema_type = _schema(profile)
    desc = (meta_description or str(profile.get("publication_descriptor") or ""))[:500]
    entity: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": display_name,
        "url": page_url,
        "description": desc,
    }
    # Do not encode ownership/control edges without direct support.
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": f"{site_origin.rstrip('/')}/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": display_name,
                "item": page_url,
            },
        ],
    }
    return [entity, crumbs]


def render_owner_profile_json_ld_scripts(
    *,
    profile: dict[str, Any],
    page_url: str,
    meta_description: str,
    site_origin: str,
) -> str:
    docs = owner_profile_json_ld_docs(
        profile=profile,
        page_url=page_url,
        meta_description=meta_description,
        site_origin=site_origin,
    )
    return "\n".join(
        f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=True)}</script>'
        for d in docs
    )
