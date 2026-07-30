"""Flask routes for PBJ320 audience signup, preferences, feedback, and admin."""

from __future__ import annotations

import csv
import html
import io
import json
import os
from typing import TYPE_CHECKING, Any

from flask import jsonify, make_response, request

from audience.admin_auth import (
    admin_noindex_headers,
    clear_admin_session,
    establish_admin_session,
    login_rate_limit_ok,
    record_login_attempt,
    verify_admin_request,
)
from audience.campaigns import (
    create_campaign_draft,
    get_campaign_audit,
    list_campaigns,
    preview_recipients,
    send_campaign,
)
from audience.cta_resolver import resolve_cta
from audience.prompt_config import prompt_config_payload
from audience.service import (
    add_preferences,
    admin_export,
    admin_export_csv_rows,
    conversion_report_queries,
    get_contact_subscriptions,
    is_prompt_suppressed,
    normalize_email,
    record_engagement_event,
    record_prompt_dismissal,
    sanitize_analytics_metadata,
    signup,
    substack_outbound_url,
    submit_feedback,
    unsubscribe_by_token,
)

if TYPE_CHECKING:
    from flask import Flask


def _parse_json_body() -> dict[str, Any]:
    if request.is_json:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    return {}


def _admin_required():
    if not verify_admin_request(request):
        return jsonify({'error': 'Unauthorized'}), 403
    return None


