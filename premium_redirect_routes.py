"""Serve the Premium marketing page at /premium and its CSS/JS/image assets.

Only ``/premium`` is a public marketing URL. Other paths under ``/premium/`` serve
files referenced by that page (styles, scripts, media) — not separate subsites.
Facility dashboards (``/premium/<CCN>``) stay on Vercel/pbjapp.
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

    @app.route('/premium')
    def premium_landing_redirect():
        return redirect('/premium/', code=301)

    @app.route('/premium/')
    def premium_landing():
        path = os.path.join(_premium_root(app_root), 'index.html')
        if not os.path.isfile(path):
            abort(404)
        with open(path, encoding='utf-8') as f:
            page_html = f.read()
        resp = make_response(page_html)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        resp.headers['Cache-Control'] = 'public, max-age=300'
        return resp

    @app.route('/premium/<path:asset_path>')
    def premium_assets(asset_path: str):
        served = try_serve_premium_asset(app_root, asset_path)
        if served is None:
            abort(404)
        return served
