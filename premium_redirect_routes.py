"""Premium marketing pages (pbj-root) and optional dashboard upstream proxy (pbjapp migration).

Marketing HTML lives under ``premium/``. Facility dashboards at ``/premium/<CCN>`` can be
proxied to a separate app when ``PREMIUM_DASHBOARD_UPSTREAM`` is set (e.g. the legacy
pbjapp Render service URL without a trailing slash).
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from flask import abort, make_response, request, send_file

if TYPE_CHECKING:
    from flask import Flask

_CCN_RE = re.compile(r'^\d{6}$')
_PREMIUM_STATIC_PREFIXES = frozenset(
    {
        'demo',
        'email',
        'media',
        'samples',
        'premium-site.css',
        'premium-hub.css',
        'premium-hub-modals.js',
        'premium-hub-rb-sandbox.js',
        'premium-hero-chart.js',
        'premium-toc.js',
        'premium-nursing-homes.json',
        'pbj_favicon.png',
    }
)


def _serve_premium_html(app_root: str, *parts: str):
    path = os.path.join(app_root, 'premium', *parts)
    if not os.path.isfile(path):
        abort(404)
    with open(path, encoding='utf-8') as f:
        page_html = f.read()
    resp = make_response(page_html)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


def _premium_dashboard_upstream() -> str:
    return (os.environ.get('PREMIUM_DASHBOARD_UPSTREAM') or '').strip().rstrip('/')


def _proxy_premium_dashboard(upstream: str, ccn: str, subpath: str = ''):
    import requests

    target = f'{upstream}/{ccn}'
    if subpath:
        target = f'{target}/{subpath.lstrip("/")}'
    qs = request.query_string
    if qs:
        target = f'{target}?{qs.decode()}'

    headers = {
        k: v
        for k, v in request.headers
        if k.lower() not in ('host', 'content-length', 'connection')
    }
    try:
        upstream_resp = requests.request(
            method=request.method,
            url=target,
            headers=headers,
            data=request.get_data() if request.method not in ('GET', 'HEAD') else None,
            allow_redirects=False,
            timeout=120,
            stream=True,
        )
    except requests.RequestException:
        abort(502)

    excluded = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
    resp = make_response(upstream_resp.content, upstream_resp.status_code)
    for key, value in upstream_resp.headers.items():
        if key.lower() not in excluded:
            resp.headers[key] = value
    return resp


def register_premium_routes(app: Flask, app_root: str) -> None:
    """Register /premium marketing pages, static assets, and optional CCN dashboard proxy."""

    @app.route('/premium')
    @app.route('/premium/')
    def premium_hub():
        return _serve_premium_html(app_root, 'index.html')

    @app.route('/premium/pricing')
    @app.route('/premium/pricing/')
    def premium_pricing():
        return _serve_premium_html(app_root, 'pricing', 'index.html')

    @app.route('/premium/tips')
    @app.route('/premium/tips/')
    def premium_tips():
        return _serve_premium_html(app_root, 'tips', 'index.html')

    @app.route('/premium/methods')
    @app.route('/premium/methods/')
    def premium_methods():
        return _serve_premium_html(app_root, 'methods', 'index.html')

    upstream = _premium_dashboard_upstream()

    if upstream:

        @app.route('/premium/<ccn>', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
        @app.route('/premium/<ccn>/', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
        @app.route(
            '/premium/<ccn>/<path:subpath>',
            methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        )
        def premium_facility_dashboard(ccn: str, subpath: str = ''):
            if not _CCN_RE.fullmatch(str(ccn or '').strip()):
                abort(404)
            return _proxy_premium_dashboard(upstream, ccn, subpath)

    @app.route('/premium/<path:asset_path>')
    def premium_static(asset_path: str):
        """CSS/JS/images under premium/ (not facility CCN dashboards)."""
        safe = asset_path.replace('\\', '/').lstrip('/')
        if '..' in safe.split('/'):
            abort(404)
        first = safe.split('/')[0]
        if _CCN_RE.fullmatch(first):
            abort(404)
        if first in ('tips', 'methods', 'pricing'):
            abort(404)
        full = os.path.join(app_root, 'premium', safe.replace('/', os.sep))
        if not os.path.isfile(full):
            abort(404)
        return send_file(full)