def register_audience_routes(app: 'Flask', *, validate_csrf_fn=None) -> None:
    """Register audience API and admin routes on the Flask app."""

    def _check_csrf() -> bool:
        if validate_csrf_fn is not None:
            try:
                validate_csrf_fn(
                    request.form.get('csrf_token')
                    or request.headers.get('X-CSRF-Token')
                    or _parse_json_body().get('csrfToken')
                )
                return True
            except Exception:
                return False
        try:
            from flask_wtf.csrf import validate_csrf
        except ImportError:
            return True
        try:
            token = (
                request.form.get('csrf_token')
                or request.headers.get('X-CSRF-Token')
                or _parse_json_body().get('csrfToken')
            )
            validate_csrf(token)
            return True
        except Exception:
            return False

    @app.route('/api/audience/config', methods=['GET'])
    def audience_config():
        return jsonify(prompt_config_payload())

    @app.route('/api/audience/resolve-cta', methods=['POST'])
    def audience_resolve_cta():
        body = _parse_json_body()
        ctx = body.get('context') if isinstance(body.get('context'), dict) else {}
        existing = body.get('existingSubscriptions') if isinstance(body.get('existingSubscriptions'), list) else []
        spec = resolve_cta(ctx, explicit_variant=body.get('variant'), existing_subscriptions=existing)
        return jsonify({'ok': True, 'cta': spec})

    @app.route('/api/audience/signup', methods=['POST'])
    def audience_signup():
        if not _check_csrf():
            return jsonify({'ok': False, 'status': 'csrf'}), 400
        body = _parse_json_body()
        email = normalize_email(body.get('email') or request.form.get('email'))
        if not email:
            return jsonify({'ok': False, 'status': 'invalid'}), 400
        cta_variant = (body.get('ctaVariant') or request.form.get('cta_variant') or 'homepage_insights').strip()[:64]
        context = body.get('context') if isinstance(body.get('context'), dict) else {}
        preferences = body.get('preferences') if isinstance(body.get('preferences'), list) else None
        result = signup(
            email,
            cta_variant=cta_variant,
            context=context,
            name=(body.get('name') or '')[:200] or None,
            organization=(body.get('organization') or '')[:200] or None,
            role=(body.get('role') or '')[:64] or None,
            preferences=preferences,
        )
        return jsonify({'ok': True, 'status': 'subscribed', **result})

    @app.route('/api/audience/preferences', methods=['POST'])
    def audience_preferences():
        if not _check_csrf():
            return jsonify({'ok': False, 'status': 'csrf'}), 400
        body = _parse_json_body()
        email = normalize_email(body.get('email'))
        prefs = body.get('preferences')
        if not email or not isinstance(prefs, list):
            return jsonify({'ok': False, 'status': 'invalid'}), 400
        ctx = body.get('context') if isinstance(body.get('context'), dict) else {}
        return jsonify(add_preferences(email, prefs, context=ctx))

    @app.route('/api/audience/status', methods=['GET', 'POST'])
    def audience_status():
        email = normalize_email(
            request.args.get('email')
            or (_parse_json_body().get('email') if request.method == 'POST' else None)
        )
        if not email:
            return jsonify({'ok': False, 'error': 'email_required'}), 400
        return jsonify(get_contact_subscriptions(email))

    @app.route('/api/audience/substack-click', methods=['POST'])
    def audience_substack_click():
        """Track Eric's Substack outbound separately from PBJ320 subscriptions."""
        body = _parse_json_body()
        visitor_key = (body.get('visitorKey') or '')[:128]
        ctx = body.get('context') if isinstance(body.get('context'), dict) else {}
        meta = sanitize_analytics_metadata(ctx)
        if visitor_key:
            record_engagement_event(
                visitor_key=visitor_key,
                event_name='substack_link_clicked',
                page_type=ctx.get('pageType'),
                resource_id=ctx.get('stateAbbr') or ctx.get('ccn'),
                metadata=meta,
            )
        url = substack_outbound_url(
            cta_variant=(ctx.get('ctaVariant') or 'eric_substack')[:64],
            page_type=ctx.get('pageType'),
        )
        return jsonify({'ok': True, 'url': url})

    @app.route('/api/audience/feedback', methods=['POST'])
    def audience_feedback():
        body = _parse_json_body()
        return jsonify(
            submit_feedback(
                rating=(body.get('rating') or '')[:16] or None,
                response=body.get('response') or '',
                source_url=body.get('sourceUrl'),
                context=body.get('context'),
                email=body.get('email'),
                quote_permission=body.get('quotePermission'),
                attribution_name=body.get('attributionName'),
                attribution_organization=body.get('attributionOrganization'),
            )
        )

    @app.route('/api/audience/engagement', methods=['POST'])
    def audience_engagement():
        body = _parse_json_body()
        visitor_key = (body.get('visitorKey') or '')[:128]
        event_name = (body.get('eventName') or '')[:64]
        if not visitor_key or not event_name:
            return jsonify({'ok': False, 'error': 'invalid'}), 400
        meta = body.get('metadata') if isinstance(body.get('metadata'), dict) else {}
        return jsonify(
            record_engagement_event(
                visitor_key=visitor_key,
                event_name=event_name,
                page_type=body.get('pageType'),
                resource_id=body.get('resourceId'),
                metadata=sanitize_analytics_metadata(meta),
            )
        )

    @app.route('/api/audience/prompt-dismiss', methods=['POST'])
    def audience_prompt_dismiss():
        body = _parse_json_body()
        visitor_key = (body.get('visitorKey') or '')[:128]
        prompt_type = (body.get('promptType') or '')[:64]
        if not visitor_key or not prompt_type:
            return jsonify({'ok': False}), 400
        return jsonify(record_prompt_dismissal(visitor_key, prompt_type))

    @app.route('/api/audience/prompt-suppressed', methods=['GET'])
    def audience_prompt_suppressed():
        visitor_key = (request.args.get('visitorKey') or '')[:128]
        prompt_type = (request.args.get('promptType') or '')[:64]
        if not visitor_key or not prompt_type:
            return jsonify({'suppressed': False})
        return jsonify({'suppressed': is_prompt_suppressed(visitor_key, prompt_type)})

    @app.route('/audience/unsubscribe')
    def audience_unsubscribe_page():
        token = (request.args.get('token') or '').strip()
        result = unsubscribe_by_token(token)
        if result.get('ok'):
            msg = 'Your PBJ320 email preferences have been updated.'
        else:
            msg = 'This unsubscribe link is invalid or has expired.'
        page = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Unsubscribe — PBJ320</title>
