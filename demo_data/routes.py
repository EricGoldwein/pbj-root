"""Demo provider routes. Admin path stays gated; local preview is loopback-only."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from flask import abort, redirect, request

from audience.admin_auth import admin_noindex_headers, verify_admin_request
from demo_data.sunny_pastures import (
    SUNNY_PASTURES_LOCAL_PATH,
    SUNNY_PASTURES_PATH,
    load_sunny_pastures_provider,
)

if TYPE_CHECKING:
    from flask import Flask


def _is_render() -> bool:
    return bool(os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID'))


def _is_loopback_host() -> bool:
    host = (request.host or '').split(':')[0].strip().lower()
    return host in ('127.0.0.1', 'localhost', '::1')


def _render_sunny_pastures_html(*, page_path: str):
    from app import generate_provider_page_html, get_canonical_latest_quarter

    payload = load_sunny_pastures_provider(
        canonical_quarter=get_canonical_latest_quarter()
    )
    html = generate_provider_page_html(
        payload.provider_id,
        payload.facility_df,
        payload.provider_info_row,
        is_demo=True,
        page_path=page_path,
    )
    headers = {
        'Content-Type': 'text/html; charset=utf-8',
        **admin_noindex_headers(),
    }
    return html, 200, headers


def register_demo_sample_routes(app: 'Flask') -> None:
    """Register demo pages. Local `/sunny-pastures` is 404 on Render."""

    @app.route(SUNNY_PASTURES_LOCAL_PATH)
    def local_sample_sunny_pastures():
        if _is_render() or not _is_loopback_host():
            abort(404)
        return _render_sunny_pastures_html(page_path=SUNNY_PASTURES_LOCAL_PATH)

    @app.route(SUNNY_PASTURES_PATH)
    def admin_sample_sunny_pastures():
        if not verify_admin_request(request):
            resp = redirect('/admin/audience/login')
            resp.headers.update(admin_noindex_headers())
            return resp
        return _render_sunny_pastures_html(page_path=SUNNY_PASTURES_PATH)
