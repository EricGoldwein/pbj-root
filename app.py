#!/usr/bin/env python3
# pyright: basic, reportGeneralTypeIssues=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOperatorIssue=false
"""
Simple Flask app to serve static files with proper headers for Facebook scraper
Now with dynamic date support
"""
from flask import Flask, send_from_directory, send_file, render_template_string, render_template, jsonify, request, redirect, make_response
import os
import sys

# Load .env from project root if present (for SUBSCRIBE_NOTIFY_*, SECRET_KEY, etc.)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass
import re
import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import html
import time
import gzip

try:
    import markdown  # type: ignore
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    markdown = None  # type: ignore
    print("Warning: markdown module not found. PBJpedia pages will not be available.")
    print("Install with: pip install markdown")

# Defer pandas import so workers can respond to /health before heavy imports (Render port check).
_pandas_module = None
HAS_PANDAS = False

def get_pd():
    """Import pandas on first use so /health can respond before workers load it."""
    global _pandas_module, HAS_PANDAS
    if _pandas_module is not None:
        return _pandas_module
    try:
        import pandas as pd
        _pandas_module = pd
        HAS_PANDAS = True
        return pd
    except ImportError:
        HAS_PANDAS = False
        return None

pd = None  # Set by _ensure_pandas() on first non-health request.

# Import date utilities from local utils package (run from pbj-root so utils is on path)
from utils.date_utils import get_latest_data_periods, get_latest_update_month_year  # type: ignore[reportMissingImports]
from utils.seo_utils import get_seo_metadata  # type: ignore[reportMissingImports]
try:
    from pbj_format import round_half_up
except ImportError:
    def round_half_up(value, decimals=0):
        if value is None or (isinstance(value, float) and __import__('math').isnan(value)):
            return None
        try:
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return None

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# SECRET_KEY required for CSRF (e.g. /subscribe). Set SECRET_KEY or FLASK_SECRET_KEY in production.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY')
if not app.config['SECRET_KEY']:
    app.config['SECRET_KEY'] = 'jak@rr23'
    print('Warning: SECRET_KEY not set; using default. Set SECRET_KEY or FLASK_SECRET_KEY in production.')
try:
    from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf  # type: ignore[reportMissingImports]
    csrf_protect = CSRFProtect(app)
    HAS_CSRF = True
except ImportError:
    HAS_CSRF = False
    csrf_protect = None
    generate_csrf = None
    validate_csrf = None
    print('Warning: Flask-WTF not installed. CSRF disabled for /subscribe. Install: pip install Flask-WTF')

# Subscribers DB: SQLite. Set SUBSCRIBERS_DB_PATH in production (e.g. on a persistent disk) so data survives deploys.
def _subscribers_db_path():
    env_path = os.environ.get('SUBSCRIBERS_DB_PATH', '').strip()
    if env_path:
        parent = os.path.dirname(env_path)
        if parent and not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except PermissionError:
                env_path = None  # fall back to writable location below
        if env_path:
            return env_path
    # Default: instance path, or writable fallback when instance path is not writable (e.g. Render)
    try:
        instance = app.instance_path
        if not os.path.isdir(instance):
            os.makedirs(instance, exist_ok=True)
        return os.path.join(instance, 'subscribers.db')
    except PermissionError:
        pass
    for candidate in (os.path.join(os.getcwd(), 'data'), '/tmp/pbj_data'):
        try:
            os.makedirs(candidate, exist_ok=True)
            return os.path.join(candidate, 'subscribers.db')
        except (PermissionError, OSError):
            continue
    # Last resort: current dir (may fail on insert)
    return os.path.join(os.getcwd(), 'subscribers.db')

def _subscribers_conn():
    """Open a connection with busy_timeout so concurrent workers don't get 'database is locked'."""
    path = _subscribers_db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute('PRAGMA busy_timeout=5000')
    return conn

_subscribers_path_logged = False

def _init_subscribers_db():
    """Create subscribers table if not exists. Called on first use."""
    global _subscribers_path_logged
    path = _subscribers_db_path()
    if not _subscribers_path_logged:
        import logging
        persistent = bool(os.environ.get('SUBSCRIBERS_DB_PATH', '').strip())
        logging.getLogger(__name__).info('Subscribers DB: %s%s', path, ' (persistent)' if persistent else ' (ephemeral if not SUBSCRIBERS_DB_PATH)')
        _subscribers_path_logged = True
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(255) NOT NULL UNIQUE,
            source VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


# Cache for built assets (cleared on app start)
_built_assets_cache = None
_built_assets_mtime = None