<style>body{{font-family:system-ui,sans-serif;background:#0a0f1a;color:#e2e8f0;padding:2rem;max-width:32rem;margin:0 auto;}}
a{{color:#818cf8;}}</style></head>
<body><h1>PBJ320 preferences</h1><p>{html.escape(msg)}</p>
<p><a href="/">Return to PBJ320</a> · <a href="/contact">Contact us</a></p></body></html>'''
        resp = make_response(page, 200, {'Content-Type': 'text/html; charset=utf-8'})
        resp.headers.update(admin_noindex_headers())
        return resp

    @app.route('/admin/audience/login', methods=['GET', 'POST'])
    def admin_audience_login():
        if verify_admin_request(request):
            return _redirect_admin_home()
        if request.method == 'GET':
            csrf_field = ''
            try:
                from flask_wtf.csrf import generate_csrf
                csrf_field = f'<input type="hidden" name="csrf_token" value="{html.escape(generate_csrf())}">'
            except Exception:
                pass
            page = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PBJ320 Audience Admin — Sign in</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;background:#0f172a;color:#e2e8f0;max-width:24rem;}}
input,button{{width:100%;padding:.6rem;margin:.4rem 0;font-size:1rem;}}
button{{background:#6366f1;color:#fff;border:none;border-radius:6px;cursor:pointer;}}</style></head>
<body><h1>Audience admin</h1>
<p>Sign in with your admin key. Keys are never stored in the URL or browser history.</p>
<form method="post" action="/admin/audience/login">
{csrf_field}
<input type="password" name="admin_key" autocomplete="current-password" required aria-label="Admin key">
<button type="submit">Sign in</button>
</form></body></html>'''
            resp = make_response(page, 200, {'Content-Type': 'text/html; charset=utf-8'})
            resp.headers.update(admin_noindex_headers())
            return resp
        if not login_rate_limit_ok(request.remote_addr):
            return make_response('Too many attempts. Try again later.', 429)
        if not _check_csrf():
            return make_response('Invalid CSRF token.', 400)
        submitted = (request.form.get('admin_key') or '').strip()
        expected = (os.environ.get('ADMIN_VIEW_KEY') or os.environ.get('PBJ_ADMIN_KEY') or '').strip()
        if submitted and expected and submitted == expected:
            record_login_attempt(request.remote_addr, success=True)
            establish_admin_session()
            return _redirect_admin_home()
        record_login_attempt(request.remote_addr, success=False)
        resp = make_response('Invalid admin key.', 403)
        resp.headers.update(admin_noindex_headers())
        return resp

    def _redirect_admin_home():
        from flask import redirect
        return redirect('/admin/audience')

    @app.route('/admin/audience/logout', methods=['POST'])
    def admin_audience_logout():
        if not _check_csrf():
            return make_response('Invalid CSRF token.', 400)
        clear_admin_session()
        from flask import redirect
        resp = redirect('/admin/audience/login')
        resp.headers.update(admin_noindex_headers())
        return resp

    @app.route('/admin/audience')
    def admin_audience():
        if not verify_admin_request(request):
            from flask import redirect
            return redirect('/admin/audience/login')
        data = admin_export()
        accept = request.headers.get('Accept', '') or ''
        if 'text/csv' in accept:
            buf = io.StringIO()
            writer = csv.writer(buf)
            for row in admin_export_csv_rows():
                writer.writerow(row)
            resp = make_response(buf.getvalue(), 200, {'Content-Type': 'text/csv; charset=utf-8'})
            resp.headers.update(admin_noindex_headers())
            resp.headers['Content-Disposition'] = 'attachment; filename=pbj320-audience.csv'
            return resp
        if 'application/json' in accept and 'text/html' not in accept:
            resp = make_response(jsonify(data))
            resp.headers.update(admin_noindex_headers())
            return resp
        queries = conversion_report_queries()
        rows_html = ''.join(
            f'<tr><td>{html.escape(str(r.get("email") or ""))}</td>'
            f'<td>{html.escape(str(r.get("subscription_type") or ""))}</td>'
            f'<td>{html.escape(str(r.get("resource_id") or ""))}</td>'
            f'<td>{html.escape(str(r.get("status") or ""))}</td>'
            f'<td>{html.escape(str(r.get("cta_variant") or ""))}</td></tr>'
            for r in data[:500]
        )
        q_html = ''.join(
            f'<h3>{html.escape(name)}</h3><pre>{html.escape(sql.strip())}</pre>'
            for name, sql in queries.items()
        )
        logout_csrf = ''
        try:
            from flask_wtf.csrf import generate_csrf
            logout_csrf = f'<input type="hidden" name="csrf_token" value="{html.escape(generate_csrf())}">'
        except Exception:
            pass
        page = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow">
<title>PBJ320 Audience Admin</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;background:#0f172a;color:#e2e8f0;}}
table{{border-collapse:collapse;width:100%;}} th,td{{border:1px solid #334155;padding:.4rem .6rem;text-align:left;}}
th{{background:#1e293b;}} pre{{background:#1e293b;padding:1rem;overflow:auto;font-size:.85rem;}}</style></head>
<body><h1>PBJ320 audience</h1><p>{len(data)} row(s). Session or header auth. CSV: <code>Accept: text/csv</code>.</p>
<form method="post" action="/admin/audience/logout" style="margin-bottom:1rem;">{logout_csrf}<button type="submit">Sign out</button></form>
<table><thead><tr><th>Email</th><th>Type</th><th>Resource</th><th>Status</th><th>CTA</th></tr></thead>
<tbody>{rows_html or '<tr><td colspan="5">No records.</td></tr>'}</tbody></table>
<h2>Conversion report queries</h2>{q_html}</body></html>'''
        resp = make_response(page, 200, {'Content-Type': 'text/html; charset=utf-8'})
        resp.headers.update(admin_noindex_headers())
        return resp

    @app.route('/api/audience/conversion-queries', methods=['GET'])
    def audience_conversion_queries():
        denied = _admin_required()
        if denied:
            return denied
        resp = make_response(jsonify(conversion_report_queries()))
        resp.headers.update(admin_noindex_headers())
        return resp

    @app.route('/api/audience/campaigns/preview', methods=['POST'])
    def audience_campaign_preview():
        denied = _admin_required()
        if denied:
            return denied
        body = _parse_json_body()
        return jsonify(preview_recipients(
            body.get('subscriptionType') or '',
            resource_type=body.get('resourceType'),
            resource_id=body.get('resourceId'),
        ))

    @app.route('/api/audience/campaigns', methods=['GET', 'POST'])
    def audience_campaigns():
        denied = _admin_required()
        if denied:
            return denied
        if request.method == 'GET':
            resp = make_response(jsonify(list_campaigns()))
            resp.headers.update(admin_noindex_headers())
            return resp
        body = _parse_json_body()
        result = create_campaign_draft(
            body.get('name') or 'Campaign',
            body.get('subscriptionType') or '',
            resource_type=body.get('resourceType'),
            resource_id=body.get('resourceId'),
            subject=body.get('subject') or '',
            body_preview=body.get('bodyPreview') or '',
            test_mode=bool(body.get('testMode')),
        )
        resp = make_response(jsonify(result))
        resp.headers.update(admin_noindex_headers())
        return resp

    @app.route('/api/audience/campaigns/<int:campaign_id>/send', methods=['POST'])
    def audience_campaign_send(campaign_id: int):
        denied = _admin_required()
        if denied:
            return denied
        body = _parse_json_body()
        result = send_campaign(
            campaign_id,
            test_email=body.get('testEmail'),
            retry_failed_only=bool(body.get('retryFailedOnly')),
        )
        resp = make_response(jsonify(result))
        resp.headers.update(admin_noindex_headers())
        return resp

    @app.route('/api/audience/campaigns/<int:campaign_id>/audit', methods=['GET'])
    def audience_campaign_audit(campaign_id: int):
        denied = _admin_required()
        if denied:
            return denied
        audit = get_campaign_audit(campaign_id)
        if not audit:
            return jsonify({'ok': False, 'error': 'campaign_not_found'}), 404
        resp = make_response(jsonify({'ok': True, 'audit': audit}))
        resp.headers.update(admin_noindex_headers())
        return resp
