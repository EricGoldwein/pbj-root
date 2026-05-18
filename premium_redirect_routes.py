"""Serve the Premium marketing page at /premium and its CSS/JS/image assets.

Only ``/premium`` is a public marketing URL. Other paths under ``/premium/`` serve
files referenced by that page (styles, scripts, media) — not separate subsites.
Facility dashboards (``/premium/<CCN>``) stay on Vercel/pbjapp.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from flask import abort, make_response, send_file

if TYPE_CHECKING:
    from flask import Flask

_CCN_RE = re.compile(r'^\d{6}$')


def register_premium_routes(app: Flask, app_root: str) -> None:
    """Register /premium landing page + assets required by premium/index.html."""

    @app.route('/premium')
    @app.route('/premium/')
    def premium_landing():
        path = os.path.join(app_root, 'premium', 'index.html')
        if not os.path.isfile(path):
            abort(404)
        with open(path, encoding='utf-8') as f:
            page_html = f.read()
        resp = make_response(page_html)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        return resp

    @app.route('/premium/<path:asset_path>')
    def premium_assets(asset_path: str):
        """CSS, JS, and images for the landing page only — not pricing/methods/tips subsites."""
        safe = asset_path.replace('\\', '/').lstrip('/')
        if '..' in safe.split('/'):
            abort(404)
        first = safe.split('/')[0]
        if first in ('tips', 'methods', 'pricing') or _CCN_RE.fullmatch(first):
            abort(404)
        full = os.path.join(app_root, 'premium', safe.replace('/', os.sep))
        if not os.path.isfile(full):
            abort(404)
        return send_file(full)
