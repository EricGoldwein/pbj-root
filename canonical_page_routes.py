"""Canonical slugged URL routes for providers and entities.

Registers /provider/{ccn}/{slug} and /entity/{id}/{slug}, ID-only 301 redirects,
and monkey-patches page renderers + sitemap builder for canonical hrefs.

Hooked from premium_redirect_routes.register_premium_routes (app.py import chain).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable

from flask import abort, redirect, request

from canonical_urls import (
    absolute_canonical_url,
    canonical_paths_match,
    entity_url,
    get_entity_name_from_search_index,
    get_facility_name_from_search_index,
    provider_url,
)

if TYPE_CHECKING:
    from flask import Flask

_PATCHED = False
_ROUTES_REGISTERED = False

_TEST_PROVIDER_RE = re.compile(r"^/test/provider/(\d{6})$")
_TEST_ENTITY_RE = re.compile(r"^/test/entity/(\d+)$")


def _provider_name_fallback_under_admission(app_module, prov: str):
    """Resolve a search-index miss without escaping the shared expensive budget."""
    from pbj_provider_perf import classify_user_agent

    ua_class = classify_user_agent(request.headers.get("User-Agent", ""))
    acquired = app_module._EXPENSIVE_BUILD_GATE.acquire(blocking=False)
    if not acquired:
        return "", app_module._expensive_build_busy_response("provider", ua_class)
    try:
        if not app_module._ensure_pandas_after_expensive_admission():
            return "", ("Pandas not available. Provider pages require pandas.", 503)
        pi = app_module._provider_info_row_for_ccn(prov) or {}
        return str(pi.get("provider_name") or "").strip(), None
    finally:
        app_module._EXPENSIVE_BUILD_GATE.release()


def _provider_canonical_redirect(ccn: str):
    """301 to canonical slugged provider URL (single hop)."""
    import app as app_module

    prov = app_module.normalize_ccn(ccn) or ""
    if not prov:
        abort(404)
    name = get_facility_name_from_search_index(prov)
    if not name:
        name, busy = _provider_name_fallback_under_admission(app_module, prov)
        if busy is not None:
            return busy
    if not name:
        abort(404)
    target = provider_url(prov, name)
    req_path = (request.path or "").rstrip("/") or "/"
    if canonical_paths_match(req_path, target):
        return app_module._provider_page_impl(prov)
    return redirect(target, code=301)


def _entity_canonical_redirect(entity_id: object):
    """301 to canonical slugged entity URL (single hop)."""
    import app as app_module

    try:
        eid = int(entity_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        abort(404)
    name = get_entity_name_from_search_index(eid)
    if not name:
        abort(404)
    target = entity_url(eid, name)
    req_path = (request.path or "").rstrip("/") or "/"
    if canonical_paths_match(req_path, target):
        return app_module._entity_page_impl(eid)
    return redirect(target, code=301)


def _wrap_provider_page_impl(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(ccn, requested_slug=None, *_args, **_kwargs):
        import app as app_module

        prov = app_module.normalize_ccn(ccn) or ""
        if not prov:
            abort(404)
        req_path = (request.path or "").rstrip("/") or "/"
        qs = request.query_string.decode() if request.query_string else ""
        name = get_facility_name_from_search_index(prov)
        if not name:
            name, busy = _provider_name_fallback_under_admission(app_module, prov)
            if busy is not None:
                return busy
        if name:
            canon_path = provider_url(prov, name)
            if not canonical_paths_match(req_path, canon_path):
                target = f"{canon_path}?{qs}" if qs else canon_path
                return redirect(target, code=301)
        return original(prov)

    wrapped.__name__ = getattr(original, "__name__", "wrapped_provider_page_impl")
    return wrapped


def _wrap_entity_page_impl(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(entity_id, requested_slug=None, *_args, **_kwargs):
        import app as app_module

        try:
            eid = int(entity_id)
        except (TypeError, ValueError):
            abort(404)
        req_path = (request.path or "").rstrip("/") or "/"
        qs = request.query_string.decode() if request.query_string else ""
        name = get_entity_name_from_search_index(eid)
        if name:
            canon_path = entity_url(eid, name)
            if not canonical_paths_match(req_path, canon_path):
                target = f"{canon_path}?{qs}" if qs else canon_path
                return redirect(target, code=301)
        return original(eid)

    wrapped.__name__ = getattr(original, "__name__", "wrapped_entity_page_impl")
    return wrapped


def _patch_generate_provider_page_html(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(prov, facility_df, provider_info_row, *args, **kwargs):
        import app as app_module

        pi = provider_info_row or {}
        ccn_n = app_module.normalize_ccn(prov) or str(prov or "").strip()
        facility_name = str(pi.get("provider_name") or "").strip()
        if not facility_name:
            facility_name = get_facility_name_from_search_index(ccn_n)
        if not facility_name and facility_df is not None and not facility_df.empty:
            last = facility_df.iloc[-1]
            for col in ("PROVNAME", "provider_name", "Provider Name"):
                if col in last.index and str(last.get(col) or "").strip():
                    facility_name = str(last.get(col) or "").strip()
                    break
        html = original(prov, facility_df, provider_info_row, *args, **kwargs)
        if not isinstance(html, str):
            return html
        canon_rel = provider_url(ccn_n, facility_name)
        id_only_abs = f'{app_module._public_site_origin()}/provider/{ccn_n}'
        canon_abs = absolute_canonical_url(canon_rel)
        html = html.replace(id_only_abs, canon_abs)
        id_only_href = f'href="{id_only_abs}"'
        if id_only_href in html:
            html = html.replace(id_only_href, f'href="{canon_abs}"')
        id_only_rel = f'"/provider/{ccn_n}"'
        canon_rel_quoted = f'"{canon_rel}"'
        if id_only_rel in html:
            html = html.replace(f'href={id_only_rel}', f'href={canon_rel_quoted}')
        ent_id = pi.get("entity_id") or pi.get("chain_id")
        ent_name = str(pi.get("entity_name") or pi.get("chain_name") or "").strip()
        if ent_id and ent_name:
            try:
                eid = int(ent_id)
                old_ent_rel = f"/entity/{eid}"
                new_ent_rel = entity_url(eid, ent_name)
                old_ent_abs = f'{app_module._public_site_origin()}/entity/{eid}'
                new_ent_abs = absolute_canonical_url(entity_url(eid, ent_name))
                html = (
                    html.replace(old_ent_abs, new_ent_abs)
                    .replace(old_ent_rel, new_ent_rel)
                )
            except (TypeError, ValueError):
                pass
        return html

    wrapped.__name__ = getattr(original, "__name__", "wrapped_generate_provider_page_html")
    return wrapped


def _patch_generate_entity_page_html(original: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(entity_id, entity_name, facilities, *args, **kwargs):
        html = original(entity_id, entity_name, facilities, *args, **kwargs)
        if not isinstance(html, str):
            return html
        import app as app_module

        try:
            eid = int(entity_id)
        except (TypeError, ValueError):
            return html
        name = str(entity_name or "").strip()
        old_abs = f'{app_module._public_site_origin()}/entity/{eid}'
        canon_abs = absolute_canonical_url(entity_url(eid, name))
        html = html.replace(old_abs, canon_abs)
        id_only_href = f'href="{old_abs}"'
        if id_only_href in html:
            html = html.replace(id_only_href, f'href="{canon_abs}"')
        id_only_rel = f'"/entity/{eid}"'
        new_rel = entity_url(eid, name)
        if id_only_rel in html:
            html = html.replace(f'href={id_only_rel}', f'href="{new_rel}"')
        for fac in facilities or []:
            ccn = str(fac.get("ccn") or "").strip().zfill(6)[-6:]
            fac_name = str(fac.get("name") or fac.get("provider_name") or "").strip()
            if ccn.isdigit() and fac_name:
                fac_canon = provider_url(ccn, fac_name)
                html = html.replace(f'href="/provider/{ccn}"', f'href="{fac_canon}"')
        return html

    wrapped.__name__ = getattr(original, "__name__", "wrapped_generate_entity_page_html")
    return wrapped


def _patch_build_sitemap_xml(original: Callable[[], str]) -> Callable[[], str]:
    def wrapped() -> str:
        xml = original()
        if not isinstance(xml, str):
            return xml
        xml = re.sub(
            r"<loc>https?://[^<]+/provider/(\d{6})</loc>",
            lambda m: _sitemap_provider_loc(m.group(1)),
            xml,
        )
        xml = re.sub(
            r"<loc>https?://[^<]+/entity/(\d+)</loc>",
            lambda m: _sitemap_entity_loc(m.group(1)),
            xml,
        )
        xml = re.sub(
            r"<loc>https?://[^<]+/owners/(\d{10})</loc>",
            lambda m: _sitemap_owner_loc(m.group(1)),
            xml,
        )
        return xml

    wrapped.__name__ = getattr(original, "__name__", "wrapped_build_sitemap_xml")
    return wrapped


def _sitemap_provider_loc(ccn: str) -> str:
    from site_public_config import normalize_public_site_origin, PUBLIC_SITE_ORIGIN

    base = normalize_public_site_origin(PUBLIC_SITE_ORIGIN)
    name = get_facility_name_from_search_index(ccn)
    path = provider_url(ccn, name)
    return f"<loc>{base}{path}</loc>"


def _sitemap_entity_loc(entity_id: str) -> str:
    from site_public_config import normalize_public_site_origin, PUBLIC_SITE_ORIGIN

    base = normalize_public_site_origin(PUBLIC_SITE_ORIGIN)
    try:
        eid = int(entity_id)
    except (TypeError, ValueError):
        return f"<loc>{base}/entity/{entity_id}/entity</loc>"
    name = get_entity_name_from_search_index(eid)
    path = entity_url(eid, name)
    return f"<loc>{base}{path}</loc>"


def _sitemap_owner_loc(pac: str) -> str:
    from site_public_config import normalize_public_site_origin, PUBLIC_SITE_ORIGIN
    from ownership.owner_profile import associate_profile_url

    base = normalize_public_site_origin(PUBLIC_SITE_ORIGIN)
    try:
        from ownership.owner_indexability import load_owner_indexability_cache

        cache = load_owner_indexability_cache() or {}
        row = cache.get(pac) or {}
        name = str(row.get("owner_name") or "").strip()
    except Exception:
        name = ""
    path = associate_profile_url(pac, name)
    return f"<loc>{base}{path}</loc>"


def _apply_monkey_patches() -> None:
    global _PATCHED
    if _PATCHED:
        return
    import app as app_module

    app_module._provider_page_impl = _wrap_provider_page_impl(app_module._provider_page_impl)
    app_module._entity_page_impl = _wrap_entity_page_impl(app_module._entity_page_impl)
    app_module.generate_provider_page_html = _patch_generate_provider_page_html(
        app_module.generate_provider_page_html
    )
    app_module.generate_entity_page_html = _patch_generate_entity_page_html(
        app_module.generate_entity_page_html
    )
    app_module._build_sitemap_xml = _patch_build_sitemap_xml(app_module._build_sitemap_xml)
    app_module._build_sitemap_xml_minimal = _patch_build_sitemap_xml(
        app_module._build_sitemap_xml_minimal
    )
    _PATCHED = True


def register_canonical_page_routes(app: Flask) -> None:
    """Register canonical URL routes, legacy redirects, and runtime patches."""
    global _ROUTES_REGISTERED
    _apply_monkey_patches()
    if _ROUTES_REGISTERED:
        return
    _ROUTES_REGISTERED = True

    @app.before_request
    def _canonical_test_redirects():
        path = (request.path or "").split("?")[0]
        if m := _TEST_PROVIDER_RE.match(path):
            return _provider_canonical_redirect(m.group(1))
        if m := _TEST_ENTITY_RE.match(path):
            return _entity_canonical_redirect(m.group(1))
        return None

    @app.route("/provider/<ccn>/<path:slug>", endpoint="provider_slug_page")
    def provider_slug_page(ccn, slug=None):
        import app as app_module

        return app_module._provider_page_impl(ccn)

    @app.route("/entity/<int:entity_id>/<path:slug>", endpoint="entity_slug_page")
    def entity_slug_page(entity_id, slug=None):
        import app as app_module

        return app_module._entity_page_impl(entity_id)