def get_built_assets():
    """Extract script and CSS link tags from built index.html (cached)"""
    global _built_assets_cache, _built_assets_mtime
    
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if not os.path.exists(wrapped_index):
        return {'scripts': '', 'stylesheets': ''}
    
    # Check if file has been modified (cache invalidation)
    try:
        current_mtime = os.path.getmtime(wrapped_index)
        if _built_assets_cache is not None and _built_assets_mtime == current_mtime:
            return _built_assets_cache
    except Exception:
        pass
    
    try:
        with open(wrapped_index, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract script tags
        script_pattern = r'<script[^>]*src=["\']([^"\']+)["\'][^>]*></script>'
        scripts = re.findall(script_pattern, content)
        script_tags = '\n'.join([f'    <script type="module" crossorigin src="{s}"></script>' for s in scripts])
        
        # Extract link tags for stylesheets
        link_pattern = r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\'][^>]*>'
        links = re.findall(link_pattern, content)
        link_tags = '\n'.join([f'    <link rel="stylesheet" crossorigin href="{l}">' for l in links])
        
        result = {'scripts': script_tags, 'stylesheets': link_tags}
        
        # Cache the result
        _built_assets_cache = result
        try:
            _built_assets_mtime = os.path.getmtime(wrapped_index)
        except Exception:
            _built_assets_mtime = None
        
        return result
    except Exception as e:
        print(f"Warning: Could not extract assets from built index.html: {e}")
        return {'scripts': '', 'stylesheets': ''}

def get_dynamic_dates():
    """Get dynamic date information. Used by /api/dynamic-dates (SFF page source text, quarter discovery).
    data_range and quarter_count come from national_quarterly_metrics.csv when available;
    provider_info_* and affiliated_entity_* are from utils.date_utils (hardcoded there)."""
    try:
        return get_latest_data_periods()
    except Exception as e:
        print(f"Warning: Could not get dynamic dates: {e}")
        return {
            'data_range': '2017-2025',
            'quarter_count': 33,
            'provider_info_latest': 'February 2026',
            'provider_info_previous': 'January 2026',
            'affiliated_entity_latest': 'July 2025',
            'current_year': 2025
        }

@app.route('/api/dates')
def api_dates():
    """API endpoint to get dynamic date information (used by SFF page for source text).
    Returns quarters: list of quarter IDs that have pre-built JSON (e.g. ["2025Q1", "2025Q2"]).
    Frontend should only request JSON files for these quarters; no CSV fallback."""
    data = get_dynamic_dates()
    # Add PBJ quarter, SFF posting, and list of available quarters for JSON discovery
    try:
        quarter_path = os.path.join(os.path.dirname(__file__), 'latest_quarter_data.json')
        if os.path.exists(quarter_path):
            with open(quarter_path, 'r', encoding='utf-8') as f:
                q = json.load(f)
            data['pbj_quarter_display'] = q.get('quarter_display', 'Q3 2025')
            # Available quarters: include current quarter from "quarter"; merge with "quarters" list if present
            current = q.get('quarter', '2025Q3')
            if isinstance(q.get('quarters'), list) and len(q['quarters']) > 0:
                quarters_list = [str(x) for x in q['quarters']]
                if isinstance(current, str) and current.strip() and current not in quarters_list:
                    quarters_list.append(current)
                    quarters_list.sort(reverse=True)
                data['quarters'] = quarters_list
            elif isinstance(current, str) and re.match(r'^\d{4}Q[1-4]$', current.strip()):
                y, n = int(current[:4]), int(current[5])
                prev_n = n - 1 if n > 1 else 4
                prev_y = y if n > 1 else y - 1
                data['quarters'] = [current, f'{prev_y}Q{prev_n}']
            else:
                data['quarters'] = ['2025Q3', '2025Q2']
        else:
            data['pbj_quarter_display'] = 'Q3 2025'
            data['quarters'] = ['2025Q3', '2025Q2']
    except Exception:
        data['pbj_quarter_display'] = 'Q3 2025'
        data['quarters'] = ['2025Q3', '2025Q2']
    data['sff_posting'] = 'Jan. 2026'  # CMS SFF posting date; update when new list is published
    return jsonify(data)

@app.route('/api/state/<state_code>/chart-data')
def api_state_chart_data(state_code):
    """Return state historical chart data as JSON (avoids embedding JSON in HTML and script syntax errors)."""
    if not state_code or len(state_code) != 2:
        return jsonify({'error': 'invalid state code'}), 400
    code = state_code.upper()
    d = get_state_historical_data(code)
    if not d or not d.get('raw_quarters'):
        return jsonify({'error': 'no data'}), 404
    return jsonify(d)

@app.route('/search_index.json')
def search_index():
    """Serve search index for home page autocomplete (facility, entity, state)"""
    path = os.path.join(os.path.dirname(__file__), 'search_index.json')
    if os.path.isfile(path):
        return send_file(path, mimetype='application/json')
    return jsonify({'f': [], 'e': [], 's': []})


_SEARCH_INDEX_CACHE = None
_SEARCH_INDEX_AT = 0
_SEARCH_INDEX_TTL = 300  # 5 min

HIGH_RISK_CRITERIA_TOOLTIP = 'PBJ320 assigns nursing homes as high-risk when CMS designates them as: Special Focus Facility (SFF), SFF candidate, 1-star overall rating, or with an abuse icon.'

def get_facility_risk_from_search_index(ccn):
    """Return (risk_flag, reason_str) for a facility CCN from search_index.json (same logic as home search). Cached 2 min."""
    global _SEARCH_INDEX_CACHE, _SEARCH_INDEX_AT
    if not ccn:
        return 0, ''
    prov = str(ccn).strip().zfill(6)
    path = os.path.join(APP_ROOT, 'search_index.json')
    if not os.path.isfile(path):
        return 0, ''
    now = time.time()
    if _SEARCH_INDEX_CACHE is None or (now - _SEARCH_INDEX_AT) >= _SEARCH_INDEX_TTL:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _SEARCH_INDEX_CACHE = json.load(f)
                _SEARCH_INDEX_AT = now
        except Exception:
            return 0, ''
    data = _SEARCH_INDEX_CACHE
    try:
        for row in (data.get('f') or []):
            if (row.get('c') or '').strip().zfill(6) == prov:
                r = 1 if row.get('r') == 1 else 0
                h = (row.get('h') or '').strip() or ''
                return r, h
    except Exception:
        pass
    return 0, ''

@app.before_request
def _ensure_pandas():
    """Load pandas on first non-health request so /health can respond before workers load it (Render)."""
    if request.path == '/health':
        return
    global pd
    if pd is None:
        pd = get_pd()

@app.route('/health')
def health():
    """Lightweight health check for Render. Side-effect free (best practice for public sites)."""
    return 'ok', 200

# Simple email format check (not RFC-strict; rejects obviously invalid)
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

@app.route('/')
def index():
    path = os.path.join(APP_ROOT, 'index.html')
    with open(path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    if HAS_CSRF and generate_csrf:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', generate_csrf())
    else:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', '')
    resp = make_response(html_content)
    resp.mimetype = 'text/html'
    return resp

@app.errorhandler(400)
def bad_request(err):
    """Redirect /subscribe and /contact CSRF or bad request to friendly page instead of 400."""
    if request.path == '/subscribe':
        return redirect('/?subscribe_error=invalid')
    if request.path == '/contact':
        return redirect('/contact?error=invalid')
    return make_response(('Bad Request', 400))

def _send_subscribe_notification(email_address, source='homepage'):
    """Send a brief notification email to configured addresses when someone subscribes. Optional: set SUBSCRIBE_NOTIFY_SMTP_* env."""
    to_list = os.environ.get('SUBSCRIBE_NOTIFY_TO', 'egoldwein@gmail.com,eric@320insight.com').strip().split(',')
    to_list = [a.strip() for a in to_list if a.strip()]
    if not to_list:
        return
    host = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_HOST', '').strip()
    if not host:
        return
    port = int(os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PORT', '587'))
    user = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_USER', '').strip()
    password = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PASSWORD', '').strip()
    from_addr = os.environ.get('SUBSCRIBE_NOTIFY_FROM', user or 'noreply@pbj320.com').strip()
    subject = 'PBJ320: New subscriber'
    body = f"New PBJ320 email signup.\n\nEmail: {email_address}\nSource: {source}\n"
    msg = f"Subject: {subject}\r\nFrom: {from_addr}\r\nTo: {', '.join(to_list)}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
    try:
        import smtplib
        with smtplib.SMTP(host, port, timeout=10) as s:
            if port == 587:
                s.starttls()
            if user and password:
                s.login(user, password)
            s.sendmail(from_addr, to_list, msg.encode('utf-8'))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning('Subscribe notification email failed: %s', e)


def _send_contact_email(sender_email, sender_name, message_body, is_press=False):
    """Send contact form submission. Uses same SMTP and recipient list as subscribe (SUBSCRIBE_NOTIFY_TO)."""
    to_list = os.environ.get('SUBSCRIBE_NOTIFY_TO', 'egoldwein@gmail.com,eric@320insight.com').strip().split(',')
    to_list = [a.strip() for a in to_list if a.strip()]
    if not to_list:
        to_list = ['egoldwein@gmail.com']
    host = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_HOST', '').strip()
    if not host:
        # No SMTP configured (e.g. local/server without env). Log so you can test the flow; on Render with SMTP set, real email is sent.
        print('[PBJ320 contact] SMTP not configured. Submission logged only:')
        print(f'  From: {sender_name} <{sender_email}>  Media: {is_press}')
        print(f'  Message: {message_body[:200]}{"..." if len(message_body) > 200 else ""}')
        return True  # show success so form flow works when testing without SMTP
    port = int(os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PORT', '587'))
    user = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_USER', '').strip()
    password = os.environ.get('SUBSCRIBE_NOTIFY_SMTP_PASSWORD', '').strip()
    from_addr = os.environ.get('SUBSCRIBE_NOTIFY_FROM', user or 'noreply@pbj320.com').strip()
    subject_type = (request.form.get('subject_type') or '').strip().lower() if request.form else ''
    if subject_type == 'data_issue':
        subject = 'PBJ320 Data Issue'
    elif is_press:
        subject = f"PRESS REQUEST: {sender_name}"
    else:
        subject = f"PBJ320 Request: {sender_name}"
    lines = [
        f"Name: {sender_name}",
        f"Email: {sender_email}",
        f"Media: {'Yes' if is_press else 'No'}",
        "",
        "Message:",
        message_body,
    ]
    body = "\n".join(lines)
    msg = f"Subject: {subject}\r\nFrom: {from_addr}\r\nTo: {', '.join(to_list)}\r\nReply-To: {sender_email}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{body}"
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
        print(f'Contact form email failed: {e}')
        return False


@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Accept email for PBJ320 updates. Stored in DB only; no public list. CSRF required."""
    if HAS_CSRF and validate_csrf is not None:
        try:
            validate_csrf(request.form.get('csrf_token'))
        except Exception:
            return redirect('/?subscribe_error=invalid')
    raw = request.form.get('email')
    if not raw or not isinstance(raw, str):
        return redirect('/?subscribe_error=invalid')
    email = raw.strip().lower()
    if not email or len(email) > 255:
        return redirect('/?subscribe_error=invalid')
    if not _EMAIL_RE.match(email):
        return redirect('/?subscribe_error=invalid')
    _init_subscribers_db()
    conn = _subscribers_conn()
    try:
        for attempt in range(2):
            try:
                conn.execute(
                    'INSERT INTO subscribers (email, source) VALUES (?, ?)',
                    (email, 'homepage')
                )
                conn.commit()
                break
            except sqlite3.OperationalError as e:
                if 'locked' in str(e).lower() and attempt == 0:
                    time.sleep(0.25)
                    continue
                raise
        _send_subscribe_notification(email, 'homepage')
        return redirect('/?subscribed=1')
    except sqlite3.IntegrityError:
        # Duplicate: treat as success (idempotent; don't leak existence)
        return redirect('/?subscribed=1')
    except Exception as e:
        if app.debug:
            raise
        import logging
        logging.getLogger(__name__).warning('Subscribe failed: %s', e, exc_info=True)
        return redirect('/?subscribe_error=error')
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.route('/admin/subscribers')
def admin_subscribers():
    """List newsletter signups (email, source, created_at). Requires ?key=ADMIN_VIEW_KEY env.
    Returns HTML table in browser, JSON if Accept is application/json."""
    admin_key = os.environ.get('ADMIN_VIEW_KEY', '').strip()
    if not admin_key or request.args.get('key') != admin_key:
        return jsonify({'error': 'Unauthorized'}), 403
    _init_subscribers_db()
    conn = _subscribers_conn()
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT email, source, created_at FROM subscribers ORDER BY created_at DESC'
        ).fetchall()
        data = [{'email': r['email'], 'source': r['source'] or '', 'created_at': r['created_at'] or ''} for r in rows]
        # Browser: return HTML table; API: return JSON
        accept = request.headers.get('Accept', '') or ''
        if 'application/json' in accept and 'text/html' not in accept:
            return jsonify(data)
        # HTML page
        rows_html = ''.join(
            f'<tr><td>{html.escape(r["email"])}</td><td>{html.escape(r["source"])}</td><td>{r["created_at"] or ""}</td></tr>'
            for r in data
        )
        html_page = f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Subscribers</title>
<style>body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #334155; padding: 0.5rem 1rem; text-align: left; }}
th {{ background: #1e293b; color: #93c5fd; }}</style>
</head>
<body>
<h1>Newsletter subscribers</h1>
<p>{len(data)} signup(s)</p>
<table><thead><tr><th>Email</th><th>Source</th><th>Created</th></tr></thead>
<tbody>{rows_html or '<tr><td colspan="3">No subscribers yet.</td></tr>'}</tbody>
</table>
</body>
</html>'''
        return make_response(html_page, 200, {'Content-Type': 'text/html; charset=utf-8'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _contact_redirect(path_fragment, param_value):
    """Redirect to path_fragment with param (contact_sent or contact_error). path_fragment must be safe (start with /, not //)."""
    if not path_fragment or not path_fragment.startswith('/') or path_fragment.startswith('//'):
        path_fragment = '/'
    sep = '&' if '?' in path_fragment else '?'
    return redirect(path_fragment + sep + param_value)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact form: GET shows form, POST sends email. Redirects back to same page (next) on success/error."""
    if request.method == 'POST':
        next_url = (request.form.get('next') or '').strip()
        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = '/'
        if HAS_CSRF and validate_csrf is not None:
            try:
                validate_csrf(request.form.get('csrf_token'))
            except Exception:
                return _contact_redirect(next_url, 'contact_error=1')
        email = (request.form.get('email') or '').strip().lower()
        message = (request.form.get('message') or '').strip()
        name = (request.form.get('name') or '').strip()[:200]
        is_press = request.form.get('press') in ('1', 'on', 'yes', 'true')
        if not name:
            return redirect('/contact?error=invalid')
        if not email or not _EMAIL_RE.match(email) or len(email) > 255:
            return redirect('/contact?error=invalid')
        if not message or len(message) > 10000:
            return redirect('/contact?error=invalid')
        if _send_contact_email(email, name, message, is_press=is_press):
            return _contact_redirect(next_url, 'contact_sent=1')
        return _contact_redirect(next_url, 'contact_error=1')
    # Contact page not public: GET redirects to home. Form is only via popup (POST).
    return redirect('/')


@app.route('/about')
def about():
    return send_file('about.html', mimetype='text/html')

@app.route('/insights')
@app.route('/insights/')
def insights():
    return send_file('insights.html', mimetype='text/html')

@app.route('/pbj-sample')
def pbj_sample():
    """Handle both /pbj-sample and /pbj-sample.html"""
    return send_file('pbj-sample.html', mimetype='text/html')

@app.route('/report')
@app.route('/report/')
def report():
    return send_file('report.html', mimetype='text/html')


@app.route('/press')
@app.route('/press/')
def press():
    return send_file('press.html', mimetype='text/html')


@app.route('/attorneys')
@app.route('/attorneys/')
def attorneys():
    return send_file('attorneys.html', mimetype='text/html')


@app.route('/phoebe')
@app.route('/phoebe/')
def phoebe():
    return send_file('phoebe.html', mimetype='text/html')


@app.route('/LI-In-Bug.png')
def serve_li_bug():
    return send_from_directory(APP_ROOT, 'LI-In-Bug.png', mimetype='image/png')


def _static_cache_headers(resp, max_age=3600):
    """Set Cache-Control for static assets (1 hr) so repeat visits avoid re-fetching."""
    if resp is not None and hasattr(resp, 'headers'):
        resp.headers['Cache-Control'] = f'public, max-age={max_age}'
    return resp

@app.route('/substack.png')
def serve_substack():
    return _static_cache_headers(send_from_directory(APP_ROOT, 'substack.png', mimetype='image/png'))


@app.route('/pbj-site-universal.js')
def serve_pbj_site_universal():
    """Single source for contact number and footer; injects into #site-footer on static pages."""
    return _static_cache_headers(send_from_directory(APP_ROOT, 'pbj-site-universal.js', mimetype='application/javascript'))


@app.route('/state-page-charts.js')
def serve_state_page_charts():
    """State page chart logic (no inline script = no brace/syntax errors)."""
    return _static_cache_headers(send_from_directory(APP_ROOT, 'state-page-charts.js', mimetype='application/javascript'))


@app.route('/press/wtvr-twin-lakes-clip.mp4')
def serve_wtvr_video():
    path = os.path.join(APP_ROOT, 'press', 'wtvr-twin-lakes-clip.mp4')
    if os.path.isfile(path):
        return send_file(path, mimetype='video/mp4')
    from flask import abort
    abort(404)


@app.route('/press/wtvr-thumbnail.jpg')
def serve_wtvr_thumbnail():
    path = os.path.join(APP_ROOT, 'press', 'wtvr-thumbnail.jpg')
    if os.path.isfile(path):
        return send_file(path, mimetype='image/jpeg')
    from flask import abort
    abort(404)


# Owner Donor Dashboard - LAZY import on first /owners request (keeps startup fast for Render port check)
# Importing owner_donor_dashboard pulls in pandas, FEC modules, etc. and was causing "No open ports" / slow startup.
_owner_app = None
_owner_app_error = None

def get_owner_app():
    """Import owner dashboard on first request; cache result. Keeps app startup fast."""
    global _owner_app, _owner_app_error
    if _owner_app is not None:
        return _owner_app
    if _owner_app_error is not None:
        raise _owner_app_error
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'donor'))
        from owner_donor_dashboard import app as owner_app  # type: ignore
        _owner_app = owner_app
        return _owner_app
    except Exception as e:
        _owner_app_error = e
        import traceback
        traceback.print_exc()
        raise

from flask import Blueprint
owner_bp = Blueprint('owners', __name__, url_prefix='/owners')


@app.route('/owners/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/owner/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/ownership/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def owner_api_proxy(api_path):
    """Handle /owners/api/* first so POST body is reliably passed to sub-app. Registered before blueprint."""
    try:
        owner_app = get_owner_app()
    except Exception:
        return jsonify({'error': 'Owner dashboard unavailable'}), 503
    try:
        req_body = None
        if request.method in ['POST', 'PUT']:
            req_body = request.get_data()
        headers = {k: v for k, v in request.headers if k.lower() != 'host'}
        with owner_app.test_request_context(
            f'/api/{api_path}',
            method=request.method,
            query_string=request.query_string.decode() if request.query_string else '',
            data=req_body,
            content_type=request.content_type,
            headers=headers
        ):
            return owner_app.full_dispatch_request()
    except Exception as e:
        from werkzeug.exceptions import BadRequest
        if isinstance(e, BadRequest):
            return jsonify({'error': getattr(e, 'description', None) or 'Bad request'}), 400
        print(f"Error in owner_api_proxy for {api_path}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Proxy error: {str(e)}'}), 500


if csrf_protect:
    csrf_protect.exempt(owner_api_proxy)


@owner_bp.route('', defaults={'path': ''})
@owner_bp.route('/', defaults={'path': ''})
@owner_bp.route('/<path:path>')
def owner_proxy(path):
    """Proxy requests to the owner donor dashboard app (lazy-loaded on first request)."""
    try:
        owner_app = get_owner_app()
    except Exception:
        return "Owner dashboard unavailable. Please check server logs.", 503
    if path.startswith('api/'):
        api_path = path[4:]
        # For POST/PUT, pass raw body so sub-app always receives it (test_request_context json= can be unreliable).
        req_body = None
        if request.method in ('POST', 'PUT'):
            req_body = request.get_data()
        with owner_app.test_request_context(
            f'/api/{api_path}',
            method=request.method,
            query_string=request.query_string.decode(),
            data=req_body,
            content_type=request.content_type,
            headers=list(request.headers)
        ):
            return owner_app.full_dispatch_request()
    elif path == '':
        with owner_app.test_request_context('/', method=request.method):
            return owner_app.full_dispatch_request()
    else:
        with owner_app.test_request_context(f'/{path}',
                                             method=request.method,
                                             query_string=request.query_string.decode(),
                                             data=request.get_data(),
                                             content_type=request.content_type,
                                             headers=list(request.headers)):
            return owner_app.full_dispatch_request()

app.register_blueprint(owner_bp)

@app.route('/top')
@app.route('/top/')
def top_redirect():
    return redirect('/owners/top', code=302)

@app.route('/owners-test')
@app.route('/owners-test/')
def owners_test_redirect():
    return redirect('/owners/test', code=302)

@app.route('/owner', defaults={'path': ''})
@app.route('/owner/', defaults={'path': ''})
@app.route('/owner/<path:path>')
@app.route('/ownership', defaults={'path': ''})
@app.route('/ownership/', defaults={'path': ''})
@app.route('/ownership/<path:path>')
def owner_alias(path=''):
    if path:
        return redirect(f'/owners/{path}', code=301)
    return redirect('/owners', code=301)

@app.route('/sitemap.xml')
def sitemap():
    """Dynamic sitemap: static pages + /state/<slug> for all states + provider/entity from search_index (subset)."""
    base = 'https://pbj320.com'
    today = datetime.now().strftime('%Y-%m-%d')
    urls = []
    # Static pages (from original sitemap.xml)
    for path, priority, changefreq in [
        ('/', '1.0', 'weekly'),
        ('/about', '0.8', 'monthly'),
        ('/insights', '0.9', 'weekly'),
        ('/report', '0.9', 'weekly'),
        ('/press', '0.8', 'monthly'),
        ('/attorneys', '0.8', 'monthly'),
        ('/pbj-sample', '0.6', 'monthly'),
    ]:
        urls.append(f'  <url><loc>{base}{path}</loc><lastmod>{today}</lastmod><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>')
    # Canonical state/provider/entity pages (pbj320.com/state/pa, /provider/xxx, /entity/123)
    for state_code in sorted(STATE_CODE_TO_NAME.keys()):
        slug = get_canonical_slug(state_code)
        urls.append(f'  <url><loc>{base}/state/{slug}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>')
    search_path = os.path.join(APP_ROOT, 'search_index.json')
    if os.path.isfile(search_path):
        try:
            with open(search_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for fac in (data.get('f') or [])[:10000]:
                if fac and fac.get('c'):
                    urls.append(f'  <url><loc>{base}/provider/{fac.get("c")}</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>')
            for ent in (data.get('e') or [])[:2000]:
                if ent and ent.get('id') is not None:
                    urls.append(f'  <url><loc>{base}/entity/{ent.get("id")}</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>')
        except Exception as e:
            print(f"Sitemap: could not load search_index: {e}")
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(urls) + '\n</urlset>'
    return xml, 200, {'Content-Type': 'application/xml; charset=utf-8'}


# State name to code mapping
STATE_NAME_TO_CODE = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
    'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
    'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
    'district of columbia': 'DC', 'puerto rico': 'PR'
}

STATE_CODE_TO_NAME = {v: k.title() for k, v in STATE_NAME_TO_CODE.items()}

# States included in rankings (exclude Puerto Rico so rankings are 51: 50 states + DC)
STATES_FOR_RANKING = set(STATE_CODE_TO_NAME.keys()) - {'PR'}

# Canonical slug mapping: state code -> canonical slug (lowercase, hyphenated)
# Examples: TN -> /tn, NY -> /new-york
def get_canonical_slug(state_code):
    """Get canonical URL slug for a state (e.g., 'tn', 'new-york')"""
    state_name = STATE_CODE_TO_NAME.get(state_code.upper(), '')
    if not state_name:
        return state_code.lower()
    # Convert state name to slug: "New York" -> "new-york", "Tennessee" -> "tennessee"
    slug = state_name.lower().replace(' ', '-')
    return slug

# Build alias mapping: all possible inputs -> canonical slug
STATE_ALIAS_TO_SLUG = {}
for state_name_lower, state_code in STATE_NAME_TO_CODE.items():
    canonical_slug = get_canonical_slug(state_code)
    state_name = STATE_CODE_TO_NAME[state_code]
    
    # Add all aliases
    STATE_ALIAS_TO_SLUG[state_code.lower()] = canonical_slug  # 'tn' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_code.upper()] = canonical_slug  # 'TN' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_name_lower] = canonical_slug  # 'tennessee' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_name_lower.replace(' ', '-')] = canonical_slug  # 'new-york' -> 'new-york'
    STATE_ALIAS_TO_SLUG[state_name_lower.replace(' ', '')] = canonical_slug  # 'newyork' -> 'new-york'
    STATE_ALIAS_TO_SLUG[state_name] = canonical_slug  # 'Tennessee' -> 'tennessee'
    STATE_ALIAS_TO_SLUG[state_name.replace(' ', '-')] = canonical_slug  # 'New York' -> 'new-york'
    STATE_ALIAS_TO_SLUG[state_name.replace(' ', '')] = canonical_slug  # 'NewYork' -> 'new-york'

def resolve_state_slug(identifier):
    """Resolve any state identifier to canonical slug and state code"""
    identifier_clean = identifier.strip().lower()
    
    # Check direct alias mapping
    if identifier_clean in STATE_ALIAS_TO_SLUG:
        canonical_slug = STATE_ALIAS_TO_SLUG[identifier_clean]
        # Find state code from slug
        for code, name in STATE_CODE_TO_NAME.items():
            if get_canonical_slug(code) == canonical_slug:
                return canonical_slug, code
    return None, None

_STATE_AGENCY_CONTACT_CACHE = None
_STATE_AGENCY_CONTACT_AT = 0
_STATE_AGENCY_CONTACT_TTL = 300  # 5 min

def load_state_agency_contact():
    """Load state agency contact information from JSON. Cached 2 min for state page speed."""
    global _STATE_AGENCY_CONTACT_CACHE, _STATE_AGENCY_CONTACT_AT
    now = time.time()
    if _STATE_AGENCY_CONTACT_CACHE is not None and (now - _STATE_AGENCY_CONTACT_AT) < _STATE_AGENCY_CONTACT_TTL:
        return _STATE_AGENCY_CONTACT_CACHE
    contact_paths = [
        'pbj-wrapped/public/data/json/state_agency_contact.json',
        'pbj-wrapped/public/data/json/state_contact.json',
    ]
    for path in contact_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convert list to dict keyed by state_code
                    if isinstance(data, list):
                        contact_dict = {}
                        for item in data:
                            state_code = item.get('state_code', '').upper()
                            if state_code:
                                contact_dict[state_code] = item
                        out = contact_dict
                    elif isinstance(data, dict):
                        out = data
                    else:
                        out = {}
                    _STATE_AGENCY_CONTACT_CACHE = out
                    _STATE_AGENCY_CONTACT_AT = now
                    return out
            except Exception as e:
                print(f"Error loading state contact data from {path}: {e}")
                continue
    _STATE_AGENCY_CONTACT_CACHE = {}
    _STATE_AGENCY_CONTACT_AT = now
    return {}

_LOAD_CSV_CACHE = {}
_LOAD_CSV_TTL = 300  # 5 min — reduces disk I/O; data typically updated in batches

def load_csv_data(filename):
    """Load CSV data, trying multiple locations. Cached 2 min for provider/state/entity page speed.
    FALLBACKS: Tries paths in order (APP_ROOT, cwd, pbj-wrapped/public/data, pbj-wrapped/dist/data, data/).
    No alternate-filename fallbacks (e.g. no automatic _latest.csv); callers that need facility_quarterly_metrics_latest
    must call load_csv_data with that filename explicitly."""
    now = time.time()
    if filename in _LOAD_CSV_CACHE:
        cached_at, data = _LOAD_CSV_CACHE[filename]
        if now - cached_at < _LOAD_CSV_TTL:
            return data
    # Prefer APP_ROOT for known large data files so provider pages always use repo data regardless of cwd
    app_root_first = ('facility_quarterly_metrics.csv', 'facility_quarterly_metrics_latest.csv', 'provider_info_combined.csv')
    if filename in app_root_first:
        possible_paths = [
            os.path.join(APP_ROOT, filename),
            filename,
            os.path.join('pbj-wrapped', 'public', 'data', filename),
            os.path.join('pbj-wrapped', 'dist', 'data', filename),
            os.path.join('data', filename),
        ]
    else:
        possible_paths = [
            filename,
            os.path.join(APP_ROOT, filename),
            os.path.join('pbj-wrapped', 'public', 'data', filename),
            os.path.join('pbj-wrapped', 'dist', 'data', filename),
            os.path.join('data', filename),
        ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                if HAS_PANDAS:
                    out = pd.read_csv(path, low_memory=False)
                    _LOAD_CSV_CACHE[filename] = (now, out)
                    return out
                else:
                    with open(path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        out = list(reader)
                    _LOAD_CSV_CACHE[filename] = (now, out)
                    return out
            except Exception as e:
                print(f"Error loading {path}: {e}")
                continue
    return None

def get_latest_quarter(df):
    """Get the most recent quarter from a dataframe"""
    if HAS_PANDAS and isinstance(df, pd.DataFrame):
        if 'CY_Qtr' in df.columns:
            return df['CY_Qtr'].max()
    return None

_CANONICAL_QUARTER_CACHE = None
_CANONICAL_QUARTER_AT = 0
_CANONICAL_QUARTER_TTL = 300  # 5 min

def get_canonical_latest_quarter():
    """Single source of truth for 'current' quarter. Used so state, provider, and entity pages
    all show the same quarter (e.g. Q3 2025). Prefers full facility_quarterly_metrics.csv so
    we use the most recent quarter (2025Q3) when that file has it; _latest may only have through Q2."""
    global _CANONICAL_QUARTER_CACHE, _CANONICAL_QUARTER_AT
    now = time.time()
    if _CANONICAL_QUARTER_CACHE is not None and (now - _CANONICAL_QUARTER_AT) < _CANONICAL_QUARTER_TTL:
        return _CANONICAL_QUARTER_CACHE
    q = None
    state_df = load_csv_data('state_quarterly_metrics.csv')
    if state_df is not None and HAS_PANDAS and isinstance(state_df, pd.DataFrame) and 'CY_Qtr' in state_df.columns:
        q = state_df['CY_Qtr'].max()
    if q is None:
        # Prefer full file so we get 2025Q3 when present; _latest may only have through Q2 2025
        fq = load_csv_data('facility_quarterly_metrics.csv')
        if fq is None or not isinstance(fq, pd.DataFrame):
            fq = load_csv_data('facility_quarterly_metrics_latest.csv')
        if fq is not None and HAS_PANDAS and isinstance(fq, pd.DataFrame) and 'CY_Qtr' in fq.columns:
            q = fq['CY_Qtr'].max()
    _CANONICAL_QUARTER_CACHE = q
    _CANONICAL_QUARTER_AT = now
    return q

def format_quarter(quarter_str):
    """Convert quarter format from 2025Q2 to Q2 2025"""
    if not quarter_str:
        return "N/A"
    match = re.match(r'(\d{4})Q(\d)', str(quarter_str))
    if match:
        return f"Q{match.group(2)} {match.group(1)}"
    return str(quarter_str)


def _quarter_display_to_cy_qtr(quarter_display):
    """Convert provider_info 'quarter' (e.g. 'Q2 2025') to CY_Qtr form '2025Q2' for lookup."""
    if not quarter_display:
        return None
    match = re.match(r'Q(\d)\s+(\d{4})', str(quarter_display).strip())
    if match:
        return f"{match.group(2)}Q{match.group(1)}"
    return None


def format_percentile_phrase(percentile, state_name):
    """Format facility state percentile as a single phrase for narrative use.

    Caller must pass the facility's within-state percentile for the same state as state_name
    (e.g. from get_facility_state_percentile). Do not pass national or other-scope percentiles.

    Args:
        percentile: 0-100, higher = better staffing. Rounded with round-half-up to whole number.
        state_name: Full state name (e.g. 'New York') preferred; if 2-letter uppercase code is passed, normalized to full name for display.

    Returns:
        E.g. 'in the top 5% of nursing homes in New York'. No trailing punctuation.

    Band boundaries (cardinal % for extremes, ordinal for middle):
        p >= 95: top 5%
        90 <= p < 95: top 10%
        71 <= p < 90: top (100-p)%
        30 <= p <= 70: ordinal (e.g. 45th percentile)
        11 <= p < 30: bottom p%
        5 < p <= 10: bottom 10%
        p <= 5: bottom 5%
    """
    if percentile is None or state_name is None or state_name == '':
        return ''
    # Normalize 2-letter state code to full state name for consistent display
    state_display = (state_name or '').strip()
    if len(state_display) == 2 and state_display.isupper():
        state_display = STATE_CODE_TO_NAME.get(state_display, state_display)
    try:
        _p = round_half_up(float(percentile), 0)
        p = int(_p) if _p is not None else None
    except (TypeError, ValueError):
        return ''
    if p is None:
        return ''
    p = max(0, min(100, p))

    def _ordinal(n):
        n = int(n)
        if 11 <= n % 100 <= 13:
            return f'{n}th'
        return f'{n}' + ({1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th'))

    if p >= 95:
        return f'in the top 5% of nursing homes in {state_display}'
    if p >= 90:
        return f'in the top 10% of nursing homes in {state_display}'
    if p >= 71:
        top_rank = 100 - p
        return f'in the top {top_rank}% of nursing homes in {state_display}'
    if 30 <= p <= 70:
        return f'in the {_ordinal(p)} percentile of nursing homes in {state_display}'
    if p >= 11:
        return f'in the bottom {p}% of nursing homes in {state_display}'
    if p > 5:
        return f'in the bottom 10% of nursing homes in {state_display}'
    return f'in the bottom 5% of nursing homes in {state_display}'


_LOAD_PROVIDER_INFO_CACHE = None
_LOAD_PROVIDER_INFO_AT = 0
_LOAD_PROVIDER_INFO_TTL = 900  # 15 min
_LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
# Only load latest N quarters from provider_info_combined.csv; full file stays on disk for other uses.
_LATEST_PROVIDER_QUARTERS = 4

def _get_latest_quarter_values(path, n_quarters=_LATEST_PROVIDER_QUARTERS):
    """Discover the latest n_quarters distinct quarter values (CY_Qtr form) by reading only the quarter column(s)."""
    try:
        # Peek at columns
        head = pd.read_csv(path, nrows=0)
        cols = set(head.columns)
        qcol = 'CY_Qtr' if 'CY_Qtr' in cols else ('quarter' if 'quarter' in cols else None)
        if not qcol:
            return None
        # Read only quarter column in chunks to get unique values
        seen = set()
        for chunk in pd.read_csv(path, usecols=[qcol], low_memory=False, chunksize=200000):
            for v in chunk[qcol].dropna().astype(str).str.strip():
                if not v:
                    continue
                if qcol == 'CY_Qtr':
                    seen.add(v)
                else:
                    cy = _quarter_display_to_cy_qtr(v)
                    if cy:
                        seen.add(cy)
        if not seen:
            return None
        sorted_q = sorted(seen)
        return sorted_q[-n_quarters:]  # last N quarters
    except Exception:
        return None

def load_provider_info():
    """Load provider info for facility details (ownership, entity, residents, city). Loads only the latest few quarters from provider_info_combined.csv. Cached 15 min."""
    global _LOAD_PROVIDER_INFO_CACHE, _LOAD_PROVIDER_INFO_AT, _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE
    now = time.time()
    if _LOAD_PROVIDER_INFO_CACHE is not None and (now - _LOAD_PROVIDER_INFO_AT) < _LOAD_PROVIDER_INFO_TTL:
        return _LOAD_PROVIDER_INFO_CACHE
    # Prefer quarter-aligned data: provider_info_combined_latest (from extract_latest_quarter.py) has CY_Qtr/quarter.
    # NH_ProviderInfo is a single snapshot (no quarter); use only when combined/latest are not present.
    provider_paths = [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        'pbj-wrapped/public/data/provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
        'pbj-wrapped/public/data/provider_info_combined.csv',
        os.path.join(APP_ROOT, 'provider_info', 'NH_ProviderInfo_Feb2026.csv'),
        'provider_info/NH_ProviderInfo_Feb2026.csv',
        os.path.join(APP_ROOT, 'provider_info', 'NH_ProviderInfo_Jan2026.csv'),
        'provider_info/NH_ProviderInfo_Jan2026.csv',
    ]
    if not HAS_PANDAS:
        return {}
    def _row_val(r, *keys):
        for k in keys:
            if k in r:
                v = r[k]
                if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() != '':
                    return v
        return None
    def _quarter_from_row(row):
        q = row.get('CY_Qtr') or row.get('quarter')
        if q is None or (isinstance(q, float) and pd.isna(q)):
            return None
        s = str(q).strip()
        if re.match(r'^\d{4}Q[1-4]$', s):
            return s
        return _quarter_display_to_cy_qtr(s)
    for path in provider_paths:
        if not os.path.exists(path):
            continue
        try:
            # _latest or NH_ProviderInfo snapshot: one snapshot; skip quarter discovery and filtering.
            is_latest_file = (
                'provider_info_combined_latest' in path or path.replace('\\', '/').endswith('_latest.csv')
                or 'NH_ProviderInfo' in path
            )
            latest_quarters = None if is_latest_file else _get_latest_quarter_values(path, _LATEST_PROVIDER_QUARTERS)
            provider_dict = {}
            provider_dict_by_quarter = {}
            # Stream CSV in chunks and keep only rows from latest quarters
            for chunk in pd.read_csv(path, low_memory=False, chunksize=150000):
                if latest_quarters is not None:
                    # Filter to latest quarters: CY_Qtr or quarter (normalized)
                    qcol = 'CY_Qtr' if 'CY_Qtr' in chunk.columns else 'quarter'
                    if qcol not in chunk.columns:
                        continue
                    if qcol == 'CY_Qtr':
                        chunk = chunk[chunk['CY_Qtr'].astype(str).str.strip().isin(latest_quarters)]
                    else:
                        cy = chunk['quarter'].astype(str).apply(lambda v: _quarter_display_to_cy_qtr(v) if pd.notna(v) else None)
                        chunk = chunk[cy.isin(latest_quarters)]
                if chunk.empty:
                    continue
                if 'CY_Qtr' in chunk.columns:
                    chunk = chunk.sort_values('CY_Qtr', ascending=False)
                for row in chunk.to_dict('records'):
                    raw = _row_val(row, 'ccn', 'PROVNUM', 'CCN', 'Provnum', 'CMS Certification Number (CCN)')
                    provnum = str(raw or '').strip().replace('.0', '')
                    if not provnum:
                        continue
                    provnum = provnum.zfill(6)
                    eid_raw = _row_val(row, 'chain_id', 'affiliated_entity_id', 'Chain ID', 'Chain_ID', 'AFFILIATED_ENTITY_ID')
                    if eid_raw is None:
                        for col, v in row.items():
                            if col and ('chain' in str(col).lower() and 'id' in str(col).lower()) or ('affiliated' in str(col).lower() and 'entity' in str(col).lower() and 'id' in str(col).lower()):
                                if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() != '':
                                    eid_raw = v
                                    break
                    try:
                        entity_id = int(float(eid_raw)) if eid_raw is not None else None
                    except (TypeError, ValueError):
                        entity_id = None
                    _sv = _row_val(row, 'state', 'STATE', 'State')
                    state_val = (str(_sv) if _sv else '').strip().upper()[:2]
                    entity_name_val = _row_val(row, 'entity_name', 'affiliated_entity', 'Entity Name', 'chain_name', 'affiliated_entity_name', 'Chain Name')
                    if entity_name_val is None:
                        for col, v in row.items():
                            c = str(col).lower()
                            if col and (('entity' in c or 'chain' in c) and ('name' in c or c in ('affiliated_entity', 'chain_name', 'chain name'))):
                                if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() != '':
                                    entity_name_val = v
                                    break
                    row_dict = {
                        'city': _row_val(row, 'CITY', 'city', 'City') or '',
                        'ownership_type': _row_val(row, 'ownership_type', 'Ownership_Type') or '',
                        'avg_residents_per_day': row.get('avg_residents_per_day', ''),
                        'entity_name': (str(entity_name_val).strip() if entity_name_val is not None else '') or '',
                        'provider_name': _row_val(row, 'provider_name', 'PROVNAME', 'PROVNAME', 'Provider Name') or '',
                        'state': state_val.strip().upper()[:2],
                        'entity_id': entity_id,
                        'reported_total_nurse_hrs_per_resident_per_day': row.get('reported_total_nurse_hrs_per_resident_per_day'),
                        'Total_Nurse_HPRD': row.get('Total_Nurse_HPRD'),
                        'reported_rn_hrs_per_resident_per_day': row.get('reported_rn_hrs_per_resident_per_day'),
                        'reported_na_hrs_per_resident_per_day': row.get('reported_na_hrs_per_resident_per_day'),
                        'case_mix_total_nurse_hrs_per_resident_per_day': row.get('case_mix_total_nurse_hrs_per_resident_per_day'),
                        'case_mix_rn_hrs_per_resident_per_day': row.get('case_mix_rn_hrs_per_resident_per_day'),
                        'case_mix_na_hrs_per_resident_per_day': row.get('case_mix_na_hrs_per_resident_per_day'),
                        'overall_rating': row.get('overall_rating'),
                        'staffing_rating': row.get('staffing_rating'),
                    }
                    if provnum not in provider_dict:
                        provider_dict[provnum] = row_dict
                    quarter_cy = _quarter_from_row(row)
                    if quarter_cy:
                        provider_dict_by_quarter[(provnum, quarter_cy)] = row_dict
            _LOAD_PROVIDER_INFO_CACHE = provider_dict
            _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = provider_dict_by_quarter
            _LOAD_PROVIDER_INFO_AT = time.time()
            return provider_dict
        except Exception as e:
            print(f"Error loading provider info from {path}: {e}")
            continue
    return {}


def get_provider_info_for_quarter(ccn, raw_quarter):
    """Return provider info row for the given CCN and quarter (CY_Qtr form e.g. 2025Q3), or None.
    Used to show case-mix and reported HPRD for the same quarter as the facility page."""
    if not ccn or not raw_quarter:
        return None
    load_provider_info()
    if _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE is None:
        return None
    key = (str(ccn).strip().zfill(6), str(raw_quarter).strip())
    return _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE.get(key)

def get_pbj_site_layout(page_title, meta_description, canonical_url):
    """Return dict with head, nav, content_open, content_close for provider/entity/state pages. Matches index.html tone, colors, and footer."""
    base = 'https://pbj320.com'
    canon = canonical_url or base
    head = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#1e40af">
<title>{page_title}</title>
<meta name="description" content="{meta_description}">
<meta property="og:title" content="{html.escape(page_title)}">
<meta property="og:description" content="{html.escape(meta_description)}">
<meta property="og:url" content="{canon}">
<meta property="og:type" content="website">
<meta property="og:image" content="https://pbj320.com/og-image-1200x630.png">
<meta property="og:site_name" content="PBJ320">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(page_title)}">
<meta name="twitter:description" content="{html.escape(meta_description)}">
<meta name="twitter:image" content="https://pbj320.com/og-image-1200x630.png">
<link rel="canonical" href="{canon}">
<link rel="icon" type="image/png" href="/pbj_favicon.png">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NDPVY6TWBK"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', 'G-NDPVY6TWBK');
</script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; min-height: 100vh; }}
.pbj-content {{ padding: 40px 20px; max-width: 1100px; margin: 0 auto; }}
.pbj-content-box {{ background: #1e293b; border-radius: 16px; padding: 40px 48px; margin-bottom: 24px; border: 1px solid rgba(59,130,246,0.25); box-shadow: 0 4px 20px rgba(0,0,0,0.2); color: #e2e8f0; }}
.pbj-content-box h1 {{ font-size: 2rem; color: #60a5fa; margin-bottom: 0.5rem; font-weight: 700; }}
.pbj-content-box h2 {{ font-size: 1.4rem; color: #60a5fa; margin-top: 1.5rem; margin-bottom: 0.75rem; font-weight: 600; }}
.pbj-content-box p {{ color: rgba(226,232,240,0.95); margin-bottom: 0.75rem; }}
.pbj-content-box a {{ color: #60a5fa; text-decoration: none; font-weight: 500; }}
.pbj-content-box a:hover {{ color: #93c5fd; text-decoration: underline; }}
.pbj-content-box a:focus {{ outline: 2px solid #60a5fa; outline-offset: 2px; }}
.pbj-content-box table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; background: rgba(15,23,42,0.5); border-radius: 12px; overflow: hidden; border: 1px solid rgba(59,130,246,0.2); }}
.pbj-content-box th, .pbj-content-box td {{ padding: 14px 18px; text-align: left; border-bottom: 1px solid rgba(148,163,184,0.2); }}
.pbj-content-box th {{ background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; font-weight: 600; font-size: 0.9rem; }}
.pbj-content-box td {{ color: #e2e8f0; font-size: 0.95rem; }}
.pbj-content-box tr:hover td {{ background: rgba(59,130,246,0.08); }}
.pbj-content-box tr:last-child td {{ border-bottom: none; }}
.pbj-infobox {{ width: 280px; float: right; margin: 0 0 1em 1.5em; border: 1px solid rgba(59,130,246,0.3); background: rgba(15,23,42,0.6); border-radius: 8px; overflow: hidden; }}
.pbj-infobox th {{ background: rgba(30,64,175,0.4); padding: 0.5em 0.6em; font-weight: bold; border-bottom: 1px solid rgba(148,163,184,0.2); color: #e2e8f0; }}
.pbj-infobox td {{ padding: 0.5em 0.6em; border-bottom: 1px solid rgba(148,163,184,0.2); color: #e2e8f0; }}
.section-header {{ margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1.35em; font-weight: 700; color: #60a5fa; border-bottom: 2.5px solid rgba(59,130,246,0.3); padding-bottom: 4px; letter-spacing: 0.01em; }}
.section-header:first-of-type {{ margin-top: 0; }}
.pbj-subtitle {{ font-size: 0.9em; color: rgba(226,232,240,0.75); margin-top: 4px; }}
.pbj-subtitle-mobile {{ display: none; }}
.pbj-meta-line {{ font-size: 0.9em; color: rgba(226,232,240,0.7); margin-top: 6px; }}
.pbj-orientation {{ margin-bottom: 18px; font-size: 0.95rem; color: #cbd5e1; max-width: 700px; }}
.pbj-percentile, .pbj-entity-summary {{ font-size: 0.85rem; color: #94a3b8; margin-top: 6px; }}
.pbj-details {{ border: 1px solid rgba(59,130,246,0.25); border-radius: 8px; background: rgba(30,41,59,0.35); margin: 1rem 0; overflow: hidden; }}
.pbj-details summary {{ list-style: none; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; padding: 0.65rem 0.9rem; font-weight: 600; font-size: 0.95rem; color: #93c5fd; background: rgba(30,41,59,0.4); transition: background 0.15s ease; }}
.pbj-details summary::-webkit-details-marker {{ display: none; }}
.pbj-details summary:hover {{ background: rgba(59,130,246,0.12); }}
.pbj-details summary:focus {{ outline: 2px solid #60a5fa; outline-offset: -2px; }}
.pbj-details-icon {{ display: inline-block; transition: transform 0.2s ease; font-size: 0.6em; opacity: 0.9; }}
.pbj-details[open] .pbj-details-icon {{ transform: rotate(180deg); }}
.pbj-high-risk-help-wrap {{ position: relative; display: inline; }}
.pbj-high-risk-help {{ cursor: help; text-decoration: none; border-bottom: 1px dotted rgba(148,163,184,0.6); transition: border-color 0.2s ease, color 0.2s ease; }}
.pbj-high-risk-help:hover {{ border-bottom-color: rgba(147,197,253,0.9); color: #93c5fd; }}
.pbj-high-risk-tooltip {{ position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 6px; padding: 8px 12px; background: #1e293b; border: 1px solid rgba(59,130,246,0.4); border-radius: 6px; font-size: 0.8rem; line-height: 1.4; color: #e2e8f0; white-space: normal; min-width: 260px; max-width: 320px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); opacity: 0; pointer-events: none; transition: opacity 0.2s; z-index: 1000; }}
.entity-section-tooltip {{ max-width: 360px; max-height: 200px; overflow-y: auto; }}
.pbj-high-risk-help-wrap:hover .pbj-high-risk-tooltip {{ opacity: 1; }}
.pbj-details-content {{ padding: 0.9rem 1rem 1rem; border-top: 1px solid rgba(59,130,246,0.15); }}
.pbj-details-content p:first-child {{ margin-top: 0; }}
.pbj-details-content p:last-child {{ margin-bottom: 0; }}
.pbj-details-content ul {{ margin: 0.5rem 0 1rem; padding-left: 1.25rem; }}
.pbj-details-content li {{ margin-bottom: 0.25rem; }}
.pbj-metrics-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1rem 0; }}
.pbj-metric-card {{ background: rgba(15,23,42,0.6); border: 1px solid rgba(59,130,246,0.2); border-radius: 8px; padding: 1rem; color: #e2e8f0; }}
.pbj-metric-card .label {{ font-size: 0.85em; color: rgba(226,232,240,0.7); margin-bottom: 4px; }}
.pbj-metric-card .value {{ font-size: 1.25rem; font-weight: 700; color: #f8fafc; }}
.pbj-metric-card .delta {{ font-size: 0.8em; color: rgba(226,232,240,0.6); margin-top: 2px; }}
.pbj-chart-container {{ margin: 20px 0; border: 1px solid rgba(59,130,246,0.2); border-radius: 8px; padding: 20px; background: rgba(30,41,59,0.5); }}
.pbj-chart-wrapper {{ height: 260px; position: relative; width: 100%; }}
/* Provider charts: desktop = one line "Census: Facility Name"; mobile = two rows */
.pbj-chart-header-oneline {{ display: none; }}
.pbj-chart-header-twoline {{ display: block; }}
@media (min-width: 769px) {{
  .pbj-chart-header-oneline {{ display: block; }}
  .pbj-chart-header-twoline {{ display: none; }}
}}
/* State page mobile only: one-row title "Illinois Census" with section-header style */
.pbj-chart-header-state-mobile {{ display: none; }}
@media (max-width: 768px) {{
  .state-page-charts .pbj-chart-header-state-mobile {{ display: block; }}
  .state-page-charts .pbj-chart-header-twoline {{ display: none; }}
}}
/* Total Staffing chart footnote: desktop = full sentence; mobile = shorter */
.pbj-chart-footnote-mobile {{ display: none; }}
@media (max-width: 768px) {{
  .pbj-chart-footnote-desktop {{ display: none; }}
  .pbj-chart-footnote-mobile {{ display: inline; }}
}}
/* Reported vs Case-Mix notes: on mobile match state-min footnote size, each on own row */
@media (max-width: 768px) {{
  .pbj-chart-notes .pbj-percentile {{ font-size: 0.7rem; line-height: 1.35; margin: 0.2rem 0; }}
}}
.pbj-table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(59,130,246,0.2); }}
.pbj-table-wrap table {{ margin: 0; min-width: 400px; }}
/* State page H1: desktop show full only; mobile shows short only (via @media) */
.pbj-state-title .pbj-state-title-full {{ display: inline; }}
.pbj-state-title .pbj-state-title-mobile {{ display: none !important; }}
.pbj-cta-premium {{ margin-top: 1.5rem; padding: 1rem 1.25rem; background: rgba(30,64,175,0.2); border: 1px solid rgba(96,165,250,0.3); border-radius: 10px; font-size: 0.95rem; color: rgba(226,232,240,0.9); }}
.pbj-cta-premium a {{ color: #93c5fd; font-weight: 600; }}
.custom-report-cta {{ margin: 1.5rem 0; padding: 0.85rem 1.15rem; background: rgba(15,23,42,0.5); border: 1px solid rgba(59,130,246,0.2); border-radius: 8px; max-width: 640px; font-size: 0.875rem; color: rgba(226,232,240,0.9); line-height: 1.5; }}
.custom-report-cta .custom-report-cta-header {{ margin: 0; font-size: 0.9rem; font-weight: 600; color: #e2e8f0; }}
.custom-report-cta .custom-report-cta-sub {{ margin: 0.2rem 0 0.35rem 0; font-size: 1em; color: rgba(226,232,240,0.9); line-height: 1.45; }}
.custom-report-cta-mobile {{ display: none; }}
@media (max-width: 768px) {{ .custom-report-cta-desktop {{ display: none; }} .custom-report-cta-mobile {{ display: inline; }} }}
.custom-report-cta .custom-report-cta-links {{ margin: 0.3rem 0 0; font-size: 0.85rem; }}
.custom-report-cta .custom-report-cta-links a {{ color: #93c5fd; font-weight: 500; text-decoration: none; }}
.custom-report-cta .custom-report-cta-links a:hover {{ color: #bfdbfe; text-decoration: underline; text-underline-offset: 3px; }}
.custom-report-cta .custom-report-cta-dot {{ color: rgba(226,232,240,0.5); margin: 0 0.2rem; font-weight: 400; }}
.custom-report-cta .custom-report-cta-box:hover {{ background: rgba(59,130,246,0.3); color: #bfdbfe; }}
.custom-report-cta.custom-report-cta-link {{ position: relative; z-index: 1; cursor: pointer; pointer-events: auto; }}
.custom-report-cta.custom-report-cta-link:hover {{ background: rgba(59,130,246,0.15); border-color: rgba(96,165,250,0.4); }}
.custom-report-cta .custom-report-cta-footer {{ margin: 0.5rem 0 0 0; font-size: 0.75rem; color: rgba(226,232,240,0.6); }}
.pbj-care-compare-badge {{ display: inline-block; margin-top: 0.25rem; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.35); color: #93c5fd; text-decoration: none; }}
.pbj-care-compare-badge:hover {{ background: rgba(59,130,246,0.25); color: #bfdbfe; }}
.custom-report-cta .custom-report-cta-sms {{ margin-top: 0.4rem; font-size: 0.8rem; color: rgba(226,232,240,0.75); }}
.custom-report-cta .custom-report-cta-sms a {{ color: #93c5fd; font-weight: 500; text-decoration: none; }}
.custom-report-cta .custom-report-cta-sms a:hover {{ color: #bfdbfe; text-decoration: underline; text-underline-offset: 3px; }}
.navbar {{ background: #0f172a; padding: 0; position: sticky; top: 0; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.2); border-bottom: 2px solid #1e40af; }}
.nav-container {{ max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; height: 60px; }}
.nav-brand {{ display: flex; align-items: center; color: white; font-size: 1.2rem; font-weight: 700; }}
.nav-brand a {{ color: inherit; text-decoration: none; display: flex; align-items: center; }}
.nav-menu {{ display: flex; gap: 30px; align-items: center; }}
.nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; font-weight: 500; padding: 8px 0; }}
.nav-link:hover {{ color: #60a5fa; }}
.nav-toggle {{ display: none; flex-direction: column; cursor: pointer; gap: 4px; }}
.nav-toggle span {{ width: 25px; height: 3px; background: white; }}
.pbj-footer {{ text-align: center; padding: 1.25rem 1rem; margin-top: 2rem; background: #0f172a; border-top: 1px solid rgba(59,130,246,0.3); color: rgba(255,255,255,0.55); font-size: 0.8rem; }}
.pbj-footer p {{ margin: 0 0 1rem 0; color: rgba(255,255,255,0.55); }}
.pbj-footer a {{ color: #60a5fa; opacity: 0.9; transition: opacity 0.3s ease; }}
.pbj-footer a:hover {{ opacity: 1; }}
.pbj-badge-mobile-only {{ display: none !important; }}
@media (max-width: 768px) {{
  .pbj-metrics-row {{ grid-template-columns: repeat(2, 1fr); gap: 0.75rem; }}
  .pbj-content {{ padding: 20px 16px; }}
  .pbj-content-box {{ padding: 24px 20px; margin-bottom: 20px; }}
  .pbj-content-box h1 {{ font-size: 1.5rem; }}
  .pbj-content-box h2 {{ font-size: 1.2rem; }}
  .section-header {{ font-size: 1.2em; }}
  .nav-menu {{ display: none; flex-direction: column; position: absolute; top: 60px; left: 0; right: 0; background: #0f172a; padding: 1rem; gap: 12px; }}
  .nav-menu.active {{ display: flex; }}
  .nav-link {{ padding: 12px 0; min-height: 44px; display: flex; align-items: center; }}
  .nav-toggle {{ display: flex; min-width: 44px; min-height: 44px; align-items: center; justify-content: center; cursor: pointer; }}
  .nav-toggle span {{ width: 25px; height: 3px; background: white; }}
  .nav-toggle.active span:nth-child(1) {{ transform: rotate(45deg) translate(5px,5px); }}
  .nav-toggle.active span:nth-child(2) {{ opacity: 0; }}
  .nav-toggle.active span:nth-child(3) {{ transform: rotate(-45deg) translate(7px,-6px); }}
  .pbj-infobox {{ float: none; width: 100%; margin: 1rem 0; }}
  .infobox {{ float: none; width: 100%; margin: 1em 0; }}
  .state-key-metrics-row {{ grid-template-columns: repeat(2, 1fr); }}
  .pbj-metric-card .value {{ font-size: 1.1rem; }}
  /* PBJ Takeaway: on desktop larger font for entity/provider/state */
  @media (min-width: 769px) {{
    .pbj-takeaway-header {{ font-size: 1.35rem !important; }}
  }}
  /* PBJ Takeaway: on mobile show only "PBJ Takeaway", hide facility/state/entity name */
  .pbj-takeaway-title-name {{ display: none; }}
  /* On mobile hide residents, direct (HPRD), contract badges, and overall rating */
  .pbj-badge-mobile-hide {{ display: none !important; }}
  .pbj-badge-mobile-only {{ display: none !important; }}
  @media (max-width: 768px) {{
    .pbj-overall-badge {{ display: none !important; }}
    .pbj-badge-mobile-only {{ display: inline-block !important; }}
  }}
  /* High-risk tooltip: wider on mobile so it's not a thin strip; use most of viewport */
  .pbj-high-risk-tooltip {{ min-width: 260px; max-width: calc(100vw - 24px); width: max-content; padding: 12px 14px; font-size: 0.875rem; line-height: 1.45; }}
  .pbj-subtitle {{ font-size: 0.85em; }}
  /* State page subtitle on mobile: "590 providers • 97,999 residents • 3.57 HPRD (Q3 2025)" - allow wrap, smaller */
  .pbj-subtitle-state {{ font-size: 0.8em; line-height: 1.4; }}
  /* Provider page: on mobile show subtitle in two rows (row1: location • HPRD • residents; row2: For Profit • Entity) */
  .pbj-subtitle-desktop {{ display: none; }}
  .pbj-subtitle-mobile {{ display: block; }}
  .pbj-subtitle-mobile-row1, .pbj-subtitle-mobile-row2 {{ display: block; }}
  .pbj-subtitle-mobile-row2 {{ margin-top: 0.2em; }}
  /* State page H1: on mobile show short "New York PBJ Staffing" only */
  .pbj-state-title .pbj-state-title-full {{ display: none !important; }}
  .pbj-state-title .pbj-state-title-mobile {{ display: inline !important; }}
  .custom-report-cta {{ font-size: 0.825rem; padding: 0.75rem 1rem; }}
  .custom-report-cta .custom-report-cta-sub {{ font-size: 1em; }}
  .pbj-page-footer {{ margin-top: 1.5rem; padding-top: 0.4rem; }}
  .entity-chain-metrics {{ grid-template-columns: repeat(2, 1fr) !important; gap: 0.75rem !important; }}
  .pbj-chart-container {{ padding: 12px; }}
  /* Entity page: hide " – Genesis Healthcare" (etc.) in subsection headers on mobile */
  .pbj-section-header-entity-name {{ display: none !important; }}
}}
/* Contact popup (entity/state/facility pages) */
.contact-overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 10000; display: none; align-items: center; justify-content: center; padding: 1rem; box-sizing: border-box; }}
.contact-overlay[aria-hidden="false"] {{ display: flex; }}
.contact-popup {{ position: relative; background: #1e293b; border: 1px solid rgba(96,165,250,0.25); border-radius: 12px; width: 100%; max-width: 440px; max-height: calc(100vh - 2rem); overflow: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.5); -webkit-overflow-scrolling: touch; }}
.contact-popup h2 {{ margin: 0; padding: 1.25rem 1.25rem 0; font-size: 1.25rem; color: #60a5fa; }}
.contact-popup .contact-popup-close {{ position: absolute; top: 0.75rem; right: 0.75rem; width: 44px; height: 44px; padding: 0; border: none; background: transparent; cursor: pointer; font-size: 1.5rem; line-height: 1; color: rgba(148,163,184,0.9); border-radius: 8px; }}
.contact-popup .contact-popup-close:hover {{ color: #e2e8f0; background: rgba(96,165,250,0.15); }}
.contact-popup .contact-popup-close:focus-visible {{ outline: 2px solid #60a5fa; outline-offset: 2px; }}
.contact-popup-form {{ padding: 1rem 1.25rem 1.5rem; }}
.contact-popup-form .f-group {{ margin-bottom: 1rem; }}
.contact-popup-form .f-group label {{ display: block; font-weight: 500; color: #cbd5e1; margin-bottom: 0.3rem; font-size: 0.9rem; }}
.contact-popup-form .f-group input[type="text"], .contact-popup-form .f-group input[type="email"], .contact-popup-form .f-group textarea {{ width: 100%; padding: 0.6rem 0.75rem; border: 1px solid rgba(96,165,250,0.35); border-radius: 8px; font: inherit; font-size: 1rem; min-height: 44px; box-sizing: border-box; background: rgba(15,23,42,0.6); color: #e2e8f0; }}
.contact-popup-form .f-group textarea {{ min-height: 100px; resize: vertical; }}
.contact-popup-form .f-group input:focus, .contact-popup-form .f-group textarea:focus {{ outline: none; border-color: #60a5fa; box-shadow: 0 0 0 2px rgba(96,165,250,0.2); }}
.contact-popup-form .f-group input:-webkit-autofill, .contact-popup-form .f-group input:-webkit-autofill:hover, .contact-popup-form .f-group input:-webkit-autofill:focus, .contact-popup-form .f-group input:-webkit-autofill:active, .contact-popup-form .f-group textarea:-webkit-autofill, .contact-popup-form .f-group textarea:-webkit-autofill:hover, .contact-popup-form .f-group textarea:-webkit-autofill:focus, .contact-popup-form .f-group textarea:-webkit-autofill:active {{ -webkit-text-fill-color: #e2e8f0; -webkit-box-shadow: 0 0 0 1000px rgba(15,23,42,0.95) inset; box-shadow: 0 0 0 1000px rgba(15,23,42,0.95) inset; transition: background-color 5000s ease-in-out 0s; }}
.contact-popup-form .f-row-submit {{ display: flex; align-items: center; justify-content: center; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; }}
.contact-popup-form .cb-wrap {{ display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }}
.contact-popup-form .cb-wrap input {{ width: 1.25rem; height: 1.25rem; cursor: pointer; flex-shrink: 0; }}
.contact-popup-form .cb-wrap span {{ color: #cbd5e1; }}
.contact-popup-form button[type="submit"] {{ background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(96,165,250,0.5); padding: 0.7rem 1.25rem; border-radius: 8px; font: inherit; font-size: 1rem; font-weight: 500; cursor: pointer; min-height: 44px; }}
.contact-popup-form button[type="submit"]:hover {{ background: rgba(96,165,250,0.3); color: #bfdbfe; }}
.custom-report-cta .pbj-contact-trigger {{ color: #93c5fd; font-weight: 500; text-decoration: none; cursor: pointer; background: none; border: none; padding: 0; font: inherit; }}
.custom-report-cta .pbj-contact-trigger:hover {{ text-decoration: underline; }}
.custom-report-cta .pbj-contact-trigger:focus-visible {{ outline: 2px solid #60a5fa; outline-offset: 2px; }}
.contact-toast {{ position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); background: rgba(30, 41, 59, 0.95); color: #e2e8f0; padding: 0.875rem 1.5rem; border-radius: 12px; font-size: 0.9375rem; font-weight: 500; z-index: 10001; box-shadow: 0 8px 32px rgba(0,0,0,0.24); border: 1px solid rgba(148, 163, 184, 0.2); backdrop-filter: blur(8px); }}
.contact-toast.error {{ background: rgba(30, 41, 59, 0.95); color: #fca5a5; border-color: rgba(248, 113, 113, 0.25); }}
</style>
</head>
<body>'''
    nav = '''
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-brand">
        <a href="/">
          <img src="/pbj_favicon.png" alt="PBJ320" style="height: 32px; margin-right: 8px;">
          <span><span style="color: white;">PBJ</span><span style="color: #60a5fa;">320</span></span>
        </a>
      </div>
      <div class="nav-menu" id="navMenu">
        <a href="/about" class="nav-link">About</a>
        <a href="/insights" class="nav-link">Insights</a>
        <a href="/report" class="nav-link">Report</a>
        <a href="/phoebe" class="nav-link">PBJ Explained</a>
        <a href="/owners" class="nav-link">Ownership</a>
      </div>
      <div class="nav-toggle" id="navToggle" aria-label="Menu"><span></span><span></span><span></span></div>
    </div>
  </nav>'''
    content_open = '''
  <div class="pbj-content">
    <div class="pbj-content-box">'''
    content_close = '''
    </div>
  </div>
  <footer class="pbj-footer">
    <p><a href="https://www.320insight.com/" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none;font-weight:700">320 Consulting</a>: Turning Spreadsheets into Stories.</p>
    <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-top: 0.5rem;">
      <a href="#" class="pbj-contact-cta pbj-contact-trigger" role="button" title="Contact form" aria-label="Contact us"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity: 0.8;" aria-hidden="true"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#60a5fa"/></svg></a>
      <a href="sms:+19298084996" title="SMS: (929) 804-4996" aria-label="Text (929) 804-4996"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity: 0.8;" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" fill="#60a5fa"/></svg></a>
      <a href="https://www.linkedin.com/in/eric-goldwein/" target="_blank" rel="noopener" title="LinkedIn" aria-label="LinkedIn"><img src="/LI-In-Bug.png" alt="" style="width: 24px; height: 24px; object-fit: contain; opacity: 0.8;"></a>
      <a href="https://320insight.substack.com/" target="_blank" rel="noopener" title="The 320 Newsletter" aria-label="The 320 Newsletter"><img src="/substack.png" alt="" style="width: 24px; height: 24px; object-fit: contain; opacity: 0.8;"></a>
    </div>
  </footer>
  <div id="contact-overlay" class="contact-overlay" aria-hidden="true" role="presentation">
    <div class="contact-popup" role="dialog" aria-labelledby="pbj-contact-popup-title" aria-modal="true" id="contact-dialog">
      <h2 id="pbj-contact-popup-title">Request PBJ Analysis</h2>
      <button type="button" class="contact-popup-close" id="pbj-contact-popup-close" aria-label="Close">×</button>
      <form action="/contact" method="POST" class="contact-popup-form" id="pbj-contact-popup-form">
        <input type="hidden" name="csrf_token" value="__CSRF_TOKEN_PLACEHOLDER__">
        <input type="hidden" name="next" id="pbj-contact-next" value="">
        <input type="hidden" name="subject_type" id="pbj-contact-subject-type" value="">
        <div class="f-group">
          <label for="pbj-popup-name">Name <span style="color:#f87171">*</span></label>
          <input type="text" id="pbj-popup-name" name="name" required autocomplete="name" maxlength="200">
        </div>
        <div class="f-group">
          <label for="pbj-popup-email">Email <span style="color:#f87171">*</span></label>
          <input type="email" id="pbj-popup-email" name="email" required autocomplete="email">
        </div>
        <div class="f-group">
          <label for="pbj-popup-message">Message <span style="color:#f87171">*</span></label>
          <textarea id="pbj-popup-message" name="message" required placeholder="Facility or topic and your request…"></textarea>
        </div>
        <div class="f-group f-row-submit">
          <label class="cb-wrap" for="pbj-popup-press">
            <input type="checkbox" id="pbj-popup-press" name="press" value="yes" aria-label="I am media">
            <span>I am media</span>
          </label>
          <button type="submit">Send</button>
        </div>
      </form>
    </div>
  </div>
  <script src="/pbj-site-universal.js"></script>
  <script>
  (function(){ var t=document.getElementById('navToggle'); var m=document.getElementById('navMenu'); if(t&&m){ t.addEventListener('click',function(){ m.classList.toggle('active'); t.classList.toggle('active'); document.body.style.overflow=m.classList.contains('active')?'hidden':''; }); } })();
  </script>
  <script>
  (function(){
    var overlay = document.getElementById('contact-overlay');
    var dialog = document.getElementById('contact-dialog');
    var closeBtn = document.getElementById('pbj-contact-popup-close');
    var form = document.getElementById('pbj-contact-popup-form');
    var messageEl = document.getElementById('pbj-popup-message');
    if (!overlay || !dialog) return;
    function focusables() { return dialog.querySelectorAll('button, [href], input:not([disabled]), select, textarea'); }
    function openContact(topic, subjectType) {
      var nextEl = document.getElementById('pbj-contact-next');
      if (nextEl) nextEl.value = window.location.pathname + (window.location.search || '');
      var subjectEl = document.getElementById('pbj-contact-subject-type');
      if (subjectEl) subjectEl.value = subjectType || '';
      overlay.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      if (messageEl && topic) messageEl.value = topic;
      var first = form ? form.querySelector('input:not([type="hidden"]), textarea') : null;
      if (first) first.focus(); else { var list = focusables(); if (list.length) list[0].focus(); }
      document.addEventListener('keydown', trapKey);
    }
    function closeContact() {
      overlay.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      document.removeEventListener('keydown', trapKey);
      var triggers = document.querySelectorAll('.pbj-contact-trigger');
      if (triggers.length) triggers[0].focus();
    }
    function trapKey(e) {
      if (e.key !== 'Tab' && e.key !== 'Escape') return;
      if (e.key === 'Escape') { e.preventDefault(); closeContact(); return; }
      var list = focusables();
      if (list.length === 0) return;
      var first = list[0], last = list[list.length - 1];
      if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last.focus(); } }
      else { if (document.activeElement === last) { e.preventDefault(); first.focus(); } }
    }
    var nextEl = document.getElementById('pbj-contact-next');
    if (nextEl) nextEl.value = window.location.pathname + (window.location.search || '');
    document.querySelectorAll('.pbj-contact-trigger').forEach(function(btn) {
      btn.addEventListener('click', function(e) { e.preventDefault(); openContact(btn.getAttribute('data-topic') || '', btn.getAttribute('data-subject-type') || ''); });
    });
    if (closeBtn) closeBtn.addEventListener('click', closeContact);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) closeContact(); });
    if (form) form.addEventListener('submit', function() { document.body.style.overflow = ''; });
    if (new URLSearchParams(window.location.search).get('contact_sent') === '1') {
      var toast = document.createElement('div');
      toast.className = 'contact-toast';
      toast.setAttribute('role', 'status');
      toast.textContent = "Message sent. We'll be in touch.";
      document.body.appendChild(toast);
      if (history.replaceState) history.replaceState({}, '', window.location.pathname || '/');
      setTimeout(function() { toast.remove(); }, 4000);
    }
    if (new URLSearchParams(window.location.search).get('contact_error') === '1') {
      var errToast = document.createElement('div');
      errToast.className = 'contact-toast error';
      errToast.setAttribute('role', 'alert');
      errToast.textContent = "Something went wrong. Please try again or email directly.";
      document.body.appendChild(errToast);
      if (history.replaceState) history.replaceState({}, '', window.location.pathname || '/');
      setTimeout(function() { errToast.remove(); }, 6000);
    }
  })();
  </script>
</body>
</html>'''
    return {'head': head, 'nav': nav, 'content_open': content_open, 'content_close': content_close}


def render_custom_report_cta(context, page_url, **kwargs):
    """Reusable CustomReportCTA: neutral copy, request links by audience (facility, state, entity).
    context: 'facility' | 'state' | 'entity'. page_url: current page URL for email/SMS body.
    kwargs: facility_name, ccn (facility); state_name (state); entity_name (entity).
    """
    email = 'eric@320insight.com'
    contact_display = '(929) 804-4996'
    header_text = ""
    sub_text_desktop = "Request custom PBJ analysis for litigation and investigative reporting."
    sub_text_mobile = "Request custom PBJ analysis."
    footer_text = ""

    def mailto(subject, body):
        if body:
            return f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"
        return f"mailto:{email}?subject={quote(subject)}"

    if context == 'facility':
        facility_name = kwargs.get('facility_name', '') or 'This facility'
        ccn = kwargs.get('ccn', '') or ''
        topic_default = f"{facility_name} ({ccn}) staffing data." if facility_name or ccn else ""
        subj_att = f"Custom Staffing Analysis – {facility_name} (CCN {ccn})"
        body_att = f"""Hello Eric,

I'm reviewing {facility_name} (CCN {ccn}) and would like to connect regarding its staffing data.

Page reference:
{page_url}

Best,"""
        subj_media = f"Data Inquiry – {facility_name} (CCN {ccn})"
        body_media = f"""Hi Eric,

I'm looking at {facility_name} (CCN {ccn}) and would appreciate any additional context you can provide.

Page reference:
{page_url}

Thank you,"""
        subj_adv = f"Staffing Question – {facility_name} (CCN {ccn})"
        body_adv = f"""Hi Eric,

I'm reviewing staffing information for {facility_name} (CCN {ccn}) and have a few questions.

Page reference:
{page_url}

Thank you,"""
        link_att = mailto(subj_att, '')
        link_media = mailto(subj_media, '')
        link_adv = mailto(subj_adv, '')
        sms_body = f"I'm reviewing {facility_name} (CCN {ccn}) and would like to connect regarding its staffing data. {page_url}"
        sms_href = f"sms:+19298084996?body={quote(sms_body)}"
        primary_mailto = link_media
        cta_label = "Request custom analysis"
        contact_topic = topic_default

    elif context == 'state':
        state_name = kwargs.get('state_name', '') or 'this state'
        contact_topic = f"{state_name} nursing home staffing data." if state_name else ""
        subj_att = f"Custom Staffing Analysis – {state_name}"
        body_att = f"""Hello Eric,

I'm reviewing nursing home staffing data in {state_name} and would like to connect.

Page reference:
{page_url}"""
        subj_media = f"Data Inquiry – {state_name} Nursing Home Staffing"
        body_media = f"""Hi Eric,

I'm looking at nursing home staffing in {state_name} and would appreciate any context you can provide.

Page reference:
{page_url}

Thank you,"""
        subj_adv = f"Staffing Question – {state_name}"
        body_adv = f"""Hi Eric,

I'm reviewing staffing data for {state_name} and have a few questions.

Page reference:
{page_url}

Thank you,"""
        link_att = mailto(subj_att, '')
        link_media = mailto(subj_media, '')
        link_adv = mailto(subj_adv, '')
        sms_body = f"I'm reviewing nursing home staffing in {state_name} and would like to connect. {page_url}"
        sms_href = f"sms:+19298084996?body={quote(sms_body)}"
        primary_mailto = link_media
        cta_label = "Request custom analysis"

    elif context == 'entity':
        entity_name = kwargs.get('entity_name', '') or 'this entity'
        contact_topic = f"{entity_name} ownership staffing data." if entity_name else ""
        subj_att = f"Ownership-Level Staffing Analysis – {entity_name}"
        body_att = f"""Hello Eric,

I'm reviewing {entity_name} and would like to connect regarding staffing trends across its facilities.

Page reference:
{page_url}"""
        subj_media = f"Data Inquiry – {entity_name} Ownership"
        body_media = f"""Hi Eric,

I'm looking at {entity_name} and would appreciate any context on staffing across its facilities.

Page reference:
{page_url}

Thank you,"""
        subj_adv = f"Staffing Question – {entity_name}"
        body_adv = f"""Hi Eric,

I'm reviewing {entity_name} and have a few questions about its facilities.

Page reference:
{page_url}

Thank you,"""
        link_att = mailto(subj_att, '')
        link_media = mailto(subj_media, '')
        link_adv = mailto(subj_adv, '')
        sms_body = f"I'm reviewing {entity_name} and would like to connect regarding staffing. {page_url}"
        sms_href = f"sms:+19298084996?body={quote(sms_body)}"
        primary_mailto = link_media
        cta_label = "Request custom analysis"

    else:
        return ''

    # Escape topic for HTML data attribute (prefill message in contact overlay)
    topic_attr = html.escape(contact_topic).replace('"', '&quot;') if contact_topic else ''
    # Single CTA: sentence is the trigger; opens contact overlay with topic prefill (no separate "Contact us")
    link_attrs = f'href="#" class="pbj-contact-trigger" data-topic="{topic_attr}" role="button" aria-label="Open contact form to request custom PBJ analysis"'
    desktop_link = f'<a {link_attrs}><span class="custom-report-cta-desktop">{html.escape(sub_text_desktop)}</span><span class="custom-report-cta-mobile">{html.escape(sub_text_mobile)}</span></a>'
    # Desktop and mobile text shown/hidden via CSS; both in one link so one click target
    footer_block = f'<p class="custom-report-cta-footer">{footer_text}</p>' if footer_text else ''
    header_block = f'<p class="custom-report-cta-header">{header_text}</p>' if header_text else ''
    return f'''<section class="custom-report-cta" aria-label="Request custom PBJ analysis">
{header_block}
<p class="custom-report-cta-sub">{desktop_link}</p>
{footer_block}</section>'''


def render_methodology_block():
    """Return collapsible Methodology & Data Transparency block for facility, state, entity pages."""
    return '''<details class="pbj-details">
<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Methodology</summary>
<div class="pbj-details-content">
<p style="margin: 0 0 0.6rem 0; font-size: 0.9rem; color: rgba(226,232,240,0.9);">This dashboard uses CMS Payroll-Based Journal (PBJ) data (2017–2025), along with other public datasets (Provider Information, Affiliated Entity). State staffing standards via MACPAC (2022).</p>
<p style="margin: 0 0 0.35rem 0; font-weight: 600; font-size: 0.9rem; color: #93c5fd;">Metrics</p>
<ul style="font-size: 0.875rem; color: rgba(226,232,240,0.88); margin: 0 0 0.75rem 0;">
<li><strong>Hours Per Resident Day (HPRD):</strong> Total staff hours ÷ average residents. Example: 350 hours for 100 residents = 3.5 HPRD.</li>
<li><strong>Direct Care</strong> (excl. Admin, DON): Hours per resident day for direct care staff only (RN, LPN, CNA, NAtrn, MedAide), excluding administrative and supervisory roles.</li>
<li><strong>Contract Staff %:</strong> Share of hours provided by contract staff.</li>
<li><strong>Census:</strong> Average number of residents during the period.</li>
</ul>
<p style="margin: 0 0 0.75rem 0; font-size: 0.85rem; color: rgba(226,232,240,0.8);">Note: Some states set minimums (e.g., NJ, CA, NY at 3.5 HPRD); a federal 3.48 minimum was recently overturned (2025). A 2001 federal study linked 4.1 HPRD to better outcomes in that study. Staffing needs vary by resident acuity (case-mix), day, and shift. Estimates on PBJ Takeaway assume roughly 60% of staff are CNAs.</p>
<p style="margin: 0 0 0.35rem 0; font-weight: 600; font-size: 0.9rem; color: #93c5fd;">Data transparency</p>
<p style="margin: 0; font-size: 0.875rem; color: rgba(226,232,240,0.88);">The PBJ Dashboard pulls directly from CMS data and is carefully vetted for accuracy. Still, sometimes a bug sneaks into the jelly. That could mean: a systemic CMS data reporting issue (e.g., Q2 2017 contract staffing, missing data in 2020 due to COVID) or there could be a coding error on our part. If you spot something that looks off, please <a href="#" class="pbj-contact-trigger" data-topic="Data issue or possible bug (please describe what looks wrong and where)." data-subject-type="data_issue" style="color: #93c5fd;" role="button">let me know via the contact form</a> so I can set things right.</p>
</div>
</details>'''


def normalize_ccn(ccn):
    """Ensure CCN is 6-digit string (audit: zfill(6))."""
    if ccn is None or ccn == '':
        return ''
    s = str(ccn).strip()
    if '.' in s:
        s = s.split('.')[0]
    return s.zfill(6)

def capitalize_facility_name(name):
    """Capitalize facility name: first letter of each word, except small words (at, and, of, the, for, in, on, to, a, an)."""
    if not name:
        return name
    words = name.split()
    small_words = {'at', 'and', 'of', 'the', 'for', 'in', 'on', 'to', 'a', 'an'}
    capitalized = []
    for i, word in enumerate(words):
        if i == 0 or word.lower() not in small_words or (i > 0 and words[i - 1][-1] in '.,;:'):
            if '-' in word:
                parts = word.split('-')
                capitalized.append('-'.join([p.capitalize() if p else p for p in parts]))
            elif "'" in word:
                parts = word.split("'")
                capitalized.append("'".join([p.capitalize() if p else p for p in parts]))
            else:
                capitalized.append(word.capitalize())
        else:
            capitalized.append(word.lower())
    return ' '.join(capitalized)

def capitalize_city_name(city):
    """Title-case city name (e.g. CAMPBELL HALL -> Campbell Hall)."""
    if not city:
        return city
    return ' '.join([word.capitalize() for word in city.split()])

# Known acronyms to preserve in entity/chain names (e.g. "Nhs management" -> "NHS Management")
ENTITY_NAME_ACRONYMS = {'NHS', 'CMS', 'RN', 'LPN', 'CCRC', 'PBJ', 'HPRD', 'SNF', 'ALF', 'LTAC', 'ID/DD'}


def capitalize_entity_name(name):
    """Entity/chain name: title-case with known acronyms kept all-caps (e.g. NHS Management)."""
    if not name or str(name).strip() == '' or name == "—":
        return name
    s = capitalize_facility_name(str(name).strip())
    for acr in ENTITY_NAME_ACRONYMS:
        # Replace title-cased or lowercase form of acronym with canonical form (word boundary)
        s = re.sub(r'\b' + re.escape(acr.capitalize()) + r'\b', acr, s, flags=re.IGNORECASE)
        s = re.sub(r'\b' + re.escape(acr.lower()) + r'\b', acr, s)
    return s

def load_facility_quarterly_for_provider(ccn):
    """Load facility quarterly metrics for one provider (PROVNUM). Returns DataFrame or None.
    Prefers full facility_quarterly_metrics.csv so we include 2025Q3 when present; _latest may only have through Q2 2025.
    This is the source for provider page longitudinal charts (staffing, census, contract); all quarters are kept. Speed
    optimizations in load_provider_info() do not affect chart data."""
    if not HAS_PANDAS:
        return None
    prov = normalize_ccn(ccn)
    if not prov:
        return None
    df = load_csv_data('facility_quarterly_metrics.csv')
    if df is None or not isinstance(df, pd.DataFrame):
        df = load_csv_data('facility_quarterly_metrics_latest.csv')
    if df is None or not isinstance(df, pd.DataFrame):
        return None
    df = df.copy()
    df['PROVNUM'] = df['PROVNUM'].astype(str).str.strip().str.zfill(6)
    out = df[df['PROVNUM'] == prov]
    return out if not out.empty else None


def get_facility_state_percentile(ccn, state_code, quarter, facility_hprd_total, facility_hprd_rn=None):
    """Compute facility percentile within state for given quarter. Returns (pct_total, pct_rn) 0-100 or (None, None) if unavailable."""
    if not HAS_PANDAS or not state_code or not quarter or facility_hprd_total is None:
        return None, None
    prov = normalize_ccn(ccn)
    # Use same source as provider page so quarter (e.g. 2025Q3) is consistent
    df = load_csv_data('facility_quarterly_metrics.csv')
    if df is None or not isinstance(df, pd.DataFrame):
        df = load_csv_data('facility_quarterly_metrics_latest.csv')
    if df is None or not isinstance(df, pd.DataFrame) or 'PROVNUM' not in df.columns or 'STATE' not in df.columns or 'Total_Nurse_HPRD' not in df.columns:
        return None, None
    df = df.copy()
    df['PROVNUM'] = df['PROVNUM'].astype(str).str.strip().str.zfill(6)
    df['STATE'] = df['STATE'].astype(str).str.strip().str.upper()
    sub = df[(df['STATE'] == state_code.strip().upper()[:2]) & (df['CY_Qtr'].astype(str) == str(quarter))]
    if sub.empty or sub.shape[0] < 2:
        return None, None
    total_vals = sub['Total_Nurse_HPRD'].dropna()
    if total_vals.empty:
        return None, None
    n = len(total_vals)
    count_le_total = (total_vals <= facility_hprd_total).sum()
    _pt = round_half_up(100 * count_le_total / n, 0)
    pct_total = int(_pt) if _pt is not None else 0
    if pct_total > 100:
        pct_total = 100
    pct_rn = None
    if facility_hprd_rn is not None and 'RN_HPRD' in sub.columns:
        rn_vals = sub['RN_HPRD'].dropna()
        if len(rn_vals) >= 2:
            count_le_rn = (rn_vals <= facility_hprd_rn).sum()
            _pr = round_half_up(100 * count_le_rn / len(rn_vals), 0)
            pct_rn = int(_pr) if _pr is not None else None
            if pct_rn is not None and pct_rn > 100:
                pct_rn = 100
    return pct_total, pct_rn


def get_macpac_hprd_for_state(state_code):
    """Return state minimum staffing HPRD (float) for horizontal reference line, or None."""
    if not state_code:
        return None
    state_code_lower = (state_code or '').strip().upper()[:2]
    for path in ['pbj-wrapped/public/data/json/state_standards.json', 'state_standards.json']:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    s = data.get(state_code_lower) or data.get(state_code_lower.lower())
                    if s and isinstance(s, dict):
                        raw = s.get('Min_Staffing', '')
                        if raw is None:
                            continue
                        v = str(raw).replace(' HPRD', '').strip()
                        return float(v)
            except Exception:
                continue
    macpac_df = load_csv_data('macpac_state_standards_clean.csv')
    if macpac_df is not None and not macpac_df.empty and 'State_Code' in macpac_df.columns:
        row = macpac_df[macpac_df['State_Code'].str.upper().str.strip() == state_code_lower]
        if not row.empty and 'Min_Staffing' in macpac_df.columns:
            raw = row.iloc[0].get('Min_Staffing', '')
            try:
                return float(str(raw).replace(' HPRD', '').strip())
            except (TypeError, ValueError):
                pass
    return None

def _series_to_list_with_none(ser):
    """Convert pandas Series to list; use None for NaN/missing (charts: null = unknown, not zero)."""
    if ser is None or (hasattr(ser, 'empty') and ser.empty):
        return []
    return [float(x) if pd.notna(x) and x is not None else None for x in ser]


def _series_to_list_rounded(ser, decimals=2):
    """Like _series_to_list_with_none but round non-null values with round_half_up(decimals). Use for chart data that is displayed with toFixed(decimals) to avoid double-rounding errors."""
    if ser is None or (hasattr(ser, 'empty') and ser.empty):
        return []
    out = []
    for x in ser:
        if pd.isna(x) or x is None:
            out.append(None)
        else:
            r = round_half_up(float(x), decimals)
            out.append(r if r is not None else None)
    return out

def _provider_charts_chartjs_data(facility_df, state_code, reported_total, reported_rn, reported_na, case_mix_total, case_mix_rn, case_mix_na):
    """Build JSON-serializable chart data for Chart.js. Use null (None) for missing; never substitute 0."""
    out = {}
    out['reportedCaseMix'] = {
        'labels': ['Total', 'RN', 'Nurse aide'],
        'reported': [round_half_up(float(reported_total), 2) if reported_total is not None and not (isinstance(reported_total, float) and pd.isna(reported_total)) else None,
                     round_half_up(float(reported_rn), 2) if reported_rn is not None and not (isinstance(reported_rn, float) and pd.isna(reported_rn)) else None,
                     round_half_up(float(reported_na), 2) if reported_na is not None and not (isinstance(reported_na, float) and pd.isna(reported_na)) else None],
        'caseMix': None
    }
    if case_mix_total is not None or case_mix_rn is not None or case_mix_na is not None:
        out['reportedCaseMix']['caseMix'] = [
            round_half_up(float(case_mix_total), 2) if case_mix_total is not None and not (isinstance(case_mix_total, float) and pd.isna(case_mix_total)) else None,
            round_half_up(float(case_mix_rn), 2) if case_mix_rn is not None and not (isinstance(case_mix_rn, float) and pd.isna(case_mix_rn)) else None,
            round_half_up(float(case_mix_na), 2) if case_mix_na is not None and not (isinstance(case_mix_na, float) and pd.isna(case_mix_na)) else None
        ]
    if facility_df is None or facility_df.empty or not HAS_PANDAS:
        return out
    try:
        if 'CY_Qtr' not in facility_df.columns or 'Total_Nurse_HPRD' not in facility_df.columns:
            return out
        df = facility_df.sort_values('CY_Qtr').copy()
        # Normalize quarter to string (e.g. 2025Q3); some CSVs have float/int
        df['CY_Qtr'] = df['CY_Qtr'].astype(str).str.strip()
        quarters = df['CY_Qtr'].tolist()
        if not quarters:
            return out
        out['totalHprd'] = {
            'quarters': quarters,
            'total': _series_to_list_with_none(df['Total_Nurse_HPRD']),
            'direct': _series_to_list_with_none(df['Nurse_Care_HPRD'] if 'Nurse_Care_HPRD' in df.columns else pd.Series(dtype=float)),
            'macpac': get_macpac_hprd_for_state(state_code),
            'stateCode': (state_code.strip().upper()[:2] if state_code else None)
        }
        out['rnHprd'] = {
            'quarters': quarters,
            'rn': _series_to_list_with_none(df['RN_HPRD']),
            'rnDirect': _series_to_list_with_none(df['RN_Care_HPRD'] if 'RN_Care_HPRD' in df.columns else pd.Series(dtype=float))
        }
        out['contract'] = {'quarters': quarters, 'facility': _series_to_list_with_none(df['Contract_Percentage'] if 'Contract_Percentage' in df.columns else pd.Series(dtype=float)), 'stateMedian': []}
        if state_code:
            fq_df = load_csv_data('facility_quarterly_metrics.csv')
            if fq_df is None or fq_df.empty:
                fq_df = load_csv_data('facility_quarterly_metrics_latest.csv')
            if fq_df is not None and not fq_df.empty and 'STATE' in fq_df.columns and 'Contract_Percentage' in fq_df.columns and 'CY_Qtr' in fq_df.columns:
                fq_df = fq_df.copy()
                fq_df['STATE'] = fq_df['STATE'].astype(str).str.strip().str.upper()
                sc = state_code.strip().upper()[:2]
                state_fac = fq_df[fq_df['STATE'] == sc]
                if not state_fac.empty:
                    medians = state_fac.groupby('CY_Qtr')['Contract_Percentage'].median()
                    out['contract']['stateMedian'] = [round_half_up(float(medians.get(q)), 2) if q in medians.index and pd.notna(medians.get(q)) else None for q in quarters]
        col = 'avg_daily_census' if 'avg_daily_census' in df.columns else 'Avg_Daily_Census'
        out['census'] = {'quarters': quarters, 'census': _series_to_list_rounded(df[col] if col in df.columns else pd.Series(dtype=float), 1)}
    except Exception as e:
        print(f"Provider chart data build failed: {e}")
    return out

def _provider_charts_html(chart_data, facility_name='', below_reported_casemix=''):
    """Render all provider charts with Chart.js: bar (Reported vs Case-Mix) + 4 line charts. Title: metric name centered, facility name smaller below.
    below_reported_casemix: optional HTML (e.g. small line) to show below the Reported vs Case-Mix chart."""
    import json
    try:
        data_esc = json.dumps(chart_data).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    except Exception:
        data_esc = '{}'
    # Centered title: desktop = one line "Census: Facility Name"; mobile = title row + facility name row
    facility_esc = html.escape(str(facility_name)) if facility_name else ''
    facility_sub = ('<p class="pbj-chart-facility" style="text-align:center;margin:0.25rem 0 0.75rem 0;font-size:0.85rem;color:rgba(226,232,240,0.75);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + facility_esc + '</p>') if facility_esc else ''
    def chart_header(main_title):
        one_line = ('<div class="pbj-chart-header-oneline section-header" style="margin-bottom:0;">' + main_title + ': ' + facility_esc + '</div>') if facility_esc else ('<div class="pbj-chart-header-oneline section-header" style="margin-bottom:0;">' + main_title + '</div>')
        two_line = '<div class="pbj-chart-header-twoline"><div class="section-header" style="margin-bottom:0;">' + main_title + '</div>' + facility_sub + '</div>'
        return '<div class="pbj-chart-header" style="text-align:center;margin-bottom:0.25rem;">' + one_line + two_line + '</div>'
    # One bordered box per chart: title + facility name, canvas, optional footer (e.g. Total Staffing MACPAC note)
    macpac_url = 'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
    total_staffing_footer = '''<p class="pbj-chart-footnote" style="margin:0.5rem 0 0 0;font-size:0.7rem;line-height:1.35;color:rgba(226,232,240,0.65);">
<span class="pbj-chart-footnote-desktop">Direct staff excludes Admin/DON. State minimums via <a href="''' + macpac_url + '''" target="_blank" rel="noopener" style="color:#93c5fd;">MACPAC (2022)</a> may reflect calculated HPRD equivalents.</span>
<span class="pbj-chart-footnote-mobile">Direct staff excludes Admin/DON. State minimums via <a href="''' + macpac_url + '''" target="_blank" rel="noopener" style="color:#93c5fd;">MACPAC</a> may reflect calculated HPRD equivalents.</span>
</p>'''
    def chart_block(title, canvas_id, footer=''):
        out = '<div class="pbj-chart-container" style="margin-bottom:1.5rem;">' + chart_header(title) + '<div class="pbj-chart-wrapper"><canvas id="' + canvas_id + '"></canvas></div>'
        if footer:
            out += footer
        return out + '</div>'
    return '''
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><div class="pbj-chart-wrapper"><canvas id="chartReportedCaseMix"></canvas></div>
''' + (below_reported_casemix or '') + '''
</div>
''' + chart_block('Total Staffing', 'chartTotalHprd', total_staffing_footer) + '''
''' + chart_block('RN Staffing', 'chartRN') + '''
''' + chart_block('Census', 'chartCensus') + '''
''' + chart_block('Contract Staff %', 'chartContract') + '''
<script>
(function(){
  var d = ''' + data_esc + ''';
  var textColor = 'rgba(226,232,240,0.9)';
  var gridColor = 'rgba(148,163,184,0.2)';
  if (typeof Chart !== 'undefined') { Chart.defaults.color = textColor; Chart.defaults.borderColor = gridColor; }
  function quarterToDate(q) {
    var s = String(q).trim();
    if (s.length < 5) return null;
    var y = parseInt(s.substring(0,4), 10);
    var rest = (s.substring(4) || '').replace(/^Q?/i,'').trim();
    var qn = rest === '1' || rest === 'Q1' ? 1 : (rest === '2' || rest === 'Q2' ? 2 : (rest === '3' || rest === 'Q3' ? 3 : (rest === '4' || rest === 'Q4' ? 4 : 1)));
    return new Date(y, (qn - 1) * 3, 1);
  }
  function buildTimeSeriesData(quarters, values) {
    if (!quarters || !quarters.length) return [];
    var out = [];
    for (var i = 0; i < quarters.length; i++) {
      var dt = quarterToDate(quarters[i]);
      out.push({ x: dt ? dt.getTime() : null, y: i < (values && values.length) ? values[i] : null });
    }
    return out;
  }
  function getSpanYears(quarters) {
    if (!quarters || quarters.length < 2) return 1;
    var first = quarterToDate(quarters[0]);
    var last = quarterToDate(quarters[quarters.length - 1]);
    return first && last ? (last.getFullYear() - first.getFullYear()) + (last.getMonth() - first.getMonth()) / 12 : 1;
  }
  function timeTickCallback(quarters) {
    var spanYears = getSpanYears(quarters);
    var showQuarters = spanYears < 2;
    var isMobile = window.innerWidth < 768;
    return function(value) {
      var d = new Date(value);
      if (showQuarters) {
        var y = d.getFullYear();
        var q = Math.floor(d.getMonth() / 3) + 1;
        return y + ' Q' + q;
      }
      if (d.getMonth() !== 0 || d.getDate() !== 1) return '';
      var y = d.getFullYear();
      return '' + y;
    };
  }
  function makeBar(id, labels, reported, caseMix) {
    var ctx = document.getElementById(id);
    if (!ctx) return;
    var datasets = [{ label: 'Reported', data: reported, backgroundColor: '#1e40af' }];
    if (caseMix && caseMix.length) datasets.push({ label: 'Case-Mix (Acuity)', data: caseMix, backgroundColor: '#dc2626' });
    new Chart(ctx.getContext('2d'), {
      type: 'bar',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: false },
          legend: { labels: { color: textColor, boxWidth: 14, boxPadding: 3, font: { size: 11 } } },
          tooltip: {
            callbacks: {
              label: function(context) {{
                var v = context.parsed.y;
                if (typeof v === 'number' && !isNaN(v)) return context.dataset.label + ': ' + (Math.round(v * 100) / 100).toFixed(2);
                return context.dataset.label + ': ' + (v != null ? v : '');
              }}
            }
          }
        },
        scales: { y: { beginAtZero: true, ticks: { color: textColor }, grid: { color: gridColor } }, x: { ticks: { color: textColor, maxTicksLimit: 10, autoSkip: true, font: { size: 11 } }, grid: { color: gridColor } } }
      }
    });
  }
  function makeLineTime(id, quarters, datasets, yTitle, quartersRef) {
    var ctx = document.getElementById(id);
    if (!ctx || !quarters || !quarters.length) return;
    var spanYears = getSpanYears(quarters);
    var maxTicks = window.innerWidth < 768 ? Math.min(12, Math.max(6, Math.ceil(spanYears) + 1)) : Math.min(15, Math.max(6, Math.ceil(spanYears) + 2));
    var timeDatasets = datasets.map(function(ds) {
      var data = buildTimeSeriesData(quarters, ds.data);
      var out = { label: ds.label, borderColor: ds.borderColor, borderDash: ds.borderDash, tension: ds.tension !== undefined ? ds.tension : 0.3, fill: false, spanGaps: false, data: data };
      if (ds._macpacNote) out._macpacNote = true;
      return out;
    });
    var opts = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor, boxWidth: 14, boxPadding: 3, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            title: function(context) {
              if (context[0] && context[0].raw && context[0].raw.x != null) {
                var d = new Date(context[0].raw.x);
                return d.getFullYear() + ' Q' + (Math.floor(d.getMonth() / 3) + 1);
              }
              return '';
            },
            label: function(context) {{
              if (context.dataset && context.dataset._macpacNote) return context.dataset.label;
              var v = context.parsed.y;
              if (typeof v === 'number' && !isNaN(v)) return context.dataset.label + ': ' + (Math.round(v * 100) / 100).toFixed(2);
              return context.dataset.label + ': ' + (v != null ? v : '');
            }},
            afterBody: function(context) { return []; }
          }
        }
      },
      scales: {
        y: { beginAtZero: false, ticks: { color: textColor }, grid: { color: gridColor }, title: { display: !!yTitle, text: yTitle || '', color: textColor } },
        x: {
          type: 'time',
          time: { unit: 'quarter', displayFormats: { year: 'yyyy', quarter: 'yyyy Qq', month: 'MMM yyyy' }, tooltipFormat: 'yyyy Qq' },
          ticks: { color: textColor, maxTicksLimit: maxTicks, autoSkip: true, font: { size: 11 }, callback: timeTickCallback(quartersRef || quarters) },
          grid: { color: gridColor }
        }
      }
    };
    new Chart(ctx.getContext('2d'), { type: 'line', data: { datasets: timeDatasets }, options: opts });
  }
  var rc = d.reportedCaseMix;
  if (rc && rc.labels) makeBar('chartReportedCaseMix', rc.labels, rc.reported || [null, null, null], rc.caseMix);
  var th = d.totalHprd;
  if (th && th.quarters && th.quarters.length) {
    var ds = [{ label: 'Total', data: th.total, borderColor: '#1e40af', tension: 0.3, fill: false, spanGaps: false },
               { label: 'Direct', data: th.direct, borderColor: '#6366f1', borderDash: [5,5], tension: 0.3, fill: false, spanGaps: false }];
    if (th.macpac != null && typeof th.macpac === 'number') {
      var macpacArr = th.quarters.map(function(){ return th.macpac; });
      var stateMinLabel = (th.stateCode || 'State') + ' Min: ~' + (Math.round(Number(th.macpac) * 100) / 100).toFixed(2) + ' (MACPAC)';
      ds.push({ label: stateMinLabel, data: macpacArr, borderColor: '#dc2626', borderDash: [4,4], tension: 0, fill: false, spanGaps: false, _macpacNote: true });
    }
    makeLineTime('chartTotalHprd', th.quarters, ds, 'Hours per resident day', th.quarters);
  }
  var rn = d.rnHprd;
  if (rn && rn.quarters && rn.quarters.length) makeLineTime('chartRN', rn.quarters, [
    { label: 'Total RN', data: rn.rn, borderColor: '#1e40af', tension: 0.3, fill: false, spanGaps: false },
    { label: 'RN (excl. Admin/DON)', data: rn.rnDirect, borderColor: '#6366f1', borderDash: [5,5], tension: 0.3, fill: false, spanGaps: false }
  ], 'Hours per resident day', rn.quarters);
  var ce = d.census;
  if (ce && ce.quarters && ce.quarters.length) makeLineTime('chartCensus', ce.quarters, [{ label: 'Avg daily census', data: ce.census, borderColor: '#1e40af', tension: 0.3, fill: false, spanGaps: false }], 'Census', ce.quarters);
  var co = d.contract;
  if (co && co.quarters && co.quarters.length) {
    var cds = [{ label: '% Contract Staff', data: co.facility, borderColor: '#1e40af', tension: 0.3, fill: false, spanGaps: false }];
    makeLineTime('chartContract', co.quarters, cds, 'Contract %', co.quarters);
  }
})();
</script>'''

def generate_provider_page_html(ccn, facility_df, provider_info_row):
    """Generate HTML for facility (provider) page per pbj-page-guide: header block, key metrics, longitudinal chart, basic info, full table, summary."""
    try:
        from pbj_format import format_metric_value, format_quarter_display
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{round_half_up(float(v), 2):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
        format_quarter_display = format_quarter
    prov = normalize_ccn(ccn)
    facility_name = ''
    state_code = ''
    county = ''
    if provider_info_row:
        facility_name = (provider_info_row.get('provider_name') or '').strip()
        state_code = (provider_info_row.get('state') or '').strip().upper()[:2]
    if not facility_name and not facility_df.empty and 'PROVNAME' in facility_df.columns:
        facility_name = (facility_df.iloc[-1].get('PROVNAME') or '').strip()
    if not state_code and not facility_df.empty and 'STATE' in facility_df.columns:
        state_code = (str(facility_df.iloc[-1].get('STATE') or '')).strip().upper()[:2]
    if not facility_name:
        facility_name = "—"
    facility_name = capitalize_facility_name(facility_name)
    city = (provider_info_row or {}).get('city', '') or ''
    city = capitalize_city_name(city) if city else ''
    if not facility_df.empty and 'COUNTY_NAME' in facility_df.columns:
        county = (str(facility_df.iloc[0].get('COUNTY_NAME') or '')).strip() or '—'
    state_name = STATE_CODE_TO_NAME.get(state_code, state_code)
    canonical_slug = get_canonical_slug(state_code) if state_code else ''
    # Use canonical latest quarter so we match state/entity pages; only if facility has no row for it use facility's max
    canonical_q = get_canonical_latest_quarter()
    if canonical_q is not None and not facility_df.empty and 'CY_Qtr' in facility_df.columns:
        match = facility_df[facility_df['CY_Qtr'].astype(str) == str(canonical_q)]
        if not match.empty:
            latest = match.iloc[0]
            raw_quarter = canonical_q
        else:
            latest = facility_df.sort_values('CY_Qtr', ascending=False).iloc[0]
            raw_quarter = latest.get('CY_Qtr', '') if latest is not None else ''
    else:
        latest = facility_df.sort_values('CY_Qtr', ascending=False).iloc[0] if not facility_df.empty else None
        raw_quarter = latest.get('CY_Qtr', '') if latest is not None else ''
    quarter_display = format_quarter_display(raw_quarter)
    def get_val(key, default=None):
        if latest is None:
            return default
        v = latest.get(key, default)
        return default if (v is None or (isinstance(v, float) and pd.isna(v))) else v
    entity_name = (provider_info_row or {}).get('entity_name', '') or ''
    entity_name = capitalize_entity_name(entity_name) if entity_name else entity_name
    entity_id = (provider_info_row or {}).get('entity_id')
    ownership_raw = (provider_info_row or {}).get('ownership_type', '') or ''
    def abbreviate_ownership(ot):
        if not ot:
            return ''
        o = str(ot).lower().strip()
        if 'profit' in o and 'non' not in o:
            return 'For Profit'
        if 'non' in o and 'profit' in o:
            return 'Non Profit'
        if 'government' in o or 'gov' in o:
            return 'Government'
        return ot
    ownership_short = abbreviate_ownership(ownership_raw) or ''
    base_url = 'https://pbj320.com'
    state_link = f'<a href="/state/{canonical_slug}">{state_code}</a>' if (canonical_slug and state_code) else (state_code or state_name)
    # Entity link (relative); same style as other footer links (no brighter color)
    entity_link = f'<a href="/entity/{entity_id}">{html.escape(entity_name or '')}</a>' if entity_id and entity_name else (entity_name or '')
    entity_breadcrumb_link = f'<a href="/entity/{entity_id}">{html.escape(entity_name or '')}</a>' if entity_id and entity_name else ''
    # Residents count for subtitle (census_int set later; we need it here for location line)
    # Prefer provider info for the same quarter as the page so case-mix matches displayed HPRD quarter
    pi = provider_info_row or {}
    pi_quarter = get_provider_info_for_quarter(prov, raw_quarter) if raw_quarter else None
    pi_metrics = (pi_quarter or pi)
    def _safe(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    reported_total = get_val('Total_Nurse_HPRD') if get_val('Total_Nurse_HPRD') is not None else _safe(pi_metrics.get('reported_total_nurse_hrs_per_resident_per_day'))
    reported_rn = get_val('RN_HPRD') if get_val('RN_HPRD') is not None else _safe(pi_metrics.get('reported_rn_hrs_per_resident_per_day'))
    reported_na = get_val('Nurse_Assistant_HPRD') if get_val('Nurse_Assistant_HPRD') is not None else _safe(pi_metrics.get('reported_na_hrs_per_resident_per_day'))
    case_mix_total = _safe(pi_metrics.get('case_mix_total_nurse_hrs_per_resident_per_day'))
    case_mix_rn = _safe(pi_metrics.get('case_mix_rn_hrs_per_resident_per_day'))
    case_mix_na = _safe(pi_metrics.get('case_mix_na_hrs_per_resident_per_day'))
    census_num = _safe(pi_metrics.get('avg_residents_per_day'))
    if census_num is None and latest is not None:
        census_num = _safe(latest.get('avg_daily_census'))
    _c = round_half_up(census_num, 0) if census_num is not None else None
    census_int = int(_c) if _c is not None else None
    state_hprd_placeholder = '—'
    state_hprd_numeric = None
    if state_code and raw_quarter:
        try:
            state_df = load_csv_data('state_quarterly_metrics.csv')
            if state_df is not None and not state_df.empty and 'STATE' in state_df.columns and 'Total_Nurse_HPRD' in state_df.columns:
                state_df = state_df.copy()
                state_df['STATE'] = state_df['STATE'].astype(str).str.strip().str.upper()
                match = state_df[(state_df['STATE'] == state_code.strip().upper()[:2]) & (state_df['CY_Qtr'].astype(str) == str(raw_quarter))]
                if not match.empty:
                    v = match.iloc[0].get('Total_Nurse_HPRD')
                    if v is not None and not (isinstance(v, float) and pd.isna(v)):
                        state_hprd_numeric = float(v)
                        state_hprd_placeholder = format_metric_value(state_hprd_numeric, 'Total_Nurse_HPRD')
        except Exception:
            pass
    def _classify(reported, benchmark):
        if benchmark is None or benchmark == 0:
            return 'compared to'
        r, b = float(reported), float(benchmark)
        if r > b * 1.05:
            return 'above'
        if r < b * 0.95:
            return 'below'
        return 'around'
    chart_data = _provider_charts_chartjs_data(facility_df, state_code, reported_total, reported_rn, reported_na, case_mix_total, case_mix_rn, case_mix_na)
    methodology = 'Case-mix is a CMS metric based on resident acuity.'
    below_reported_casemix = ''
    note_style = 'margin-top: 0.35rem; margin-bottom: 0.5rem; font-size: 0.7rem; color: rgba(226,232,240,0.75);'
    if case_mix_total is not None and (reported_total or 0) is not None and case_mix_total > 0:
        reported_hprd_fmt = f'{round_half_up(reported_total or 0, 2):.2f}'
        casemix_hprd_fmt = f'{round_half_up(case_mix_total, 2):.2f}'
        pct_fmt = f'{100 * (reported_total or 0) / case_mix_total:.1f}'
        line1 = f'<p class="pbj-percentile" style="{note_style}">Reported HPRD ({reported_hprd_fmt}) is {pct_fmt}% of case-mix ({casemix_hprd_fmt}).</p>'
        below_reported_casemix = f'<div class="pbj-chart-notes">{line1}</div>'
    elif case_mix_total is None:
        below_reported_casemix = f'<div class="pbj-chart-notes"><p class="pbj-percentile" style="{note_style}">CMS did not report case-mix (acuity) data for this quarter. Chart shows reported staffing only.</p></div>'
    reported_vs_casemix_section = f'<div class="section-header">Reported vs. Case-Mix (Acuity)</div><p class="pbj-subtitle" style="font-style: italic; margin-bottom: 8px; font-size: 0.8rem; color: rgba(226,232,240,0.8);">{methodology}</p>'
    chart_section = _provider_charts_html(chart_data, facility_name=facility_name, below_reported_casemix=below_reported_casemix)
    hprd_val = format_metric_value(reported_total or get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')
    casemix_str = format_metric_value(case_mix_total, 'Total_Nurse_HPRD') if case_mix_total is not None else '—'
    above_below_state = _classify(reported_total or 0, None)
    above_below_casemix = _classify(reported_total or 0, case_mix_total)
    # Residents per total staff (per day): 24 hours / HPRD (e.g. 2.90 HPRD -> 24/2.9 ≈ 8.3)
    residents_per_staff = round_half_up(24 / (reported_total or 0), 1) if reported_total and reported_total > 0 else '—'
    if isinstance(residents_per_staff, (int, float)) and residents_per_staff != '—' and round_half_up(residents_per_staff, 0) == residents_per_staff:
        residents_per_staff = int(residents_per_staff)
    put_another_way = ''
    if census_int and reported_total and reported_total > 0:
        # Staff = residents * HPRD / 24 (residents per staff = 24/HPRD)
        total_staff_raw = (census_int * (reported_total or 0)) / 24
        aides_raw = (census_int * (float(reported_na or 0))) / 24
        floor_staff_raw = (30 * (reported_total or 0)) / 24
        floor_aides_raw = (30 * (float(reported_na or 0))) / 24
        _t = round_half_up(total_staff_raw, 1)
        total_staff = max(1, _t if _t is not None else total_staff_raw)
        _a = round_half_up(aides_raw, 1)
        aides = max(0, _a if _a is not None else 0)
        _f = round_half_up(floor_staff_raw, 1)
        floor_staff = max(0.1, _f if _f is not None else floor_staff_raw)
        _fa = round_half_up(floor_aides_raw, 1)
        floor_aides = max(0, _fa if _fa is not None else 0)
        put_another_way = f'On a typical <strong>30-bed floor</strong> at {facility_name} you’d see about <strong>{floor_staff:.1f}</strong> staff, including {floor_aides:.1f} nurse aides. For the entire {census_int:,}-resident facility, that’s about {total_staff:.1f} total staff, including {aides:.1f} nurse aides.'
    else:
        put_another_way = f'Staffing counts depend on census and HPRD; see key metrics above for this facility’s reported HPRD.'
    narrative = f'<strong>{facility_name}</strong> reported <strong>{hprd_val} HPRD</strong> (≈ {residents_per_staff} residents per total staff) in {quarter_display}. This level is {above_below_casemix} its case-mix (acuity) {casemix_str} HPRD.'
    if case_mix_total is None:
        narrative = f'<strong>{facility_name}</strong> reported <strong>{hprd_val} HPRD</strong> in {quarter_display}. CMS did not report case-mix data for this quarter.'
    risk_flag, risk_reason = get_facility_risk_from_search_index(prov)
    sff_facilities_list = load_sff_facilities()
    is_sff = any((str(f.get('provider_number') or '').strip().zfill(6)) == prov for f in (sff_facilities_list or []))
    if risk_flag and risk_reason:
        risk_badge_label = risk_reason
    elif risk_flag:
        risk_badge_label = 'Meets high-risk criteria'
    elif is_sff:
        risk_badge_label = 'SFF'
    else:
        risk_badge_label = ''
    risk_badge = ('<span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(220,38,38,0.25); color: #fca5a5; border: 1px solid rgba(220,38,38,0.4);">' + risk_badge_label + '</span>') if risk_badge_label else ''
    contract_pct = format_metric_value(get_val("Contract_Percentage"), "Contract_Percentage")
    direct_hprd_val = format_metric_value(get_val('Nurse_Care_HPRD'), 'Nurse_Care_HPRD')
    residents_str = f"{census_int:,} residents" if census_int else "Census not reported"
    total_direct_badge = f"Total HPRD: {hprd_val} (Direct: {direct_hprd_val})"
    # CMS star ratings (1-5): show as "Overall: ★" or "Overall: ★★★★" (number of stars only)
    def _star_icons(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "—"
        try:
            _n = round_half_up(float(val), 0)
            n = int(_n) if _n is not None else None
            if n is not None and 1 <= n <= 5:
                return "★" * n
        except (TypeError, ValueError):
            pass
        return "—"
    _overall_raw = (provider_info_row or {}).get('overall_rating')
    _staffing_raw = (provider_info_row or {}).get('staffing_rating')
    overall_star_icons = _star_icons(_overall_raw)
    staffing_star_icons = _star_icons(_staffing_raw)
    overall_star_label = f'Overall: {overall_star_icons}' if overall_star_icons != '—' else 'Overall: not reported'
    staffing_star_label = f'Staffing: {staffing_star_icons}' if staffing_star_icons != '—' else 'Staffing: not reported'
    badge_span = 'display: inline-block; padding: 3px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; background: rgba(96,165,250,0.15); color: #b8d4f0; white-space: nowrap;'
    badge_span_red = 'display: inline-block; padding: 3px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; background: rgba(220,38,38,0.25); color: #fca5a5; border: 1px solid rgba(220,38,38,0.4); white-space: nowrap;'
    # Omit separate risk badge when the only risk is 1-star overall (we show that via red Overall badge)
    _risk_reason_lower = (risk_reason or '').strip().lower()
    _skip_risk_badge = _risk_reason_lower in ('1-star overall', '1 star overall', '1-star', '1 star')
    risk_badge_conditional = risk_badge if (risk_badge and not _skip_risk_badge) else ''
    try:
        _on = round_half_up(float(_overall_raw), 0) if _overall_raw is not None else None
        is_1_star_overall = (_on is not None and int(_on) == 1)
    except (TypeError, ValueError):
        is_1_star_overall = False
    overall_badge_style = badge_span_red if is_1_star_overall else badge_span
    overall_badge_html = f'<span style="{overall_badge_style}">{overall_star_label}</span>'
    staffing_badge_html = f'<span style="{badge_span}">{staffing_star_label}</span>'
    state_percentile_total, _ = get_facility_state_percentile(prov, state_code, raw_quarter, reported_total or 0, reported_rn)
    percentile_line = ''
    state_pct_phrase = format_percentile_phrase(state_percentile_total, state_name)
    if state_pct_phrase:
        state_ratio_str = f' (state HPRD: {state_hprd_placeholder})' if state_hprd_placeholder and state_hprd_placeholder != '—' else ''
        # When case-mix is missing, the narrative is a full sentence; add percentile as a second sentence. Otherwise join with "and".
        if case_mix_total is None:
            narrative = narrative.rstrip('.') + '. It ranks ' + state_pct_phrase + state_ratio_str + '.'
        else:
            narrative = narrative.rstrip('.') + ' and ' + state_pct_phrase + state_ratio_str + '.'
    yoy_line = ''
    if facility_df is not None and not facility_df.empty and raw_quarter and reported_total is not None:
        try:
            qstr = str(raw_quarter)
            if len(qstr) >= 6 and qstr[4:6] in ('Q1', 'Q2', 'Q3', 'Q4'):
                yr = int(qstr[:4])
                prior_q = f'{yr - 1}{qstr[4:6]}'
                prior_row = facility_df[facility_df['CY_Qtr'].astype(str) == prior_q]
                if not prior_row.empty and 'Total_Nurse_HPRD' in prior_row.columns:
                    prev_hprd = prior_row.iloc[0].get('Total_Nurse_HPRD')
                    if prev_hprd is not None and not (isinstance(prev_hprd, float) and pd.isna(prev_hprd)) and float(prev_hprd) != 0:
                        prev_hprd = float(prev_hprd)
                        yoy_change = (reported_total or 0) - prev_hprd
                        yoy_pct = 100 * yoy_change / prev_hprd
                        sign = '' if yoy_change >= 0 else '−'
                        yoy_line = f'<div class="pbj-percentile">Year-over-year change (Total Nurse HPRD): {sign}{round_half_up(abs(yoy_change), 2):.2f} ({sign}{abs(yoy_pct):.0f}%)</div>'
        except Exception:
            pass
    entity_summary_html = ''
    if entity_id and entity_name:
        try:
            _ent_name, ent_facilities = load_entity_facilities(entity_id)
            if ent_facilities and len(ent_facilities) >= 1:
                state_avgs = {}
                if raw_quarter:
                    sd = load_csv_data('state_quarterly_metrics.csv')
                    if sd is not None and not sd.empty and 'STATE' in sd.columns and 'CY_Qtr' in sd.columns and 'Total_Nurse_HPRD' in sd.columns:
                        sd = sd[sd['CY_Qtr'].astype(str) == str(raw_quarter)]
                        for _, r in sd.iterrows():
                            st = (r.get('STATE') or '').strip().upper()[:2]
                            v = r.get('Total_Nurse_HPRD')
                            if st and v is not None and not (isinstance(v, float) and pd.isna(v)):
                                state_avgs[st] = float(v)
                below_count = 0
                states_seen = set()
                for fac in ent_facilities:
                    st = (fac.get('state') or '').strip().upper()[:2]
                    if st:
                        states_seen.add(st)
                    hprd = fac.get('Total_Nurse_HPRD')
                    if hprd is not None and st and st in state_avgs:
                        try:
                            if float(hprd) < state_avgs[st]:
                                below_count += 1
                        except (TypeError, ValueError):
                            pass
                state_count = len(states_seen)
                # Prefer Chain Performance (2025-11/Chain_Performance_20260218.csv) facility count when available
                chain_perf = load_chain_performance()
                chain_row_prov = chain_perf.get(int(entity_id)) if chain_perf else None
                _chain_fac = _chain_val(chain_row_prov, 'Number of facilities') if chain_row_prov else None
                try:
                    facility_count = int(float(_chain_fac)) if _chain_fac is not None else len(ent_facilities)
                except (TypeError, ValueError):
                    facility_count = len(ent_facilities)
                entity_summary_html = f'<div class="pbj-entity-summary">Part of a {facility_count}-facility network operating in {state_count} state{"s" if state_count != 1 else ""}. {below_count} facilities report staffing below their respective state ratio this quarter.</div>'
        except Exception:
            pass
    orientation_parts = []
    if state_hprd_numeric is not None and reported_total is not None:
        r, b = float(reported_total), float(state_hprd_numeric)
        if b > 0:
            ratio = r / b
            if ratio > 1.03:
                orientation_parts.append('total nurse staffing at this facility was above the state average')
            elif ratio < 0.97:
                orientation_parts.append('total nurse staffing at this facility was below the state average')
            else:
                orientation_parts.append('total nurse staffing at this facility was near the state average')
    if orientation_parts:
        orientation_parts[0] = 'In the most recent quarter, ' + orientation_parts[0] + '.'
    yoy_sentence = ''
    if facility_df is not None and not facility_df.empty and raw_quarter and reported_total is not None:
        try:
            qstr = str(raw_quarter)
            if len(qstr) >= 6 and qstr[4:6] in ('Q1', 'Q2', 'Q3', 'Q4'):
                yr = int(qstr[:4])
                prior_q = f'{yr - 1}{qstr[4:6]}'
                prior_row = facility_df[facility_df['CY_Qtr'].astype(str) == prior_q]
                if not prior_row.empty and 'Total_Nurse_HPRD' in prior_row.columns:
                    prev_hprd = prior_row.iloc[0].get('Total_Nurse_HPRD')
                    if prev_hprd is not None and not (isinstance(prev_hprd, float) and pd.isna(prev_hprd)) and float(prev_hprd) != 0:
                        prev_hprd = float(prev_hprd)
                        yoy_change = (reported_total or 0) - prev_hprd
                        yoy_pct = 100 * yoy_change / prev_hprd
                        if yoy_change > 0:
                            yoy_sentence = f' Compared to the same quarter last year, staffing has increased by {abs(yoy_pct):.0f}%.'
                        elif yoy_change < 0:
                            yoy_sentence = f' Compared to the same quarter last year, staffing has declined by {abs(yoy_pct):.0f}%.'
                        else:
                            yoy_sentence = ' Compared to the same quarter last year, staffing is unchanged.'
        except Exception:
            pass
    if orientation_parts:
        orientation_summary = orientation_parts[0] + yoy_sentence
    elif yoy_sentence:
        orientation_summary = yoy_sentence.strip()
    else:
        orientation_summary = ''
    entity_link_bottom = ''
    pbj_takeaway_card = f'''
<div id="pbj-takeaway" class="pbj-content-box" style="margin: 1rem 0; padding: 1rem; border: 1px solid rgba(59,130,246,0.3); border-radius: 8px;">
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(96,165,250,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-header" style="font-size: 16px; font-weight: bold; color: #e2e8f0;">PBJ Takeaway<span class="pbj-takeaway-title-name">: {html.escape(facility_name)}</span></div>
</div>
<div class="pbj-takeaway-badges" style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0.5rem 0 0.4rem 0;">{risk_badge_conditional}<span class="pbj-badge-mobile-only" style="{badge_span}">Total HPRD: {hprd_val}</span><span class="pbj-badge-mobile-hide" style="{badge_span}">{total_direct_badge}</span><span class="pbj-badge-mobile-hide" style="{badge_span}">{residents_str}</span>{staffing_badge_html}<span class="pbj-overall-badge">{overall_badge_html}</span></div>
{percentile_line}
<p class="pbj-takeaway-narrative" style="margin: 0.5rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{narrative}</p>
<p class="pbj-takeaway-put-another-way" style="margin: 0.5rem 0 0 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.9);"><strong>Put another way…</strong> {put_another_way}</p>
<div style="margin-top: 0.35rem; margin-bottom: 0.15rem; display: flex; justify-content: flex-end;"><span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(96,165,250,0.4);">320 Consulting</span></div>
</div>'''
    seo_desc = f"{facility_name} nursing home staffing: {format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')} HPRD total nurse staffing in {quarter_display}."
    page_title = f"{facility_name} | Nursing Home Staffing | PBJ320"
    layout = get_pbj_site_layout(page_title, seo_desc, f"{base_url}/provider/{prov}")
    facility_page_url = f"{base_url}/provider/{prov}"
    care_compare_facility_url = f'https://www.medicare.gov/care-compare/details/nursing-home/{prov}/view-all/?state={state_code}' if state_code else ''
    custom_report_cta_html = render_custom_report_cta('facility', facility_page_url, facility_name=facility_name, ccn=prov, state_name=state_name, entity_name=entity_name or '')
    _residents_sub = f"{census_int:,} residents" if census_int else "Census not reported"
    # City, ST as one part (e.g. "Brooklyn, NY" with state linked)
    if city and state_link:
        _city_state = f'{city}, {state_link}'
    elif city:
        _city_state = city
    elif state_link:
        _city_state = state_link
    else:
        _city_state = ''
    # Desktop subtitle order: Brooklyn, NY • 2.90 HPRD • 351 residents • For Profit • Entity: ...
    _loc_parts = []
    if _city_state.strip():
        _loc_parts.append(_city_state)
    _loc_parts.append(f'{hprd_val} HPRD')
    _loc_parts.append(_residents_sub)
    if ownership_short and ownership_short.strip():
        _loc_parts.append(ownership_short)
    _loc_sub = ' &bull; '.join(_loc_parts) if _loc_parts else _residents_sub
    subtitle_one_line = _loc_sub + (f' &bull; Entity: {entity_link}' if (entity_id and entity_name) else '')
    # Mobile subtitle: row 1 = Brooklyn, NY • 2.90 HPRD • 351 residents; row 2 = For Profit • Entity link (no bullet after residents)
    _row1_parts = []
    if _city_state.strip():
        _row1_parts.append(_city_state)
    _row1_parts.append(f'{hprd_val} HPRD')
    _row1_parts.append(_residents_sub)
    _row1 = ' &bull; '.join(_row1_parts) if _row1_parts else _residents_sub
    _row2_parts = []
    if ownership_short and ownership_short.strip():
        _row2_parts.append(ownership_short)
    if entity_id and entity_name:
        _row2_parts.append(entity_link)
    _row2 = ' &bull; '.join(_row2_parts) if _row2_parts else ''
    if _row2:
        subtitle_mobile = f'<span class="pbj-subtitle-mobile-row1">{_row1}</span><span class="pbj-subtitle-mobile-row2">{_row2}</span>'
    else:
        subtitle_mobile = f'<span class="pbj-subtitle-mobile-row1">{_row1}</span>'
    inner = f"""
<h1>{facility_name}</h1>
<p class="pbj-subtitle"><span class="pbj-subtitle-desktop">{subtitle_one_line}</span><span class="pbj-subtitle-mobile">{subtitle_mobile}</span></p>

{pbj_takeaway_card}

{reported_vs_casemix_section}

{chart_section}

{custom_report_cta_html}

{render_methodology_block()}

<div class="pbj-page-footer" style="margin-top: 1.75rem; padding-top: 0.5rem; border-top: 1px solid rgba(59,130,246,0.15);">
<p style="margin: 0 0 0.4rem 0; font-size: 0.875rem; color: rgba(226,232,240,0.85); line-height: 1.5;"><a href="/">Home</a> &middot; <a href="/state/{canonical_slug}">{state_name}</a>{' &middot; ' + entity_breadcrumb_link if entity_breadcrumb_link else ''}</p>
<p style="margin: 0 0 0.35rem 0; font-size: 0.8rem; color: rgba(226,232,240,0.6); line-height: 1.45;">Source: CMS Payroll-Based Journal (PBJ) data.</p>
""" + (f'<p style="margin: 0.25rem 0 0 0;"><a href="{care_compare_facility_url}" target="_blank" rel="noopener" class="pbj-care-compare-badge">View on Care Compare</a></p>' if care_compare_facility_url else '') + """
</div>"""
    html_content = layout['head'] + layout['nav'] + layout['content_open'] + inner + layout['content_close']
    if HAS_CSRF and generate_csrf:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', generate_csrf())
    else:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', '')
    return html_content

_PROVIDER_INFO_ENTITY_CACHE = None
_PROVIDER_INFO_ENTITY_AT = 0
_PROVIDER_INFO_ENTITY_TTL = 300  # 5 min — avoid re-reading full CSV on every entity request

def load_entity_facilities(entity_id):
    """Load entity name and list of facilities (ccn, name, city, state, latest metrics) for chain_id/affiliated_entity_id.
    Returns (entity_name, list of dicts). Empty list if not found. Tries both chain_id and affiliated_entity_id when both exist.
    Caches provider_info DataFrame for 5 min to speed entity page loads."""
    global _PROVIDER_INFO_ENTITY_CACHE, _PROVIDER_INFO_ENTITY_AT
    if not HAS_PANDAS:
        return '', []
    # Prefer quarter-aligned data (provider_info_combined_latest has CY_Qtr/quarter). NH_ProviderInfo is fallback (no quarter).
    paths = [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        'pbj-wrapped/public/data/provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
        'pbj-wrapped/public/data/provider_info_combined.csv',
        os.path.join(APP_ROOT, 'provider_info', 'NH_ProviderInfo_Feb2026.csv'),
        'provider_info/NH_ProviderInfo_Feb2026.csv',
        os.path.join(APP_ROOT, 'provider_info', 'NH_ProviderInfo_Jan2026.csv'),
        'provider_info/NH_ProviderInfo_Jan2026.csv',
    ]
    now = time.time()
    df = None
    used_path = None
    for path in paths:
        if not os.path.exists(path):
            continue
        used_path = path
        if _PROVIDER_INFO_ENTITY_CACHE is not None and (now - _PROVIDER_INFO_ENTITY_AT) < _PROVIDER_INFO_ENTITY_TTL and _PROVIDER_INFO_ENTITY_CACHE.get('_path') == path:
            df = _PROVIDER_INFO_ENTITY_CACHE.get('_df')
            break
        try:
            df = pd.read_csv(path, low_memory=False)
            _PROVIDER_INFO_ENTITY_CACHE = {'_df': df, '_path': path}
            _PROVIDER_INFO_ENTITY_AT = now
            break
        except Exception as e:
            print(f"Error loading provider_info from {path}: {e}")
            continue
    if df is None and used_path:
        try:
            df = pd.read_csv(used_path, low_memory=False)
            _PROVIDER_INFO_ENTITY_CACHE = {'_df': df, '_path': used_path}
            _PROVIDER_INFO_ENTITY_AT = time.time()
        except Exception as e:
            print(f"Error loading entity {entity_id} from {used_path}: {e}")
            return '', []
    if df is None:
        return '', []
    try:
        df = df.copy()
        # Normalize CMS NH_ProviderInfo column names to combined format so entity logic works
        if 'Chain ID' in df.columns and 'chain_id' not in df.columns:
            rename = {
                'CMS Certification Number (CCN)': 'ccn',
                'Provider Name': 'provider_name',
                'Chain ID': 'chain_id',
                'Chain Name': 'chain_name',
                'State': 'state',
                'City/Town': 'city',
            }
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
            if 'chain_id' in df.columns and 'affiliated_entity_id' not in df.columns:
                df['affiliated_entity_id'] = df['chain_id']
        if 'ccn' not in df.columns and 'CMS Certification Number (CCN)' in df.columns:
            df['ccn'] = df['CMS Certification Number (CCN)'].astype(str).str.strip()
        if 'provider_name' not in df.columns and 'Provider Name' in df.columns:
            df['provider_name'] = df['Provider Name']
        eid_col = 'chain_id' if 'chain_id' in df.columns else 'affiliated_entity_id'
        name_col = 'chain_name' if 'chain_id' in df.columns else 'affiliated_entity_name'
        if eid_col not in df.columns:
            return '', []
        df[eid_col] = pd.to_numeric(df[eid_col], errors='coerce')
        # When both columns exist, match entity_id in either (same chain can appear as either)
        if 'chain_id' in df.columns and 'affiliated_entity_id' in df.columns:
            df['affiliated_entity_id'] = pd.to_numeric(df['affiliated_entity_id'], errors='coerce')
            sub = df[(df['chain_id'] == int(entity_id)) | (df['affiliated_entity_id'] == int(entity_id))]
            if not sub.empty and name_col in sub.columns:
                entity_name_from_chain = (sub['chain_name'].iloc[0] if 'chain_name' in sub.columns else '') or ''
                entity_name_from_aff = (sub['affiliated_entity_name'].iloc[0] if 'affiliated_entity_name' in sub.columns else '') or ''
                name_col = 'chain_name' if (entity_name_from_chain and str(entity_name_from_chain).strip() != '') else 'affiliated_entity_name'
        else:
            sub = df[df[eid_col] == int(entity_id)]
        if sub.empty:
            return '', []
        entity_name = (sub[name_col].iloc[0] if name_col in sub.columns else '') or "—"
        entity_name = str(entity_name).strip() if entity_name else "—"
        entity_name = capitalize_entity_name(entity_name) if entity_name and entity_name != "—" else entity_name
        # One row per CCN (latest by processing_date or CY_Qtr if present)
        ccn_col = 'ccn' if 'ccn' in sub.columns else 'PROVNUM'
        if 'processing_date' in sub.columns:
            sub = sub.sort_values('processing_date', ascending=False)
        elif 'CY_Qtr' in sub.columns:
            sub = sub.sort_values('CY_Qtr', ascending=False)
        by_ccn = {}
        for _, row in sub.iterrows():
            c = str(row.get(ccn_col, '')).strip()
            if '.' in c:
                c = c.split('.')[0]
            c = c.zfill(6)
            if c and c not in by_ccn:
                _n = (row.get('provider_name', row.get('PROVNAME', '')) or '')
                _city = (row.get('city', row.get('CITY', '')) or '')
                _st = (row.get('state', row.get('STATE', '')) or '')
                by_ccn[c] = {
                    'ccn': c,
                    'name': str(_n).strip(),
                    'city': str(_city).strip(),
                    'state': str(_st).strip().upper()[:2],
                }
        facilities = list(by_ccn.values())
        if not facilities:
            return '', []
        # Attach latest-quarter metrics from facility_quarterly_metrics (same quarter as state/provider pages)
        fq = load_csv_data('facility_quarterly_metrics.csv')
        if fq is not None and isinstance(fq, pd.DataFrame) and 'PROVNUM' in fq.columns:
            fq = fq.copy()
            fq['PROVNUM'] = fq['PROVNUM'].astype(str).str.strip().str.zfill(6)
            latest_q = get_canonical_latest_quarter()
            if latest_q is None and 'CY_Qtr' in fq.columns:
                latest_q = fq['CY_Qtr'].max()
            if latest_q:
                # Normalize quarter to str so CSV string/int don't mismatch
                fq_latest = fq[fq['CY_Qtr'].astype(str) == str(latest_q)]
                census_col = 'avg_daily_census' if 'avg_daily_census' in fq_latest.columns else 'Avg_Daily_Census'
                for fac in facilities:
                    row = fq_latest[fq_latest['PROVNUM'] == fac['ccn']]
                    if not row.empty:
                        r = row.iloc[0]
                        fac['Total_Nurse_HPRD'] = r.get('Total_Nurse_HPRD')
                        fac['RN_HPRD'] = r.get('RN_HPRD')
                        fac['Contract_Percentage'] = r.get('Contract_Percentage')
                        if census_col in fq_latest.columns:
                            fac['avg_daily_census'] = r.get(census_col)
                        fac['quarter'] = latest_q
        return entity_name, facilities
    except Exception as e:
        print(f"Error loading entity {entity_id}: {e}")
        return '', []

_CHAIN_PERF_CACHE = None
_CHAIN_PERF_AT = 0
_CHAIN_PERF_TTL = 300  # 5 min

def load_chain_performance():
    """Load chain/entity performance data from CMS Chain Performance CSV.
    Prefers 2025-11/Chain_Performance_20260218.csv (canonical; commit to git). Used for entity PBJ takeaway and key metrics.
    Returns dict mapping entity_id (int) -> row dict with keys matching CSV columns (strip-spaced)."""
    global _CHAIN_PERF_CACHE, _CHAIN_PERF_AT, _CHAIN_PERF_TTL
    now = time.time()
    if _CHAIN_PERF_CACHE is not None and (now - _CHAIN_PERF_AT) < _CHAIN_PERF_TTL:
        return _CHAIN_PERF_CACHE
    if not HAS_PANDAS:
        return {}
    import glob
    # Prefer the canonical Chain Performance file (track in git: 2025-11/Chain_Performance_20260218.csv)
    canonical_path = os.path.join(APP_ROOT, '2025-11', 'Chain_Performance_20260218.csv')
    paths = []
    if os.path.isfile(canonical_path):
        paths.append(canonical_path)
    for g in [
        os.path.join(APP_ROOT, '2025-11', 'Chain_Performance_*.csv'),
        os.path.join(APP_ROOT, 'chain_performance.csv'),
        os.path.join(APP_ROOT, '2025-11', 'Chain*.csv'),
    ]:
        paths.extend(glob.glob(g))
    seen = set()
    paths = [p for p in paths if p not in seen and not seen.add(p)]
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_csv(path, low_memory=False)
            df.columns = [str(c).strip() for c in df.columns]
            if 'Chain ID' not in df.columns:
                continue
            out = {}
            for _, row in df.iterrows():
                eid = row.get('Chain ID')
                if pd.isna(eid) or eid == '' or str(eid).strip() == '':
                    continue
                try:
                    eid_int = int(float(eid))
                except (TypeError, ValueError):
                    continue
                out[eid_int] = row.to_dict()
            _CHAIN_PERF_CACHE = out
            _CHAIN_PERF_AT = now
            return out
        except Exception as e:
            print(f"Error loading chain performance from {path}: {e}")
            continue
    return {}

def _chain_val(row, *keys, default=None):
    """Get value from chain row trying multiple column names; return default if missing/invalid."""
    if row is None:
        return default
    for k in keys:
        if k in row:
            v = row[k]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                return v
    return default

def _star_display(val):
    """Format 1–5 rating as star string (number of stars only, e.g. ★★★★). Returns '—' if missing."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        _f = round_half_up(float(val), 0)
        full = min(5, max(0, int(_f))) if _f is not None else 0
        return "★" * full if full else "—"
    except (TypeError, ValueError):
        return "—"

def generate_entity_page_html(entity_id, entity_name, facilities, chain_row=None):
    """Generate HTML for entity (chain) page. facilities: list of dicts with ccn, name, city, state, optional metrics.
    If chain_row is provided (from load_chain_performance), show chain-level metrics, ownership pie, high-risk, and CMS star breakdown.
    Ownership page uses a PBJ Takeaway: Tier 1 (scope), Tier 2 (risk, conditional), Tier 3 (operational), plus 3 narrative paragraphs."""
    entity_name = capitalize_entity_name(entity_name) if entity_name else entity_name
    try:
        from pbj_format import format_metric_value, get_metric_label
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{round_half_up(float(v), 2):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
        get_metric_label = lambda k: k.replace('_', ' ')
    base_url = 'https://pbj320.com'
    n = len(facilities)
    subtitle = f"{n} nursing home{'s' if n != 1 else ''}"

    # Chain-level metrics from latest quarter (aggregate across facilities)
    states_set = set()
    total_hprd_vals = []
    rn_hprd_vals = []
    contract_vals = []
    total_residents = 0
    quarter_display = ''
    raw_quarter = None
    for fac in facilities:
        st = (fac.get('state') or '').strip().upper()[:2]
        if st:
            states_set.add(st)
        tn = fac.get('Total_Nurse_HPRD')
        if tn is not None and not (isinstance(tn, float) and pd.isna(tn)):
            total_hprd_vals.append(float(tn))
        rn = fac.get('RN_HPRD')
        if rn is not None and not (isinstance(rn, float) and pd.isna(rn)):
            rn_hprd_vals.append(float(rn))
        c = fac.get('Contract_Percentage')
        if c is not None and not (isinstance(c, float) and pd.isna(c)):
            contract_vals.append(float(c))
        census = fac.get('avg_daily_census')
        if census is not None and not (isinstance(census, float) and pd.isna(census)):
            try:
                _c = round_half_up(float(census), 0)
                total_residents += int(_c) if _c is not None else 0
            except (TypeError, ValueError):
                pass
        if not quarter_display and fac.get('quarter'):
            raw_q = fac['quarter']
            raw_quarter = raw_q
            match = re.match(r'(\d{4})Q(\d)', str(raw_q))
            quarter_display = f"Q{match.group(2)} {match.group(1)}" if match else str(raw_q)
    num_states = len(states_set)
    avg_total = sum(total_hprd_vals) / len(total_hprd_vals) if total_hprd_vals else None
    avg_rn = sum(rn_hprd_vals) / len(rn_hprd_vals) if rn_hprd_vals else None
    avg_contract = sum(contract_vals) / len(contract_vals) if contract_vals else None
    chain_metrics_html = ''
    ownership_pie_html = ''
    high_risk_html = ''
    cms_stars_html = ''
    delta_fmt = '<span class="entity-delta" style="font-size:0.8em;color:rgba(226,232,240,0.6);">—</span>'
    # Always show a PBJ Takeaway when we have facilities (short version first; overwrite with full when chain_row)
    pbj_takeaway_ownership = ''
    if n > 0:
        _b = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(30,64,175,0.25);color:#93c5fd;border:1px solid rgba(59,130,246,0.3);'
        _scope = f'<span style="{_b}">{n:,} Facilities</span><span style="{_b}">{num_states} States</span>'
        if avg_total is not None:
            _scope += f'<span style="{_b}">Avg Total HPRD: {format_metric_value(avg_total, "Total_Nurse_HPRD")}</span>'
        _entity_esc = html.escape(entity_name or "This chain")
        _p_ops = f"<strong>{_entity_esc}</strong> operates <strong>{n:,}</strong> nursing home{'s' if n != 1 else ''} across <strong>{num_states}</strong> state{'s' if num_states != 1 else ''}."
        _p_value = ""
        if avg_total is not None:
            _p_value = f" Average total nurse HPRD this quarter: <strong>{format_metric_value(avg_total, 'Total_Nurse_HPRD')}</strong>."
        pbj_takeaway_ownership = f'''
<div id="pbj-takeaway" class="pbj-content-box" style="margin: 1rem 0; padding: 1rem; border: 1px solid rgba(59,130,246,0.3); border-radius: 8px;">
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(96,165,250,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-header" style="font-size: 16px; font-weight: bold; color: #e2e8f0;">PBJ Takeaway<span class="pbj-takeaway-title-name">: {html.escape(entity_name or "Chain")}</span></div>
</div>
<p style="margin: 0.5rem 0 0.25rem 0;">{_scope}</p>
<p style="margin: 0.5rem 0 0; font-size: 0.95rem; color: rgba(226,232,240,0.95);">{_p_ops}{_p_value}</p>
<div style="margin-top: 0.35rem; display: flex; justify-content: flex-end;"><span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(59,130,246,0.4);">320 Consulting</span></div>
</div>'''
    if chain_row:
        def _f(v, default='—'):
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return default
            return v
        def _num(k, *keys):
            v = _chain_val(chain_row, k, *keys)
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        n_chain = _num('Number of facilities')
        states_chain = _num('Number of states and territories with operations')
        overall_rating = _num('Average overall 5-star rating')
        fines_dollars = _num('Total amount of fines in dollars')
        sff = _num('Number of Special Focus Facilities (SFF)')
        sff_cand = _num('Number of SFF candidates')
        abuse_count = _num('Number of facilities with an abuse icon')
        abuse_pct = _num('Percentage of facilities with an abuse icon')
        for_profit = _num('Percent of facilities classified as for-profit')
        non_profit = _num('Percent of facilities classified as non-profit')
        govt = _num('Percent of facilities classified as government-owned')
        hi_rating = _num('Average health inspection rating')
        staff_rating = _num('Average staffing rating')
        quality_rating = _num('Average quality rating')
        chain_hprd_total = _num('Average total nurse hours per resident day')
        chain_hprd_rn = _num('Average total Registered Nurse hours per resident day')
        turnover_pct = _num('Average total nursing staff turnover percentage')
        payment_denials = _num('Total number of payment denials')
        total_fines_count = _num('Total number of fines')
        # Prefer Chain Performance (CMS) facility count when available; else use PBJ facility list length
        n_fac = int(n_chain) if n_chain is not None else (n if n else 0)
        n_st = num_states if num_states else (int(states_chain) if states_chain is not None else 0)
        # Use chain CSV HPRD if present, else PBJ aggregate
        hprd_for_narrative = chain_hprd_total if chain_hprd_total is not None else avg_total
        rn_for_narrative = chain_hprd_rn if chain_hprd_rn is not None else avg_rn
        national_hprd = get_national_hprd_for_quarter(raw_quarter) if raw_quarter else None
        # High-risk % from same logic as search_index (SFF, 1-star, abuse icon, etc.)
        n_high_risk = 0
        for fac in facilities:
            ccn_f = fac.get('ccn')
            r, _ = get_facility_risk_from_search_index(ccn_f) if ccn_f else (0, '')
            if r:
                n_high_risk += 1
        _ph = round_half_up(100 * n_high_risk / n_fac, 0) if n_fac else None
        pct_high_risk = int(_ph) if _ph is not None else 0

        # ——— PBJ Takeaway: Ownership (structural, portfolio pattern) ———
        _badge = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(30,64,175,0.25);color:#93c5fd;border:1px solid rgba(59,130,246,0.3);'
        _badge_risk = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(245,158,11,0.2);color:#fcd34d;border:1px solid rgba(245,158,11,0.4);'
        _badge_severe = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(220,38,38,0.2);color:#fca5a5;border:1px solid rgba(220,38,38,0.4);'
        _badge_neutral = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(100,116,139,0.2);color:#94a3b8;border:1px solid rgba(100,116,139,0.3);'
        _fp = round_half_up(for_profit, 0) if for_profit is not None else None
        fp_pct = int(_fp) if _fp is not None else None
        tier1_badges = f'<span style="{_badge}">{n_fac:,} Facilities</span><span style="{_badge}">{n_st} States</span>'
        if fp_pct is not None:
            tier1_badges += f'<span style="{_badge}">{fp_pct}% For-Profit</span>'
        tier1_badges += f'<span style="{_badge}">Avg. Staffing: {(f"{staff_rating:.1f}" if staff_rating is not None else "—")}</span><span class="pbj-overall-badge" style="{_badge}">Avg. Rating: {(f"{overall_rating:.1f}" if overall_rating is not None else "—")}</span>'

        risk_parts = []
        if sff is not None and sff > 0:
            risk_parts.append(('SFF: ' + str(int(sff)), _badge_severe if sff >= 3 else _badge_risk))
        if sff_cand is not None and sff_cand > 0:
            risk_parts.append(('SFF Candidates: ' + str(int(sff_cand)), _badge_risk))
        if abuse_pct is not None and abuse_pct > 0:
            risk_parts.append((f'Abuse icon: {abuse_pct:.0f}% of facilities', _badge_risk if abuse_pct > 10 else _badge_neutral))
        if fines_dollars is not None and fines_dollars > 0:
            fines_label = f'${fines_dollars/1e6:.1f}M fines' if fines_dollars >= 1e6 else f'${fines_dollars:,.0f} fines'
            risk_parts.append((fines_label, _badge_severe if fines_dollars >= 5e6 else _badge_risk))
        if payment_denials is not None and payment_denials > 0:
            risk_parts.append(('Payment denials: ' + str(int(payment_denials)), _badge_risk))
        tier2_html = ''.join(f'<span style="{style}">{text}</span>' for text, style in risk_parts) if risk_parts else ''

        tier3_parts = []
        if hprd_for_narrative is not None:
            tier3_parts.append(f'Avg Total Nurse HPRD: {format_metric_value(hprd_for_narrative, "Total_Nurse_HPRD")}')
        if rn_for_narrative is not None:
            tier3_parts.append(f'Avg RN HPRD: {format_metric_value(rn_for_narrative, "RN_HPRD")}')
        tier3_parts.append(f'Avg. Staffing rating: {(f"{staff_rating:.1f}" if staff_rating is not None else "—")}')
        tier3_html = ''.join(f'<span style="{_badge_neutral}">{t}</span>' for t in tier3_parts)

        # Paragraph 1 — Scale & Model (neutral)
        chain_esc = html.escape(entity_name or 'This chain')
        p1_simple = f"<strong>{chain_esc}</strong> operates <strong>{n_fac:,}</strong> nursing home{'s' if n_fac != 1 else ''} across <strong>{n_st}</strong> state{'s' if n_st != 1 else ''}"
        if fp_pct is not None:
            if fp_pct == 100:
                p1_simple += ", all classified as for-profit. "
            else:
                p1_simple += f", with <strong>{fp_pct}%</strong> classified as for-profit. "
        else:
            p1_simple += ". "
        if overall_rating is not None:
            p1_simple += f"Its average CMS overall rating is <strong>{overall_rating:.1f} stars</strong>."
        else:
            p1_simple += "CMS overall rating is not available for this chain."

        # Paragraph 2 — Staffing pattern vs national
        if hprd_for_narrative is not None:
            p2 = f"Across the portfolio, facilities report an average of <strong>{hprd_for_narrative:.2f}</strong> total nurse HPRD"
            if rn_for_narrative is not None:
                p2 += f", including <strong>{rn_for_narrative:.2f}</strong> RN hours"
            if national_hprd is not None:
                if hprd_for_narrative < national_hprd * 0.97:
                    p2 += f", below the national ratio of <strong>{national_hprd:.2f} HPRD</strong>."
                elif hprd_for_narrative > national_hprd * 1.03:
                    p2 += f", above the national ratio of <strong>{national_hprd:.2f} HPRD</strong>."
                else:
                    p2 += f", near the national ratio of <strong>{national_hprd:.2f} HPRD</strong>."
            else:
                p2 += "."
        else:
            p2 = "Staffing averages are not available for this chain for the latest quarter."

        # Paragraph 3 — High-risk % (search_index logic) + fines; no turnover (factual: PBJ320 criteria, not editorial)
        high_risk_span = '<span class="pbj-high-risk-help-wrap"><span class="pbj-high-risk-help">high-risk</span><span class="pbj-high-risk-tooltip" role="tooltip">' + html.escape(HIGH_RISK_CRITERIA_TOOLTIP) + '</span></span>'
        p3 = f"<strong>{pct_high_risk}%</strong> of {chain_esc} facilities meet PBJ320 {high_risk_span} criteria (e.g. special focus facility, one-star overall, abuse icon). "
        if fines_dollars is not None and fines_dollars > 0:
            fines_phrase = f"${fines_dollars/1e6:.1f} million" if fines_dollars >= 1e6 else f"${fines_dollars:,.0f}"
            if total_fines_count is not None and total_fines_count > 0:
                p3 += f"CMS reports a total of <strong>{int(total_fines_count):,} fines</strong> (<strong>{fines_phrase}</strong>) for the chain's nursing homes."
            else:
                p3 += f"Total fines: <strong>{fines_phrase}</strong>."
        else:
            p3 = p3.rstrip()
            if not p3.endswith("."):
                p3 += "."

        pbj_takeaway_ownership = f'''
<div id="pbj-takeaway" class="pbj-content-box" style="margin: 1rem 0; padding: 1rem; border: 1px solid rgba(59,130,246,0.3); border-radius: 8px;">
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(96,165,250,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-header" style="font-size: 16px; font-weight: bold; color: #e2e8f0;">PBJ Takeaway<span class="pbj-takeaway-title-name">: {html.escape(entity_name or "Chain")}</span></div>
</div>
<p style="margin: 0.5rem 0 0.25rem 0;">{tier1_badges}</p>
<p class="pbj-takeaway-narrative" style="margin: 0.5rem 0 0.25rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{p1_simple}</p>
<p class="pbj-takeaway-narrative" style="margin: 0.25rem 0 0.25rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{p2}</p>
<p class="pbj-takeaway-narrative" style="margin: 0.25rem 0 0 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{p3}</p>
<div style="margin-top: 0.35rem; margin-bottom: 0.15rem; display: flex; justify-content: flex-end;"><span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(59,130,246,0.4);">320 Consulting</span></div>
</div>'''

        chain_metrics_html = '<div class="section-header">Key metrics</div>'
        chain_metrics_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0;">'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Total Facilities</div><div class="value">{n_fac:,}</div></div>'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">States of Operation</div><div class="value">{n_st}</div></div>'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Overall Rating</div><div class="value">{(f"{overall_rating:.1f}" if overall_rating is not None else "—")}</div></div>'
        if fines_dollars is not None:
            if fines_dollars >= 1e6:
                fines_str = f'${fines_dollars/1e6:.1f} million'
            else:
                fines_str = f'${fines_dollars:,.0f}'
        else:
            fines_str = '—'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Total Fines</div><div class="value">{fines_str}</div></div>'
        chain_metrics_html += '</div>'
        # Count facilities with 1-star overall rating from provider info (for high-risk section)
        one_star_count = None
        try:
            provider_info = load_provider_info()
            if provider_info and facilities:
                count_1 = 0
                for fac in facilities:
                    ccn = (fac.get('ccn') or '').strip().zfill(6)
                    if not ccn:
                        continue
                    info = provider_info.get(ccn) or {}
                    rating = info.get('overall_rating')
                    if rating is not None and not (isinstance(rating, float) and pd.isna(rating)):
                        try:
                            _r = round_half_up(float(rating), 0)
                            if _r is not None and int(_r) == 1:
                                count_1 += 1
                        except (TypeError, ValueError):
                            pass
                one_star_count = count_1 if (provider_info and facilities) else None
        except Exception:
            pass
        high_risk_html = f'<div class="section-header"><span class="pbj-high-risk-help-wrap entity-section-tooltip-wrap"><span class="pbj-high-risk-help">High-Risk Facilities</span><span class="pbj-high-risk-tooltip entity-section-tooltip" role="tooltip">{html.escape(HIGH_RISK_CRITERIA_TOOLTIP)}</span></span><span class="pbj-section-header-entity-name"> – {html.escape(entity_name)}</span></div>'
        high_risk_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0;">'
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Special Focus Facilities (SFFs)</div><div class="value">{int(sff) if sff is not None else "—"}</div></div>'
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">SFF Candidates</div><div class="value">{int(sff_cand) if sff_cand is not None else "—"}</div></div>'
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">1-Star Overall Rating</div><div class="value">{int(one_star_count) if one_star_count is not None else "—"}</div></div>'
        abuse_display = f'{int(abuse_count)} ({abuse_pct:.1f}%)' if abuse_count is not None and abuse_pct is not None else (f'{int(abuse_count)}' if abuse_count is not None else '—')
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Facilities Cited for Abuse</div><div class="value">{abuse_display}</div></div>'
        high_risk_html += '</div>'
        cms_stars_html = f'<div class="section-header">Avg. CMS 5-Star Rating<span class="pbj-section-header-entity-name"> – {html.escape(entity_name)}</span></div>'
        cms_stars_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0;">'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Overall</div><div class="value">{(f"{overall_rating:.1f}" if overall_rating is not None else "—")}</div></div>'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Health Inspection</div><div class="value">{(f"{hi_rating:.1f}" if hi_rating is not None else "—")}</div></div>'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Staffing</div><div class="value">{(f"{staff_rating:.1f}" if staff_rating is not None else "—")}</div></div>'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Quality Measures</div><div class="value">{(f"{quality_rating:.1f}" if quality_rating is not None else "—")}</div></div>'
        cms_stars_html += '</div>'
        fp = for_profit or 0
        np_ = non_profit or 0
        gov = govt or 0
    if not chain_metrics_html and (quarter_display or avg_total is not None or total_residents or avg_contract is not None):
        chain_metrics_html = '<div class="section-header">Key metrics' + (f' ({quarter_display})' if quarter_display else '') + '</div>'
        chain_metrics_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin:1rem 0;">'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Facilities</div><div class="value">{n:,}</div></div>'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">States</div><div class="value">{num_states}</div></div>'
        if total_residents:
            chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Residents (approx.)</div><div class="value">{total_residents:,}</div></div>'
        if avg_total is not None:
            chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Avg Total HPRD</div><div class="value">{format_metric_value(avg_total, "Total_Nurse_HPRD")}</div></div>'
        if avg_contract is not None:
            chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:1rem;"><div class="label">Avg Contract %</div><div class="value">{format_metric_value(avg_contract, "Contract_Percentage")}%</div></div>'
        chain_metrics_html += '</div>'

    PAGE_SIZE = 20
    provider_info = load_provider_info() or {}
    rows = []
    for fac in facilities:
        ccn = fac.get('ccn', '')
        name_raw = (fac.get('name') or '').strip() or "—"
        name = capitalize_facility_name(name_raw)
        city_raw = (fac.get('city') or '').strip()
        city = capitalize_facility_name(city_raw) if city_raw else ''
        state = (fac.get('state') or '').strip().upper()[:2]
        state_name = STATE_CODE_TO_NAME.get(state, state)
        canonical_slug = get_canonical_slug(state) if state else ''
        state_cell = f'<a href="/state/{canonical_slug}">{state}</a>' if canonical_slug else state
        tn = fac.get('Total_Nurse_HPRD')
        rn = fac.get('RN_HPRD')
        tn_num = float(tn) if tn is not None and not (isinstance(tn, float) and pd.isna(tn)) else None
        rn_num = float(rn) if rn is not None and not (isinstance(rn, float) and pd.isna(rn)) else None
        info = provider_info.get(ccn, {}) if ccn else {}
        _overall = info.get('overall_rating')
        _staff = info.get('staffing_rating')
        try:
            overall_num = int(round_half_up(float(_overall), 0)) if _overall is not None and not (isinstance(_overall, float) and pd.isna(_overall)) else None
        except (TypeError, ValueError):
            overall_num = None
        try:
            staff_num = int(round_half_up(float(_staff), 0)) if _staff is not None and not (isinstance(_staff, float) and pd.isna(_staff)) else None
        except (TypeError, ValueError):
            staff_num = None
        risk_flag, risk_reason = get_facility_risk_from_search_index(ccn) if ccn else (False, '')
        row_class = 'entity-facility-row high-risk' if risk_flag else 'entity-facility-row'
        facility_cell = f'<a href="/provider/{ccn}">{name}</a>'
        if risk_flag and risk_reason:
            facility_cell += f' <span class="pbj-high-risk-help-wrap entity-facility-risk-wrap" style="position:relative;display:inline-flex;align-items:center;vertical-align:middle;"><span class="entity-facility-risk-icon" aria-label="High risk" style="color:#fca5a5;font-size:0.85em;cursor:help;margin-left:2px;">⚠</span><span class="pbj-high-risk-tooltip entity-facility-risk-tooltip" role="tooltip">{html.escape(risk_reason)}</span></span>'
        cells = [state_cell, facility_cell, city or '—']
        if tn is not None:
            cells.append(format_metric_value(tn, 'Total_Nurse_HPRD'))
        else:
            cells.append('—')
        if rn is not None:
            cells.append(format_metric_value(rn, 'RN_HPRD'))
        else:
            cells.append('—')
        cells.append(str(overall_num) if overall_num is not None else '—')
        cells.append(str(staff_num) if staff_num is not None else '—')
        data_attrs = f' data-facility="{name}" data-city="{city or ""}" data-state="{state}" data-ccn="{ccn}" data-total-hprd="{tn_num if tn_num is not None else ""}" data-rn-hprd="{rn_num if rn_num is not None else ""}" data-overall-rating="{overall_num if overall_num is not None else ""}" data-staffing-rating="{staff_num if staff_num is not None else ""}"'
        rows.append('<tr class="' + row_class + '"' + data_attrs + '><td>' + '</td><td>'.join(cells) + '</td></tr>')
    thead = '<tr><th scope="col" data-sort="state">State</th><th scope="col" data-sort="facility">Facility</th><th scope="col" data-sort="city">City</th><th scope="col" data-sort="total-hprd">Total Nurse HPRD</th><th scope="col" data-sort="rn-hprd">RN HPRD</th><th scope="col" data-sort="overall-rating">Overall Rating</th><th scope="col" data-sort="staffing-rating">Staffing Rating</th></tr>'
    tbody = '\n'.join(rows)
    show_more_btn = ''
    if n > PAGE_SIZE:
        show_more_btn = f'<p class="entity-table-more" style="margin-top:0.75rem; display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;"><span id="entity-showing" style="color:#94a3b8; font-size:0.875rem;">1–{PAGE_SIZE} of {n}</span> <button type="button" id="entity-view-more" style="padding:0.4rem 0.8rem; font-size:0.875rem; background:rgba(148,163,184,0.2); color:#e2e8f0; border:1px solid rgba(148,163,184,0.4); border-radius:6px; cursor:pointer;">Load more</button></p>'
    table_script = '''
<script>
(function(){
  var PAGE = 20;
  var rows = document.querySelectorAll(".entity-facility-row");
  var tbody = rows[0] && rows[0].parentNode;
  if (!tbody || !rows.length) return;
  var total = rows.length;
  for (var i = PAGE; i < rows.length; i++) rows[i].style.display = "none";
  var showing = PAGE;
  function updateLabel(){ var el = document.getElementById("entity-showing"); if(el) el.textContent = "1–" + Math.min(showing, total) + " of " + total; }
  var btn = document.getElementById("entity-view-more");
  if (btn) {
    btn.onclick = function(){
      for (var i = showing; i < Math.min(showing + PAGE, total); i++) rows[i].style.display = "";
      showing = Math.min(showing + PAGE, total);
      updateLabel();
      if (showing >= total) btn.style.display = "none";
    };
  }
  updateLabel();
  var headers = tbody.parentNode.querySelectorAll("th[data-sort]");
  headers.forEach(function(th){
    th.style.cursor = "pointer";
    th.setAttribute("title", "Sort by this column");
    th.addEventListener("click", function(){
      var key = th.getAttribute("data-sort");
      var dir = th.getAttribute("data-dir") === "asc" ? "desc" : "asc";
      th.parentNode.querySelectorAll("th[data-sort]").forEach(function(h){ h.removeAttribute("data-dir"); });
      th.setAttribute("data-dir", dir);
      var arr = [].slice.call(rows);
      arr.sort(function(a, b){
        var av = a.getAttribute("data-" + key) || "";
        var bv = b.getAttribute("data-" + key) || "";
        var an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return dir === "asc" ? an - bn : bn - an;
        var as = (av || "").toString().toLowerCase(), bs = (bv || "").toString().toLowerCase();
        var c = as.localeCompare(bs);
        return dir === "asc" ? c : -c;
      });
      arr.forEach(function(r){ tbody.appendChild(r); });
      var children = tbody.children;
      for (var i = 0; i < children.length; i++) children[i].style.display = i < showing ? "" : "none";
    });
  });
})();
</script>'''
    seo_desc = f"{entity_name} operates {subtitle}. PBJ staffing data for affiliated nursing homes."
    page_title = f"{entity_name} ({n} facilities) | Nursing Home Staffing | PBJ320"
    layout = get_pbj_site_layout(page_title, seo_desc, f"{base_url}/entity/{entity_id}")
    entity_page_url = f"{base_url}/entity/{entity_id}"
    care_compare_entity_url = f'https://www.medicare.gov/care-compare/details/chains/{entity_id}'
    custom_report_cta_html = render_custom_report_cta('entity', entity_page_url, entity_name=entity_name)
    # Expandable "All chain data" when we have chain_row (avoid wall of metrics)
    all_chain_data_html = ''
    if chain_row and (chain_metrics_html or high_risk_html or cms_stars_html):
        _entity_esc = html.escape(entity_name or "Chain")
        # Single header "Genesis Healthcare Key Metrics"; strip the duplicate "Key metrics" line from chain_metrics
        _chain_metrics_body = chain_metrics_html.replace('<div class="section-header">Key metrics</div>', '', 1)
        all_chain_data_html = f'''
<div class="pbj-cms-data-block" style="margin: 1rem 0; border: 1px solid rgba(59,130,246,0.25); border-radius: 8px; background: rgba(15,23,42,0.4); padding: 0 1rem 1rem 1rem;">
<div class="section-header" style="margin-top: 0; padding-top: 0.75rem;">{_entity_esc} Key Metrics</div>
''' + _chain_metrics_body + high_risk_html + cms_stars_html + '''
</div>'''
    elif chain_metrics_html:
        all_chain_data_html = chain_metrics_html

    inner = f"""
<h1 style="position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;">{html.escape(entity_name)}</h1>
{pbj_takeaway_ownership}
{all_chain_data_html}

<div class="section-header">{html.escape(entity_name)} Facilities</div>
<p class="pbj-subtitle">Nursing homes affiliated with this entity. Latest quarter staffing from CMS PBJ data. Click column headers to sort.</p>
<style>.entity-facilities-table {{ font-size: 0.875rem; }} .entity-facilities-table tr.high-risk {{ background: rgba(220,38,38,0.08); }} .entity-facilities-table tr.high-risk a {{ color: #fca5a5; text-decoration: none; }} .entity-facilities-table tr.high-risk a:hover {{ color: #fecaca; text-decoration: none; }} .entity-facility-risk-wrap {{ position: relative; display: inline-flex; }} .entity-facility-risk-wrap:hover .entity-facility-risk-tooltip {{ opacity: 1; }} .entity-facility-risk-tooltip {{ position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 6px; min-width: 120px; max-width: 200px; padding: 6px 10px; font-size: 0.75rem; line-height: 1.35; white-space: normal; z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.2s; background: #1e293b; border: 1px solid rgba(59,130,246,0.4); border-radius: 6px; color: #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }} @media (max-width: 768px) {{ .entity-facilities-table {{ font-size: 0.8rem; }} .entity-facilities-table th, .entity-facilities-table td {{ padding: 0.4rem 0.35rem; }} .pbj-table-wrap {{ -webkit-overflow-scrolling: touch; }} }}</style>
<div class="pbj-table-wrap"><table class="entity-facilities-table">
<thead>{thead}</thead>
<tbody>
{tbody}
</tbody>
</table></div>
{show_more_btn}
{table_script}

{render_methodology_block()}

{custom_report_cta_html}

<div class="pbj-page-footer" style="margin-top: 1.75rem; padding-top: 0.5rem; border-top: 1px solid rgba(59,130,246,0.15);">
<p style="margin: 0 0 0.4rem 0; font-size: 0.875rem; color: rgba(226,232,240,0.85); line-height: 1.5;"><a href="/">Home</a></p>
<p style="margin: 0; font-size: 0.8rem; color: rgba(226,232,240,0.6); line-height: 1.45;">Source: CMS Payroll-Based Journal (PBJ) data for facility list and staffing. Chain-level metrics (ratings, fines, SFF, ownership) from CMS Care Compare chain performance data. <a href="{care_compare_entity_url}" target="_blank" rel="noopener" style="color: #93c5fd; text-decoration: underline; text-underline-offset: 2px;">View on CMS Care Compare</a></p>
</div>"""
    html_content = layout['head'] + layout['nav'] + layout['content_open'] + inner + layout['content_close']
    if HAS_CSRF and generate_csrf:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', generate_csrf())
    else:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', '')
    return html_content

_SFF_CACHE = None
_SFF_CACHE_AT = 0
_SFF_CACHE_TTL = 300  # 5 min
# CMS SFF posting PDF; update when a new list is published (e.g. sff-posting-candidate-list-july-2026.pdf)
SFF_SOURCE_URL = 'https://www.cms.gov/files/document/sff-posting-candidate-list-january-2026.pdf'

def load_sff_facilities():
    """Load Special Focus Facilities (SFF) data. Cached 2 min."""
    global _SFF_CACHE, _SFF_CACHE_AT
    now = time.time()
    if _SFF_CACHE is not None and (now - _SFF_CACHE_AT) < _SFF_CACHE_TTL:
        return _SFF_CACHE
    sff_paths = [
        'pbj-wrapped/public/sff-facilities.json',
        'pbj-wrapped/dist/sff-facilities.json',
        'sff-facilities.json',
    ]
    for path in sff_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    out = data['facilities'] if isinstance(data, dict) and 'facilities' in data else (data if isinstance(data, list) else [])
                    _SFF_CACHE = out
                    _SFF_CACHE_AT = time.time()
                    return out
            except Exception as e:
                print(f"Error loading SFF data from {path}: {e}")
                continue
    return []

def get_state_historical_data(state_code):
    """Get historical quarterly data for a state (for longitudinal charts).

    FALLBACKS (order is intentional; do not reorder without review):
    1. Primary: state_quarterly_metrics.csv (state-level rows). Normalized STATE, filtered by code, sorted by CY_Qtr.
    2. Fallback: If no state rows, aggregate facility_quarterly_metrics.csv by STATE and CY_Qtr (mean of HPRD/contract, mean census).
    3. Fallback for (2): If facility_quarterly_metrics.csv missing, try facility_quarterly_metrics_latest.csv.
    No other fallbacks (no older quarters, no synthetic data).
    """
    if not HAS_PANDAS:
        return None
    code = (state_code or '').strip().upper()[:2]
    if not code:
        return None

    def build_result(state_rows, cols):
        raw_quarters = []
        total_data = []
        direct_data = []
        rn_data = []
        rn_care_data = []
        census_data = []
        contract_data = []
        for _, row in state_rows.iterrows():
            q_str = str(row['CY_Qtr'])
            raw_quarters.append(q_str)
            total_data.append(round_half_up(float(row['Total_Nurse_HPRD']), 2) if pd.notna(row.get('Total_Nurse_HPRD')) else None)
            direct_data.append(round_half_up(float(row['Nurse_Care_HPRD']), 2) if 'Nurse_Care_HPRD' in cols and pd.notna(row.get('Nurse_Care_HPRD')) else None)
            rn_data.append(round_half_up(float(row['RN_HPRD']), 2) if pd.notna(row.get('RN_HPRD')) else None)
            rn_care_data.append(round_half_up(float(row['RN_Care_HPRD']), 2) if 'RN_Care_HPRD' in cols and pd.notna(row.get('RN_Care_HPRD')) else None)
            # State resident census: resident_census (fallback sum), total_resident_days/90, or facility_count * avg_daily_census
            resident_census = None
            if 'resident_census' in cols and pd.notna(row.get('resident_census')):
                resident_census = round_half_up(float(row['resident_census']), 0)
            if resident_census is None and 'total_resident_days' in cols and pd.notna(row.get('total_resident_days')):
                trd = float(row['total_resident_days'])
                if trd >= 0:
                    resident_census = round_half_up(trd / 90, 0)
            if resident_census is None and 'facility_count' in cols and pd.notna(row.get('facility_count')):
                census_col = 'avg_daily_census' if 'avg_daily_census' in cols else 'Avg_Daily_Census'
                if census_col in cols and pd.notna(row.get(census_col)):
                    resident_census = round_half_up(float(row['facility_count']) * float(row[census_col]), 0)
            if resident_census is None:
                census_col = 'avg_daily_census' if 'avg_daily_census' in cols else 'Avg_Daily_Census'
                resident_census = round_half_up(float(row[census_col]), 1) if census_col in cols and pd.notna(row.get(census_col)) else None
            census_data.append(int(resident_census) if resident_census is not None and (pd.notna(resident_census) if hasattr(pd, 'notna') else resident_census == resident_census) and resident_census >= 0 else None)
            contract_data.append(round_half_up(float(row['Contract_Percentage']), 2) if 'Contract_Percentage' in cols and pd.notna(row.get('Contract_Percentage')) else None)
        return {
            'raw_quarters': raw_quarters,
            'total': total_data,
            'direct': direct_data,
            'rn': rn_data,
            'rn_care': rn_care_data,
            'census': census_data,
            'contract': contract_data,
        }

    try:
        state_df = load_csv_data('state_quarterly_metrics.csv')
        if state_df is not None and not state_df.empty:
            state_df = state_df.copy()
            state_df['STATE'] = state_df['STATE'].astype(str).str.strip().str.upper()
            state_rows = state_df[state_df['STATE'] == code].sort_values('CY_Qtr')
            if not state_rows.empty:
                return build_result(state_rows, state_rows.columns)
    except Exception as e:
        print(f"Error loading state_quarterly for {state_code}: {e}")

    # Fallback: aggregate from facility_quarterly_metrics by state and quarter
    try:
        fq = load_csv_data('facility_quarterly_metrics.csv')
        if fq is None or not isinstance(fq, pd.DataFrame):
            fq = load_csv_data('facility_quarterly_metrics_latest.csv')
        if fq is None or not isinstance(fq, pd.DataFrame) or 'STATE' not in fq.columns or 'CY_Qtr' not in fq.columns:
            return None
        fq = fq.copy()
        fq['STATE'] = fq['STATE'].astype(str).str.strip().str.upper()
        sub = fq[fq['STATE'] == code]
        if sub.empty:
            return None
        agg_dict = {}
        for col in ['Total_Nurse_HPRD', 'Nurse_Care_HPRD', 'RN_HPRD', 'RN_Care_HPRD', 'Contract_Percentage']:
            if col in sub.columns:
                agg_dict[col] = 'mean'
        if not agg_dict:
            return None
        agg = sub.groupby('CY_Qtr', as_index=False).agg(agg_dict)
        census_col = 'avg_daily_census' if 'avg_daily_census' in sub.columns else ('Census' if 'Census' in sub.columns else None)
        if census_col and census_col in sub.columns:
            # State resident census = sum of facility census per quarter (not mean)
            census_sums = sub.groupby('CY_Qtr')[census_col].sum()
            agg = agg.merge(census_sums.rename('resident_census'), left_on='CY_Qtr', right_index=True, how='left')
            agg['resident_census'] = agg['resident_census'].round(0)
        state_rows = agg.sort_values('CY_Qtr')
        return build_result(state_rows, state_rows.columns)
    except Exception as e:
        print(f"Error loading historical data (facility fallback) for {state_code}: {e}")
        return None


def get_state_facility_count_from_facility_quarterly(state_code, raw_quarter):
    """Count distinct facilities in state for quarter from facility_quarterly_metrics (avoids wrong state_quarterly facility_count)."""
    if not HAS_PANDAS or not state_code or not raw_quarter:
        return None
    try:
        df = load_csv_data('facility_quarterly_metrics.csv')
        if df is None or not isinstance(df, pd.DataFrame):
            df = load_csv_data('facility_quarterly_metrics_latest.csv')
        if df is None or not isinstance(df, pd.DataFrame) or 'PROVNUM' not in df.columns or 'STATE' not in df.columns:
            return None
        df = df.copy()
        df['STATE'] = df['STATE'].astype(str).str.strip().str.upper()
        df['CY_Qtr'] = df['CY_Qtr'].astype(str)
        sub = df[(df['STATE'] == state_code.strip().upper()[:2]) & (df['CY_Qtr'] == str(raw_quarter))]
        return int(sub['PROVNUM'].nunique()) if not sub.empty else 0  # 0 = known empty result set
    except Exception:
        return None


def get_national_historical_data():
    """Get historical quarterly data for USA to build time series chart"""
    if not HAS_PANDAS:
        return None, None
    try:
        national_df = load_csv_data('national_quarterly_metrics.csv')
        if national_df is None:
            return None, None
        
        # Sort by quarter
        national_rows = national_df.sort_values('CY_Qtr') if isinstance(national_df, pd.DataFrame) else sorted(national_df, key=lambda x: x.get('CY_Qtr', ''))
        
        if isinstance(national_df, pd.DataFrame):
            if national_rows.empty:
                return None, None
        else:
            if not national_rows:
                return None, None
        
        # Build quarters and data arrays
        quarters = []
        hprd_data = []
        
        if isinstance(national_df, pd.DataFrame):
            for _, row in national_rows.iterrows():
                q_str = str(row['CY_Qtr'])
                # Convert 2025Q2 to Q2 2025
                match = re.match(r'(\d{4})Q(\d)', q_str)
                if match:
                    quarters.append(f"Q{match.group(2)} {match.group(1)}")
                else:
                    quarters.append(q_str)
                
                hprd = float(row['Total_Nurse_HPRD']) if pd.notna(row['Total_Nurse_HPRD']) else 0
                _h = round_half_up(hprd, 2)
                hprd_data.append(_h if _h is not None else hprd)
        else:
            for row in national_rows:
                q_str = str(row.get('CY_Qtr', ''))
                match = re.match(r'(\d{4})Q(\d)', q_str)
                if match:
                    quarters.append(f"Q{match.group(2)} {match.group(1)}")
                else:
                    quarters.append(q_str)
                
                hprd = float(row.get('Total_Nurse_HPRD', 0)) if row.get('Total_Nurse_HPRD') else 0
                _h = round_half_up(hprd, 2)
                hprd_data.append(_h if _h is not None else hprd)
        
        return quarters, hprd_data
    except Exception as e:
        print(f"Error loading national historical data: {e}")
        return None, None


def get_national_hprd_for_quarter(raw_quarter):
    """Return national Total_Nurse_HPRD for a given quarter (e.g. 2025Q3), or None."""
    if not HAS_PANDAS or not raw_quarter:
        return None
    try:
        national_df = load_csv_data('national_quarterly_metrics.csv')
        if national_df is None or national_df.empty or 'CY_Qtr' not in national_df.columns or 'Total_Nurse_HPRD' not in national_df.columns:
            return None
        row = national_df[national_df['CY_Qtr'].astype(str) == str(raw_quarter)]
        if row.empty:
            return None
        v = row.iloc[0].get('Total_Nurse_HPRD')
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None


def generate_us_chart_html():
    """Generate HTML and JavaScript for US staffing trends chart"""
    quarters, hprd_data = get_national_historical_data()
    
    if not quarters or not hprd_data:
        return ""  # Return empty if no data
    
    # Convert to JavaScript arrays
    quarters_js = json.dumps(quarters)
    data_js = json.dumps(hprd_data)
    
    # Calculate end year from quarters
    end_year = quarters[-1].split(' ')[1] if quarters else "2025"
    start_year = quarters[0].split(' ')[1] if quarters else "2017"
    
    chart_html = f"""
    <section class="mobile-chart" id="usChart" aria-label="US nursing home staffing trends chart" style="margin: 1.5em 0; max-width: 600px;">
        <div class="chart-container" style="background-color: #f8f9fa; padding: 0.5em; border-radius: 4px;">
            <canvas id="usStaffingChart" width="600" height="300" aria-label="US staffing trends line chart" style="max-width: 100%; height: auto;"></canvas>
        </div>
        <div class="chart-footer" style="margin-top: 0.5em;">
            <div class="explore-link" style="text-align: center; margin-bottom: 0.3em;">
                <a href="https://pbj320.com/" target="_blank" style="color: #0645ad; text-decoration: none;">Explore US PBJ Data ↗</a>
            </div>
        </div>
        <div class="chart-source" style="font-size: 0.75em; color: #54595d; text-align: center; margin-top: 0.5em;">
            Source: CMS Payroll-Based Journal Data • 320 Consulting
        </div>
    </section>
    <script>
        (function() {{
            const chartCanvas = document.getElementById('usStaffingChart');
            if (!chartCanvas) return;
            
            const ctx = chartCanvas.getContext('2d');
            const quarters = {quarters_js};
            const data = {data_js};
            
            function drawChart() {{
                const paddingTop = 30;
                const paddingBottom = 40;
                const paddingLeft = 50;
                const paddingRight = 20;
                const chartWidth = chartCanvas.width - paddingLeft - paddingRight;
                const chartHeight = chartCanvas.height - paddingTop - paddingBottom;
                
                // Clear canvas
                ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
                
                // Find min and max values
                const minValue = Math.min(...data);
                const maxValue = Math.max(...data);
                const range = maxValue - minValue || 1;
                
                // Draw grid lines
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                for (let i = 0; i <= 5; i++) {{
                    const y = paddingTop + (chartHeight * i / 5);
                    ctx.beginPath();
                    ctx.moveTo(paddingLeft, y);
                    ctx.lineTo(chartCanvas.width - paddingRight, y);
                    ctx.stroke();
                    
                    // Y-axis labels
                    const value = maxValue - (range * i / 5);
                    ctx.fillStyle = '#54595d';
                    ctx.font = '10px Arial';
                    ctx.textAlign = 'right';
                    ctx.fillText((Math.round(value * 100) / 100).toFixed(2), paddingLeft - 10, y + 4);
                }}
                
                // Draw line
                ctx.strokeStyle = '#0645ad';
                ctx.lineWidth = 2;
                ctx.beginPath();
                data.forEach((value, index) => {{
                    const x = paddingLeft + (chartWidth * index / (data.length - 1));
                    const y = chartCanvas.height - paddingBottom - ((value - minValue) / range * chartHeight);
                    if (index === 0) {{
                        ctx.moveTo(x, y);
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }});
                ctx.stroke();
                
                // Draw points
                ctx.fillStyle = '#0645ad';
                data.forEach((value, index) => {{
                    const x = paddingLeft + (chartWidth * index / (data.length - 1));
                    const y = chartCanvas.height - paddingBottom - ((value - minValue) / range * chartHeight);
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }});
                
                // X-axis labels
                ctx.fillStyle = '#202122';
                ctx.font = '10px Arial';
                ctx.textAlign = 'center';
                const maxLabels = 12;
                const labelStep = Math.max(1, Math.ceil(data.length / maxLabels));
                data.forEach((value, index) => {{
                    if (index === 0 || index === data.length - 1 || index % labelStep === 0) {{
                        const x = paddingLeft + (chartWidth * index / (data.length - 1));
                        const label = quarters[index] || '';
                        ctx.save();
                        ctx.translate(x, chartCanvas.height - paddingBottom + 20);
                        ctx.rotate(-Math.PI / 4);
                        ctx.fillText(label, 0, 0);
                        ctx.restore();
                    }}
                }});
                
                // Title
                ctx.fillStyle = '#202122';
                ctx.font = 'bold 13px Arial';
                ctx.textAlign = 'center';
                ctx.fillText('US Nursing Home Staffing ({start_year}-{end_year})', chartCanvas.width / 2, paddingTop - 5);
            }}
            
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', drawChart);
            }} else {{
                drawChart();
            }}
        }})();
    </script>
    """
    return chart_html

def generate_state_chart_html(state_name, state_code):
    """Generate Chart.js state staffing charts (Total+Direct, RN, Census, Contract). Data loaded via API to avoid JSON-in-HTML syntax errors."""
    state_esc = html.escape(str(state_name)) if state_name else ''
    state_code_esc = html.escape(state_code.upper(), quote=True) if state_code else ''
    state_sub = f'<p class="pbj-chart-facility" style="text-align:center;margin:0.25rem 0 0.75rem 0;font-size:0.85rem;color:rgba(226,232,240,0.75);">{state_esc}</p>' if state_esc else ''
    macpac_url = 'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
    macpac_hprd = get_macpac_hprd_for_state(state_code) if state_code else None
    if macpac_hprd is not None and macpac_hprd >= 1.5:
        min_str = f'~{macpac_hprd:.2f}'
        state_min_phrase = f' State min. ({min_str} HPRD) may reflect calculated equivalents by <a href="{macpac_url}" target="_blank" rel="noopener" style="color:#93c5fd;">MACPAC</a>.'
    else:
        state_min_phrase = ''
    total_staffing_footer = f'''<p class="pbj-chart-footnote" style="margin:0.5rem 0 0 0;font-size:0.7rem;line-height:1.35;color:rgba(226,232,240,0.65);">
<span class="pbj-chart-footnote-desktop">Direct staff excludes Admin/DON.{state_min_phrase}</span>
<span class="pbj-chart-footnote-mobile">Direct staff excludes Admin/DON.{state_min_phrase}</span>
</p>'''
    def chart_header(main_title):
        one_line = (f'<div class="pbj-chart-header-oneline section-header" style="margin-bottom:0;">{main_title}: {state_esc}</div>') if state_esc else (f'<div class="pbj-chart-header-oneline section-header" style="margin-bottom:0;">{main_title}</div>')
        two_line = f'<div class="pbj-chart-header-twoline"><div class="section-header" style="margin-bottom:0;">{main_title}</div>{state_sub}</div>'
        # State page mobile only: one row "Illinois Census" (state + metric) with same section-header style
        state_mobile_line = (f'<div class="pbj-chart-header-state-mobile section-header" style="margin-bottom:0;">{state_esc} {main_title}</div>') if state_esc else ''
        return f'<div class="pbj-chart-header" style="text-align:center;margin-bottom:0.25rem;">{one_line}{two_line}{state_mobile_line}</div>'
    def chart_block(title, canvas_id, footer=''):
        out = f'<div class="pbj-chart-container" style="margin-bottom:1.5rem;">{chart_header(title)}<div class="pbj-chart-wrapper"><canvas id="{canvas_id}"></canvas></div>'
        if footer:
            out += footer
        return out + '</div>'
    return f'''
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<div id="state-chart-meta" data-state-code="{state_code_esc}" style="display:none;"></div>
<div class="state-page-charts">
''' + chart_block('Total Staffing', 'stateChartTotal', total_staffing_footer) + '''
''' + chart_block('RN Staffing', 'stateChartRN') + '''
''' + chart_block('Resident Census', 'stateChartCensus') + '''
''' + chart_block('Contract Staff %', 'stateChartContract') + '''
</div>
<script src="/state-page-charts.js"></script>
'''

def generate_state_page_html(state_name, state_code, state_data, macpac_standard, region_info, quarter, rank_total=None, rank_rn=None, total_states=None, sff_facilities=None, raw_quarter=None, contact_info=None):
    """Generate state page content. Returns (content, page_title, seo_description, canonical_url) for use with get_pbj_site_layout (state page is separate from PBJpedia)."""
    try:
        from pbj_format import format_metric_value
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{round_half_up(float(v), 2):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
    # Format data values (use format_metric_value for audit-grade ROUND_HALF_UP; fmt for generic decimals)
    def fmt(val, decimals=2):
        try:
            if pd.isna(val) or val is None:
                return "N/A"
            r = round_half_up(float(val), decimals)
            return f"{r:.{decimals}f}" if r is not None else "N/A"
        except Exception:
            return "N/A"
    
    def get_val(key, default='N/A'):
        try:
            if isinstance(state_data, dict):
                return state_data.get(key, default)
            else:
                return state_data.get(key, default) if hasattr(state_data, 'get') else getattr(state_data, key, default)
        except:
            return default
    
    # Calculate rankings for each metric
    def get_rank_for_metric(metric_key):
        """Get ranking for a specific metric (1 = best/highest)"""
        if not HAS_PANDAS or raw_quarter is None:
            return None
        try:
            # Load all state data for latest quarter
            state_df = load_csv_data('state_quarterly_metrics.csv')
            if state_df is None:
                return None
            latest_all = state_df[(state_df['CY_Qtr'] == raw_quarter) & (state_df['STATE'].astype(str).str.strip().str.upper().isin(STATES_FOR_RANKING))]
            if latest_all.empty:
                return None
            latest_all_sorted = latest_all.sort_values(metric_key, ascending=False).reset_index(drop=True)
            state_idx = latest_all_sorted[latest_all_sorted['STATE'] == state_code].index
            if not state_idx.empty:
                return int(state_idx[0]) + 1
        except:
            pass
        return None
    
    # Region link removed per user request
    region_link = ""
    
    # State standard (MACPAC) as badge only when relevant (> 1.5 HPRD)
    state_standard_badge = ""
    state_standard_footer = ""
    if macpac_standard is not None:
        try:
            min_staffing_raw = macpac_standard.get('Min_Staffing', '') if isinstance(macpac_standard, dict) else getattr(macpac_standard, 'Min_Staffing', '')
            min_staffing_val = str(min_staffing_raw).replace(' HPRD', '').strip()
            try:
                min_staffing_num = float(min_staffing_val)
                if min_staffing_num > 1.5:
                    state_standard_badge = f'<span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #b8d4f0;">{state_code} Min: {fmt(min_staffing_num, 2)} HPRD</span>'
            except (TypeError, ValueError):
                pass
        except Exception:
            pass

    # Get basics: prefer facility count from facility_quarterly for this same quarter; fall back to state_quarterly (same quarter). Never show 0 when both missing; no synthetic data.
    _fcount = get_state_facility_count_from_facility_quarterly(state_code, raw_quarter)
    _fallback = get_val('facility_count', None)
    try:
        _fallback_num = None if _fallback is None or _fallback == '' or str(_fallback).strip() == '' else int(float(_fallback))
    except (TypeError, ValueError):
        _fallback_num = None
    if _fcount is not None:
        facility_count = int(_fcount)
        facility_count_display = f"{facility_count:,}"
    elif _fallback_num is not None:
        facility_count = _fallback_num
        facility_count_display = f"{facility_count:,}"
    else:
        facility_count = None
        facility_count_display = "—"
    avg_daily_census_val = get_val('avg_daily_census', 0)
    try:
        avg_daily_census_float = float(avg_daily_census_val) if avg_daily_census_val not in ('N/A', None, '') else 0
    except (TypeError, ValueError):
        avg_daily_census_float = 0
    
    # Total residents: facility_count × avg_daily_census, or total_resident_days/90 from state data
    total_resident_days = get_val('total_resident_days', 0)
    try:
        trd = float(total_resident_days) if total_resident_days not in ('N/A', None, '') else 0
    except (TypeError, ValueError):
        trd = 0
    if facility_count is not None and facility_count > 0 and avg_daily_census_float > 0:
        _tr = round_half_up(facility_count * avg_daily_census_float, 0)
        total_residents = int(_tr) if _tr is not None else 0
    elif trd > 0:
        _tr = round_half_up(trd / 90, 0)
        total_residents = int(_tr) if _tr is not None else 0
    else:
        total_residents = 0
    total_residents_display = f"{total_residents:,}" if total_residents > 0 else "N/A"
    try:
        resident_count = int(float(total_resident_days) / 90) if total_resident_days != 'N/A' else 'N/A'
    except:
        resident_count = 'N/A'
    
    # Get rankings for each metric
    rank_total_nurse = get_rank_for_metric('Total_Nurse_HPRD') or rank_total
    rank_rn_hprd = get_rank_for_metric('RN_HPRD') or rank_rn
    rank_direct_care = get_rank_for_metric('Nurse_Care_HPRD')
    rank_rn_care = get_rank_for_metric('RN_Care_HPRD')
    rank_nurse_aide = get_rank_for_metric('Nurse_Assistant_HPRD')
    
    # Get Total HPRD with rank for overview table (use format_metric_value for audit rounding)
    total_hprd_val = format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')
    total_hprd_display = total_hprd_val
    if rank_total_nurse and total_states:
        # Proper ordinal suffix: 1st, 2nd, 3rd, 4th, etc.
        # Special cases: 11th, 12th, 13th (not 11st, 12nd, 13rd)
        rank = rank_total_nurse
        if rank % 100 in [11, 12, 13]:
            suffix = 'th'
        elif rank % 10 == 1:
            suffix = 'st'
        elif rank % 10 == 2:
            suffix = 'nd'
        elif rank % 10 == 3:
            suffix = 'rd'
        else:
            suffix = 'th'
        total_hprd_display = f"{total_hprd_val} ({rank}{suffix})"
    
    # Key metrics row (4 columns) with deltas vs previous quarter — per pbj-page-guide
    prev_facility_count = prev_residents = prev_hprd = prev_contract = None
    try:
        state_df = load_csv_data('state_quarterly_metrics.csv')
        if state_df is not None and HAS_PANDAS and raw_quarter:
            state_rows = state_df[state_df['STATE'] == state_code].sort_values('CY_Qtr', ascending=False)
            if len(state_rows) >= 2:
                prev = state_rows.iloc[1]
                _pf = prev.get('facility_count')
                prev_facility_count = int(float(_pf)) if _pf is not None and str(_pf).strip() != '' and not (isinstance(_pf, float) and pd.isna(_pf)) else None
                prev_residents = int(float(prev.get('facility_count')) * float(prev.get('avg_daily_census'))) if prev.get('facility_count') is not None and prev.get('avg_daily_census') is not None and pd.notna(prev.get('facility_count')) and pd.notna(prev.get('avg_daily_census')) else None
                prev_hprd = prev.get('Total_Nurse_HPRD')
                prev_contract = prev.get('Contract_Percentage')
            elif len(state_rows) == 1:
                prev_facility_count = prev_residents = prev_hprd = prev_contract = None
    except Exception:
        pass
    def delta_str(cur, prev, is_pct=False):
        if prev is None or cur is None: return "—"
        try:
            c, p = float(cur), float(prev)
            if p == 0: return "—"
            d = c - p
            if is_pct: return f"{d:+.1f}%"
            if abs(d) == int(d): return f"{int(d):+d}"
            return f"{d:+.2f}"
        except Exception: return "—"
    key_metrics_section = f"""
    <div class="section-header">Key metrics ({quarter})</div>
    <style>.state-key-metrics-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin:1rem 0;}}@media(max-width:768px){{.state-key-metrics-row{{grid-template-columns:repeat(2,1fr);}}}}</style>
    <div class="state-key-metrics-row">
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Nursing Homes</div>
            <div class="value">{facility_count_display}</div>
            <div class="delta">{delta_str(facility_count, prev_facility_count)} vs prior quarter</div>
        </div>
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Resident Census</div>
            <div class="value">{total_residents_display}</div>
            <div class="delta">{delta_str(total_residents if total_residents else None, prev_residents)} vs prior quarter</div>
        </div>
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Nurse Staffing (HPRD)</div>
            <div class="value">{format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')}</div>
            <div class="delta">{delta_str(get_val('Total_Nurse_HPRD'), prev_hprd)} vs prior quarter</div>
        </div>
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Contract Staff %</div>
            <div class="value">{format_metric_value(get_val('Contract_Percentage'), 'Contract_Percentage', 'N/A')}%</div>
            <div class="delta">{delta_str(get_val('Contract_Percentage'), prev_contract, True)} vs prior quarter</div>
        </div>
    </div>
    """
    
    # Load provider info for SFF facilities
    provider_info = load_provider_info()
    
    # Helper to format ownership type
    def format_ownership_type(ownership):
        """Format ownership type: For-Profit, Non Profit, or Government"""
        if not ownership:
            return ""
        ownership_lower = str(ownership).lower().strip()
        # Remove common suffixes like "Corporation", "LLC", etc.
        ownership_clean = re.sub(r'\s*(corporation|corp|llc|l\.l\.c\.|inc|incorporated|partnership|partners|co\.|company)\s*$', '', ownership_lower, flags=re.IGNORECASE)
        if 'profit' in ownership_clean and 'non' not in ownership_clean:
            return "For-Profit"
        elif 'non-profit' in ownership_clean or 'nonprofit' in ownership_clean or ('non' in ownership_clean and 'profit' in ownership_clean):
            return "Non Profit"
        elif 'government' in ownership_clean or 'gov' in ownership_clean:
            return "Government"
        return ownership
    
    # SFF facilities section: tabbed table (Current SFF, Candidates, Graduates, No longer in program)
    sff_section = ""
    if sff_facilities:
        by_cat = {'SFF': [], 'Candidate': [], 'Graduate': [], 'Terminated': []}
        for f in sff_facilities:
            cat = f.get('category') or 'SFF'
            if cat in by_cat:
                by_cat[cat].append(f)
        total_sff = len(sff_facilities)
        sff_section = f"""
    <details class="pbj-details">
    <summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Special Focus Facilities</summary>
    <div class="pbj-details-content">
    <p class="pbj-subtitle" style="color: rgba(226,232,240,0.95); margin: 0 0 0.75rem 0;">{state_name} has facilities in the Special Focus Facility program. Select a tab to view Current SFFs, Candidates, Graduates, or facilities no longer in Medicare/Medicaid.</p>
    <div class="sff-tabs" role="tablist" style="display:flex; flex-wrap:wrap; gap:0.25rem; margin-bottom:0.5rem;">
    """
        tab_id_prefix = "sff-tab-"
        panel_id_prefix = "sff-panel-"
        categories_order = [('SFF', 'Current SFF', 'months as SFF'), ('Candidate', 'Candidates', 'months as candidate'), ('Graduate', 'Graduates', 'months as SFF'), ('Terminated', 'No longer in program', 'months as SFF')]
        first_selected = next((k for k, _, _ in categories_order if by_cat.get(k)), 'SFF')
        for cat_key, tab_label, months_label in categories_order:
            lst = by_cat.get(cat_key) or []
            count = len(lst)
            tid = tab_id_prefix + cat_key.lower()
            pid = panel_id_prefix + cat_key.lower()
            selected = (cat_key == first_selected)
            aria_val = 'true' if selected else 'false'
            sff_section += f'<button type="button" role="tab" id="{tid}" aria-controls="{pid}" aria-selected="{aria_val}" class="sff-tab-btn" data-panel="{pid}" style="padding:0.4rem 0.75rem; font-size:0.875rem; background:rgba(15,23,42,0.6); color:rgba(226,232,240,0.85); border:1px solid rgba(59,130,246,0.35); border-radius:6px; cursor:pointer;">{tab_label} ({count})</button>'
        sff_section += '</div>'
        for cat_key, tab_label, months_label in categories_order:
            lst = by_cat.get(cat_key) or []
            pid = panel_id_prefix + cat_key.lower()
            tid = tab_id_prefix + cat_key.lower()
            is_first = (cat_key == first_selected)
            panel_style = 'display:block;' if is_first else 'display:none;'
            sff_section += f'<div role="tabpanel" id="{pid}" aria-labelledby="{tid}" class="sff-panel" style="{panel_style}">'
            if not lst:
                sff_section += f'<p style="color:rgba(226,232,240,0.8); font-size:0.9rem;">No {tab_label.lower()} in this state.</p>'
            else:
                # Table: Facility (name, city), Months, Residents, Ownership; Graduate/Terminated add date column
                extra_col = ''
                if cat_key == 'Graduate':
                    extra_col = '<th scope="col">Graduation</th>'
                elif cat_key == 'Terminated':
                    extra_col = '<th scope="col">Termination</th>'
                sff_section += f'''
    <div class="pbj-table-wrap" style="overflow-x:auto; -webkit-overflow-scrolling:touch; margin:0.5rem 0;">
    <table class="sff-facilities-table" style="width:100%; min-width:320px; border-collapse:collapse; font-size:0.875rem;">
    <thead><tr><th scope="col">Facility</th><th scope="col">Months</th><th scope="col">Residents</th><th scope="col">Total HPRD</th><th scope="col">Ownership</th>{extra_col}</tr></thead>
    <tbody>'''
                for facility in lst:
                    facility_name = facility.get('facility_name', 'Unknown')
                    provider_number = facility.get('provider_number', '')
                    months_val = facility.get('months_as_sff')
                    city = facility.get('city', '')
                    prov_info = provider_info.get(provider_number, {})
                    if not city:
                        city = prov_info.get('city', '')
                    residents = prov_info.get('avg_residents_per_day', '')
                    ownership = format_ownership_type(prov_info.get('ownership_type', ''))
                    facility_name_cap = capitalize_facility_name(facility_name)
                    city_cap = capitalize_city_name(city) if city else ''
                    dashboard_link = f'/provider/{provider_number}'
                    facility_cell = f'<a href="{dashboard_link}">{html.escape(facility_name_cap)}</a>' + (f' <span style="color:rgba(226,232,240,0.75);">({html.escape(city_cap)})</span>' if city_cap else '')
                    months_cell = str(months_val) if months_val is not None else '—'
                    residents_cell = str(int(float(residents))) if residents and str(residents).strip() else '—'
                    try:
                        if residents and str(residents).strip():
                            residents_cell = str(int(float(residents)))
                    except (ValueError, TypeError):
                        residents_cell = '—'
                    total_hprd_raw = prov_info.get('reported_total_nurse_hrs_per_resident_per_day') or prov_info.get('Total_Nurse_HPRD')
                    try:
                        total_hprd_cell = fmt(float(total_hprd_raw)) if total_hprd_raw is not None and str(total_hprd_raw).strip() else '—'
                    except (ValueError, TypeError):
                        total_hprd_cell = '—'
                    ownership_cell = ownership or '—'
                    extra_cell = ''
                    if cat_key == 'Graduate':
                        d = facility.get('date_of_graduation') or ''
                        extra_cell = f'<td>{html.escape(d) if d else "—"}</td>'
                    elif cat_key == 'Terminated':
                        d = facility.get('date_of_termination') or ''
                        extra_cell = f'<td>{html.escape(d) if d else "—"}</td>'
                    sff_section += f'<tr><td>{facility_cell}</td><td>{months_cell}</td><td>{residents_cell}</td><td>{total_hprd_cell}</td><td>{ownership_cell}</td>{extra_cell}</tr>'
                sff_section += '</tbody></table></div>'
            sff_section += '</div>'
        sff_section += f'''
    <style>
    .sff-facilities-table th, .sff-facilities-table td {{ padding: 0.5rem 0.4rem; border: 1px solid rgba(59,130,246,0.25); text-align:left; }}
    .sff-facilities-table th {{ background: rgba(30,64,175,0.2); color: #93c5fd; font-weight:600; }}
    .sff-facilities-table tbody tr:nth-child(even) {{ background: rgba(15,23,42,0.4); }}
    .sff-tab-btn[aria-selected="true"] {{ background: rgba(59,130,246,0.55) !important; border-color: #60a5fa !important; color: #e2e8f0 !important; font-weight: 600; box-shadow: 0 0 0 1px rgba(96,165,250,0.5); }}
    @media (max-width: 640px) {{ .sff-facilities-table {{ font-size: 0.8rem; }} .sff-facilities-table th, .sff-facilities-table td {{ padding: 0.35rem 0.25rem; }} }}
    </style>
    <p style="margin-top:0.75rem; font-size:0.85rem;"><a href="{html.escape(SFF_SOURCE_URL)}" target="_blank" rel="noopener">Source: CMS Special Focus Facility program</a></p>
    <script>
    (function(){{
      var tabs = document.querySelectorAll(".sff-tab-btn");
      var panels = document.querySelectorAll(".sff-panel");
      tabs.forEach(function(btn){{
        btn.addEventListener("click", function(){{
          var panelId = btn.getAttribute("data-panel");
          tabs.forEach(function(t){{ t.setAttribute("aria-selected", "false"); }});
          panels.forEach(function(p){{ p.style.display = "none"; }});
          btn.setAttribute("aria-selected", "true");
          var p = document.getElementById(panelId);
          if(p) p.style.display = "block";
        }});
      }});
    }})();
    </script>
    </div></details>'''
    
    # Ranking info removed - already shown in overview table
    ranking_info = ""
    
    # Generate chart HTML (with dynamic state name in heading)
    chart_html = generate_state_chart_html(state_name, state_code)
    
    # Contact/complaint section removed per user request
    contact_section = ""
    if False and contact_info:  # disabled
        phone_html = ""
        if contact_info.get('phone'):
            phones = contact_info['phone']
            phone_parts = []
            if phones.get('general'):
                phone_parts.append(f"General: {', '.join(phones['general'])}")
            if phones.get('toll_free'):
                phone_parts.append(f"Toll-free: {', '.join(phones['toll_free'])}")
            if phones.get('hha'):
                phone_parts.append(f"Home Health Agency: {', '.join(phones['hha'])}")
            if phones.get('hospice'):
                phone_parts.append(f"Hospice: {', '.join(phones['hospice'])}")
            if phone_parts:
                phone_html = "<p>" + " | ".join(phone_parts) + "</p>"
        
        website_url = contact_info.get('website_url', '')
        website_link = f'<p>Complaint website: <a href="{website_url}" target="_blank" rel="noopener">{website_url}</a></p>' if website_url else ""
        
        notes = contact_info.get('notes', [])
        notes_html = ""
        if notes:
            notes_html = "<p>" + " ".join(notes) + "</p>"
        
        contact_section = f"""
    <div class="section-header">Filing Complaints & Contact Information</div>
    <p style="color: rgba(226,232,240,0.95);">Complaints about nursing homes in {state_name} may be filed with the state regulatory agency. Contact information:</p>
    {phone_html}
    {website_link}
    {notes_html}
    <p style="font-size: 0.9em; color: rgba(226,232,240,0.75);">Contact information is provided for reference. For current information, consult the state agency website.</p>
    """
    elif False and macpac_standard is None:  # contact section removed per user request
        contact_section = ""
    
    # CustomReportCTA for state page
    _canonical_slug = get_canonical_slug(state_code)
    _state_page_url = f"https://pbj320.com/state/{_canonical_slug}"
    _region_str = ''
    if region_info is not None and hasattr(region_info, 'get'):
        _region_str = str(region_info.get('CMS_Region_Number', '') or region_info.get('Region_Number', '') or '')
    cta_section = render_custom_report_cta('state', _state_page_url, state_name=state_name, region=_region_str)
    
    total_hprd_val = format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')
    cur_hprd = None
    try:
        v = get_val('Total_Nurse_HPRD')
        if v != 'N/A':
            cur_hprd = float(v)
    except (TypeError, ValueError):
        pass
    national_hprd = get_national_hprd_for_quarter(raw_quarter)
    yoy_diff = None
    if cur_hprd is not None and raw_quarter:
        try:
            qstr = str(raw_quarter)
            if len(qstr) >= 6 and qstr[4:6] in ('Q1', 'Q2', 'Q3', 'Q4'):
                prior_q = f'{int(qstr[:4]) - 1}{qstr[4:6]}'
                state_df_yoy = load_csv_data('state_quarterly_metrics.csv')
                if state_df_yoy is not None and not state_df_yoy.empty:
                    prior_row = state_df_yoy[(state_df_yoy['STATE'].astype(str).str.strip().str.upper() == state_code.strip().upper()[:2]) & (state_df_yoy['CY_Qtr'].astype(str) == prior_q)]
                    if not prior_row.empty:
                        pv = prior_row.iloc[0].get('Total_Nurse_HPRD')
                        if pv is not None and not (isinstance(pv, float) and pd.isna(pv)):
                            yoy_diff = cur_hprd - float(pv)
        except Exception:
            pass
    # Residents per total staff (per day): 24 hours / HPRD = residents one FTE covers per day
    _rps = round_half_up(24 / cur_hprd, 1) if cur_hprd and cur_hprd > 0 else None
    residents_per_staff = _rps
    state_na_hprd = None
    try:
        na = get_val('Nurse_Assistant_HPRD')
        if na != 'N/A':
            state_na_hprd = float(na)
    except (TypeError, ValueError):
        pass
    _afc = round_half_up(avg_daily_census_float, 0) if avg_daily_census_float and avg_daily_census_float > 0 else None
    avg_facility_census = int(_afc) if _afc is not None else None
    state_narrative = ''
    if cur_hprd is not None:
        parts = [f"<strong>{html.escape(state_name)}</strong> reported <strong>{total_hprd_val} HPRD</strong>"]
        if residents_per_staff is not None:
            parts[0] += f" (≈ {residents_per_staff} residents per total staff)"
        parts[0] += f" in {quarter}."
        if yoy_diff is not None and yoy_diff != 0:
            qstr = str(raw_quarter)
            prior_yr = int(qstr[:4]) - 1 if len(qstr) >= 4 else None
            prior_label = f"{qstr[4:6]} {prior_yr}" if len(qstr) >= 6 and prior_yr is not None else "same quarter last year"
            parts.append(f" HPRD is {'up' if yoy_diff > 0 else 'down'} {abs(yoy_diff):.2f} since {prior_label}.")
        if national_hprd is not None:
            if cur_hprd < national_hprd * 0.97:
                parts.append(f" This level is below the national ratio of {format_metric_value(national_hprd, 'Total_Nurse_HPRD', 'N/A')} HPRD")
            elif cur_hprd > national_hprd * 1.03:
                parts.append(f" This level is above the national ratio of {format_metric_value(national_hprd, 'Total_Nurse_HPRD', 'N/A')} HPRD")
            else:
                parts.append(f" This level is near the national ratio of {format_metric_value(national_hprd, 'Total_Nurse_HPRD', 'N/A')} HPRD")
            if rank_total_nurse and total_states:
                parts.append(f" and ranks <strong>#{rank_total_nurse}</strong> out of {total_states} states.")
            else:
                parts.append(".")
        elif rank_total_nurse and total_states:
            parts.append(f" and ranks <strong>#{rank_total_nurse}</strong> out of {total_states} states.")
        state_narrative = '<p class="pbj-takeaway-narrative" style="margin: 0.5rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">' + ''.join(parts) + '</p>'
    else:
        state_narrative = f'<p class="pbj-takeaway-narrative" style="margin: 0.5rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">In {quarter}, <strong>{html.escape(state_name)}</strong> nursing homes reported an average of <strong>{total_hprd_val} HPRD</strong> of total nurse staffing.{" Ranks <strong>#" + str(rank_total_nurse) + "</strong> of " + str(total_states) + " states." if rank_total_nurse and total_states else ""}</p>'
    state_put_another_way = ''
    if cur_hprd and cur_hprd > 0:
        _fs = round_half_up(30 * cur_hprd / 24, 1)
        floor_staff = max(0.1, _fs if _fs is not None else 30 * cur_hprd / 24)
        _fa = round_half_up(30 * (state_na_hprd or 0) / 24, 1) if state_na_hprd is not None else None
        floor_aides = max(0, _fa if _fa is not None else 0)
        state_put_another_way = f"On a 30-bed floor at a typical {html.escape(state_name)} nursing home you'd see about <strong>{floor_staff:.1f} staff members</strong>, including {floor_aides:.1f} nurse aides."
        if avg_facility_census and avg_facility_census > 0:
            _fst = round_half_up(avg_facility_census * cur_hprd / 24, 1)
            fac_staff = max(1, _fst if _fst is not None else avg_facility_census * cur_hprd / 24)
            _fai = round_half_up(fac_staff * (state_na_hprd or 0) / cur_hprd, 1) if state_na_hprd is not None else None
            fac_aides = max(0, _fai if _fai is not None else 0)
            state_put_another_way += f" For the entire {avg_facility_census}-resident facility ({html.escape(state_name)} average), that's about {fac_staff:.1f} total staff, including {fac_aides:.1f} nurse aides."
        state_put_another_way = '<p style="margin: 0.5rem 0 0 0; color: #e2e8f0;"><strong>Put another way…</strong> ' + state_put_another_way + '</p>'
    # Badge order: HPRD (rank), RN HPRD, contract %, then state min
    rn_hprd_val = format_metric_value(get_val('RN_HPRD'), 'RN_HPRD', 'N/A')
    _bs = 'display: inline-block; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #b8d4f0;'
    badges_line = f'<span style="{_bs}">{total_hprd_val} HPRD (rank: {rank_total_nurse or "—"})</span><span class="pbj-badge-mobile-hide" style="{_bs}">{rn_hprd_val} RN HPRD</span><span class="pbj-badge-mobile-hide" style="{_bs}">{format_metric_value(get_val("Contract_Percentage"), "Contract_Percentage", "N/A")}% contract</span>{state_standard_badge}'
    # State outline: D3 + TopoJSON (will be placed inside PBJ takeaway card)
    state_code_esc = html.escape(state_code, quote=True)
    state_name_esc = html.escape(state_name, quote=True)
    state_outline_inset = f'''
    <div id="state-outline-wrap" style="position:absolute;top:0.5rem;right:0.5rem;width:120px;height:120px;opacity:0.2;pointer-events:none;z-index:0;" data-state-code="{state_code_esc}" data-state-name="{state_name_esc}" aria-hidden="true">
      <svg id="state-outline-svg" width="100%" height="100%" viewBox="0 0 400 400" style="overflow:visible;"></svg>
    </div>
    <script>
    (function(){{
      var wrap = document.getElementById("state-outline-wrap");
      if (!wrap) return;
      var stateCode = (wrap.getAttribute("data-state-code") || "").toUpperCase();
      var stateName = wrap.getAttribute("data-state-name") || "";
      var svgEl = document.getElementById("state-outline-svg");
      function fallback() {{
        if (svgEl) svgEl.innerHTML = "<text x=\\"200\\" y=\\"200\\" text-anchor=\\"middle\\" dominant-baseline=\\"middle\\" font-size=\\"72\\" font-weight=\\"bold\\" fill=\\"currentColor\\" style=\\"opacity:0.3\\">" + stateCode + "</text>";
      }}
      function loadScript(src) {{
        return new Promise(function(resolve, reject) {{
          if (document.querySelector('script[src="' + src + '"]')) {{ resolve(); return; }}
          var s = document.createElement("script");
          s.src = src;
          s.onload = resolve;
          s.onerror = reject;
          document.head.appendChild(s);
        }});
      }}
      Promise.all([loadScript("https://d3js.org/d3.v7.min.js"), loadScript("https://cdn.jsdelivr.net/npm/topojson-client@3")]).then(function() {{
        var d3 = window.d3, topojson = window.topojson;
        if (!d3 || !topojson) {{ fallback(); return; }}
        d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json").then(function(us) {{
          var states = topojson.feature(us, us.objects.states);
          var feat = states.features.find(function(f) {{ return f.properties.name === stateName; }});
          if (!feat) feat = states.features.find(function(f) {{ return f.properties.abbrev === stateCode; }});
          if (!feat) {{ fallback(); return; }}
          var projection = d3.geoAlbersUsa().fitSize([360, 360], {{ type: "FeatureCollection", features: [feat] }});
          var path = d3.geoPath().projection(projection);
          d3.select(svgEl).selectAll("*").remove();
          d3.select(svgEl).append("g").append("path").datum(feat).attr("d", path).attr("fill", "none").attr("stroke", "currentColor").attr("stroke-width", "2").attr("stroke-linecap", "round").attr("stroke-linejoin", "round").style("color", "#60a5fa");
        }}).catch(fallback);
      }}).catch(fallback);
    }})();
    </script>
    '''
    state_takeaway_card = f'''
<div id="pbj-takeaway" class="pbj-content-box" style="margin: 1rem 0; padding: 1rem; border: 1px solid rgba(59,130,246,0.3); border-radius: 8px; position: relative;">
{state_outline_inset}
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(96,165,250,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-header" style="font-size: 16px; font-weight: bold; color: #e2e8f0;">PBJ Takeaway<span class="pbj-takeaway-title-name">: {html.escape(state_name)}</span></div>
</div>
<p style="margin: 0.5rem 0 0.5rem 0;">{badges_line}</p>
{state_narrative}
{state_put_another_way}
<div style="margin-top: 0.35rem; margin-bottom: 0.15rem; display: flex; justify-content: flex-end;"><span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(96,165,250,0.4);">320 Consulting</span></div>
</div>'''
    # State page content: H1, subtitle (context first), Phoebe takeaway (with state outline inside), chart, collapsible table, SFF, Explore, CTA, contact
    content = f"""
    <h1 class="pbj-state-title"><span class="pbj-state-title-full">{state_name} PBJ Nursing Home Staffing</span><span class="pbj-state-title-mobile">{state_name} PBJ Staffing</span></h1>
    <p class="pbj-subtitle pbj-subtitle-state">{facility_count_display} providers • {total_residents_display} residents • {total_hprd_val} HPRD</p>
    {state_takeaway_card}
    {chart_html}
    <details class="pbj-details">
    <summary><span class="pbj-details-icon" aria-hidden="true">▼</span> {state_name} PBJ Metrics</summary>
    <div class="pbj-details-content">
    <div class="pbj-table-wrap"><table style="max-width: 600px;">
        <tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">National Rank</th></tr>
        <tr><td>Total Nurse Staffing HPRD</td><td>{format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')}</td><td>#{rank_total_nurse} of {total_states if total_states else 'N/A'}</td></tr>
        <tr><td title="Excludes admin, DON (Director of Nursing)">Direct Care Nurse HPRD</td><td>{format_metric_value(get_val('Nurse_Care_HPRD'), 'Nurse_Care_HPRD', 'N/A')}</td><td>#{rank_direct_care} of {total_states if rank_direct_care and total_states else 'N/A'}</td></tr>
        <tr><td>RN HPRD</td><td>{format_metric_value(get_val('RN_HPRD'), 'RN_HPRD', 'N/A')}</td><td>#{rank_rn_hprd} of {total_states if total_states else 'N/A'}</td></tr>
        <tr><td title="Excludes admin, DON (Director of Nursing)">RN Direct Care HPRD</td><td>{format_metric_value(get_val('RN_Care_HPRD'), 'RN_Care_HPRD', 'N/A')}</td><td>#{rank_rn_care} of {total_states if rank_rn_care and total_states else 'N/A'}</td></tr>
        <tr><td>Nurse Aide HPRD</td><td>{format_metric_value(get_val('Nurse_Assistant_HPRD'), 'Nurse_Assistant_HPRD', 'N/A')}</td><td>#{rank_nurse_aide} of {total_states if rank_nurse_aide and total_states else 'N/A'}</td></tr>
        <tr><td>Contract Staff Percentage</td><td>{format_metric_value(get_val('Contract_Percentage'), 'Contract_Percentage', 'N/A')}%</td><td>—</td></tr>
    </table></div>
    </div>
    </details>
    {sff_section}
    {render_methodology_block()}
    {cta_section}
    </div>
    """
    
    # Page title and OG: clear "PBJ nursing home staffing" / "PBJ nursing home staffing data"
    page_title = f"{state_name} PBJ Nursing Home Staffing"
    
    # Build SEO description for OG/meta (clearly nursing home staffing data)
    total_hprd = format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')
    seo_description_parts = [
        f"{state_name} PBJ nursing home staffing data: {total_hprd} HPRD in {quarter} across {facility_count_display} nursing homes and {total_residents_display} residents."
    ]
    if rank_total_nurse and total_states:
        seo_description_parts.append(f"Ranked #{rank_total_nurse} of {total_states} states.")
    if macpac_standard:
        min_staffing = macpac_standard.get('Min_Staffing', '')
        if min_staffing:
            try:
                min_val = float(str(min_staffing).replace(' HPRD', ''))
                seo_description_parts.append(f"State minimum: {round_half_up(min_val, 2):.2f} HPRD.")
            except:
                pass
    seo_description_parts.append("CMS Payroll-Based Journal (PBJ) data.")
    seo_description = " ".join(seo_description_parts)
    
    # Canonical slug for URL (state page has its own URL, not under /pbjpedia)
    canonical_slug = get_canonical_slug(state_code)
    canonical_url = f"https://pbj320.com/state/{canonical_slug}"
    
    # Return content and metadata so caller can render state page with its own layout (separate from PBJpedia)
    return (content, page_title, seo_description, canonical_url)

def generate_region_page_html(region_num, region_data, states_in_region, state_data_list, quarter, rank=None, total_regions=None, sff_facilities=None, raw_quarter=None):
    """Generate HTML for CMS region page"""
    try:
        from pbj_format import format_metric_value
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{round_half_up(float(v), 2):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
    def fmt(val, decimals=2):
        try:
            if pd.isna(val) or val is None:
                return "N/A"
            r = round_half_up(float(val), decimals)
            return f"{r:.{decimals}f}" if r is not None else "N/A"
        except Exception:
            return "N/A"
    
    def get_val(key, default='N/A'):
        try:
            if isinstance(region_data, dict):
                return region_data.get(key, default)
            else:
                return getattr(region_data, key, default)
        except:
            return default
    
    region_name = get_val('REGION_NAME', f'Region {region_num}')
    region_full = get_val('REGION', f'Region {region_num}')
    
    # Get basics — never default facility_count to 0 when missing (litigation-grade: unknown = "—")
    _fc_raw = get_val('facility_count', None)
    try:
        facility_count = int(float(_fc_raw)) if _fc_raw is not None and str(_fc_raw).strip() != '' else None
    except (TypeError, ValueError):
        facility_count = None
    facility_count_display = f"{facility_count:,}" if facility_count is not None else "—"
    avg_daily_census_val = get_val('avg_daily_census', 0)
    try:
        avg_daily_census_float = float(avg_daily_census_val) if avg_daily_census_val != 'N/A' else 0
    except:
        avg_daily_census_float = 0
    
    # Calculate total residents: nursing homes × average daily census (only when both are known)
    total_residents = int(facility_count * avg_daily_census_float) if facility_count is not None and facility_count > 0 and avg_daily_census_float > 0 else 0
    total_residents_display = f"{total_residents:,}" if total_residents > 0 else "N/A"
    
    # Basics section
    basics_section = f"""
    <div class="infobox" style="width: 280px; margin-bottom: 1em;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><th colspan="2" scope="colgroup" style="background-color: #eaecf0; padding: 0.3em; text-align: center; border-bottom: 1px solid #a2a9b1;">{region_full} Overview</th></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">Nursing Homes</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{facility_count_display}</td></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">Total Residents</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{total_residents_display}</td></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">States</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{len(states_in_region)}</td></tr>
            <tr><td style="padding: 0.3em; font-weight: bold;">Reporting Quarter</td><td style="padding: 0.3em;">{quarter}</td></tr>
        </table>
    </div>
    """
    
    # SFF facilities section
    sff_section = ""
    if sff_facilities:
        sff_section = f"""
    <h2>Special Focus Facilities (SFF)</h2>
    <p>{region_full} has <strong>{len(sff_facilities)}</strong> {'facility' if len(sff_facilities) == 1 else 'facilities'} in the Special Focus Facility program across all states in the region.</p>
    """
    
    # Add ranking info
    ranking_info = ""
    if rank and total_regions:
        ranking_info = f"<p><strong>National Ranking:</strong> {region_full} ranks <strong>#{rank} of {total_regions}</strong> CMS regions for Total Nurse Staffing HPRD.</p>"
    
    # States table
    states_table = ""
    if state_data_list:
        # Sort states by Total Nurse HPRD (descending) for ranking
        sorted_states = sorted(state_data_list, key=lambda x: float(x['data'].get('Total_Nurse_HPRD', 0) if isinstance(x['data'], dict) else getattr(x['data'], 'Total_Nurse_HPRD', 0)), reverse=True)
        
        states_table = f"""
        <h2>States in {region_full}</h2>
        <table class="wikitable">
            <tr>
                <th scope="col">Rank</th>
                <th scope="col">State</th>
                <th scope="col">Total Nurse HPRD</th>
                <th scope="col">RN HPRD</th>
                <th scope="col">Direct Care HPRD</th>
                <th scope="col">Contract %</th>
                <th scope="col">Facilities</th>
            </tr>
        """
        for idx, item in enumerate(sorted_states, 1):
            state_info = item['info']
            state_data = item['data']
            state_code = state_info.get('State_Code', '')
            state_name = state_info.get('State_Name', '')
            
            def get_state_val(key, default='N/A'):
                try:
                    if isinstance(state_data, dict):
                        return state_data.get(key, default)
                    else:
                        return getattr(state_data, key, default)
                except:
                    return default
            
            facility_count_val = get_state_val('facility_count', 0)
            try:
                facility_count_int = int(float(facility_count_val))
            except:
                facility_count_int = 0
            
            states_table += f"""
            <tr>
                <td><strong>{idx}</strong></td>
                <td><a href="/pbjpedia/state/{state_code}">{state_name}</a></td>
                <td>{format_metric_value(get_state_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')}</td>
                <td>{format_metric_value(get_state_val('RN_HPRD'), 'RN_HPRD', 'N/A')}</td>
                <td>{format_metric_value(get_state_val('Nurse_Care_HPRD'), 'Nurse_Care_HPRD', 'N/A')}</td>
                <td>{format_metric_value(get_state_val('Contract_Percentage'), 'Contract_Percentage', 'N/A')}%</td>
                <td>{facility_count_int}</td>
            </tr>
            """
        states_table += "</table>"
    
    content = f"""
    {basics_section}
    {ranking_info}
    <h2>Region-Wide Staffing Metrics ({quarter})</h2>
    <table class="wikitable">
        <tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">Median</th></tr>
        <tr><td>Total Nurse Staffing HPRD</td><td>{format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD', 'N/A')}</td><td>{format_metric_value(get_val('Total_Nurse_HPRD_Median'), 'Total_Nurse_HPRD', 'N/A')}</td></tr>
        <tr><td>RN HPRD</td><td>{format_metric_value(get_val('RN_HPRD'), 'RN_HPRD', 'N/A')}</td><td>{format_metric_value(get_val('RN_HPRD_Median'), 'RN_HPRD', 'N/A')}</td></tr>
        <tr><td>Direct Care Nurse HPRD</td><td>{format_metric_value(get_val('Nurse_Care_HPRD'), 'Nurse_Care_HPRD', 'N/A')}</td><td>{format_metric_value(get_val('Nurse_Care_HPRD_Median'), 'Nurse_Care_HPRD', 'N/A')}</td></tr>
        <tr><td>RN Direct Care HPRD</td><td>{format_metric_value(get_val('RN_Care_HPRD'), 'RN_Care_HPRD', 'N/A')}</td><td>{format_metric_value(get_val('RN_Care_HPRD_Median'), 'RN_Care_HPRD', 'N/A')}</td></tr>
        <tr><td>Nurse Aide HPRD</td><td>{format_metric_value(get_val('Nurse_Assistant_HPRD'), 'Nurse_Assistant_HPRD', 'N/A')}</td><td>{format_metric_value(get_val('Nurse_Assistant_HPRD_Median'), 'Nurse_Assistant_HPRD', 'N/A')}</td></tr>
        <tr><td>Contract Staff Percentage</td><td>{format_metric_value(get_val('Contract_Percentage'), 'Contract_Percentage', 'N/A')}%</td><td>{format_metric_value(get_val('Contract_Percentage_Median'), 'Contract_Percentage', 'N/A')}%</td></tr>
        <tr><td>Direct Care Percentage</td><td>{format_metric_value(get_val('Direct_Care_Percentage'), 'Contract_Percentage', 'N/A')}%</td><td>—</td></tr>
        <tr><td>Total RN Percentage</td><td>{format_metric_value(get_val('Total_RN_Percentage'), 'Contract_Percentage', 'N/A')}%</td><td>—</td></tr>
        <tr><td>Nurse Aide Percentage</td><td>{format_metric_value(get_val('Nurse_Aide_Percentage'), 'Contract_Percentage', 'N/A')}%</td><td>—</td></tr>
        <tr><td>Number of Facilities</td><td>{facility_count_display}</td><td>—</td></tr>
        <tr><td>Average Daily Census</td><td>{format_metric_value(get_val('avg_daily_census'), 'avg_daily_census', 'N/A')}</td><td>—</td></tr>
    </table>
    
    {states_table}
    
    {sff_section}
    
    <h2>Related PBJpedia Pages</h2>
    <ul>
        <li><a href="/pbjpedia/state-standards">State Staffing Standards</a> – Overview of federal and state minimum staffing requirements</li>
        <li><a href="/pbjpedia/metrics">PBJ Metrics</a> – Definitions of HPRD and other staffing measures</li>
        <li><a href="/pbjpedia/methodology">PBJ Methodology</a> – How PBJ data are collected and published</li>
    </ul>
    """
    
    return generate_dynamic_pbjpedia_page(f"{region_full} Nursing Home Staffing", f"region/{region_num}", content)

def get_pbjpedia_sidebar():
    """Get the PBJpedia sidebar navigation HTML"""
    return """
        <div id="mw-navigation">
            <h2>Navigation menu</h2>
            <div id="mw-panel">
                <div id="p-logo" role="banner">
                    <a href="/pbjpedia/overview" title="Visit the main page">
                        <div style="text-align: center; padding: 0.3em 0.2em;">
                            <img src="/pbj_favicon.png" alt="PBJ320" width="50" height="50" style="margin: 0 auto 0.1em; display: block; max-width: 50px; max-height: 50px;">
                            <div style="font-size: 0.9em; font-weight: bold; color: #0645ad; margin-top: 0;">PBJ320</div>
                        </div>
                    </a>
                </div>
                <div class="portal" role="navigation" id="p-navigation">
                    <div class="body">
                        <ul>
                            <li><a href="/pbjpedia/overview">Overview</a></li>
                            <li><a href="/pbjpedia/methodology">Methodology</a></li>
                            <li><a href="/pbjpedia/metrics">Metrics</a></li>
                            <li><a href="/pbjpedia/state-standards">State Standards</a></li>
                        </ul>
                    </div>
                </div>
                <div class="portal" role="navigation" id="p-tb">
                    <h3>PBJ320</h3>
                    <div class="body">
                        <ul>
                            <li><a href="/">Dashboard</a></li>
                            <li><a href="/insights">Insights</a></li>
                            <li><a href="/phoebe" class="external-link">PBJ Explained</a></li>
                        </ul>
                    </div>
                </div>
                <div class="portal" role="navigation" id="p-more">
                    <h3>More</h3>
                    <div class="body">
                        <ul>
                            <li><a href="/about">About</a></li>
                            <li><a href="#" class="pbj-contact-modal-trigger" aria-label="Open contact options (email or copy)">Contact</a></li>
                            <li><a href="https://www.320insight.com" target="_blank" class="external-link">320 Consulting</a></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    """

def generate_dynamic_pbjpedia_page(title, page_path, content, toc_html='', seo_description=None, og_title=None, og_description=None, og_image=None, canonical_url=None):
    """Generate Wikipedia-style HTML page with rigid CSS Grid layout"""
    sidebar_nav = get_pbjpedia_sidebar()
    
    # Move TOC to sidebar if it exists - extract just the UL from TOC
    sidebar_with_toc = sidebar_nav
    if toc_html:
        # Extract the UL content from TOC HTML
        toc_match = re.search(r'<ul[^>]*>(.*?)</ul>', toc_html, re.DOTALL)
        # TOC removed from sidebar per user request
        # if toc_match:
        #     ... (code disabled)
    
    # Set defaults for SEO
    meta_description = seo_description or f"Learn about {title} in PBJpedia, the comprehensive reference guide for Payroll-Based Journal nursing home staffing data."
    og_description_final = og_description or seo_description or f"Nursing home staffing data and analysis for {title} from PBJ320."
    canonical = canonical_url or f"https://pbj320.com/pbjpedia/{page_path}"
    og_image_tag = f'<meta property="og:image" content="{og_image}">' if og_image else ''
    twitter_image_tag = f'<meta name="twitter:image" content="{og_image}">' if og_image else ''
    
    return f"""<!DOCTYPE html>
<html lang="en" dir="ltr" class="client-nojs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="/pbj_favicon.png">
    <title>{og_title if og_title else title} | PBJ320</title>
    <meta name="description" content="{meta_description}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{og_title if og_title else title} | PBJ320">
    <meta property="og:description" content="{og_description_final}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:site_name" content="PBJ320">
    {og_image_tag}
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="{title} - PBJpedia | PBJ320">
    <meta name="twitter:description" content="{og_description_final}">
    {twitter_image_tag}
    <style>
        /* HARD RESET: Rigid CSS Grid Layout - No Floating, No Absolute Positioning */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Liberation Sans', sans-serif;
            font-size: 0.875em;
            line-height: 1.6;
            color: #202122;
            background-color: #f8f9fa;
        }}
        
        /* PAGE GRID: Sidebar | Article */
        .pbjpedia-page-container {{
            display: grid;
            grid-template-columns: 10em 1fr;
            min-height: 100vh;
        }}
        
        /* LEFT SIDEBAR - Fixed width, no floating */
        #mw-navigation {{
            grid-column: 1;
            background-color: #f8f9fa;
            border-right: 1px solid #a7d7f9;
            padding: 0.5em;
            font-size: 0.875em;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
        }}
        #mw-panel {{
            display: flex;
            flex-direction: column;
            gap: 0.5em;
        }}
        #p-logo {{
            margin-bottom: 0.5em;
        }}
        #p-logo a {{
            display: block;
            text-decoration: none;
            padding: 0.3em 0.2em;
            text-align: center;
        }}
        #p-logo img {{
            max-width: 50px;
            max-height: 50px;
            margin: 0 auto 0.1em;
            display: block;
        }}
        #p-logo > a > div > div:first-of-type {{
            font-size: 0.9em;
            font-weight: bold;
            color: #0645ad;
            margin-top: 0;
        }}
        .portal {{
            margin: 0.5em 0;
        }}
        .portal h3 {{
            font-size: 0.75em;
            color: #72777d;
            font-weight: 500;
            margin: 0 0 0.3em 0.7em;
            padding: 0.25em 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            pointer-events: none;
        }}
        .portal .body li a.external-link::after {{
            content: ' ↗';
            font-size: 0.8em;
            opacity: 0.7;
        }}
        .portal .body ul {{
            list-style: none;
            margin: 0;
            padding: 0.3em 0 0 0;
        }}
        .portal .body li {{
            line-height: 1.125em;
            margin: 0;
            padding: 0.25em 0;
            font-size: 0.85em;
        }}
        .portal .body li a {{
            color: #0645ad;
            text-decoration: none;
        }}
        .portal .body li a:hover {{
            text-decoration: underline;
        }}
        /* TOC in sidebar */
        #p-toc .body ul {{
            list-style: none;
            margin: 0;
            padding-left: 0.5em;
        }}
        #p-toc .body li {{
            font-size: 0.7em;
            line-height: 1.3;
        }}
        #mw-navigation h2 {{
            display: none;
        }}
        
        /* MAIN ARTICLE COLUMN */
        .mw-body {{
            grid-column: 2;
            background-color: #ffffff;
            border: 1px solid #a7d7f9;
            border-left: none;
            padding: 1em 1.5em;
            max-width: 100%;
            overflow-x: hidden;
        }}
        h1.firstHeading {{
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.25em;
            margin-bottom: 0.3em;
            font-size: 1.8em;
            font-weight: 600;
            margin-top: 0;
        }}
        #siteSub {{
            font-size: 0.9em;
            color: #202122;
            margin-bottom: 0.5em;
            font-weight: 500;
        }}
        .breadcrumb {{
            font-size: 0.875em;
            margin-bottom: 0.5em;
            color: #54595d;
        }}
        .breadcrumb a {{
            color: #0645ad;
        }}
        .breadcrumb span {{
            margin: 0 0.3em;
            color: #54595d;
        }}
        .breadcrumb span:last-of-type {{
            color: #202122;
            font-weight: 500;
        }}
        h2 {{
            margin-bottom: 0.5em;
            padding-top: 0.8em;
            padding-bottom: 0.25em;
            border-bottom: 2px solid #a7d7f9;
            font-size: 1.5em;
            font-weight: normal;
            margin-top: 1em;
            page-break-after: avoid;  /* Polish: Prevent page breaks after headings */
        }}
        h3 {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 0.4em;
            margin-top: 1em;
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.2em;
        }}
        h4 {{
            font-size: 1.05em;
            font-weight: bold;
            margin-bottom: 0.3em;
            margin-top: 0.8em;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 0.15em;
        }}
        p {{
            margin: 0.4em 0 0.5em 0;
            line-height: 1.6;
        }}
        .mw-parser-output ul,
        .mw-parser-output ol {{
            margin: 0.3em 0 0.5em 1.6em;
            padding-left: 0.4em;
            line-height: 1.6;
        }}
        .mw-parser-output li {{
            margin: 0.25em 0;
            padding-left: 0.2em;
        }}
        table.wikitable {{
            border: 1px solid #a2a9b1;
            border-collapse: collapse;
            background-color: #f8f9fa;
            margin: 1em 0;
            width: 100%;
            max-width: 100%;
            empty-cells: show;  /* Polish: Show empty cells for clarity */
        }}
        table.wikitable th,
        table.wikitable td {{
            border: 1px solid #a2a9b1;
            padding: 0.4em 0.6em;
            word-wrap: break-word;
        }}
        table.wikitable th {{
            background-color: #eaecf0;
            text-align: center;
            font-weight: bold;
        }}
        table.wikitable th[scope="col"] {{
            /* Accessibility: scope attribute for screen readers */
        }}
        table.wikitable th[scope="row"] {{
            text-align: left;
        }}
        .infobox {{
            float: right;
            margin-top: 0.5em;
            margin-bottom: 1em;
            margin-left: 1em;
            margin-right: 0;
            width: 280px;
            clear: right;
        }}
        .infobox table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .infobox th {{
            background-color: #eaecf0;
            padding: 0.4em;
            text-align: center;
            font-weight: bold;
        }}
        .infobox td {{
            padding: 0.4em;
            border: 1px solid #a2a9b1;
        }}
        .categories {{
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #a7d7f9;
            font-size: 0.875em;
            color: #54595d;
        }}
        .categories a {{
            color: #0645ad;
            margin-right: 0.5em;
        }}
        .edit-link {{
            font-size: 0.875em;
            color: #54595d;
            margin-top: 1em;
        }}
        .mw-footer {{
            grid-column: 2;
            margin-top: 0;
            margin-left: 0;
            padding: 0.75em 1.5em 0.75em 1.5em;
            border-top: 1px solid #a7d7f9;
            background-color: #f8f9fa;
            font-size: 0.75em;
            clear: both;
        }}
        .mw-footer ul {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .mw-footer li {{
            color: #0645ad;
            margin: 0;
            padding: 0.3em 0;
        }}
        .sff-facilities-list {{
            margin: 0.3em 0 0.5em 1.6em !important;
            padding-left: 0.4em !important;
            list-style-position: outside !important;
        }}
        .sff-facilities-list li {{
            margin: 0.3em 0 !important;
            padding-left: 0.2em !important;
        }}
        
        /* Mobile header - hidden on desktop */
        .mobile-header {{
            display: none;
        }}
        
        /* MOBILE: Stack layout */
        @media screen and (max-width: 800px) {{
            .pbjpedia-page-container {{
                grid-template-columns: 1fr;
            }}
            
            /* Mobile header - visible on mobile */
            .mobile-header {{
                display: block;
                position: sticky;
                top: 0;
                z-index: 1000;
                background-color: #f8f9fa;
                border-bottom: 1px solid #a7d7f9;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .mobile-header-content {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.5em 1em;
                max-width: 100%;
            }}
            .mobile-logo-link {{
                display: flex;
                align-items: center;
                gap: 0.5em;
                text-decoration: none;
                color: #0645ad;
            }}
            .mobile-logo-link img {{
                display: block;
            }}
            .mobile-logo-text {{
                font-size: 0.9em;
                font-weight: bold;
            }}
            .mobile-page-title {{
                flex: 1;
                margin: 0 0.5em;
                font-size: 1em;
                font-weight: normal;
                color: #202122;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .mobile-menu-toggle {{
                background: none;
                border: none;
                padding: 0.5em;
                cursor: pointer;
                min-width: 44px;
                min-height: 44px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }}
            .mobile-menu-toggle:focus {{
                outline: 2px solid #0645ad;
                outline-offset: 2px;
            }}
            .hamburger-icon {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                width: 24px;
                height: 18px;
                position: relative;
                justify-content: center;
            }}
            .hamburger-line {{
                width: 100%;
                height: 2px;
                background-color: #0645ad;
                transition: all 0.3s ease;
            }}
            body.mobile-menu-open .hamburger-icon {{
                gap: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(1) {{
                transform: rotate(45deg) translateY(0px);
            }}
            body.mobile-menu-open .hamburger-line:nth-child(2) {{
                opacity: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(3) {{
                transform: rotate(-45deg) translateY(-2px);
            }}
            
            /* Hide sidebar by default on mobile */
            #mw-navigation {{
                display: none;
                grid-column: 1;
                position: fixed;
                top: 56px;
                left: 0;
                width: 100%;
                max-width: 280px;
                height: calc(100vh - 56px);
                z-index: 1001;
                background-color: #ffffff;
                border-right: 1px solid #a7d7f9;
                overflow-y: auto;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                box-shadow: 2px 0 12px rgba(0,0,0,0.15);
                padding-top: 0;
            }}
            
            /* Show sidebar when menu is open */
            body.mobile-menu-open #mw-navigation {{
                display: block;
                transform: translateX(0);
            }}
            
            /* Simplify mobile menu - hide logo section when open */
            body.mobile-menu-open #p-logo {{
                display: none;
            }}
            
            /* Simplify mobile menu - reduce padding and spacing, ensure top is visible */
            body.mobile-menu-open #mw-panel {{
                padding: 0.8em 0.5em 1em 0.5em;
                margin-top: 0;
            }}
            
            /* Ensure first portal has enough top space */
            body.mobile-menu-open .portal:first-of-type {{
                margin-top: 0;
                padding-top: 0;
            }}
            
            /* Hide less important menu items on mobile */
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/non-nursing-staff"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/data-limitations"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/history"] {{
                display: none;
            }}
            
            body.mobile-menu-open .portal {{
                margin: 0;
                padding-top: 0.8em;
                padding-bottom: 0.2em;
            }}
            
            body.mobile-menu-open .portal:first-of-type {{
                padding-top: 0;
            }}
            
            body.mobile-menu-open .portal:not(:first-of-type) {{
                border-top: 1px solid #d0d0d0;
                margin-top: 0;
            }}
            
            body.mobile-menu-open .portal h3 {{
                font-size: 0.75em;
                margin-bottom: 0.4em;
                padding-bottom: 0;
                border-bottom: none;
                font-weight: 500;
                color: #72777d;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                pointer-events: none;
            }}
            
            body.mobile-menu-open .portal .body li a.external-link::after {{
                content: ' ↗';
                font-size: 0.8em;
                opacity: 0.7;
            }}
            
            body.mobile-menu-open .portal .body ul {{
                padding: 0;
                margin: 0;
            }}
            
            body.mobile-menu-open .portal .body li {{
                padding: 0;
                margin: 0;
                border-bottom: 1px solid #e8e8e8;
            }}
            
            /* Remove border from last item in each section - this prevents double divider with next section */
            body.mobile-menu-open .portal .body li:last-child {{
                border-bottom: none !important;
            }}
            
            body.mobile-menu-open .portal .body li a {{
                font-size: 1em;
                padding: 0.5em 0.5em;
                border-radius: 0;
                display: block;
            }}
            
            body.mobile-menu-open .portal .body li a:hover {{
                background-color: #f0f0f0;
            }}
            
            /* Overlay when menu is open */
            body.mobile-menu-open::before {{
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
                z-index: 998;
            }}
            
            .mw-body {{
                grid-column: 1;
                padding: 1em;
            }}
            
            .mw-footer {{
                grid-column: 1;
            }}
            
            table.wikitable {{
                font-size: 0.85em;
                display: block;
                overflow-x: auto;
            }}
            h1.firstHeading {{
                font-size: 1.5em;
                font-weight: 600;
            }}
            h2 {{
                font-size: 1.3em;
            }}
            
            /* Improve touch targets */
            .portal .body li a {{
                padding: 0.5em 0;
                display: block;
                min-height: 44px;
                display: flex;
                align-items: center;
            }}
        }}
    </style>
</head>
<body class="mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject page-{page_path.replace('/', '_')} skin-vector action-view">
    <nav class="navbar" style="background:#0f172a;padding:0;position:sticky;top:0;z-index:1001;box-shadow:0 2px 10px rgba(0,0,0,0.1);border-bottom:2px solid #1e40af;">
        <div class="nav-container" style="max-width:1200px;margin:0 auto;padding:0 20px;display:flex;justify-content:space-between;align-items:center;height:60px;">
            <div class="nav-brand" style="display:flex;align-items:center;color:white;font-size:1.2rem;font-weight:700;">
                <a href="/" style="color:inherit;text-decoration:none;display:flex;align-items:center;">
                    <img src="/pbj_favicon.png" alt="PBJ320" style="height:32px;margin-right:8px;">
                    <span><span style="color:white;">PBJ</span><span style="color:#60a5fa;">320</span></span>
                </a>
            </div>
            <div class="nav-menu" id="navMenu" style="display:flex;gap:30px;align-items:center;">
                <a href="/about" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">About</a>
                <a href="/insights" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Insights</a>
                <a href="/report" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Report</a>
                <a href="/phoebe" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">PBJ Explained</a>
                <a href="/owners" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Ownership</a>
            </div>
        </div>
    </nav>
    <div class="mobile-header">
        <div class="mobile-header-content">
            <a href="/pbjpedia/overview" class="mobile-logo-link">
                <img src="/pbj_favicon.png" alt="PBJ320" width="32" height="32">
                <span class="mobile-logo-text">PBJpedia</span>
            </a>
            <h1 class="mobile-page-title">PBJpedia: PBJ Nursing Home Staffing</h1>
            <button class="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="mw-navigation">
                <span class="hamburger-icon">
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                </span>
            </button>
        </div>
    </div>
    <div class="pbjpedia-page-container">
        {sidebar_with_toc}
        <div class="mw-body" role="main" id="content">
            <h1 id="firstHeading" class="firstHeading"><span class="mw-headline">{title}</span></h1>
            <div class="breadcrumb noprint">
                <a href="/pbjpedia/overview">PBJpedia</a> <span>›</span> <span>{title}</span>
            </div>
            <div class="mw-parser-output">
                {content}
            </div>
            <div class="categories">
                <strong>Categories:</strong>
                <a href="/pbjpedia/overview">PBJ Data</a>
                <a href="/pbjpedia/overview">Nursing Home Staffing</a>
                <a href="/pbjpedia/overview">CMS Regulations</a>
            </div>
        </div>
        <div class="mw-footer">
        <p style="margin: 0.2em 0; line-height: 1.4;">
            Updated {get_latest_update_month_year()}.<br>
            <a href="/about">About PBJ320</a> | 
            <a href="/pbjpedia/overview">PBJpedia Overview</a> | 
            <a href="https://www.320insight.com" target="_blank">320 Consulting</a> | 
            <a href="/about?open=contact">Contact</a> | <a href="tel:+19298084996">(929) 804-4996</a> (text preferred)
        </p>
    </div>
    <script>
        (function() {{
            var menuToggle = document.querySelector('.mobile-menu-toggle');
            var body = document.body;
            
            if (menuToggle) {{
                menuToggle.addEventListener('click', function() {{
                    var isOpen = body.classList.contains('mobile-menu-open');
                    
                    if (isOpen) {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }} else {{
                        body.classList.add('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'true');
                        body.style.overflow = 'hidden';
                        // Scroll menu to top when opening
                        var nav = document.querySelector('#mw-navigation');
                        if (nav) {{
                            nav.scrollTop = 0;
                        }}
                    }}
                }});
                
                // Close menu when clicking outside navigation
                document.addEventListener('click', function(e) {{
                    if (body.classList.contains('mobile-menu-open')) {{
                        var nav = document.querySelector('#mw-navigation');
                        var isClickInsideNav = nav && nav.contains(e.target);
                        var isClickOnToggle = menuToggle.contains(e.target);
                        
                        if (!isClickInsideNav && !isClickOnToggle) {{
                            // Close menu if clicking outside (on overlay or content area)
                            body.classList.remove('mobile-menu-open');
                            menuToggle.setAttribute('aria-expanded', 'false');
                            body.style.overflow = '';
                        }}
                    }}
                }});
                
                // Close menu when clicking navigation links
                var navLinks = document.querySelectorAll('#mw-navigation a');
                navLinks.forEach(function(link) {{
                    link.addEventListener('click', function() {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }});
                }});
                
                // Keyboard support
                menuToggle.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        menuToggle.click();
                    }}
                }});
            }}
        }})();
    </script>
    <script src="/pbj-site-universal.js"></script>
</body>
</html>"""

# PBJpedia routes - serve markdown files as HTML
@app.route('/pbjpedia')
@app.route('/pbjpedia/')
def pbjpedia_index():
    """Redirect to PBJpedia overview page"""
    from flask import redirect
    return redirect('/pbjpedia/overview')


# Per-CCN provider page HTML cache (short TTL for fast repeat loads)
_PROVIDER_PAGE_CACHE = {}
_PROVIDER_PAGE_CACHE_TTL = 120  # seconds

# Canonical provider/state/entity pages (pbj320.com/provider/xxx, /state/pa, /entity/123)
def _provider_page_impl(ccn):
    from flask import abort
    if not HAS_PANDAS:
        return "Pandas not available. Provider pages require pandas.", 503
    prov = normalize_ccn(ccn)
    if not prov:
        abort(404)
    now = time.time()
    cached = _PROVIDER_PAGE_CACHE.get(prov)
    if cached is not None:
        cached_at, html = cached
        if now - cached_at < _PROVIDER_PAGE_CACHE_TTL:
            return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    facility_df = load_facility_quarterly_for_provider(prov)
    if facility_df is None or facility_df.empty:
        abort(404)
    provider_info = load_provider_info()
    provider_info_row = provider_info.get(prov, {})
    html = generate_provider_page_html(prov, facility_df, provider_info_row)
    _PROVIDER_PAGE_CACHE[prov] = (now, html)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

def _state_page_impl(state_slug):
    canonical_slug, state_code = resolve_state_slug(state_slug)
    if not canonical_slug or not state_code:
        from flask import abort
        abort(404)
    return generate_state_page(state_code)

def _entity_page_impl(entity_id):
    from flask import abort
    if not HAS_PANDAS:
        return "Pandas not available. Entity pages require pandas.", 503
    entity_name, facilities = load_entity_facilities(entity_id)
    if not facilities:
        abort(404)
    chain_perf = load_chain_performance()
    chain_row = chain_perf.get(int(entity_id)) if chain_perf else None
    html = generate_entity_page_html(entity_id, entity_name, facilities, chain_row=chain_row)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/provider/<ccn>')
def provider_page(ccn):
    return _provider_page_impl(ccn)

@app.route('/state/<state_slug>')
def state_page(state_slug):
    return _state_page_impl(state_slug)

@app.route('/entity/<int:entity_id>')
def entity_page(entity_id):
    return _entity_page_impl(entity_id)


# Legacy /test/... URLs redirect to canonical
@app.route('/test/provider/<ccn>')
def test_provider_redirect(ccn):
    from flask import redirect
    return redirect(f'/provider/{ccn}', code=301)

@app.route('/test/state/<state_slug>')
def test_state_redirect(state_slug):
    from flask import redirect
    canonical_slug, state_code = resolve_state_slug(state_slug)
    if not canonical_slug:
        from flask import abort
        abort(404)
    return redirect(f'/state/{canonical_slug}', code=301)

@app.route('/test/entity/<int:entity_id>')
def test_entity_redirect(entity_id):
    from flask import redirect
    return redirect(f'/entity/{entity_id}', code=301)


# Dynamic state and region pages - must come before catch-all route
# Dynamic state canonical pages - must come after specific routes but before PBJpedia routes
# This route handles /tn, /new-york, etc. and redirects aliases to canonical
@app.route('/<state_slug>')
def canonical_state_page(state_slug):
    """Canonical state page route (e.g., /tn, /new-york)"""
    # Handle JSON files first - serve them directly
    if state_slug.endswith('.json'):
        json_path = os.path.join(APP_ROOT, state_slug)
        if os.path.isfile(json_path):
            return send_file(json_path, mimetype='application/json')
        from flask import abort
        abort(404)
    
    # Handle image files - serve them directly
    if state_slug.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg')):
        image_path = os.path.join(APP_ROOT, state_slug)
        if os.path.isfile(image_path):
            mimetype = 'image/png' if state_slug.endswith('.png') else 'image/jpeg' if state_slug.endswith(('.jpg', '.jpeg')) else 'image/gif' if state_slug.endswith('.gif') else 'image/webp' if state_slug.endswith('.webp') else 'image/svg+xml' if state_slug.endswith('.svg') else 'image/x-icon'
            return send_file(image_path, mimetype=mimetype)
        from flask import abort
        abort(404)
    
    # Handle CSV files - serve them directly
    if state_slug.endswith('.csv'):
        csv_path = os.path.join(APP_ROOT, state_slug)
        if os.path.isfile(csv_path):
            return send_file(csv_path, mimetype='text/csv')
        from flask import abort
        abort(404)
    
    # Check if this is a known route first (avoid conflicts)
    known_routes = ['pbjpedia', 'wrapped', 'api', 'static', 'favicon.ico', 'robots.txt', 'sitemap.xml', 'owner', 'owners', 'ownership', 'provider', 'state', 'entity']
    if state_slug.lower() in known_routes:
        # Let Flask continue to next route by aborting (Flask will handle 404)
        from flask import abort
        abort(404)
    
    canonical_slug, state_code = resolve_state_slug(state_slug)
    
    if not canonical_slug or not state_code:
        return f"State '{state_slug}' not found", 404
    
    # Redirect to canonical state URL (e.g. /state/new-york, /state/pa)
    return redirect(f'/state/{canonical_slug}', code=302)

@app.route('/pbjpedia/state/<state_identifier>')
def pbjpedia_state_page(state_identifier):
    """Legacy PBJpedia state page route - redirects to canonical"""
    canonical_slug, state_code = resolve_state_slug(state_identifier)
    
    if not canonical_slug or not state_code:
        return f"State '{state_identifier}' not found", 404
    
    # Redirect to canonical state URL
    return redirect(f'/state/{canonical_slug}', code=301)

def generate_state_page(state_code):
    """Generate state page with all data - used by both canonical and legacy routes"""
    if not HAS_PANDAS:
        return "Pandas not available. Dynamic state pages require pandas.", 503
    
    state_name = STATE_CODE_TO_NAME.get(state_code, state_code)
    
    # Load data
    state_df = load_csv_data('state_quarterly_metrics.csv')
    region_mapping_df = load_csv_data('cms_region_state_mapping.csv')
    
    # Load MACPAC standards from JSON (preferred) or CSV (fallback)
    macpac_standard = None
    state_standards_json_path = 'pbj-wrapped/public/data/json/state_standards.json'
    if os.path.exists(state_standards_json_path):
        try:
            with open(state_standards_json_path, 'r', encoding='utf-8') as f:
                state_standards_json = json.load(f)
                # JSON is keyed by lowercase state code
                state_code_lower = state_code.lower()
                if state_code_lower in state_standards_json:
                    macpac_standard = state_standards_json[state_code_lower]
        except Exception as e:
            print(f"Error loading state standards JSON: {e}")
    
    # Fallback to CSV if JSON not available
    if macpac_standard is None:
        macpac_df = load_csv_data('macpac_state_standards_clean.csv')
        if macpac_df is not None and not macpac_df.empty:
            try:
                # Try matching by state name first (case-insensitive)
                macpac_row = macpac_df[macpac_df['State'].str.upper().str.strip() == state_name.upper().strip()]
                if macpac_row.empty:
                    # Try matching by state code if there's a State_Code column
                    if 'State_Code' in macpac_df.columns:
                        macpac_row = macpac_df[macpac_df['State_Code'].str.upper().str.strip() == state_code.upper().strip()]
                if not macpac_row.empty:
                    macpac_standard = macpac_row.iloc[0].to_dict()
            except Exception as e:
                print(f"Error loading MACPAC standard from CSV for {state_name}: {e}")
    
    if state_df is None:
        return "State data not available", 503
    
    # Use canonical latest quarter so all pages (state, provider, entity) show the same quarter
    latest_quarter = get_canonical_latest_quarter()
    state_data = state_df[state_df['STATE'] == state_code]
    if state_data.empty:
        return f"No data found for {state_name}", 404
    # Prefer row for canonical quarter; only if this state has no row for it use this state's max quarter
    if latest_quarter is not None and not state_data[state_data['CY_Qtr'] == latest_quarter].empty:
        latest_data = state_data[state_data['CY_Qtr'] == latest_quarter].iloc[0]
    else:
        latest_quarter = get_latest_quarter(state_data)
        latest_data = state_data[state_data['CY_Qtr'] == latest_quarter].iloc[0] if latest_quarter is not None else state_data.iloc[-1]
    formatted_quarter = format_quarter(latest_quarter)
    
    # Load SFF facilities for this state
    sff_facilities = load_sff_facilities()
    state_sff = [f for f in sff_facilities if f.get('state', '').upper() == state_code]
    
    # Rankings use same canonical quarter; exclude PR (51 = 50 states + DC)
    _rank_df = state_df[state_df['STATE'].astype(str).str.strip().str.upper().isin(STATES_FOR_RANKING)]
    latest_all_states = _rank_df[_rank_df['CY_Qtr'] == latest_quarter] if latest_quarter is not None else _rank_df
    total_states = len(latest_all_states)
    
    # Rank by Total Nurse HPRD (higher is better)
    latest_all_states_sorted = latest_all_states.sort_values('Total_Nurse_HPRD', ascending=False).reset_index(drop=True)
    state_rank_total = None
    if not latest_all_states_sorted[latest_all_states_sorted['STATE'] == state_code].empty:
        state_rank_total = latest_all_states_sorted[latest_all_states_sorted['STATE'] == state_code].index[0] + 1
    
    # Rank by RN HPRD
    latest_all_states_sorted_rn = latest_all_states.sort_values('RN_HPRD', ascending=False).reset_index(drop=True)
    state_rank_rn = None
    if not latest_all_states_sorted_rn[latest_all_states_sorted_rn['STATE'] == state_code].empty:
        state_rank_rn = latest_all_states_sorted_rn[latest_all_states_sorted_rn['STATE'] == state_code].index[0] + 1
    
    
    # Get region info
    region_info = None
    if region_mapping_df is not None:
        region_row = region_mapping_df[region_mapping_df['State_Code'] == state_code]
        if not region_row.empty:
            region_info = region_row.iloc[0]
    
    # Load state agency contact info
    state_contacts = load_state_agency_contact()
    contact_info = state_contacts.get(state_code, None)
    
    # Generate state page content (state has its own page; PBJpedia is separate)
    content, page_title, seo_description, canonical_url = generate_state_page_html(
        state_name, state_code, latest_data, macpac_standard, region_info, 
        formatted_quarter, state_rank_total, state_rank_rn, total_states, 
        state_sff, latest_quarter, contact_info
    )
    layout = get_pbj_site_layout(page_title, seo_description, canonical_url)
    html_content = layout['head'] + layout['nav'] + layout['content_open'] + content + layout['content_close']
    if HAS_CSRF and generate_csrf:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', generate_csrf())
    else:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', '')
    return html_content, 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

@app.route('/pbjpedia/region/<region_number>')
def pbjpedia_region_page(region_number):
    """Dynamic CMS region page with region-wide metrics and state breakdowns"""
    if not HAS_PANDAS:
        return "Pandas not available. Dynamic region pages require pandas.", 503
    
    try:
        region_num = int(region_number)
    except ValueError:
        return f"Invalid region number: {region_number}", 404
    
    # Load data
    region_df = load_csv_data('cms_region_quarterly_metrics.csv')
    state_df = load_csv_data('state_quarterly_metrics.csv')
    region_mapping_df = load_csv_data('cms_region_state_mapping.csv')
    
    if region_df is None:
        return "Region data not available", 503
    
    # Get region data
    region_data = region_df[region_df['REGION_NUMBER'] == region_num]
    if region_data.empty:
        return f"Region {region_num} not found", 404
    
    latest_quarter = get_latest_quarter(region_data)
    latest_region_data = region_data[region_data['CY_Qtr'] == latest_quarter].iloc[0] if latest_quarter else region_data.iloc[-1]
    formatted_quarter = format_quarter(latest_quarter)
    
    # Get states in this region FIRST (before using it)
    states_in_region = []
    if region_mapping_df is not None:
        region_states = region_mapping_df[region_mapping_df['CMS_Region_Number'] == region_num]
        states_in_region = region_states.to_dict('records')
    
    # Load SFF facilities for states in this region
    sff_facilities = load_sff_facilities()
    region_sff = []
    if states_in_region:
        state_codes = [s.get('State_Code', '') for s in states_in_region]
        region_sff = [f for f in sff_facilities if f.get('state', '').upper() in state_codes]
    
    # Calculate region ranking
    all_regions = region_df[region_df['CY_Qtr'] == latest_quarter] if latest_quarter else region_df
    total_regions = len(all_regions)
    all_regions_sorted = all_regions.sort_values('Total_Nurse_HPRD', ascending=False).reset_index(drop=True)
    region_rank = None
    if not all_regions_sorted[all_regions_sorted['REGION_NUMBER'] == region_num].empty:
        region_rank = all_regions_sorted[all_regions_sorted['REGION_NUMBER'] == region_num].index[0] + 1
    
    # Get state data for states in this region
    state_data_list = []
    if state_df is not None and states_in_region:
        for state_info in states_in_region:
            state_code = state_info.get('State_Code', '')
            state_data = state_df[(state_df['STATE'] == state_code) & (state_df['CY_Qtr'] == latest_quarter)]
            if not state_data.empty:
                state_data_list.append({
                    'info': state_info,
                    'data': state_data.iloc[0]
                })
    
    # Generate HTML content
    html_content = generate_region_page_html(region_num, latest_region_data, states_in_region, state_data_list, formatted_quarter, region_rank, total_regions, region_sff, latest_quarter)
    
    return html_content, 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

@app.route('/pbjpedia/<path:page>')
def pbjpedia_page(page):
    """Serve PBJpedia markdown files as HTML"""
    if not HAS_MARKDOWN:
        return "PBJpedia is not available. Please install markdown: pip install markdown", 503
    
    pbjpedia_dir = 'PBJPedia'
    
    # Map page names to filenames
    page_map = {
        'overview': 'pbjpedia-overview.md',
        'methodology': 'pbjpedia-methodology.md',
        'metrics': 'pbjpedia-metrics.md',
        'state-standards': 'pbjpedia-state-standards.md',
        'non-nursing-staff': 'pbjpedia-non-nursing-staff.md',
        'data-limitations': 'pbjpedia-data-limitations.md',
        'history': 'pbjpedia-history.md',
    }
    
    # Handle both with and without .md extension
    if page.endswith('.md'):
        filename = page
    else:
        filename = page_map.get(page, f'pbjpedia-{page}.md')
    
    file_path = os.path.join(pbjpedia_dir, filename)
    
    if not os.path.exists(file_path):
        from flask import abort
        abort(404)
    
    try:
        # Read markdown file
        with open(file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Extract title from markdown
        title = page.replace('-', ' ').title()
        for line in md_content.split('\n'):
            if line.strip().startswith('# '):
                title = line.strip()[2:].strip()
                # Remove anchor tags if any
                title = re.sub(r'<a[^>]*></a>', '', title)
                break
        
        # Special case: overview page should use full name
        if page == 'overview':
            title = 'Payroll-Based Journal Nursing Home Staffing Data'
        
        # Convert markdown to HTML with TOC
        if markdown is None:
            return "Markdown module not available", 503
        
        # Configure markdown with TOC extension
        def slugify(value, separator='-'):
            """Create URL-friendly slug from heading text"""
            value = re.sub(r'[^\w\s-]', '', value).strip().lower()
            value = re.sub(r'[-\s]+', separator, value)
            return value
        
        md_ext = markdown.Markdown(extensions=[
            'extra',
            'codehilite', 
            'toc',
            'fenced_code',
            'tables',
            'attr_list'
        ], extension_configs={
            'toc': {
                'permalink': False,
                'baselevel': 2,
                'slugify': slugify
            }
        })
        
        html_content = md_ext.convert(md_content)
        toc = md_ext.toc if hasattr(md_ext, 'toc') and md_ext.toc else ''
        
        # Special handling for overview page - rewrite top content
        if page == 'overview':
            # Get US chart HTML first
            us_chart = generate_us_chart_html() or ""
            
            # Replace the first paragraph(s) with the new content, including chart
            new_intro = f"""<p>The <strong>Payroll-Based Journal (PBJ)</strong> is a federally mandated staffing data reporting system for U.S. nursing homes. Medicare- and Medicaid-certified long-term care facilities are required to submit daily, employee-level staffing data each quarter using payroll and timekeeping records. Facilities report hours worked for each staff member, including agency and contract staff, by job category and date. Submissions are considered timely only if received within 45 days after the end of the quarter. PBJ data are auditable and are used by the Centers for Medicare & Medicaid Services (CMS) for public reporting, enforcement activities, and research.</p>

<p>PBJ replaced earlier staffing surveys that captured staffing over a limited reporting period. The system became mandatory on July 1, 2016, and CMS began releasing public use files in 2017. PBJ is the most detailed national dataset on nursing home staffing currently available, but it reflects only paid hours and does not include information such as shift start times, wages, or clinical outcomes.</p>

{us_chart}

<h2>Why PBJ Exists</h2>

<p>Before PBJ, nursing home staffing data were collected through periodic surveys, including the CMS-671 and CMS-672 forms. These surveys typically measured staffing during a two-week period and relied on facility-reported counts. Section 6106 of the Affordable Care Act directed CMS to establish an auditable, standardized system for collecting staffing data based on payroll records. PBJ fulfills this requirement by requiring facilities to submit daily staffing data and by making public use files available for analysis by regulators, researchers, and the public.</p>"""
            
            # Find and replace the first few paragraphs and "Why PBJ Exists" section
            # Remove everything from start until after "Why PBJ Exists" section
            html_content = re.sub(
                r'^.*?<h2[^>]*>Why PBJ Exists</h2>.*?</p>',
                new_intro,
                html_content,
                flags=re.DOTALL | re.IGNORECASE
            )
        
        # AGGRESSIVELY Remove ALL H1 tags from markdown content (we use the page title instead)
        # This prevents duplicate titles - remove ALL h1 tags, no exceptions
        html_content = re.sub(r'<h1[^>]*>.*?</h1>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove ANY heading (h1-h6) that contains the title text
        title_escaped = re.escape(title)
        html_content = re.sub(rf'<h[1-6][^>]*>.*?{title_escaped}.*?</h[1-6]>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove any paragraph that contains the full title
        html_content = re.sub(rf'<p><strong>{title_escaped}</strong>.*?</p>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        html_content = re.sub(rf'<p>{title_escaped}</p>\s*', '', html_content, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        # Remove first element if it's the title (any tag)
        # Check if the very first element after whitespace is the title
        html_content_stripped = html_content.lstrip()
        title_patterns = [
            rf'^<h[1-6][^>]*>.*?{re.escape(title)}.*?</h[1-6]>',
            rf'^<p><strong>.*?{re.escape(title)}.*?</strong>.*?</p>',
            rf'^<p>.*?{re.escape(title)}.*?</p>'
        ]
        for pattern in title_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        # Ensure all headings have IDs for section jumping and TOC
        # Add IDs to any headings that don't have them
        heading_pattern = r'<h([2-4])([^>]*)>(.*?)</h[2-4]>'
        def add_id_if_missing(match):
            level = match.group(1)
            attrs = match.group(2)
            text = match.group(3)
            text_clean = re.sub(r'<[^>]+>', '', text).strip()
            
            if 'id=' not in attrs:
                anchor = slugify(text_clean)
                return f'<h{level}{attrs} id="{anchor}">{text}</h{level}>'
            return match.group(0)
        
        html_content = re.sub(heading_pattern, add_id_if_missing, html_content)
        
        # Now extract headings for TOC (after IDs are added)
        headings_for_toc = re.findall(r'<h([2-4])[^>]*id="([^"]*)"[^>]*>(.*?)</h[2-4]>', html_content)
        
        # Convert markdown links to pbjpedia URLs
        # Replace ./pbjpedia-*.md links with /pbjpedia/* URLs
        html_content = re.sub(
            r'href="\./pbjpedia-([^"]+)\.md"',
            lambda m: f'href="/pbjpedia/{m.group(1)}"',
            html_content
        )
        # Also handle links without ./
        html_content = re.sub(
            r'href="pbjpedia-([^"]+)\.md"',
            lambda m: f'href="/pbjpedia/{m.group(1)}"',
            html_content
        )
        
        # Stub notices removed per user request
        
        # Improve reference formatting
        # Wrap references section in proper div if it exists
        if re.search(r'<h2[^>]*>References</h2>', html_content, re.IGNORECASE):
            # Find the References heading and wrap content until next h2 or end
            html_content = re.sub(
                r'(<h2[^>]*>References</h2>)(.*?)(?=<h2|</div>|$)',
                r'<div class="references">\1\2</div>',
                html_content,
                flags=re.IGNORECASE | re.DOTALL
            )
        
        # Generate table of contents from headings
        toc_html = ''
        # First try to use markdown TOC extension output
        if toc and '<ul' in toc:
            # Extract just the UL element for sidebar
            toc_match = re.search(r'<ul[^>]*>.*?</ul>', toc, re.DOTALL)
            if toc_match:
                toc_html = toc_match.group(0)  # Full UL element
            else:
                toc_html = toc
        
        # If no TOC from extension, generate manually from headings we just extracted
        if not toc_html:
            if headings_for_toc:
                headings = headings_for_toc
            else:
                # Fallback: extract headings again if headings_for_toc is empty
                headings = re.findall(r'<h([2-4])[^>]*id="([^"]*)"[^>]*>(.*?)</h[2-4]>', html_content)
            
            if headings:
                toc_items = []
                prev_level = 2
                counters = {2: 0, 3: 0, 4: 0}
                
                for level, anchor, text in headings:
                    level_int = int(level)
                    # Clean text from HTML tags
                    text_clean = re.sub(r'<[^>]+>', '', text).strip()
                    
                    # Reset lower level counters when going up a level
                    if level_int < prev_level:
                        for l in range(level_int + 1, 5):
                            counters[l] = 0
                    
                    # Increment counter for this level
                    counters[level_int] += 1
                    
                    # Build number string (e.g., "1.2.3")
                    number_parts = []
                    for l in range(2, level_int + 1):
                        number_parts.append(str(counters[l]))
                    number_str = '.'.join(number_parts)
                    
                    # Handle nested lists
                    if level_int > prev_level:
                        # Open new nested ul
                        for _ in range(prev_level, level_int):
                            toc_items.append('<ul>')
                    elif level_int < prev_level:
                        # Close nested uls
                        for _ in range(level_int, prev_level):
                            toc_items.append('</li></ul>')
                        toc_items.append('</li>')
                    elif prev_level == level_int and toc_items:
                        # Same level, close previous item
                        toc_items.append('</li>')
                    
                    toc_items.append(f'<li class="toclevel-{level_int}"><a href="#{anchor}"><span class="tocnumber">{number_str}</span> <span class="toctext">{text_clean}</span></a>')
                    prev_level = level_int
                
                # Close any remaining open tags
                if toc_items:
                    toc_items.append('</li>')
                    for _ in range(2, prev_level):
                        toc_items.append('</ul>')
                    
                    toc_html = f'<ul>{"".join(toc_items)}</ul>'
        
        # Generate sidebar navigation
        sidebar_nav = get_pbjpedia_sidebar()
        
        # Move TOC to sidebar if it exists
        sidebar_with_toc = sidebar_nav
        if toc_html and toc_html.strip():
            # Extract UL content - handle both full UL or just content
            toc_match = re.search(r'<ul[^>]*>(.*?)</ul>', toc_html, re.DOTALL)
            if toc_match:
                toc_ul_content = toc_match.group(1)
                toc_in_sidebar = f'<div class="portal" role="navigation" id="p-toc"><h3>Contents</h3><div class="body"><ul>{toc_ul_content}</ul></div></div>'
            elif toc_html.strip().startswith('<ul'):
                # Already a full UL, wrap it
                toc_in_sidebar = f'<div class="portal" role="navigation" id="p-toc"><h3>Contents</h3><div class="body">{toc_html}</div></div>'
            else:
                toc_in_sidebar = None
            
            # TOC removed from sidebar per user request
            # if toc_in_sidebar and page != 'overview':
            #     ... (code disabled)
        
        # Wikipedia-style HTML template with rigid CSS Grid
        html_page = f"""<!DOCTYPE html>
<html lang="en" dir="ltr" class="client-nojs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="/pbj_favicon.png">
    <title>{title} - PBJpedia | PBJ320</title>
    <meta name="description" content="Learn about {title} in PBJpedia, the comprehensive reference guide for Payroll-Based Journal nursing home staffing data.">
    <link rel="canonical" href="https://pbj320.com/pbjpedia/{page}">
    <style>
        /* HARD RESET: Rigid CSS Grid Layout - No Floating, No Absolute Positioning */
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Liberation Sans', sans-serif;
            font-size: 0.875em;
            line-height: 1.6;
            color: #202122;
            background-color: #f8f9fa;
        }}
        
        /* PAGE GRID: Sidebar | Article */
        .pbjpedia-page-container {{
            display: grid;
            grid-template-columns: 10em 1fr;
            min-height: 100vh;
        }}
        
        /* LEFT SIDEBAR - Fixed width, no floating */
        #mw-navigation {{
            grid-column: 1;
            background-color: #f8f9fa;
            border-right: 1px solid #a7d7f9;
            padding: 0.5em;
            font-size: 0.875em;
            position: sticky;
            top: 0;
            height: 100vh;
            overflow-y: auto;
        }}
        #mw-panel {{
            display: flex;
            flex-direction: column;
            gap: 0.5em;
        }}
        #p-logo {{
            margin-bottom: 0.5em;
        }}
        #p-logo a {{
            display: block;
            text-decoration: none;
            padding: 0.3em 0.2em;
            text-align: center;
        }}
        #p-logo img {{
            max-width: 50px;
            max-height: 50px;
            margin: 0 auto 0.1em;
            display: block;
        }}
        #p-logo > a > div > div:first-of-type {{
            font-size: 0.9em;
            font-weight: bold;
            color: #0645ad;
            margin-top: 0;
        }}
        .portal {{
            margin: 0.5em 0;
        }}
        .portal h3 {{
            font-size: 0.75em;
            color: #72777d;
            font-weight: 500;
            margin: 0 0 0.3em 0.7em;
            padding: 0.25em 0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            pointer-events: none;
        }}
        .portal .body li a.external-link::after {{
            content: ' ↗';
            font-size: 0.8em;
            opacity: 0.7;
        }}
        .portal .body ul {{
            list-style: none;
            margin: 0;
            padding: 0.3em 0 0 0;
        }}
        .portal .body li {{
            line-height: 1.125em;
            margin: 0;
            padding: 0.25em 0;
            font-size: 0.85em;
        }}
        .portal .body li a {{
            color: #0645ad;
            text-decoration: none;
        }}
        .portal .body li a:hover {{
            text-decoration: underline;
        }}
        /* TOC in sidebar - Wikipedia style, larger and at top */
        #p-toc {{
            margin-bottom: 1em;
        }}
        #p-toc h3 {{
            font-size: 0.875em;
            font-weight: bold;
            color: #202122;
            margin: 0 0 0.3em 0.7em;
            padding: 0.25em 0;
            border-bottom: 1px solid #a7d7f9;
        }}
        #p-toc .body ul {{
            list-style: none;
            margin: 0;
            padding-left: 0.5em;
        }}
        #p-toc .body li {{
            font-size: 0.875em;
            line-height: 1.4;
            margin: 0.2em 0;
        }}
        #p-toc .body li a {{
            color: #0645ad;
        }}
        #mw-navigation h2 {{
            display: none;
        }}
        
        /* MAIN ARTICLE COLUMN */
        .mw-body {{
            grid-column: 2;
            background-color: #ffffff;
            border: 1px solid #a7d7f9;
            border-left: none;
            padding: 1em 1.5em;
            max-width: 100%;
            overflow-x: hidden;
        }}
        h1.firstHeading {{
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.25em;
            margin-bottom: 0.3em;
            font-size: 1.8em;
            font-weight: 600;
            margin-top: 0;
        }}
        #siteSub {{
            font-size: 0.9em;
            color: #202122;
            margin-bottom: 0.5em;
            font-weight: 500;
        }}
        .breadcrumb {{
            font-size: 0.875em;
            margin-bottom: 0.5em;
            color: #54595d;
        }}
        .breadcrumb a {{
            color: #0645ad;
        }}
        .breadcrumb span {{
            margin: 0 0.3em;
            color: #54595d;
        }}
        .breadcrumb span:last-of-type {{
            color: #202122;
            font-weight: 500;
        }}
        h2 {{
            margin-bottom: 0.5em;
            padding-top: 0.8em;
            padding-bottom: 0.25em;
            border-bottom: 2px solid #a7d7f9;
            font-size: 1.5em;
            font-weight: normal;
            line-height: 1.4;
            margin-top: 1em;
            clear: both;
        }}
        h3 {{
            font-size: 1.2em;
            font-weight: bold;
            line-height: 1.4;
            margin-bottom: 0.4em;
            margin-top: 1em;
            border-bottom: 1px solid #a7d7f9;
            padding-bottom: 0.2em;
        }}
        h4 {{
            font-size: 1.05em;
            font-weight: bold;
            margin-bottom: 0.3em;
            margin-top: 0.8em;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 0.15em;
        }}
        p {{
            margin: 0.4em 0 0.5em 0;
            line-height: 1.6;
        }}
        /* List styling - proper indentation - IMPORTANT: Override any markdown defaults */
        .mw-parser-output ul,
        .mw-parser-output ol,
        ul:not(.portal .body ul):not(.toc ul):not(.mw-footer ul):not(.sff-facilities-list),
        ol:not(.portal .body ol):not(.toc ol):not(.mw-footer ol) {{
            margin: 0.3em 0 0.5em 1.6em !important;
            padding-left: 0.4em !important;
            line-height: 1.6;
            list-style-position: outside;
        }}
        .sff-facilities-list {{
            margin: 0.3em 0 0.5em 1.6em !important;
            padding-left: 0.4em !important;
            list-style-position: outside !important;
        }}
        .sff-facilities-list li {{
            margin: 0.3em 0 !important;
            padding-left: 0.2em !important;
        }}
        .mw-parser-output li,
        li:not(.portal .body li):not(.toc li):not(.mw-footer li) {{
            margin: 0.25em 0 !important;
            padding-left: 0.2em !important;
        }}
        .mw-parser-output ul ul,
        .mw-parser-output ol ol,
        .mw-parser-output ul ol,
        .mw-parser-output ol ul,
        ul ul:not(.portal .body ul):not(.toc ul),
        ol ol:not(.portal .body ol):not(.toc ol) {{
            margin: 0.2em 0 0.2em 1.2em !important;
        }}
        a {{
            color: #0645ad;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        a:visited {{
            color: #0b0080;
        }}
        /* Keyboard navigation improvements */
        a:focus,
        button:focus {{
            outline: 2px solid #0645ad;
            outline-offset: 2px;
        }}
        /* Skip to content link for accessibility */
        .skip-to-content {{
            position: absolute;
            left: -9999px;
            z-index: 999;
        }}
        .skip-to-content:focus {{
            left: 1em;
            top: 1em;
            background: #0645ad;
            color: white;
            padding: 0.5em 1em;
            text-decoration: none;
            border-radius: 3px;
        }}
        /* Back to top link */
        .back-to-top {{
            display: block;
            text-align: center;
            margin: 2em 0 1em;
            padding: 0.5em;
            font-size: 0.9em;
        }}
        .back-to-top a {{
            color: #0645ad;
            text-decoration: none;
        }}
        .back-to-top a:hover {{
            text-decoration: underline;
        }}
        /* Smooth scroll behavior */
        html {{
            scroll-behavior: smooth;
        }}
        /* Print stylesheet */
        @media print {{
            .pbjpedia-page-container {{
                grid-template-columns: 1fr;
            }}
            #mw-navigation,
            .breadcrumb,
            .categories,
            .edit-link,
            .back-to-top,
            .mw-footer {{
                display: none;
            }}
            .mw-body {{
                border: none;
                padding: 0;
            }}
            a {{
                color: #000;
                text-decoration: underline;
            }}
            a[href^="http"]:after {{
                content: " (" attr(href) ")";
                font-size: 0.8em;
            }}
        }}
        /* TOC removed from article - now in sidebar */
        .toctitle {{
            text-align: center;
            direction: ltr;
        }}
        .toctitle h2 {{
            display: inline;
            border: 0;
            padding: 0;
            font-size: 100%;
            font-weight: bold;
            margin: 0;
        }}
        .toc ul {{
            list-style-type: none;
            list-style-image: none;
            margin-left: 0;
            padding-left: 0;
            text-align: left;
        }}
        .toc ul ul {{
            margin: 0 0 0 2em;
        }}
        .toc li {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .toc a {{
            display: block;
            padding: 0.1em 0;
        }}
        .tocnumber {{
            color: #222;
            padding-right: 0.5em;
        }}
        .toctext {{
            color: #0645ad;
        }}
        table {{
            border: 1px solid #a2a9b1;
            border-collapse: collapse;
            background-color: #f8f9fa;
            color: black;
            margin: 1em 0;
            font-size: 100%;
        }}
        table.wikitable > tr > th,
        table.wikitable > tr > td,
        table.wikitable > * > tr > th,
        table.wikitable > * > tr > td {{
            border: 1px solid #a2a9b1;
            padding: 0.2em 0.4em;
        }}
        table.wikitable > tr > th,
        table.wikitable > * > tr > th {{
            background-color: #eaecf0;
            text-align: center;
            font-weight: bold;
        }}
        code {{
            background-color: #eaecf0;
            border: 1px solid #c8ccd1;
            border-radius: 2px;
            padding: 1px 4px;
            font-family: 'Courier New', 'Courier', monospace;
        }}
        pre {{
            padding: 1em;
            border: 1px solid #c8ccd1;
            background-color: #f8f9fa;
            overflow-x: auto;
        }}
        .mw-footer {{
            grid-column: 2;
            margin-top: 0;
            margin-left: 0;
            padding: 0.75em 1.5em 0.75em 1.5em;
            border-top: 1px solid #a7d7f9;
            background-color: #f8f9fa;
            font-size: 0.75em;
            clear: both;
        }}
        .mw-footer ul {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .mw-footer li {{
            color: #0645ad;
            margin: 0;
            padding: 0.3em 0;
        }}
        .mw-footer p {{
            margin: 0.2em 0;
            line-height: 1.4;
        }}
        .infobox {{
            border: 1px solid #a7d7f9;
            border-spacing: 3px;
            background-color: #f8f9fa;
            color: black;
            margin-top: 0.5em;
            margin-bottom: 1em;
            margin-left: 1em;
            margin-right: 0;
            padding: 0.2em;
            float: right;
            clear: right;
            font-size: 88%;
            line-height: 1.5em;
            width: 22em;
        }}
        .breadcrumb {{
            font-size: 0.875em;
            margin-bottom: 0.5em;
            color: #54595d;
        }}
        .breadcrumb a {{
            color: #0645ad;
        }}
        .breadcrumb span {{
            margin: 0 0.3em;
            color: #54595d;
        }}
        .breadcrumb span:last-of-type {{
            color: #202122;
            font-weight: 500;
        }}
        .stub {{
            background-color: #fef6e7;
            border: 1px solid #fc3;
            padding: 0.5em;
            margin: 1em 0;
            font-size: 0.9em;
        }}
        .stub strong {{
            color: #d97706;
        }}
        .categories {{
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #a7d7f9;
            font-size: 0.875em;
            color: #54595d;
        }}
        .categories a {{
            color: #0645ad;
            margin-right: 0.5em;
        }}
        .references {{
            font-size: 0.9em;
        }}
        .references ol {{
            margin: 0.5em 0;
            padding-left: 2em;
        }}
        .references li {{
            margin: 0.3em 0;
        }}
        
        /* Mobile header - hidden on desktop */
        .mobile-header {{
            display: none;
        }}
        
        /* MOBILE: Stack layout */
        @media screen and (max-width: 800px) {{
            .pbjpedia-page-container {{
                grid-template-columns: 1fr;
            }}
            
            /* Mobile header - visible on mobile */
            .mobile-header {{
                display: block;
                position: sticky;
                top: 0;
                z-index: 1000;
                background-color: #f8f9fa;
                border-bottom: 1px solid #a7d7f9;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .mobile-header-content {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.5em 1em;
                max-width: 100%;
            }}
            .mobile-logo-link {{
                display: flex;
                align-items: center;
                gap: 0.5em;
                text-decoration: none;
                color: #0645ad;
            }}
            .mobile-logo-link img {{
                display: block;
            }}
            .mobile-logo-text {{
                font-size: 0.9em;
                font-weight: bold;
            }}
            .mobile-page-title {{
                flex: 1;
                margin: 0 0.5em;
                font-size: 1em;
                font-weight: normal;
                color: #202122;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .mobile-menu-toggle {{
                background: none;
                border: none;
                padding: 0.5em;
                cursor: pointer;
                min-width: 44px;
                min-height: 44px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }}
            .mobile-menu-toggle:focus {{
                outline: 2px solid #0645ad;
                outline-offset: 2px;
            }}
            .hamburger-icon {{
                display: flex;
                flex-direction: column;
                gap: 4px;
                width: 24px;
                height: 18px;
                position: relative;
                justify-content: center;
            }}
            .hamburger-line {{
                width: 100%;
                height: 2px;
                background-color: #0645ad;
                transition: all 0.3s ease;
            }}
            body.mobile-menu-open .hamburger-icon {{
                gap: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(1) {{
                transform: rotate(45deg) translateY(0px);
            }}
            body.mobile-menu-open .hamburger-line:nth-child(2) {{
                opacity: 0;
            }}
            body.mobile-menu-open .hamburger-line:nth-child(3) {{
                transform: rotate(-45deg) translateY(-2px);
            }}
            
            /* Hide sidebar by default on mobile */
            #mw-navigation {{
                display: none;
                grid-column: 1;
                position: fixed;
                top: 56px;
                left: 0;
                width: 100%;
                max-width: 280px;
                height: calc(100vh - 56px);
                z-index: 1001;
                background-color: #ffffff;
                border-right: 1px solid #a7d7f9;
                overflow-y: auto;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
                box-shadow: 2px 0 12px rgba(0,0,0,0.15);
                padding-top: 0;
            }}
            
            /* Show sidebar when menu is open */
            body.mobile-menu-open #mw-navigation {{
                display: block;
                transform: translateX(0);
            }}
            
            /* Simplify mobile menu - hide logo section when open */
            body.mobile-menu-open #p-logo {{
                display: none;
            }}
            
            /* Simplify mobile menu - reduce padding and spacing, ensure top is visible */
            body.mobile-menu-open #mw-panel {{
                padding: 0.8em 0.5em 1em 0.5em;
                margin-top: 0;
            }}
            
            /* Ensure first portal has enough top space */
            body.mobile-menu-open .portal:first-of-type {{
                margin-top: 0;
                padding-top: 0;
            }}
            
            /* Hide less important menu items on mobile */
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/non-nursing-staff"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/data-limitations"],
            body.mobile-menu-open .portal .body li a[href="/pbjpedia/history"] {{
                display: none;
            }}
            
            body.mobile-menu-open .portal {{
                margin: 0;
                padding-top: 0.8em;
                padding-bottom: 0.2em;
            }}
            
            body.mobile-menu-open .portal:first-of-type {{
                padding-top: 0;
            }}
            
            body.mobile-menu-open .portal:not(:first-of-type) {{
                border-top: 1px solid #d0d0d0;
                margin-top: 0;
            }}
            
            body.mobile-menu-open .portal h3 {{
                font-size: 0.75em;
                margin-bottom: 0.4em;
                padding-bottom: 0;
                border-bottom: none;
                font-weight: 500;
                color: #72777d;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                pointer-events: none;
            }}
            
            body.mobile-menu-open .portal .body li a.external-link::after {{
                content: ' ↗';
                font-size: 0.8em;
                opacity: 0.7;
            }}
            
            body.mobile-menu-open .portal .body ul {{
                padding: 0;
                margin: 0;
            }}
            
            body.mobile-menu-open .portal .body li {{
                padding: 0;
                margin: 0;
                border-bottom: 1px solid #e8e8e8;
            }}
            
            /* Remove border from last item in each section - this prevents double divider with next section */
            body.mobile-menu-open .portal .body li:last-child {{
                border-bottom: none !important;
            }}
            
            body.mobile-menu-open .portal .body li a {{
                font-size: 1em;
                padding: 0.5em 0.5em;
                border-radius: 0;
                display: block;
            }}
            
            body.mobile-menu-open .portal .body li a:hover {{
                background-color: #f0f0f0;
            }}
            
            /* Overlay when menu is open */
            body.mobile-menu-open::before {{
                content: '';
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
                z-index: 998;
            }}
            
            .mw-body {{
                grid-column: 1;
                padding: 1em;
            }}
            
            .mw-footer {{
                grid-column: 1;
            }}
            
            table.wikitable {{
                font-size: 0.85em;
                display: block;
                overflow-x: auto;
            }}
            h1.firstHeading {{
                font-size: 1.5em;
                font-weight: 600;
            }}
            h2 {{
                font-size: 1.3em;
            }}
            
            /* Improve touch targets */
            .portal .body li a {{
                padding: 0.5em 0;
                display: block;
                min-height: 44px;
                display: flex;
                align-items: center;
            }}
        }}
        /* Readability improvements */
        .mw-parser-output {{
            max-width: 100%;
            word-wrap: break-word;
        }}
        table.wikitable {{
            width: 100%;
            max-width: 100%;
            table-layout: auto;
        }}
        table.wikitable th, table.wikitable td {{
            word-wrap: break-word;
            hyphens: auto;
        }}
        /* Better spacing for content sections */
        .mw-parser-output > * {{
            margin-bottom: 0.8em;
        }}
        .mw-parser-output > h2:first-child {{
            margin-top: 0;
        }}
        /* Improve external link visibility */
        a[href^="http"]:not([href*="pbj320.com"]):not([href*="pbj320.com"]) {{
            /* External links - could add icon if desired */
        }}
        /* Improve definition lists if used */
        dl {{
            margin: 0.5em 0;
        }}
        dt {{
            font-weight: bold;
            margin-top: 0.5em;
        }}
        dd {{
            margin-left: 1.5em;
            margin-bottom: 0.5em;
        }}
    </style>
</head>
<body class="mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-0 ns-subject page-{page.replace('-', '_')} rootpage-{page.replace('-', '_')} skin-vector action-view">
    <nav class="navbar" style="background:#0f172a;padding:0;position:sticky;top:0;z-index:1001;box-shadow:0 2px 10px rgba(0,0,0,0.1);border-bottom:2px solid #1e40af;">
        <div class="nav-container" style="max-width:1200px;margin:0 auto;padding:0 20px;display:flex;justify-content:space-between;align-items:center;height:60px;">
            <div class="nav-brand" style="display:flex;align-items:center;color:white;font-size:1.2rem;font-weight:700;">
                <a href="/" style="color:inherit;text-decoration:none;display:flex;align-items:center;">
                    <img src="/pbj_favicon.png" alt="PBJ320" style="height:32px;margin-right:8px;">
                    <span><span style="color:white;">PBJ</span><span style="color:#60a5fa;">320</span></span>
                </a>
            </div>
            <div class="nav-menu" id="navMenu" style="display:flex;gap:30px;align-items:center;">
                <a href="/about" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">About</a>
                <a href="/insights" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Insights</a>
                <a href="/report" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Report</a>
                <a href="/phoebe" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">PBJ Explained</a>
                <a href="/owners" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Ownership</a>
            </div>
        </div>
    </nav>
    <div class="mobile-header">
        <div class="mobile-header-content">
            <a href="/pbjpedia/overview" class="mobile-logo-link">
                <img src="/pbj_favicon.png" alt="PBJ320" width="32" height="32">
                <span class="mobile-logo-text">PBJpedia</span>
            </a>
            <button class="mobile-menu-toggle" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="mw-navigation">
                <span class="hamburger-icon">
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                    <span class="hamburger-line"></span>
                </span>
            </button>
        </div>
    </div>
    <div class="pbjpedia-page-container">
        {sidebar_with_toc}
        <div class="mw-body" role="main" id="content">
            <h1 id="firstHeading" class="firstHeading"><span class="mw-headline">{title}</span></h1>
            <div class="breadcrumb noprint">
                <a href="/pbjpedia/overview">PBJpedia</a> <span>›</span> <span>{title}</span>
            </div>
            <div class="mw-parser-output">
                {html_content}
            </div>
            <div style="background-color: #f8f9fa; border: 1px solid #a7d7f9; border-radius: 4px; padding: 1.5em; margin: 2em 0;">
                <h3 style="margin-top: 0; font-size: 1.1em;">Custom PBJ Analysis for Attorneys & Journalists</h3>
                <p>320 Consulting offers custom reports and dashboards with daily, position-level analysis and data visualizations tied to ratings, enforcement, and other critical metrics to support your casework and advocacy. Check out a <a href="https://pbj320-395258.vercel.app/" target="_blank" rel="noopener">sample dashboard</a>.</p>
                <p><strong>Contact:</strong> <a href="/about?open=contact">Contact form</a> | <a href="tel:+19298084996">(929) 804-4996</a> (text preferred)</p>
                <p style="margin-bottom: 0;"><strong>Journalists:</strong> If you're working on a story, I'm happy to share data or walk you through it.</p>
            </div>
            <div class="categories">
                <strong>Categories:</strong>
                <a href="/pbjpedia/overview">PBJ Data</a>
                <a href="/pbjpedia/overview">Nursing Home Staffing</a>
                <a href="/pbjpedia/overview">CMS Regulations</a>
            </div>
        </div>
        <div class="mw-footer">
        <p style="margin: 0.2em 0; line-height: 1.4;">
            Updated {get_latest_update_month_year()}.<br>
            <a href="/about">About PBJ320</a> | 
            <a href="/pbjpedia/overview">PBJpedia Overview</a> | 
            <a href="https://www.320insight.com" target="_blank">320 Consulting</a> | 
            <a href="/about?open=contact">Contact</a> | <a href="tel:+19298084996">(929) 804-4996</a> (text preferred)
        </p>
    </div>
    <script>
        (function() {{
            var menuToggle = document.querySelector('.mobile-menu-toggle');
            var body = document.body;
            
            if (menuToggle) {{
                menuToggle.addEventListener('click', function() {{
                    var isOpen = body.classList.contains('mobile-menu-open');
                    
                    if (isOpen) {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }} else {{
                        body.classList.add('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'true');
                        body.style.overflow = 'hidden';
                        // Scroll menu to top when opening
                        var nav = document.querySelector('#mw-navigation');
                        if (nav) {{
                            nav.scrollTop = 0;
                        }}
                    }}
                }});
                
                // Close menu when clicking outside navigation
                document.addEventListener('click', function(e) {{
                    if (body.classList.contains('mobile-menu-open')) {{
                        var nav = document.querySelector('#mw-navigation');
                        var isClickInsideNav = nav && nav.contains(e.target);
                        var isClickOnToggle = menuToggle.contains(e.target);
                        
                        if (!isClickInsideNav && !isClickOnToggle) {{
                            // Close menu if clicking outside (on overlay or content area)
                            body.classList.remove('mobile-menu-open');
                            menuToggle.setAttribute('aria-expanded', 'false');
                            body.style.overflow = '';
                        }}
                    }}
                }});
                
                // Close menu when clicking navigation links
                var navLinks = document.querySelectorAll('#mw-navigation a');
                navLinks.forEach(function(link) {{
                    link.addEventListener('click', function() {{
                        body.classList.remove('mobile-menu-open');
                        menuToggle.setAttribute('aria-expanded', 'false');
                        body.style.overflow = '';
                    }});
                }});
                
                // Keyboard support
                menuToggle.addEventListener('keydown', function(e) {{
                    if (e.key === 'Enter' || e.key === ' ') {{
                        e.preventDefault();
                        menuToggle.click();
                    }}
                }});
            }}
        }})();
    </script>
</body>
</html>"""
        
        return html_page, 200, {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    
    except Exception as e:
        return f"Error rendering page: {str(e)}", 500

# Serve favicon with no-cache headers
@app.route('/favicon.ico')
def favicon():
    """Serve favicon with no-cache headers to ensure updates are visible"""
    favicon_path = 'pbj_favicon.png'
    if os.path.exists(favicon_path):
        response = send_file(favicon_path, mimetype='image/png')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    # Fallback to favicon.ico if it exists
    if os.path.exists('favicon.ico'):
        response = send_file('favicon.ico', mimetype='image/x-icon')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    from flask import abort
    abort(404)

# Serve pbj_favicon.png with no-cache headers
@app.route('/pbj_favicon.png')
def pbj_favicon():
    """Serve pbj_favicon.png with no-cache headers"""
    favicon_path = 'pbj_favicon.png'
    if os.path.exists(favicon_path):
        response = send_file(favicon_path, mimetype='image/png')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    from flask import abort
    abort(404)

# Serve images from pbj-wrapped/dist/images (for SEO meta tags)
# This route MUST come before the catch-all route to work correctly
@app.route('/images/<path:filename>')
def images_files(filename):
    """Serve image files from pbj-wrapped/dist/images directory"""
    images_dir = os.path.join('pbj-wrapped', 'dist', 'images')
    file_path = os.path.join(images_dir, filename)
    
    if os.path.isfile(file_path):
        # Serve with proper MIME type
        return send_file(file_path, mimetype='image/png')
    else:
        # Fallback to root directory for backward compatibility
        root_file = os.path.join('.', filename)
        if os.path.isfile(root_file) and filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            return send_file(root_file, mimetype='image/png')
        from flask import abort
        abort(404)

# Serve data files: try pbj-wrapped/dist/data, then public/data, then cwd, then repo root for CSVs
# This route MUST come before the catch-all route to work correctly
@app.route('/data', defaults={'path': ''})
@app.route('/data/', defaults={'path': ''})
@app.route('/data/<path:path>')
def data_files(path):
    """Serve data files; try dist/data, public/data (APP_ROOT and cwd), then APP_ROOT for known CSVs."""
    if '..' in path or path.startswith('/'):
        from flask import abort
        abort(404)
    path_normalized = path.strip('/')
    if not path_normalized and path:
        path_normalized = path

    # Build list of data dirs: APP_ROOT-relative first, then cwd-relative (for deploy where cwd may differ)
    cwd = None
    try:
        cwd = os.getcwd()
    except Exception:
        pass
    _data_dirs = [
        os.path.join(APP_ROOT, 'pbj-wrapped', 'dist', 'data'),
        os.path.join(APP_ROOT, 'pbj-wrapped', 'public', 'data'),
    ]
    if cwd and cwd != APP_ROOT:
        _data_dirs.append(os.path.join(cwd, 'pbj-wrapped', 'dist', 'data'))
        _data_dirs.append(os.path.join(cwd, 'pbj-wrapped', 'public', 'data'))

    for data_dir in _data_dirs:
        if not data_dir:
            continue
        file_path = os.path.join(data_dir, path_normalized) if path_normalized else None
        if path_normalized and file_path and os.path.isfile(file_path):
            if path_normalized.endswith('.json'):
                return send_file(file_path, mimetype='application/json')
            if path_normalized.endswith('.csv'):
                return send_file(file_path, mimetype='text/csv')
            return send_from_directory(data_dir, path_normalized)

    # Fallback: serve known CSVs from repo root or data/ subdir (same files as root /filename.csv)
    if path_normalized.endswith('.csv'):
        filename = os.path.basename(path_normalized)
        allowed_csv = {
            'facility_quarterly_metrics.csv', 'state_quarterly_metrics.csv', 'national_quarterly_metrics.csv',
            'cms_region_quarterly_metrics.csv', 'cms_region_state_mapping.csv', 'provider_info_combined.csv',
        }
        if filename in allowed_csv:
            # Try multiple locations so /data/X.csv works wherever CSVs are deployed (root or data/)
            candidates = [
                os.path.join(APP_ROOT, filename),
                os.path.join(APP_ROOT, 'data', filename),
            ]
            if cwd:
                candidates.extend([
                    os.path.join(cwd, filename),
                    os.path.join(cwd, 'data', filename),
                ])
            for root_path in candidates:
                if root_path and os.path.isfile(root_path):
                    return send_file(root_path, mimetype='text/csv')

    from flask import abort
    abort(404)

# Serve data for SFF app: /sff/data/... same as /data/... (SPA may request from either)
@app.route('/sff/data', defaults={'path': ''})
@app.route('/sff/data/', defaults={'path': ''})
@app.route('/sff/data/<path:path>')
def sff_data_files(path):
    """Serve data files for SFF route; same as data_files() so /sff/data/json/... works."""
    return data_files(path)

# Serve SFF routes at /sff (for pbj320.com/sff/)
@app.route('/sff')
@app.route('/sff/')
def sff_index():
    """Serve the wrapped React app index page for SFF routes with server-rendered SEO metadata"""
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        # Fallback to static file if template rendering fails
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    else:
        return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/sff/<path:path>')
def sff_static(path):
    """Serve static files and handle SPA routing for SFF"""
    wrapped_dist = os.path.join('pbj-wrapped', 'dist')
    wrapped_public = os.path.join('pbj-wrapped', 'public')
    file_path = os.path.join(wrapped_dist, path)
    if os.path.isfile(file_path):
        # Serve the static file with proper MIME types
        if path.endswith('.js'):
            return send_file(file_path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_file(file_path, mimetype='text/css')
        elif path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
            return send_file(file_path)
        else:
            return send_from_directory(wrapped_dist, path)
    # SFF JSON: if not in dist, serve from public so updated data works without rebuild
    if path in ('sff-facilities.json', 'sff-candidate-months.json'):
        public_path = os.path.join(wrapped_public, path)
        if os.path.isfile(public_path):
            return send_file(public_path, mimetype='application/json')
    # For SPA routing, serve index.html
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join(wrapped_dist, 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

# Serve wrapped app at /wrapped (for pbj320.com/wrapped/)
@app.route('/wrapped')
@app.route('/wrapped/')
def wrapped_index():
    """Serve the wrapped React app index page with server-rendered SEO metadata"""
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        # Fallback to static file if template rendering fails
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    else:
        return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/wrapped/<path:path>')
def wrapped_static(path):
    """Serve static files and handle SPA routing for wrapped"""
    wrapped_dist = os.path.join('pbj-wrapped', 'dist')
    wrapped_public = os.path.join('pbj-wrapped', 'public')
    file_path = os.path.join(wrapped_dist, path)
    if os.path.isfile(file_path):
        # Serve the static file with proper MIME types
        if path.endswith('.js'):
            return send_file(file_path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_file(file_path, mimetype='text/css')
        elif path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
            return send_file(file_path)
        else:
            return send_from_directory(wrapped_dist, path)
    # SFF JSON: if not in dist, serve from public so updated data works without rebuild
    if path in ('sff-facilities.json', 'sff-candidate-months.json'):
        public_path = os.path.join(wrapped_public, path)
        if os.path.isfile(public_path):
            return send_file(public_path, mimetype='application/json')
    # For SPA routing, serve index.html for any route with server-rendered SEO metadata
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join(wrapped_dist, 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

# Legacy route: Serve pbj-wrapped app (for backward compatibility)
@app.route('/pbj-wrapped')
@app.route('/pbj-wrapped/')
def pbj_wrapped_index():
    """Serve the pbj-wrapped React app index page (legacy) with server-rendered SEO metadata"""
    seo = get_seo_metadata(request.path)
    assets = get_built_assets()
    try:
        return render_template('wrapped_index.html', seo=seo, assets=assets)
    except Exception as e:
        # Fallback to static file if template rendering fails
        print(f"Warning: Template rendering failed: {e}, falling back to static file")
    wrapped_index = os.path.join('pbj-wrapped', 'dist', 'index.html')
    if os.path.exists(wrapped_index):
        return send_file(wrapped_index, mimetype='text/html')
    else:
        return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/pbj-wrapped/<path:path>')
def pbj_wrapped_static(path):
    """Serve static files and handle SPA routing for pbj-wrapped (legacy)"""
    wrapped_dist = os.path.join('pbj-wrapped', 'dist')
    
    # Check if it's a static asset (has extension)
    file_path = os.path.join(wrapped_dist, path)
    if os.path.isfile(file_path):
        # Serve the static file with proper MIME types
        if path.endswith('.js'):
            return send_file(file_path, mimetype='application/javascript')
        elif path.endswith('.css'):
            return send_file(file_path, mimetype='text/css')
        elif path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.ttf', '.eot')):
            return send_file(file_path)
        else:
            return send_from_directory(wrapped_dist, path)
    else:
        # For SPA routing, serve index.html for any route with server-rendered SEO metadata
        # This allows React Router to handle client-side routing
        seo = get_seo_metadata(request.path)
        assets = get_built_assets()
        try:
            return render_template('wrapped_index.html', seo=seo, assets=assets)
        except Exception as e:
            # Fallback to static file if template rendering fails
            print(f"Warning: Template rendering failed: {e}, falling back to static file")
        wrapped_index = os.path.join(wrapped_dist, 'index.html')
        if os.path.exists(wrapped_index):
            return send_file(wrapped_index, mimetype='text/html')
        else:
            return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

@app.route('/<path:filename>')
def static_files(filename):
    # Don't handle routes that are already defined (exact or prefix)
    if filename in ['insights', 'insights.html', 'about', 'pbj-sample', 'report', 'report.html', 'sitemap.xml', 'pbj-wrapped', 'wrapped', 'sff', 'data', 'pbjpedia', 'owner']:
        from flask import abort
        abort(404)
    # Entity and provider/state pages are served by their own routes; avoid serving as static path
    if filename.startswith('entity/') or filename.startswith('provider/') or filename.startswith('state/'):
        from flask import abort
        abort(404)
    
    # Exclude directories that shouldn't be served (prevents connection failures)
    excluded_prefixes = ['node_modules/', '.git/', 'pbj-wrapped/node_modules/', 'pbj-wrapped/.git/', 'data/']
    if any(filename.startswith(prefix) for prefix in excluded_prefixes):
        from flask import abort
        abort(404)
    
    # Handle images with proper headers (including favicon)
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico')):
        response = send_from_directory(APP_ROOT, filename, mimetype='image/png' if filename.endswith('.ico') else 'image/png')
        if filename.endswith('.ico') or 'favicon' in filename.lower():
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        else:
            response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    # Handle CSS
    elif filename.endswith('.css'):
        response = send_from_directory('.', filename, mimetype='text/css')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    # Handle JS
    elif filename.endswith('.js'):
        response = send_from_directory('.', filename, mimetype='application/javascript')
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    # Handle JSON files
    elif filename.endswith('.json'):
        json_path = os.path.join(APP_ROOT, filename)
        if os.path.isfile(json_path):
            return send_file(json_path, mimetype='application/json')
        from flask import abort
        abort(404)
    # Handle CSV files
    elif filename.endswith('.csv'):
        csv_path = os.path.join('.', filename)
        if os.path.isfile(csv_path):
            return send_file(csv_path, mimetype='text/csv')
        from flask import abort
        abort(404)
    # Handle video files (e.g. press/wtvr-twin-lakes-clip.mp4)
    elif filename.endswith('.mp4'):
        video_path = os.path.join(APP_ROOT, filename)
        if os.path.isfile(video_path):
            return send_file(video_path, mimetype='video/mp4')
        from flask import abort
        abort(404)
    # Handle other static files
    else:
        return send_from_directory(APP_ROOT, filename)


# Gzip compress responses for text content (faster transfer; many hosts don't gzip by default)
_COMPRESSIBLE_TYPES = ('text/html', 'text/css', 'application/javascript', 'application/json', 'application/xml', 'text/plain')
_MIN_SIZE_TO_COMPRESS = 256

@app.after_request
def compress_response(response):
    """Compress response with gzip when client supports it and content type is compressible."""
    if not response.direct_passthrough and response.status_code == 200:
        ae = request.headers.get('Accept-Encoding', '') or ''
        if 'gzip' not in ae.lower():
            return response
        if response.headers.get('Content-Encoding'):
            return response
        ct = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if ct not in _COMPRESSIBLE_TYPES:
            return response
        try:
            data = response.get_data()
            if data is None or len(data) < _MIN_SIZE_TO_COMPRESS:
                return response
            compressed = gzip.compress(data, compresslevel=6)
            response.set_data(compressed)
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = len(compressed)
        except Exception:
            pass
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

