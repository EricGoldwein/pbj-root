"""JSON-LD and SEO helpers for /owners/<state> index pages."""
from __future__ import annotations

import json
from typing import Any

from ownership.state_owner_index import (
    STATE_INDEX_META,
    state_index_lastmod_iso,
    state_index_layout_meta,
)


def build_state_owner_index_json_ld(
    state_code: str,
    *,
    site_origin: str,
    page_title: str | None = None,
    meta_description: str | None = None,
    canonical_url: str | None = None,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """
    Return (CollectionPage doc, breadcrumb items as (name, url) tuples).
    URLs in breadcrumbs should be absolute when emitted.
    """
    layout = state_index_layout_meta(state_code)
    st = layout["state_code"]
    meta = STATE_INDEX_META.get(st) or {}
    state_name = layout["state_name"]
    origin = (site_origin or "").rstrip("/")
    page_url = (canonical_url or "").strip()
    if page_url.startswith("/"):
        page_url = f"{origin}{page_url}"
    if not page_url:
        page_url = f"{origin}{layout['canonical_path']}"

    title = (page_title or layout["page_title"])[:240]
    description = (meta_description or layout["meta_description"])[:500]

    web_page: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": page_url,
        "name": title,
        "url": page_url,
        "description": description,
        "isPartOf": {"@type": "WebSite", "name": "PBJ320", "url": f"{origin}/"},
        "publisher": {
            "@type": "Organization",
            "name": "320 Consulting",
            "url": "https://www.320insight.com/",
        },
        "about": [
            {"@type": "Thing", "name": "Nursing home ownership"},
            {"@type": "Thing", "name": "CMS SNF ownership data"},
            {"@type": "Thing", "name": "Payroll-Based Journal staffing data"},
            {"@type": "AdministrativeArea", "name": state_name},
        ],
    }
    lastmod = state_index_lastmod_iso(st)
    if lastmod:
        web_page["dateModified"] = lastmod

    crumbs = [
        ("Home", f"{origin}/"),
        ("Ownership", f"{origin}/owners"),
        (layout.get("breadcrumb_name") or state_name, page_url),
    ]
    return web_page, crumbs


def render_state_owner_index_json_ld_scripts(
    state_code: str,
    *,
    site_origin: str,
    page_title: str,
    meta_description: str,
    canonical_url: str,
) -> str:
    """HTML script tags for CollectionPage + BreadcrumbList."""
    web_page, crumbs = build_state_owner_index_json_ld(
        state_code,
        site_origin=site_origin,
        page_title=page_title,
        meta_description=meta_description,
        canonical_url=canonical_url,
    )
    breadcrumb_doc = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": name[:240],
                "item": url,
            }
            for idx, (name, url) in enumerate(crumbs)
            if name and url
        ],
    }
    return (
        f'<script type="application/ld+json">{json.dumps(web_page, ensure_ascii=True)}</script>\n'
        f'<script type="application/ld+json">{json.dumps(breadcrumb_doc, ensure_ascii=True)}</script>'
    )
