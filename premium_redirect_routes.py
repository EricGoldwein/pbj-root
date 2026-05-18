"""Serve the Premium marketing page at /premium and its CSS/JS/image assets.

Production routing (www.pbj320.com):
  - ``/premium`` (no trailing slash) → Render (Flask) — marketing landing page
  - ``/premium-assets/*``, ``/premium-samples/*`` → Render — static files for that page
  - ``/premium/<6-digit CCN>`` → Vercel — facility dashboards
  - ``/premium/`` and ``/premium/*`` (other) → often Vercel/edge → 404 unless Cloudflare
    is updated to send non-CCN paths to Render

Use ``/premium`` and ``/premium-assets/`` in links (not ``/premium/``) until Cloudflare
routes non-CCN ``/premium/*`` to Render. Facility dashboards stay at ``/premium/<CCN>``.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
from typing import TYPE_CHECKING, Optional

from flask import abort, jsonify, make_response, redirect, request, send_file

if TYPE_CHECKING:
    from flask import Flask, Response

_CCN_RE = re.compile(r'^\d{6}$')
# Subsites we do not expose publicly (linked from old hub only).
_BLOCKED_FIRST_SEGMENTS = frozenset({'tips', 'methods', 'pricing'})

# Render-safe public prefixes (bypass Cloudflare /premium/* → Vercel rule).
PREMIUM_ASSETS_PREFIX = '/premium-assets'
PREMIUM_SAMPLES_PREFIX = '/premium-samples'


def _premium_root(app_root: str) -> str:
    return os.path.join(app_root, 'premium')


def _safe_premium_relpath(asset_path: str) -> Optional[str]:
    safe = (asset_path or '').replace('\\', '/').lstrip('/')
    if not safe or '..' in safe.split('/'):
        return None
    first = safe.split('/')[0]
    if first in _BLOCKED_FIRST_SEGMENTS:
        return None
    if _CCN_RE.fullmatch(first):
        return None
    return safe


def try_serve_premium_asset(app_root: str, asset_path: str) -> Optional['Response']:
    """Return a Flask response for a file under premium/, or None if not allowed/missing."""
    safe = _safe_premium_relpath(asset_path)
    if not safe:
        return None
    full = os.path.join(_premium_root(app_root), safe.replace('/', os.sep))
    if not os.path.isfile(full):
        return None
    mime, _ = mimetypes.guess_type(full)
    if not mime:
        if full.endswith('.js'):
            mime = 'application/javascript'
        elif full.endswith('.json'):
            mime = 'application/json'
        elif full.endswith('.css'):
            mime = 'text/css'
        else:
            mime = 'application/octet-stream'
    resp = send_file(full, mimetype=mime)
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


def _serve_premium_landing(app_root: str) -> 'Response':
    path = os.path.join(_premium_root(app_root), 'index.html')
    if not os.path.isfile(path):
        abort(404)
    with open(path, encoding='utf-8') as f:
        page_html = f.read()
    resp = make_response(page_html)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


def _send_premium_dashboard_request_email(payload: dict) -> bool:
    """Notify team of a Premium dashboard request (same SMTP env as contact form)."""
    to_list = os.environ.get('SUBSCRIBE_NOTIFY_TO', 'egoldwein@gmail.com,eric@320insight.com').strip().split(',')
    to_list = [a.strip() for a in to_list if a.strip()]
    if not to_list:
        to_list = ['egoldwein@gmail.com']
    host = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_HOST', '').strip()
    email = (payload.get('email') or '').strip()
    ccn = (payload.get('ccn') or '').strip()
    req_type = (payload.get('request_type') or 'pilot_dashboard').strip()
    provider = (payload.get('provider_name') or '').strip()
    lines = [
        'PBJ320 Premium dashboard request (premium hub form)',
        '',
        f'Request type: {req_type}',
        f'CCN: {ccn}',
        f'Provider: {provider or "(not specified)"}',
        f'Email: {email}',
        f'Date range: {payload.get("audit_from") or ""} — {payload.get("audit_to") or ""}',
        f'Consult times: {payload.get("consult_times") or "(none)"}',
        f'Care Compare: {payload.get("care_compare_url") or ""}',
        f'Source: {payload.get("source") or "premium_hub"}',
        '',
        'Full payload:',
        json.dumps(payload, indent=2, default=str),
    ]
    body = '\n'.join(lines)
    if not host:
        print('[PBJ320 premium request] SMTP not configured. Logged only:')
        print(body[:500])
        return True
    port = int(os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PORT', '587'))
    user = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_USER', '').strip()
    password = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PASSWORD', '').strip()
    from_addr = os.environ.get('SUBSCRIBE_NOTIFY_FROM', user or 'noreply@pbj320.com').strip()
    subject = f'PBJ320 Premium request — CCN {ccn or "?"} ({req_type})'
    msg = (
        f'Subject: {subject}\r\nFrom: {from_addr}\r\nTo: {", ".join(to_list)}\r\n'
        f'Reply-To: {email}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}'
    )
    try:
        import smtplib

        with smtplib.SMTP(host, port, timeout=10) as s:
            if port == 587:
                s.starttls()
            if user and password:
                s.login(user, password)
            s.sendmail(from_addr, to_list, msg.encode('utf-8'))
        return True
    except Exception as e:
        print(f'Premium dashboard request email failed: {e}')
        return False


def register_premium_routes(app: Flask, app_root: str) -> None:
    """Register /premium landing page, static assets, and booking API."""

    @app.route('/api/premium/dashboard-request', methods=['POST'])
    def premium_dashboard_request():
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        ccn_raw = (data.get('ccn') or '').strip()
        ccn = re.sub(r'\D', '', ccn_raw)[:6]
        if not email or '@' not in email:
            return jsonify({'ok': False, 'error': 'Valid email required'}), 400
        if len(ccn) != 6:
            return jsonify({'ok': False, 'error': 'Valid 6-digit CCN required'}), 400
        payload = {
            'request_type': (data.get('request_type') or 'pilot_dashboard').strip(),
            'ccn': ccn,
            'provider_name': (data.get('provider_name') or '').strip() or None,
            'audit_from': (data.get('audit_from') or '').strip(),
            'audit_to': (data.get('audit_to') or '').strip(),
            'email': email,
            'consult_times': (data.get('consult_times') or '').strip() or None,
            'care_compare_url': (data.get('care_compare_url') or '').strip() or None,
            'source': (data.get('source') or 'premium_hub').strip(),
        }
        if not _send_premium_dashboard_request_email(payload):
            return jsonify({'ok': False, 'error': 'Could not send request'}), 503
        return jsonify({'ok': True})

    @app.route('/api/premium/routing-check')
    def premium_routing_check():
        """Diagnostics: confirms this app serves premium marketing + assets."""
        index_path = os.path.join(_premium_root(app_root), 'index.html')
        return jsonify({
            'ok': True,
            'marketing_url': '/premium',
            'assets_prefix': PREMIUM_ASSETS_PREFIX,
            'samples_prefix': PREMIUM_SAMPLES_PREFIX,
            'facility_dashboard_pattern': '/premium/<6-digit CCN> (Vercel)',
            'index_html_present': os.path.isfile(index_path),
            'note': (
                'Production: use /premium (no trailing slash) and /premium-assets/* '
                'unless Cloudflare sends all /premium/* to Render.'
            ),
        })

    @app.route('/premium')
    def premium_landing():
        # Do not 301 to /premium/ — Cloudflare often routes /premium/* to Vercel (404).
        return _serve_premium_landing(app_root)

    @app.route('/premium/')
    def premium_landing_slash():
        return _serve_premium_landing(app_root)

    @app.route(f'{PREMIUM_ASSETS_PREFIX}/<path:asset_path>')
    def premium_public_assets(asset_path: str):
        served = try_serve_premium_asset(app_root, asset_path)
        if served is None:
            abort(404)
        return served

    @app.route(f'{PREMIUM_SAMPLES_PREFIX}/<path:sample_path>')
    def premium_public_samples(sample_path: str):
        served = try_serve_premium_asset(app_root, f'samples/{sample_path}')
        if served is None:
            abort(404)
        return served

    @app.route('/premium/<path:asset_path>')
    def premium_assets(asset_path: str):
        served = try_serve_premium_asset(app_root, asset_path)
        if served is None:
            abort(404)
        return served
