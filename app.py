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
from urllib.parse import quote, urlparse
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET
import html
from html.parser import HTMLParser
import time
import gzip

from pbj_review_framework import public_framework_json_for_js
from pbj_ai_config import (
    pbj_ai_dashboards_enabled,
    pbj_ai_page_enabled,
    pbj_ai_sample_enabled,
    pbj_ai_zip_download_enabled,
)
from premium_redirect_routes import register_premium_routes
from site_public_config import (
    PUBLIC_SITE_ORIGIN,
    ROBOTS_TXT,
    SECURITY_HEADER_VALUES,
    SITEMAP_TRUST_PAGES,
)
from pbj_ai_support import (
    CLAUDE_INSTALL_INSTRUCTIONS,
    CLAUDE_SKILL_BLURB,
    PBJ_AI_FRAMEWORK_BADGE,
    PBJ_AI_AVOID_BULLETS,
    PBJ_AI_DO_BULLETS,
    PBJ_AI_HERO_CONTEXT,
    PBJ_AI_HERO_LEAD,
    PBJ_AI_HERO_SUBHEAD,
    PBJ_AI_HERO_TITLE,
    hero_lead_html,
    PBJ_AI_PROMPT_ADVANCED,
    PBJ_AI_PROMPT_QUICK,
    PBJ_AI_THESIS_LINE,
    PBJ_BROWSER_AI_CAUTION,
    PBJ_AI_VERSION_LABEL,
    SKILL_ZIP_URL,
    audiences_html,
    different_users_html,
    how_it_works_html,
    responsible_ai_html,
    prompt_role_options_html,
    prompt_source_options_html,
    PBJ_AI_FACILITY_CARD_COPY,
    PBJ_AI_FACILITY_CARD_TITLE,
    PBJ_AI_FACILITY_NEXT_STEP,
    PBJ_AI_PROMPT_CARD_COPY,
    PBJ_AI_PROMPT_CARD_TITLE,
    PBJ_AI_CLAUDE_CARD_COPY,
    PBJ_AI_CLAUDE_CARD_TITLE,
    PBJ_AI_CLAUDE_HELPER,
    PBJ_AI_RESPONSIBLE_LEAD,
    PBJ_AI_RESPONSIBLE_TITLE,
    build_dashboard_context,
    build_facility_snapshot_csv,
    build_facility_snapshot_csv_row,
    build_facility_trend_csv_row,
    build_facility_trends_csv,
    facility_snapshot_csv_filename,
    facility_trends_csv_filename,
    free_premium_boundary_html,
    interpretation_checks_html,
    ai_helper_framework_json_for_js,
    render_ai_facility_helper,
    render_facility_csv_page_footer,
    strip_html_to_plain,
    _ul_html,
)

# Memory debugging — only logs when PBJ_MEM_DEBUG=1 (e.g. for profiling)
try:
    import psutil  # type: ignore[reportMissingImports]
    _psutil_process = psutil.Process()
    def _log_mem(label):
        if os.environ.get('PBJ_MEM_DEBUG', '').strip() in ('1', 'true', 'yes'):
            try:
                rss_mb = _psutil_process.memory_info().rss / (1024 * 1024)
                print(f"[MEM] {label}: {rss_mb:.1f} MB RSS", flush=True)
            except Exception:
                pass
except ImportError:
    _psutil_process = None
    def _log_mem(label):
        pass

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
    global _pandas_module, HAS_PANDAS, pd
    if _pandas_module is not None:
        return _pandas_module
    try:
        import pandas as _pd_mod
        _pandas_module = _pd_mod
        HAS_PANDAS = True
        pd = _pd_mod
        return _pd_mod
    except ImportError:
        HAS_PANDAS = False
        return None

pd = None  # Set by get_pd() on first pandas use, or by _ensure_pandas() on first non-health request.

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
# Local (non-Render): always rebuild provider HTML so case-mix / chart edits show on refresh.
if not (os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID')):
    if (os.environ.get('PBJ_SKIP_PROVIDER_PAGE_CACHE') or '').strip().lower() not in ('0', 'false', 'no', 'off'):
        os.environ.setdefault('PBJ_SKIP_PROVIDER_PAGE_CACHE', '1')

# SECRET_KEY required for CSRF (e.g. /subscribe). Set SECRET_KEY or FLASK_SECRET_KEY in .env or production env.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY')
if not app.config['SECRET_KEY']:
    app.config['SECRET_KEY'] = 'jak@rr23'
    # Only warn in production (or when FLASK_ENV is not development) so local dev is quieter
    if os.environ.get('FLASK_ENV', '').lower() != 'development':
        print('Warning: SECRET_KEY not set; using default. Set SECRET_KEY or FLASK_SECRET_KEY in production.', flush=True)
try:
    from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf  # type: ignore[reportMissingImports]
    app.config.setdefault('WTF_CSRF_CHECK_DEFAULT', False)
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
        current_year = datetime.now().year
        return {
            'data_range': f'2017-{current_year}',
            'quarter_count': 33,
            'provider_info_latest': 'Latest available',
            'provider_info_previous': 'Prior available',
            'affiliated_entity_latest': 'Latest available',
            'current_year': current_year
        }


def _api_dates_fallback_quarters():
    """Return resilient fallback quarter display and quarter list."""
    try:
        q = get_canonical_latest_quarter()
        if isinstance(q, str) and re.match(r'^\d{4}Q[1-4]$', q.strip()):
            q = q.strip()
            y, n = int(q[:4]), int(q[5])
            prev_n = n - 1 if n > 1 else 4
            prev_y = y if n > 1 else y - 1
            return format_quarter(q), [q, f'{prev_y}Q{prev_n}']
    except Exception:
        pass
    # Avoid stale hardcoded quarter literals in runtime fallback path.
    return 'N/A', []

@app.route('/api/dates')
def api_dates():
    """API endpoint to get dynamic date information (used by SFF page for source text).
    Returns quarters: list of quarter IDs that have pre-built JSON (e.g. ["2025Q1", "2025Q2"]).
    Frontend should only request JSON files for these quarters; no CSV fallback."""
    data = get_dynamic_dates()
    fallback_display, fallback_quarters = _api_dates_fallback_quarters()
    # Add PBJ quarter, SFF posting, and list of available quarters for JSON discovery
    try:
        quarter_path = os.path.join(os.path.dirname(__file__), 'latest_quarter_data.json')
        if os.path.exists(quarter_path):
            with open(quarter_path, 'r', encoding='utf-8') as f:
                q = json.load(f)
            data['pbj_quarter_display'] = q.get('quarter_display', fallback_display)
            # Available quarters: include current quarter from "quarter"; merge with "quarters" list if present
            current = q.get('quarter')
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
                data['quarters'] = fallback_quarters
        else:
            data['pbj_quarter_display'] = fallback_display
            data['quarters'] = fallback_quarters
    except Exception:
        data['pbj_quarter_display'] = fallback_display
        data['quarters'] = fallback_quarters
    data['sff_posting'] = get_sff_posting_display()
    data['sff_source_url'] = get_sff_source_url()
    return jsonify(data)

@app.route('/api/entity-summary/<int:entity_id>')
def api_entity_summary(entity_id):
    """Return lightweight entity summary stats for static pages (e.g., /about)."""
    try:
        entity_name, facilities = load_entity_facilities(entity_id)
        canonical_name = get_entity_name_from_search_index(entity_id)
        if canonical_name:
            entity_name = canonical_name
        if not facilities:
            return jsonify({'error': 'entity not found'}), 404
        chain_perf = load_chain_performance() or {}
        row = chain_perf.get(int(entity_id)) or {}
        state_set = {str((f or {}).get('state') or '').strip() for f in facilities if str((f or {}).get('state') or '').strip()}
        states_count = len(state_set)
        facilities_count = len(facilities)
        # Prefer canonical CMS chain-performance counts when available.
        for k in ('Number of facilities', 'number_of_facilities'):
            v = row.get(k)
            try:
                if v is not None and str(v).strip() != '':
                    facilities_count = int(float(v))
                    break
            except Exception:
                pass
        for k in ('Number of states and territories with operations', 'number_of_states_and_territories_with_operations'):
            v = row.get(k)
            try:
                if v is not None and str(v).strip() != '':
                    states_count = int(float(v))
                    break
            except Exception:
                pass
        avg_star = None
        for key in (
            'Average overall 5-star rating',
            'Average Overall Rating',
            'avg_overall_rating',
            'average_overall_rating',
        ):
            v = row.get(key)
            if v is None or str(v).strip() == '':
                continue
            try:
                avg_star = round(float(v), 1)
                break
            except Exception:
                continue
        return jsonify({
            'entity_id': int(entity_id),
            'entity_name': entity_name or '',
            'facilities_count': facilities_count,
            'states_count': states_count,
            'average_overall_rating': avg_star
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _entity_portfolio_ai_line(entity_id) -> str:
    """One-line affiliated-entity snapshot for AI page context (roster size, states, CMS chain stars when available)."""
    if entity_id is None or not HAS_PANDAS:
        return ''
    try:
        eid = int(entity_id)
    except (TypeError, ValueError):
        return ''
    try:
        _en, facilities = load_entity_facilities(eid)
        if not facilities:
            return ''
        chain_perf = load_chain_performance() or {}
        row = chain_perf.get(eid) or {}
        state_set = {str((f or {}).get('state') or '').strip().upper() for f in facilities if str((f or {}).get('state') or '').strip()}
        states_count = len(state_set)
        facilities_count = len(facilities)
        for k in ('Number of facilities', 'number_of_facilities'):
            v = row.get(k)
            try:
                if v is not None and str(v).strip() != '':
                    facilities_count = int(float(v))
                    break
            except (TypeError, ValueError):
                continue
        for k in ('Number of states and territories with operations', 'number_of_states_and_territories_with_operations'):
            v = row.get(k)
            try:
                if v is not None and str(v).strip() != '':
                    states_count = int(float(v))
                    break
            except (TypeError, ValueError):
                continue
        avg_star = None
        for key in (
            'Average overall 5-star rating',
            'Average Overall Rating',
            'avg_overall_rating',
            'average_overall_rating',
        ):
            v = row.get(key)
            if v is None or str(v).strip() == '':
                continue
            try:
                avg_star = round(float(v), 1)
                break
            except (TypeError, ValueError):
                continue
        chain_hprd = None
        for hk in ('Average total nurse hours per resident per day',):
            v = row.get(hk)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            try:
                chain_hprd = round(float(v), 2)
                break
            except (TypeError, ValueError):
                continue
        parts = [
            f'~{facilities_count:,} nursing home{"s" if facilities_count != 1 else ""} (PBJ320 roster / CMS chain file)',
            f'{states_count} state{"s" if states_count != 1 else ""} with operations',
        ]
        if avg_star is not None:
            parts.append(f'CMS chain snapshot avg overall Five-Star ~{avg_star} (rating, not HPRD)')
        if chain_hprd is not None:
            parts.append(f'CMS chain snapshot avg total nurse HPRD ~{chain_hprd}')
        return '; '.join(parts) + '.'
    except Exception:
        return ''


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

HIGH_RISK_CRITERIA_TOOLTIP = (
    'PBJ320 high-risk badge when the page shows: Special Focus Facility (SFF) or SFF candidate, '
    '1-star overall rating (Care Compare), or abuse icon flagged yes (Care Compare).'
)
FACILITY_RISK_BADGE_TOOLTIP = (
    f'{HIGH_RISK_CRITERIA_TOOLTIP} '
    'SFF facilities often have no star ratings on the page; staffing and overall stars are hidden when not reported.'
)


def _sort_risk_reason_display(label: str) -> str:
    """Order multi-reason risk labels with SFF before Abuse, etc."""
    text = (label or '').strip()
    if not text or ',' not in text:
        return text

    def _prio(part: str) -> int:
        pl = part.strip().lower()
        if 'sff' in pl:
            return 0
        if 'abuse' in pl:
            return 1
        if '1 star' in pl or '1-star' in pl:
            return 2
        return 3

    parts = [p.strip() for p in text.split(',') if p.strip()]
    return ', '.join(sorted(parts, key=_prio))

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


def get_entity_name_from_search_index(entity_id):
    """Return canonical entity name for an entity ID from search_index.json."""
    global _SEARCH_INDEX_CACHE, _SEARCH_INDEX_AT
    try:
        target = int(entity_id)
    except Exception:
        return ''
    path = os.path.join(APP_ROOT, 'search_index.json')
    if not os.path.isfile(path):
        return ''
    now = time.time()
    if _SEARCH_INDEX_CACHE is None or (now - _SEARCH_INDEX_AT) >= _SEARCH_INDEX_TTL:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _SEARCH_INDEX_CACHE = json.load(f)
                _SEARCH_INDEX_AT = now
        except Exception:
            return ''
    try:
        for row in (_SEARCH_INDEX_CACHE.get('e') or []):
            rid = row.get('id')
            rlink = row.get('linkId')
            if (rid is not None and int(rid) == target) or (rlink is not None and int(rlink) == target):
                nm = str(row.get('n') or '').strip()
                if nm:
                    return capitalize_entity_name(nm)
    except Exception:
        return ''
    return ''

@app.before_request
def _ensure_pandas():
    """Load pandas on first non-health request so /health can respond before workers load it (Render)."""
    if request.path == '/health':
        return
    global pd
    if pd is None:
        pd = get_pd()


@app.before_request
def _csrf_protect_selectively():
    """Only run CSRF for /subscribe and /contact. Skip all /owners/* so query-fec and owner pages never get 400."""
    if not HAS_CSRF or csrf_protect is None:
        return
    if request.path.startswith('/owners'):
        return
    if request.path in ('/subscribe', '/contact') or request.path.startswith('/contact?'):
        csrf_protect.protect()

@app.route('/health')
def health():
    """Lightweight health check for Render. Side-effect free (best practice for public sites)."""
    return 'ok', 200

# Simple email format check (not RFC-strict; rejects obviously invalid)
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def _serve_public_html(filename: str, *, inject_csrf: bool = False):
    """Serve a root-level public HTML file with optional CSRF token injection."""
    path = os.path.join(APP_ROOT, filename)
    if not os.path.isfile(path):
        from flask import abort
        abort(404)
    with open(path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    if inject_csrf:
        token = generate_csrf() if (HAS_CSRF and generate_csrf) else ''
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', token)
    resp = make_response(html_content)
    resp.mimetype = 'text/html'
    return resp


@app.route('/')
def index():
    return _serve_public_html('index.html', inject_csrf=True)

@app.errorhandler(400)
def bad_request(err):
    """Redirect /subscribe and /contact CSRF or bad request to friendly page instead of 400."""
    if request.path == '/subscribe':
        return redirect('/?subscribe_error=invalid')
    if request.path == '/contact':
        return redirect('/contact?error=invalid')
    # Owners API: return JSON so frontend sees real error (e.g. query-fec "Owner name required")
    if request.path.startswith('/owners/api/'):
        return make_response((json.dumps({'error': getattr(err, 'description', None) or 'Bad request'}), 400, {'Content-Type': 'application/json'}))
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
th {{ background: #1e293b; color: #818cf8; }}</style>
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
    return _serve_public_html('contact.html', inject_csrf=True)


@app.route('/about')
def about():
    return send_file('about.html', mimetype='text/html')


@app.route('/data-sources')
@app.route('/data-sources/')
def data_sources_page():
    from flask import abort
    abort(404)


@app.route('/privacy')
@app.route('/privacy/')
def privacy_page():
    from flask import abort
    abort(404)


@app.route('/terms')
@app.route('/terms/')
def terms_page():
    from flask import abort
    abort(404)


@app.route('/robots.txt')
def robots_txt():
    return ROBOTS_TXT, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/insights')
@app.route('/insights/')
def insights():
    """Insights hub with server-rendered feed (SEO), JSON-LD ItemList, and client refresh."""
    posts = _get_dual_track_insights_posts()
    base = _public_site_origin()
    feed_html = _render_insights_hub_feed_html(posts)
    itemlist_json_ld = _insights_hub_item_list_json_ld(posts, base)
    og_image = f'{base}/og-image-1200x630.png'
    return render_template(
        'insights_hub.html',
        feed_html=feed_html,
        itemlist_json_ld=itemlist_json_ld,
        site_base=base,
        og_image=og_image,
        substack_feed_url=NEWSLETTER_SUBSTACK_FEED,
    )


@app.route('/insights-theme.css')
def insights_theme_css():
    """Shared palette for /insights hub and native /insights/<slug> articles."""
    return _static_cache_headers(send_from_directory(APP_ROOT, 'insights-theme.css', mimetype='text/css'))


@app.route('/insights-visualizations')
@app.route('/insights-visualizations/')
def insights_visualizations():
    """Legacy interactive visualizations now housed under the Insights article track."""
    return send_file('insights.html', mimetype='text/html')

_PBJ_AI_SAMPLE_BLOCK_RE = re.compile(
    r'<!--\s*PBJ_AI_SAMPLE_BLOCK\s*-->.*?<!--\s*/PBJ_AI_SAMPLE_BLOCK\s*-->',
    re.DOTALL | re.IGNORECASE,
)


@app.route('/pbj-sample')
def pbj_sample():
    """Handle both /pbj-sample and /pbj-sample.html"""
    path = os.path.join(APP_ROOT, 'pbj-sample.html')
    with open(path, encoding='utf-8') as f:
        page_html = f.read()
    if pbj_ai_sample_enabled():
        page_html = page_html.replace('__PBJ_AI_PROMPT_QUICK__', html.escape(PBJ_AI_PROMPT_QUICK))
    else:
        page_html = _PBJ_AI_SAMPLE_BLOCK_RE.sub('', page_html)
        page_html = page_html.replace('<script src="/pbj-ai-support.js"></script>', '')
    resp = make_response(page_html)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


@app.route('/pbj-ai-support')
def pbj_ai_support():
    """PBJ320 AI Support: copyable prompts and responsible AI guidance (no public skill ZIP)."""
    if not pbj_ai_page_enabled():
        from flask import abort
        abort(404)
    path = os.path.join(APP_ROOT, 'pbj-ai-support.html')
    with open(path, encoding='utf-8') as f:
        page_html = f.read()
    page_html = re.sub(
        r'<article class="content-box ai-section ai-section--claude\b.*?</article>\s*',
        '',
        page_html,
        count=1,
        flags=re.DOTALL,
    )
    page_html = page_html.replace(
        '<a href="__PBJ_SKILL_ZIP_URL__" class="ai-btn ai-btn-claude" download data-pbj-track="download_claude_skill">Download Claude Skill</a>',
        '<a href="https://pbj320.com/premium" class="ai-btn ai-btn-secondary">Premium analysis</a>',
    )
    page_html = page_html.replace(
        '<a href="__PBJ_SKILL_ZIP_URL__" class="ai-mobile-bar__btn ai-mobile-bar__btn--claude" download data-pbj-track="download_claude_skill">Claude Skill</a>',
        '<a href="https://pbj320.com/premium" class="ai-mobile-bar__btn">Premium</a>',
    )
    page_html = page_html.replace('__PBJ_AI_HERO_TITLE__', html.escape(PBJ_AI_HERO_TITLE))
    page_html = page_html.replace('__PBJ_AI_HERO_SUBHEAD__', html.escape(PBJ_AI_HERO_SUBHEAD))
    page_html = page_html.replace('__PBJ_AI_HERO_LEAD__', hero_lead_html())
    page_html = page_html.replace('__PBJ_AI_HERO_CONTEXT__', html.escape(PBJ_AI_HERO_CONTEXT))
    page_html = page_html.replace('__PBJ_AI_THESIS_LINE__', html.escape(PBJ_AI_THESIS_LINE))
    page_html = page_html.replace('__PBJ_AI_BROWSER_CAUTION__', html.escape(PBJ_BROWSER_AI_CAUTION))
    page_html = page_html.replace('__PBJ_AI_DIFFERENT_USERS__', different_users_html())
    page_html = page_html.replace('__PBJ_AI_FRAMEWORK_BADGE__', html.escape(PBJ_AI_FRAMEWORK_BADGE))
    page_html = page_html.replace('__PBJ_AI_HOW_IT_WORKS__', how_it_works_html())
    page_html = page_html.replace('__PBJ_AI_RESPONSIBLE_AI__', responsible_ai_html())
    page_html = page_html.replace('__PBJ_AI_PROMPT_ROLE_OPTIONS__', prompt_role_options_html())
    page_html = page_html.replace('__PBJ_AI_PROMPT_SOURCE_OPTIONS__', prompt_source_options_html())
    page_html = page_html.replace('__PBJ_AI_FACILITY_CARD_TITLE__', html.escape(PBJ_AI_FACILITY_CARD_TITLE))
    page_html = page_html.replace('__PBJ_AI_FACILITY_CARD_COPY__', html.escape(PBJ_AI_FACILITY_CARD_COPY))
    page_html = page_html.replace('__PBJ_AI_FACILITY_NEXT_STEP__', html.escape(PBJ_AI_FACILITY_NEXT_STEP))
    page_html = page_html.replace('__PBJ_AI_PROMPT_CARD_TITLE__', html.escape(PBJ_AI_PROMPT_CARD_TITLE))
    page_html = page_html.replace('__PBJ_AI_PROMPT_CARD_COPY__', html.escape(PBJ_AI_PROMPT_CARD_COPY))
    page_html = page_html.replace('__PBJ_AI_CLAUDE_CARD_TITLE__', html.escape(PBJ_AI_CLAUDE_CARD_TITLE))
    page_html = page_html.replace('__PBJ_AI_CLAUDE_CARD_COPY__', html.escape(PBJ_AI_CLAUDE_CARD_COPY))
    page_html = page_html.replace('__PBJ_AI_CLAUDE_HELPER__', html.escape(PBJ_AI_CLAUDE_HELPER))
    page_html = page_html.replace('__PBJ_AI_RESPONSIBLE_TITLE__', html.escape(PBJ_AI_RESPONSIBLE_TITLE))
    page_html = page_html.replace('__PBJ_AI_RESPONSIBLE_LEAD__', html.escape(PBJ_AI_RESPONSIBLE_LEAD))
    page_html = page_html.replace('__PBJ_AI_VERSION_LABEL__', html.escape(PBJ_AI_VERSION_LABEL))
    page_html = page_html.replace('__PBJ_AI_DO_LIST__', _ul_html(PBJ_AI_DO_BULLETS))
    page_html = page_html.replace('__PBJ_AI_AVOID_LIST__', _ul_html(PBJ_AI_AVOID_BULLETS))
    page_html = page_html.replace('__PBJ_AI_INTERPRETATION_CHECKS__', interpretation_checks_html())
    page_html = page_html.replace('__PBJ_AI_AUDIENCES__', audiences_html())
    page_html = page_html.replace('__PBJ_AI_FREE_PREMIUM__', free_premium_boundary_html())
    page_html = page_html.replace('__PBJ_AI_INSTALL__', '')
    page_html = page_html.replace('__PBJ_AI_CLAUDE_BLURB__', '')
    page_html = page_html.replace('__PBJ_SKILL_ZIP_URL__', 'https://pbj320.com/premium')
    import json as _json
    page_html = page_html.replace('__PBJ_AI_PROMPT_QUICK_JSON__', _json.dumps(PBJ_AI_PROMPT_QUICK))
    page_html = page_html.replace('__PBJ_AI_PROMPT_ADVANCED_JSON__', _json.dumps(PBJ_AI_PROMPT_ADVANCED))
    page_html = page_html.replace('__PBJ_REVIEW_FRAMEWORK_JSON__', public_framework_json_for_js())
    # HTML-only placeholders — never share __PBJ_AI_PROMPT_QUICK__ (breaks window.__PBJ_AI_PROMPT_QUICK__).
    page_html = page_html.replace('__PBJ_AI_PROMPT_QUICK_HTML__', html.escape(PBJ_AI_PROMPT_QUICK))
    page_html = page_html.replace('__PBJ_AI_PROMPT_ADVANCED_HTML__', html.escape(PBJ_AI_PROMPT_ADVANCED))
    resp = make_response(page_html)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


def _load_ai_prompts_catalog() -> dict:
    path = os.path.join(INSIGHTS_NATIVE_DIR, 'pbj_ai_audience_prompts.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _render_ai_prompt_cards_html(catalog: dict) -> str:
    prompts = catalog.get('prompts') or []
    if not isinstance(prompts, list):
        return ''
    allowed_ids = frozenset({'ombudsman', 'family', 'journalist', 'reporter'})
    chunks = []
    for row in prompts:
        if not isinstance(row, dict):
            continue
        raw_id = str(row.get('id') or 'prompt').strip() or 'prompt'
        if raw_id not in allowed_ids:
            continue
        pid = html.escape(raw_id)
        label = html.escape(str(row.get('label') or 'Prompt').strip())
        desc = html.escape(str(row.get('description') or '').strip())
        text = html.escape(str(row.get('text') or '').strip())
        if not text:
            continue
        chunks.append(
            f'<article class="prompt-card" id="prompt-{pid}">'
            f'<h2>{label}</h2>'
            f'<p class="prompt-card__desc">{desc}</p>'
            f'<pre id="prompt-text-{pid}">{text}</pre>'
            f'<button type="button" class="prompt-copy" data-copy-target="prompt-text-{pid}">Copy prompt</button>'
            '</article>'
        )
    return '\n'.join(chunks)


@app.route('/ai/prompts')
@app.route('/ai/prompts/')
def ai_prompts_page():
    """Lightweight copyable PBJ prompts — disabled on public site until Insights article ships."""
    from flask import abort
    abort(404)


@app.route('/ai-icons/<path:icon_name>')
def ai_icons(icon_name):
    safe = os.path.basename(icon_name.replace('\\', '/'))
    if safe not in ('claude.svg', 'chatgpt.svg', 'gemini.svg'):
        from flask import abort
        abort(404)
    path = os.path.join(APP_ROOT, 'ai-icons', safe)
    if not os.path.isfile(path):
        from flask import abort
        abort(404)
    return send_file(path, mimetype='image/svg+xml')


@app.route('/pbj-ai-support.css')
def pbj_ai_support_css():
    path = os.path.join(APP_ROOT, 'pbj-ai-support.css')
    if not os.path.isfile(path):
        from flask import abort
        abort(404)
    resp = send_file(path, mimetype='text/css')
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


@app.route('/pbj-review-framework.js')
def pbj_review_framework_js():
    """Client-side review mode config + prompt compose (for future toggles)."""
    path = os.path.join(APP_ROOT, 'pbj-review-framework.js')
    if not os.path.isfile(path):
        from flask import abort
        abort(404)
    return _static_cache_headers(send_from_directory(APP_ROOT, 'pbj-review-framework.js', mimetype='application/javascript'))


@app.route('/pbj-ai-support.js')
def pbj_ai_support_js():
    """Serve AI support clipboard helpers (explicit route; do not rely on catch-all)."""
    path = os.path.join(APP_ROOT, 'pbj-ai-support.js')
    if not os.path.isfile(path):
        from flask import abort
        abort(404)
    return _static_cache_headers(send_from_directory(APP_ROOT, 'pbj-ai-support.js', mimetype='application/javascript'))


@app.route('/static/downloads/pbj320-staffing-review.zip')
@app.route('/downloads/pbj320-staffing-review.zip')
def download_pbj_claude_skill_zip():
    """Downloadable Claude Skill package for PBJ320 staffing review."""
    if not pbj_ai_zip_download_enabled():
        from flask import abort
        abort(404)
    import zipfile
    zip_path = os.path.join(APP_ROOT, 'downloads', 'pbj320-staffing-review.zip')
    skill_dir = os.path.join(APP_ROOT, 'downloads', 'pbj320-staffing-review')
    if not os.path.isfile(zip_path) and os.path.isdir(skill_dir):
        os.makedirs(os.path.dirname(zip_path), exist_ok=True)
        prefix = 'pbj320-staffing-review'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _dirnames, filenames in os.walk(skill_dir):
                for name in filenames:
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, skill_dir)
                    arc = os.path.join(prefix, rel).replace('\\', '/')
                    zf.write(full, arc)
    if not os.path.isfile(zip_path):
        from flask import abort
        abort(404)
    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name='pbj320-staffing-review.zip',
    )


# ---------------------------------------------------------------------------
# Report page: same-origin JSON/CSV via GET /report?p=… (report.html relies on this)
# ---------------------------------------------------------------------------
# Pinned snapshot for GET /report?p=pi (report.html embed); path relative to app root.
_REPORT_PINNED_PROVIDER_NORM_REL = os.path.join('provider_info', 'ProviderInfoNorm_2026_04.csv')
_HIGH_RISK_BY_STATE_CACHE_KEY = None
_HIGH_RISK_BY_STATE_CACHE_VAL = None
_HIGH_RISK_BY_STATE_CACHE_AT = 0.0
_HIGH_RISK_BY_STATE_TTL = 600.0


def _report_first_provider_snapshot_path():
    """Newest ``ProviderInfoNorm_*`` / ``NH_ProviderInfo_*`` CSV under ``provider_info/`` only (no combined_latest)."""
    seen = set()
    for p in _provider_snapshot_candidate_paths():
        abs_p = p if os.path.isabs(p) else os.path.join(APP_ROOT, p.replace('/', os.sep))
        if os.path.isfile(abs_p) and abs_p not in seen:
            seen.add(abs_p)
            return abs_p
    return None


def _provider_paths_report_prefer_pinned():
    """Paths for /report provider-derived JSON: pinned Norm snapshot first when present, then newest-first discovery."""
    out = []
    pinned = os.path.join(APP_ROOT, _REPORT_PINNED_PROVIDER_NORM_REL.replace('/', os.sep))
    if os.path.isfile(pinned):
        out.append(pinned)
    for p in _provider_info_snapshot_paths_newest_first():
        if p not in out:
            out.append(p)
    return out


def _pick_provider_csv_column(headers, *candidates):
    lowmap = {str(h).strip().lower(): h for h in headers}
    for cand in candidates:
        k = str(cand).strip().lower()
        if k in lowmap:
            return lowmap[k]
    return None


def _build_high_risk_provider_usecols(headers):
    picks = {
        'ccn': _pick_provider_csv_column(headers, 'ccn', 'provnum', 'CCN', 'CMS Certification Number (CCN)'),
        'state': _pick_provider_csv_column(headers, 'state', 'STATE', 'State'),
        'cy_qtr': _pick_provider_csv_column(headers, 'CY_Qtr'),
        'quarter': _pick_provider_csv_column(headers, 'quarter'),
        'provider_name': _pick_provider_csv_column(headers, 'provider_name', 'PROVNAME', 'Provider Name'),
        'city': _pick_provider_csv_column(headers, 'city', 'CITY', 'City'),
        'sff_status': _pick_provider_csv_column(headers, 'sff_status', 'Special Focus Status'),
        'overall_rating': _pick_provider_csv_column(headers, 'overall_rating'),
        'staffing_rating': _pick_provider_csv_column(headers, 'staffing_rating'),
        'abuse_icon': _pick_provider_csv_column(headers, 'abuse_icon', 'Abuse Icon'),
        'has_abuse_icon': _pick_provider_csv_column(headers, 'has_abuse_icon'),
        'reported_total': _pick_provider_csv_column(
            headers, 'reported_total_nurse_hrs_per_resident_per_day', 'Total_Nurse_HPRD'
        ),
        'case_mix_total': _pick_provider_csv_column(headers, 'case_mix_total_nurse_hrs_per_resident_per_day'),
        'ownership_type': _pick_provider_csv_column(headers, 'ownership_type', 'OWNERSHIP'),
    }
    usecols = []
    col_refs = {}
    for canon, actual in picks.items():
        if actual and actual not in usecols:
            usecols.append(actual)
            col_refs[canon] = actual
    return usecols, col_refs


def _row_cy_qtr_for_high_risk(row, col_refs, pd_local):
    ccy = col_refs.get('cy_qtr')
    cqu = col_refs.get('quarter')
    if ccy:
        v = row.get(ccy)
        if v is not None and not (isinstance(v, float) and pd_local.isna(v)):
            s = str(v).strip()
            if re.match(r'^\d{4}Q[1-4]$', s):
                return s
    if cqu:
        v = row.get(cqu)
        if v is not None and not (isinstance(v, float) and pd_local.isna(v)):
            s = str(v).strip()
            if re.match(r'^\d{4}Q[1-4]$', s):
                return s
            qn = _quarter_display_to_cy_qtr(s)
            if qn:
                return qn
    return None


def _cy_qtr_sort_key(q):
    m = re.match(r'^(\d{4})Q([1-4])$', str(q).strip())
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


def _provider_csv_collect_quarters(path_used, col_refs, pd_local):
    """Distinct canonical CY_Qtr values present in a ProviderInfo-style CSV (non-snapshot)."""
    qcols = []
    if col_refs.get('cy_qtr'):
        qcols.append(col_refs['cy_qtr'])
    if col_refs.get('quarter'):
        qcols.append(col_refs['quarter'])
    qcols = list(dict.fromkeys(qcols))
    if not qcols:
        return set()
    quarters = set()
    try:
        for chunk in pd_local.read_csv(path_used, usecols=qcols, low_memory=False, chunksize=100000):
            for row in chunk.to_dict('records'):
                rq = _row_cy_qtr_for_high_risk(row, col_refs, pd_local)
                if rq:
                    quarters.add(rq)
    except Exception:
        return set()
    return quarters


def _resolve_effective_cy_qtr(cy_qtr, quarters_set):
    """If requested quarter is absent from the file, use the latest quarter present."""
    if not quarters_set:
        return cy_qtr
    if cy_qtr in quarters_set:
        return cy_qtr
    return max(quarters_set, key=_cy_qtr_sort_key)


def _report_max_cy_qtr_from_pinned_paths(pd_local):
    """Latest ``YYYYQN`` present on the first readable pinned/provider snapshot (non-CMS-snapshot)."""
    for path in _provider_paths_report_prefer_pinned():
        if not os.path.isfile(path) or _provider_csv_is_cms_snapshot(path):
            continue
        try:
            head = pd_local.read_csv(path, nrows=0)
            usecols, col_refs = _build_high_risk_provider_usecols(list(head.columns))
            if not col_refs.get('cy_qtr') and not col_refs.get('quarter'):
                continue
            qset = _provider_csv_collect_quarters(path, col_refs, pd_local)
            if qset:
                return max(qset, key=_cy_qtr_sort_key)
        except Exception as e:
            print(f'report max CY_Qtr scan failed for {path}: {e}', flush=True)
            continue
    return ''


def _report_effective_cy_qtr_for_embed_request(quarter_requested, pd_local):
    """Resolve ``quarter`` query / canonical / max-in-file for ``fp`` and ``hrs`` embeds."""
    s = (quarter_requested or '').strip()
    if re.match(r'^\d{4}Q[1-4]$', s):
        return s
    cq = get_canonical_latest_quarter()
    cy = str(cq).strip() if cq else ''
    if re.match(r'^\d{4}Q[1-4]$', cy):
        return cy
    return _report_max_cy_qtr_from_pinned_paths(pd_local) or ''


def _ownership_text_is_for_profit(ot):
    if ot is None:
        return False
    low = str(ot).strip().lower()
    if not low:
        return False
    if re.search(r'for[\s_-]*profit', low):
        return True
    compact = low.replace(' ', '').replace('-', '').replace('_', '')
    if 'forprofit' in compact:
        return True
    return False


def _high_risk_facility_payload_from_row(row, col_refs, pd_local):
    c = col_refs

    def _cell(col_key):
        name = c.get(col_key)
        if not name:
            return ''
        v = row.get(name)
        if v is None or (isinstance(v, float) and pd_local.isna(v)):
            return ''
        return str(v).strip()

    raw_ccn = _cell('ccn').replace('.0', '')
    if not raw_ccn:
        return None
    ccn = raw_ccn.zfill(6)
    st = _cell('state').upper()[:2]
    if len(st) != 2:
        return None
    sff_raw = _cell('sff_status')
    try:
        overall_rating = int(float(_cell('overall_rating') or 0))
    except (TypeError, ValueError):
        overall_rating = 0
    try:
        staffing_rating = int(float(_cell('staffing_rating') or 0))
    except (TypeError, ValueError):
        staffing_rating = 0
    ai = _cell('abuse_icon').upper()
    hai = _cell('has_abuse_icon').upper()
    has_abuse = ai in ('Y', '1') or hai in ('Y', '1')
    try:
        total_hprd = float(_cell('reported_total') or 0)
    except (TypeError, ValueError):
        total_hprd = 0.0
    try:
        case_mix_hprd = float(_cell('case_mix_total') or 0)
    except (TypeError, ValueError):
        case_mix_hprd = 0.0
    fac = {
        'ccn': ccn,
        'name': _cell('provider_name') or 'Unknown provider',
        'city': _cell('city'),
        'state': st,
        'overall_rating': _cell('overall_rating') or '',
        'staffing_rating': _cell('staffing_rating') or '',
        'status': sff_raw,
        'hasAbuse': has_abuse,
        'total_nurse_hprd': total_hprd if total_hprd > 0 else None,
        'case_mix_total_hprd': case_mix_hprd if case_mix_hprd > 0 else None,
        'categories': [],
    }
    return fac, sff_raw, overall_rating, staffing_rating, has_abuse, total_hprd, case_mix_hprd, st


def _provider_csv_is_cms_snapshot(path_used):
    return 'nh_providerinfo' in os.path.basename(path_used).lower()


def _provider_info_snapshot_paths_newest_first():
    out = []
    seen = set()
    for p in _provider_snapshot_candidate_paths():
        abs_p = p if os.path.isabs(p) else os.path.join(APP_ROOT, p.replace('/', os.sep))
        if os.path.isfile(abs_p) and abs_p not in seen:
            seen.add(abs_p)
            out.append(abs_p)
    return out


def _compute_high_risk_by_state_for_quarter(cy_qtr):
    """Return ``(states_by_abbr, effective_cy_qtr)`` for the provider snapshot used."""
    global _HIGH_RISK_BY_STATE_CACHE_KEY, _HIGH_RISK_BY_STATE_CACHE_VAL, _HIGH_RISK_BY_STATE_CACHE_AT
    pd_local = get_pd()
    if pd_local is None:
        return {}, str(cy_qtr or '').strip() if cy_qtr else ''
    if not cy_qtr or not re.match(r'^\d{4}Q[1-4]$', str(cy_qtr).strip()):
        return {}, str(cy_qtr or '').strip()
    cy_qtr = str(cy_qtr).strip()
    provider_paths = _provider_paths_report_prefer_pinned()
    if not provider_paths:
        return {}, cy_qtr
    now = time.time()
    for path_used in provider_paths:
        if not os.path.isfile(path_used):
            continue
        is_snapshot = _provider_csv_is_cms_snapshot(path_used)
        try:
            mtime = os.path.getmtime(path_used)
        except Exception:
            mtime = 0.0

        try:
            head = pd_local.read_csv(path_used, nrows=0)
            headers = list(head.columns)
            usecols, col_refs = _build_high_risk_provider_usecols(headers)
            if not col_refs.get('ccn') or not col_refs.get('state'):
                continue
            if not is_snapshot and not col_refs.get('cy_qtr') and not col_refs.get('quarter'):
                continue

            if is_snapshot:
                effective_cy_qtr = cy_qtr
            else:
                quarters_in_file = _provider_csv_collect_quarters(path_used, col_refs, pd_local)
                if not quarters_in_file:
                    print(f'high-risk: no quarters parsed from {path_used}', flush=True)
                effective_cy_qtr = _resolve_effective_cy_qtr(cy_qtr, quarters_in_file)

            cache_key = (path_used, mtime, effective_cy_qtr if not is_snapshot else '__cms_snapshot__')
            if (
                _HIGH_RISK_BY_STATE_CACHE_VAL is not None
                and _HIGH_RISK_BY_STATE_CACHE_KEY == cache_key
                and (now - _HIGH_RISK_BY_STATE_CACHE_AT) < _HIGH_RISK_BY_STATE_TTL
            ):
                cached = _HIGH_RISK_BY_STATE_CACHE_VAL
                if isinstance(cached, dict):
                    return cached, (effective_cy_qtr if not is_snapshot else cy_qtr)
                return cached

            state_hprds = {}
            slim_rows = []
            for chunk in pd_local.read_csv(path_used, usecols=usecols, low_memory=False, chunksize=100000):
                for row in chunk.to_dict('records'):
                    rq = _row_cy_qtr_for_high_risk(row, col_refs, pd_local)
                    if not is_snapshot and rq != effective_cy_qtr:
                        continue
                    parsed = _high_risk_facility_payload_from_row(row, col_refs, pd_local)
                    if not parsed:
                        continue
                    _fac, _sff, _overall_rt, _sr, _ha, th, _cm, st_abbr = parsed
                    if th and th > 0:
                        state_hprds.setdefault(st_abbr, []).append(th)
                    slim_rows.append(parsed)

            state_bottom10 = {}
            for st_abbr, vals in state_hprds.items():
                arr = sorted([v for v in vals if v and v > 0])
                if arr:
                    idx = int(len(arr) * 0.1)
                    state_bottom10[st_abbr] = arr[idx] if idx < len(arr) else arr[-1]
                else:
                    state_bottom10[st_abbr] = 0.0

            out = {}
            for parsed in slim_rows:
                fac, sff_raw, overall_rating, staffing_rating, has_abuse, total_hprd, case_mix_hprd, st_abbr = parsed
                bottom = state_bottom10.get(st_abbr) or 0.0
                is_understaffed = (
                    staffing_rating == 1
                    or (
                        case_mix_hprd > 0
                        and total_hprd > 0
                        and (total_hprd / case_mix_hprd) < 0.8
                    )
                    or (bottom > 0 and total_hprd > 0 and total_hprd <= bottom)
                )
                sff_trim = (sff_raw or '').strip()
                qualifies = (
                    fac['ccn']
                    and st_abbr
                    and (
                        sff_trim == 'SFF'
                        or sff_trim == 'SFF Candidate'
                        or has_abuse
                        or overall_rating == 1
                        or is_understaffed
                    )
                )
                if not qualifies:
                    continue
                fac['categories'] = []
                if sff_trim == 'SFF':
                    fac['categories'].append('sff')
                if sff_trim == 'SFF Candidate':
                    fac['categories'].append('candidate')
                if has_abuse:
                    fac['categories'].append('abuse')
                if overall_rating == 1:
                    fac['categories'].append('oneStarOverall')
                if is_understaffed:
                    fac['categories'].append('understaffing')

                bucket = out.setdefault(
                    st_abbr,
                    {'sff': [], 'sffCandidates': [], 'abuse': [], 'oneStarOverall': [], 'oneStarStaffing': []},
                )
                if sff_trim == 'SFF':
                    bucket['sff'].append(fac)
                elif sff_trim == 'SFF Candidate':
                    bucket['sffCandidates'].append(fac)
                elif has_abuse:
                    bucket['abuse'].append(fac)
                elif overall_rating == 1:
                    bucket['oneStarOverall'].append(fac)
                elif is_understaffed:
                    bucket['oneStarStaffing'].append(fac)

            _HIGH_RISK_BY_STATE_CACHE_KEY = cache_key
            _HIGH_RISK_BY_STATE_CACHE_VAL = (out, effective_cy_qtr if not is_snapshot else cy_qtr)
            _HIGH_RISK_BY_STATE_CACHE_AT = now
            return _HIGH_RISK_BY_STATE_CACHE_VAL
        except Exception as e:
            print(f'high-risk scan failed for {path_used}: {e}', flush=True)
            continue
    return {}, cy_qtr


def _load_state_abbr_to_cms_region_full():
    path = os.path.join(APP_ROOT, 'cms_region_state_mapping.csv')
    out = {}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                abbr = (row.get('State_Code') or '').strip().upper()
                rfull = (row.get('CMS_Region_Full') or '').strip()
                if abbr and rfull:
                    out[abbr] = rfull
    except Exception as e:
        print(f'cms_region_state_mapping read failed: {e}', flush=True)
    return out


def _rollup_high_risk_states_to_regions(states_by_abbr):
    mm = _load_state_abbr_to_cms_region_full()
    keys = ('sff', 'sffCandidates', 'abuse', 'oneStarOverall', 'oneStarStaffing')
    regions = {}
    for abbr, bucket in (states_by_abbr or {}).items():
        if not isinstance(bucket, dict):
            continue
        rfull = mm.get(str(abbr).strip().upper())
        if not rfull:
            continue
        rb = regions.setdefault(
            rfull,
            {'sff': [], 'sffCandidates': [], 'abuse': [], 'oneStarOverall': [], 'oneStarStaffing': []},
        )
        for k in keys:
            for fac in bucket.get(k) or []:
                rb[k].append(fac)
    return regions


def _report_embed_provider_latest_csv():
    path = os.path.join(APP_ROOT, _REPORT_PINNED_PROVIDER_NORM_REL.replace('/', os.sep))
    if not os.path.isfile(path):
        return jsonify({'error': 'Pinned provider snapshot missing: provider_info/ProviderInfoNorm_2026_04.csv'}), 404
    return send_file(path, mimetype='text/csv', max_age=3600, download_name=os.path.basename(path))


def _report_embed_high_risk_by_state():
    pd_local = get_pd()
    if pd_local is None:
        return jsonify({'error': 'pandas unavailable', 'quarterRequested': '', 'quarter': '', 'states': {}}), 503
    quarter_requested = (request.args.get('quarter') or '').strip()
    cy_qtr = _report_effective_cy_qtr_for_embed_request(quarter_requested, pd_local)
    if not re.match(r'^\d{4}Q[1-4]$', cy_qtr):
        return jsonify(
            {'error': 'invalid or missing quarter', 'quarterRequested': quarter_requested, 'quarter': cy_qtr, 'states': {}}
        ), 400
    states, quarter_used = _compute_high_risk_by_state_for_quarter(cy_qtr)
    if not states:
        print(
            f'report hrs: empty states (requested={quarter_requested!r} used={quarter_used!r})',
            flush=True,
        )
    return jsonify({'quarter': quarter_used, 'quarterRequested': quarter_requested, 'states': states})


def _report_embed_high_risk_by_cms_region():
    pd_local = get_pd()
    if pd_local is None:
        return jsonify({'error': 'pandas unavailable', 'quarterRequested': '', 'quarter': '', 'regions': {}}), 503
    quarter_requested = (request.args.get('quarter') or '').strip()
    cy_qtr = _report_effective_cy_qtr_for_embed_request(quarter_requested, pd_local)
    if not re.match(r'^\d{4}Q[1-4]$', cy_qtr):
        return jsonify(
            {'error': 'invalid or missing quarter', 'quarterRequested': quarter_requested, 'quarter': cy_qtr, 'regions': {}}
        ), 400
    states_by_abbr, quarter_used = _compute_high_risk_by_state_for_quarter(cy_qtr)
    regions = _rollup_high_risk_states_to_regions(states_by_abbr)
    if not regions:
        print(
            f'report hrr: empty regions (requested={quarter_requested!r} used={quarter_used!r})',
            flush=True,
        )
    return jsonify({'quarter': quarter_used, 'quarterRequested': quarter_requested, 'regions': regions})


def _report_embed_for_profit_by_state():
    pd_local = get_pd()
    if pd_local is None:
        return jsonify({'states': {}, 'quarterRequested': '', 'quarter': '', 'embedWarning': 'pandas_unavailable'})
    quarter_requested = (request.args.get('quarter') or '').strip()
    cy_qtr = _report_effective_cy_qtr_for_embed_request(quarter_requested, pd_local)
    paths_try = _provider_paths_report_prefer_pinned()
    path = paths_try[0] if paths_try else None
    if not path:
        return jsonify({'states': {}, 'quarterRequested': quarter_requested, 'quarter': cy_qtr, 'embedWarning': 'no_provider_csv'})
    if not re.match(r'^\d{4}Q[1-4]$', cy_qtr):
        return jsonify({'states': {}, 'quarterRequested': quarter_requested, 'quarter': cy_qtr, 'embedWarning': 'invalid_cy_qtr'})
    try:
        head = pd_local.read_csv(path, nrows=0)
        headers = list(head.columns)
        usecols, col_refs = _build_high_risk_provider_usecols(headers)
        if not col_refs.get('state') or not col_refs.get('ownership_type'):
            return jsonify({'states': {}, 'quarterRequested': quarter_requested, 'quarter': cy_qtr, 'embedWarning': 'missing_columns'})
        is_snapshot = _provider_csv_is_cms_snapshot(path)
        quarters_in_file = set()
        if is_snapshot:
            effective_cy_qtr = cy_qtr
        else:
            quarters_in_file = _provider_csv_collect_quarters(path, col_refs, pd_local)
            if not quarters_in_file:
                print(f'report fp: no quarters parsed from {path} (check CY_Qtr/quarter columns)', flush=True)
            effective_cy_qtr = _resolve_effective_cy_qtr(cy_qtr, quarters_in_file)
        st_total = {}
        st_fp = {}
        cols = [c for c in usecols if c in head.columns]
        if col_refs.get('cy_qtr') and col_refs['cy_qtr'] not in cols:
            cols.append(col_refs['cy_qtr'])
        if col_refs.get('quarter') and col_refs['quarter'] not in cols:
            cols.append(col_refs['quarter'])
        for chunk in pd_local.read_csv(path, usecols=cols, low_memory=False, chunksize=100000):
            for row in chunk.to_dict('records'):
                rq = _row_cy_qtr_for_high_risk(row, col_refs, pd_local)
                if not is_snapshot and rq != effective_cy_qtr:
                    continue
                st = (row.get(col_refs['state']) or '')
                if st is None or (isinstance(st, float) and pd_local.isna(st)):
                    continue
                abbr = str(st).strip().upper()[:2]
                if len(abbr) != 2:
                    continue
                st_total[abbr] = st_total.get(abbr, 0) + 1
                ot = (row.get(col_refs['ownership_type']) or '')
                if ot is None or (isinstance(ot, float) and pd_local.isna(ot)):
                    ot = ''
                if _ownership_text_is_for_profit(ot):
                    st_fp[abbr] = st_fp.get(abbr, 0) + 1
        out = {}
        for abbr, tot in st_total.items():
            if tot <= 0:
                continue
            fp = st_fp.get(abbr, 0)
            out[abbr] = {'percent': round(100.0 * float(fp) / float(tot), 1)}
        payload = {
            'states': out,
            'quarterRequested': quarter_requested,
            'quarter': effective_cy_qtr,
        }
        if not is_snapshot and quarters_in_file and cy_qtr not in quarters_in_file:
            payload['quarterAdjusted'] = True
        if not out:
            payload['embedWarning'] = 'empty_states'
            qn = len(quarters_in_file) if not is_snapshot else -1
            print(
                f'report fp: empty states path={path} embed_cy_qtr={cy_qtr!r} effective={effective_cy_qtr!r} q_in_file={qn}',
                flush=True,
            )
        return jsonify(payload)
    except Exception as e:
        print(f'for-profit by state failed: {e}', flush=True)
        return jsonify(
            {
                'states': {},
                'quarterRequested': quarter_requested,
                'quarter': cy_qtr,
                'embedWarning': 'read_error',
            }
        )


def _cy_qtr_to_iso_date(cy_qtr) -> str:
    """Map CY_Qtr (e.g. 2025Q4) to an ISO date for structured data / sitemap lastmod."""
    if not cy_qtr:
        return datetime.now().strftime('%Y-%m-%d')
    match = re.match(r'(\d{4})Q(\d)', str(cy_qtr).strip())
    if not match:
        return datetime.now().strftime('%Y-%m-%d')
    year, qn = int(match.group(1)), int(match.group(2))
    month = {1: 1, 2: 4, 3: 7, 4: 10}.get(qn, 1)
    return f'{year}-{month:02d}-01'


def _report_ssr_float_cell(value, decimals: int = 2) -> str:
    if value is None or (HAS_PANDAS and isinstance(value, float) and pd.isna(value)):
        return '—'
    try:
        return f'{float(value):.{decimals}f}'
    except (TypeError, ValueError):
        return '—'


def _build_report_ssr_snapshot() -> dict | None:
    """Build crawler-visible rankings snapshot for /report initial HTML."""
    import csv as _csv

    quarter = get_canonical_latest_quarter()
    ranking_states = STATES_FOR_RANKING if 'STATES_FOR_RANKING' in globals() else set(STATE_CODE_TO_NAME.keys()) - {'PR'}
    rows_data = []
    if HAS_PANDAS:
        if not quarter:
            return None
        state_df = load_csv_data('state_quarterly_metrics.csv')
        if state_df is None or not isinstance(state_df, pd.DataFrame) or state_df.empty:
            return None
        latest = state_df[state_df['CY_Qtr'].astype(str) == str(quarter)].copy()
        if latest.empty:
            return None
        latest['STATE'] = latest['STATE'].astype(str).str.strip().str.upper()
        latest = latest[latest['STATE'].isin(ranking_states)]
        if latest.empty:
            return None
        latest = latest.sort_values('Total_Nurse_HPRD', ascending=False).reset_index(drop=True)
        for _, row in latest.iterrows():
            rows_data.append(row.to_dict())
    else:
        path = os.path.join(APP_ROOT, 'state_quarterly_metrics.csv')
        if not os.path.isfile(path):
            return None
        quarters = set()
        by_state_quarter = {}
        with open(path, newline='', encoding='utf-8') as f:
            for row in _csv.DictReader(f):
                q = (row.get('CY_Qtr') or '').strip()
                if q:
                    quarters.add(q)
                st = (row.get('STATE') or '').strip().upper()
                if not st or st not in ranking_states:
                    continue
                by_state_quarter[(st, q)] = row
        if not quarters:
            return None
        if not quarter:
            quarter = sorted(quarters)[-1]
        for st in ranking_states:
            row = by_state_quarter.get((st, str(quarter)))
            if row:
                rows_data.append(row)
        if not rows_data:
            return None
        rows_data.sort(key=lambda r: float(r.get('Total_Nurse_HPRD') or 0), reverse=True)
    if not quarter or not rows_data:
        return None
    quarter_label = format_quarter(quarter)
    doc_title = f'{quarter_label} U.S. Nursing Home Staffing Rankings by State'
    h1 = doc_title
    table_heading = f'US Nursing Home PBJ Staffing Data ({quarter_label})'
    og_title = f'State and Regional Staffing Rankings for {quarter_label}'
    meta_desc = (
        f'Comprehensive nursing home staffing analysis by state with ratios, medians, and interactive map. '
        f'{quarter_label} staffing rankings, trends, and insights from CMS Payroll-Based Journal (PBJ) data. '
        f'Brought to you by 320 Consulting.'
    )
    og_desc = (
        f'Nursing home staffing rankings by state and CMS region for {quarter_label} '
        f'with comprehensive analysis, ratios, medians, and interactive map.'
    )
    rows = []
    for idx, row in enumerate(rows_data):
        rank = idx + 1
        code = str(row.get('STATE') or row.get('state') or '').strip().upper()
        name = STATE_CODE_TO_NAME.get(code, code)
        slug = get_canonical_slug(code)
        hprd = _report_ssr_float_cell(row.get('Total_Nurse_HPRD'))
        rn_hprd = _report_ssr_float_cell(row.get('RN_HPRD'))
        na_hprd = _report_ssr_float_cell(row.get('Nurse_Assistant_HPRD'))
        try:
            facility_count = int(float(row.get('facility_count') or 0))
        except (TypeError, ValueError):
            facility_count = 0
        try:
            avg_days = float(row.get('avg_days_reported') or 0)
            total_resident_days = float(row.get('total_resident_days') or 0)
        except (TypeError, ValueError):
            avg_days, total_resident_days = 0, 0
        residents = int(round(total_resident_days / avg_days)) if avg_days > 0 else 0
        contract = row.get('Contract_Percentage')
        try:
            contract_text = f'{float(contract):.1f}%' if contract not in (None, '', 'nan') else '—'
        except (TypeError, ValueError):
            contract_text = '—'
        rows.append(
            f'<tr data-report-ssr="1">'
            f'<td class="col-rank rank">{rank}</td>'
            f'<td class="col-state state"><a href="/state/{html.escape(slug)}">{html.escape(name)}</a></td>'
            f'<td class="col-facilities facilities" style="text-align:center">{facility_count:,}</td>'
            f'<td class="col-residents">{residents:,}</td>'
            f'<td class="col-sff desktop-sff-cell"><span class="text-muted">—</span></td>'
            f'<td class="col-hprd reported-value">{hprd}</td>'
            f'<td class="col-hprd reported-value">{rn_hprd}</td>'
            f'<td class="col-hprd reported-value nurse-aide-mobile-hide">{na_hprd}</td>'
            f'<td class="col-contract">{html.escape(contract_text)}</td>'
            f'<td class="col-forprofit">—</td>'
            f'</tr>'
        )
    return {
        'document_title': doc_title,
        'h1': h1,
        'table_heading': table_heading,
        'meta_description': meta_desc,
        'og_title': og_title,
        'og_description': og_desc,
        'jsonld_name': doc_title,
        'date_published': _cy_qtr_to_iso_date(quarter),
        'table_rows': '\n            '.join(rows) if rows else (
            '<tr><td colspan="10" class="loading" id="loadingRow">Loading data...</td></tr>'
        ),
    }


def _inject_report_ssr_html(page_html: str) -> str:
    snap = _build_report_ssr_snapshot()
    if not snap:
        return page_html
    replacements = {
        '__REPORT_SSR_DOCUMENT_TITLE__': html.escape(snap['document_title']),
        '__REPORT_SSR_H1__': html.escape(snap['h1']),
        '__REPORT_SSR_TABLE_HEADING__': html.escape(snap['table_heading']),
        '__REPORT_SSR_META_DESCRIPTION__': html.escape(snap['meta_description'], quote=True),
        '__REPORT_SSR_OG_TITLE__': html.escape(snap['og_title'], quote=True),
        '__REPORT_SSR_OG_DESCRIPTION__': html.escape(snap['og_description'], quote=True),
        '__REPORT_SSR_JSONLD_NAME__': json.dumps(snap['jsonld_name'])[1:-1],
        '__REPORT_SSR_DATE_PUBLISHED__': snap['date_published'],
        '__REPORT_SSR_TABLE_ROWS__': snap['table_rows'],
    }
    for token, value in replacements.items():
        page_html = page_html.replace(token, value)
    return page_html


def _serve_report_page_html():
    path = os.path.join(APP_ROOT, 'report.html')
    with open(path, encoding='utf-8') as f:
        page_html = f.read()
    page_html = _inject_report_ssr_html(page_html)
    resp = make_response(page_html)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


@app.route('/report')
@app.route('/report/')
def report():
    """HTML report, or JSON/CSV when ``?p=`` is set (same URL as the page — survives stacks that only route ``/report``)."""
    p = (request.args.get('p') or '').strip().lower()
    if p == 'fp':
        return _report_embed_for_profit_by_state()
    if p == 'hrs':
        return _report_embed_high_risk_by_state()
    if p == 'hrr':
        return _report_embed_high_risk_by_cms_region()
    if p == 'pi':
        return _report_embed_provider_latest_csv()
    return _serve_report_page_html()


@app.route('/rankings')
@app.route('/rankings/')
def rankings_redirect():
    return redirect('/report', code=301)


# Path-based embeds (same handlers as ``?p=``). Use these from report.html so JSON still works if a
# proxy or dev tool strips query parameters from ``/report?p=fp`` while leaving the path intact.
@app.route('/report/embed/fp')
@app.route('/report/embed/fp/')
def report_embed_fp():
    return _report_embed_for_profit_by_state()


@app.route('/report/embed/hrs')
@app.route('/report/embed/hrs/')
def report_embed_hrs():
    return _report_embed_high_risk_by_state()


@app.route('/report/embed/hrr')
@app.route('/report/embed/hrr/')
def report_embed_hrr():
    return _report_embed_high_risk_by_cms_region()


@app.route('/report/embed/pi')
@app.route('/report/embed/pi/')
def report_embed_pi():
    return _report_embed_provider_latest_csv()


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


# ---------------------------------------------------------------------------
# Insights Hub: dual-track feed (external Substack + native on-site analyses)
# ---------------------------------------------------------------------------
NEWSLETTER_SUBSTACK_FEED = 'https://320insight.substack.com/feed'
NEWSLETTER_POSTS_JSON = 'newsletter_posts.json'
NEWSLETTER_CACHE_SECONDS = 600  # 10 min
_newsletter_cache = None
_newsletter_cache_time = 0
_native_insights_cache = None
_native_insights_cache_time = 0
_NATIVE_INSIGHTS_CACHE_TTL = 60
NEWSLETTER_PBJ_KEYWORDS = (
    'pbj',
    'payroll-based journal',
    'payroll based journal',
    'cms-671',
    'cms 671',
    'five-star',
    'five star',
    'nursing home staffing',
    'staffing hours',
    'staffing threshold',
    'weekend staffing',
    'rn coverage',
    'registered nurse',
    'licensed practical nurse',
    'certified nursing assistant',
    'cna',
    'snf',
    'skilled nursing',
    'medicaid staffing',
    'medicare staffing',
    'long-term care',
    'long term care',
    'nursing facility',
    'nursing homes',
)

INSIGHTS_NATIVE_DIR = os.path.join(APP_ROOT, 'insights_posts')

_INSIGHTS_NATIVE_PAGE_TEMPLATE = """
<!doctype html>
<html lang="en" class="pbj-insights-article">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} | PBJ320 Insights</title>
  <meta name="description" content="{{ description|e }}">
  <link rel="canonical" href="{{ canonical_url|e }}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{{ (title ~ ' | PBJ320 Insights')|e }}">
  <meta property="og:description" content="{{ og_description|e }}">
  <meta property="og:url" content="{{ og_url|e }}">
  <meta property="og:image" content="{{ og_image|e }}">
  <meta property="og:site_name" content="PBJ320">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{{ (title ~ ' | PBJ320 Insights')|e }}">
  <meta name="twitter:description" content="{{ og_description|e }}">
  <meta name="twitter:image" content="{{ og_image|e }}">
  {% if iso_published %}<meta property="article:published_time" content="{{ iso_published }}">{% endif %}
  {% if iso_modified %}<meta property="article:modified_time" content="{{ iso_modified }}">{% endif %}
  <meta name="theme-color" content="#f6f7f9">
  <link rel="icon" type="image/png" href="/pbj_favicon.png">
  <link rel="stylesheet" href="/insights-theme.css?v=29">
  {{ article_json_ld|safe }}
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--pbj-canvas);
      color: var(--pbj-text);
      line-height: 1.62;
    }
    .navbar { position: sticky; top: 0; z-index: 1000; }
    .nav-container { width: min(100%, var(--insights-content-max, 720px)); max-width: var(--insights-content-max, 720px); margin-inline: auto; padding-inline: var(--insights-gutter, clamp(1rem, 3vw, 2rem)); box-sizing: border-box; display: flex; align-items: center; justify-content: space-between; }
    .brand { color: #ffffff; text-decoration: none; font-weight: 700; display: inline-flex; align-items: center; gap: 8px; }
    .brand img { height: 28px; width: auto; }
    .nav-links { display: flex; align-items: center; gap: 30px; }
    .nav-links a { text-decoration: none; font-weight: 500; }
    .wrap { width: min(100%, var(--insights-content-max, 720px)); max-width: var(--insights-content-max, 720px); margin-inline: auto; padding: 1.75rem var(--insights-gutter, clamp(1rem, 3vw, 2rem)) calc(5.5rem + env(safe-area-inset-bottom, 0px)); box-sizing: border-box; }
    .article-shell {
      max-width: none;
      margin: 0;
      background: transparent;
      border: none;
      border-radius: 0;
      box-shadow: none;
      padding: 0;
    }
    .eyebrow {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--pbj-text-muted);
      background: var(--pbj-pill-bg);
      border: 1px solid var(--pbj-pill-ring);
      padding: 0.28rem 0.55rem;
      border-radius: 6px;
      margin: 0 0 0.75rem;
    }
    h1 { margin: 0 0 0.5rem; font-size: clamp(1.65rem, 3.5vw, 2.1rem); line-height: 1.2; color: #0a0f1a; letter-spacing: -0.02em; font-weight: 700; }
    .meta { color: var(--pbj-text-muted); font-size: 0.8rem; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 1rem; font-weight: 600; }
    .lead { color: var(--pbj-text); font-size: 1.02rem; margin-bottom: 1.5rem; line-height: 1.6; border-left: 3px solid var(--pbj-accent, var(--pbj-blue-500)); padding-left: 0.85rem; }
    .article-body { display: flex; flex-direction: column; font-size: 1.075rem; color: #1e293b; max-width: 100%; width: 100%; line-height: 1.78; column-count: 1; columns: auto; }
    .article-body > *, .insight-tips-section, .insight-tips-section li { column-count: 1 !important; columns: auto !important; }
    .article-body h2, .article-body h3 { color: #0a0f1a; margin-top: 1.75rem; line-height: 1.28; font-weight: 700; }
    .article-masthead { margin-bottom: 0.95rem; padding-bottom: 0.8rem; border-bottom: 1px solid #e2e8f0; }
    .article-masthead__top { margin: 0 0 0.65rem; }
    .article-masthead__back { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.32rem 0.7rem 0.32rem 0.55rem; font-size: 0.8125rem; font-weight: 600; color: #334155; text-decoration: none; background: #fff; border: 1px solid rgba(10, 15, 26, 0.1); border-radius: 999px; box-shadow: 0 1px 2px rgba(10, 15, 26, 0.04); transition: border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease; }
    .article-masthead__back:hover { color: #0a0f1a; border-color: rgba(10, 15, 26, 0.18); box-shadow: 0 2px 6px rgba(10, 15, 26, 0.06); }
    .article-masthead__back-icon { display: inline-block; width: 0.45rem; height: 0.45rem; margin-left: 0.1rem; border-left: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor; transform: rotate(45deg); opacity: 0.75; }
    .article-masthead__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0.2rem 0.4rem; margin: 0 0 0.5rem; font-size: 0.78rem; font-weight: 500; letter-spacing: 0.02em; color: #64748b; }
    .article-masthead__title { line-height: 1.12; letter-spacing: -0.03em; margin: 0; font-size: clamp(1.38rem, 3vw, 1.82rem); color: #0a0f1a; }
    .article-dek { margin: 0.4rem 0 0; font-size: 0.875rem; font-weight: 500; line-height: 1.45; color: #64748b; }
    .article-cover { margin: 1rem 0 0; padding: 0; max-width: 100%; }
    .article-cover img { display: block; width: 100%; height: auto; border-radius: 12px; border: 1px solid rgba(10, 15, 26, 0.08); }
    .article-cover__caption { margin: 0.5rem 0 0; font-size: 0.84rem; line-height: 1.4; font-style: italic; color: #64748b; text-align: center; }
    .article-masthead__sep { opacity: 0.55; }
    .article-body h3.insight-section-heading { margin: 1.75rem 0 0.65rem; font-size: 1.15rem; font-weight: 700; line-height: 1.3; color: var(--pbj-heading); }
    .insight-source-directory { background: #eef2f7; border: 1px solid rgba(10, 15, 26, 0.08); border-radius: 10px; }
    .insight-source-directory__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.1rem 1.75rem; }
    .insight-source-directory__title { margin: 0 0 0.75rem; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #1e293b; }
    .article-body .insight-source-directory__heading { font-size: 0.84rem; color: #0a0f1a; text-transform: none; letter-spacing: 0; }
    .insight-source-directory__links li { display: block; margin-bottom: 0.65rem; }
    .insight-source-directory__desc { display: block; margin-top: 0.12rem; font-size: 0.8125rem; }
    .article-body .insight-source-directory__links a { font-size: 0.9rem; font-weight: 600; color: #2563eb; text-decoration: underline; text-underline-offset: 0.14em; }
    .insight-phoebe-callout { background: #eef2f7; border: 1px solid rgba(10, 15, 26, 0.08); border-left: 3px solid #60a5fa; border-radius: 10px; }
    .insight-fast-callout { background: #eef2f7; border: 1px solid rgba(10, 15, 26, 0.08); border-left: 3px solid #60a5fa; border-radius: 10px; }
    .insight-pbj320-fit { margin: 1rem 0 1.5rem; padding: 1rem 1.15rem; background: #eef2f7; border: 1px solid rgba(10, 15, 26, 0.08); border-radius: 10px; }
    .insight-pbj320-fit__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1.1rem 1.75rem; }
    .insight-pbj320-fit__col--is { padding-left: 0.85rem; border-left: 3px solid #60a5fa; }
    .insight-pbj320-fit__col--ai { padding-left: 0.85rem; border-left: 3px solid rgba(96, 165, 250, 0.55); }
    .insight-pbj320-fit__label { margin: 0 0 0.4rem; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #334155; }
    .insight-pbj320-fit__text { margin: 0; font-size: 0.94rem; line-height: 1.55; color: #1e293b; }
    .insight-colophon { display: flex; gap: 0.85rem; align-items: flex-start; margin: 2rem 0 0.15rem; padding: 0.95rem 1rem 1rem; background: #eef2f7; border: 1px solid rgba(10, 15, 26, 0.08); border-left: 3px solid #60a5fa; border-radius: 10px; }
    .insight-colophon__avatar { flex-shrink: 0; width: 44px; height: 44px; border-radius: 50%; box-shadow: 0 1px 3px rgba(10, 15, 26, 0.08); }
    .insight-colophon__label { margin: 0 0 0.4rem; font-size: 0.9rem; font-weight: 700; color: #0a0f1a; text-transform: none; }
    .insight-colophon__sublabel { font-weight: 500; color: #64748b; }
    .insight-colophon__body { margin: 0; font-size: 0.9rem; line-height: 1.65; color: #475569; }
    .article-body h2.insight-tips-heading { margin: 1.65rem 0 1rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; font-size: clamp(1.28rem, 2.8vw, 1.48rem); color: #0a0f1a; }
    .insight-source-directory__desc { font-size: 0.875rem; color: var(--pbj-text-muted); }
    .article-body .insight-media__frame { font-size: 0.875rem; border-style: solid; }
    .article-body p { margin: 0.95rem 0; }
    .article-body ul:not(.insight-tips-list):not(.insight-source-directory__links),
    .article-body ol:not(.insight-tips-list) { margin: 0.9rem 0 0.9rem 1.15rem; padding-left: 1.15rem; }
    .article-body table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.94rem; }
    .article-body figure.insight-chart { margin: 1.35rem 0 1.5rem; max-width: 100%; }
    .article-body figure.insight-chart img { max-width: 100%; height: auto; display: block; border-radius: 8px; border: 1px solid var(--pbj-border-panel); }
    .article-body figcaption { font-size: 0.88rem; color: var(--pbj-text-muted); line-height: 1.45; margin-top: 0.5rem; }
    .article-body th, .article-body td { border: 1px solid var(--pbj-slate-700); padding: 0.5rem 0.55rem; text-align: left; }
    .article-body th { background: var(--pbj-slate-800); color: var(--pbj-slate-200); font-weight: 600; }
    .article-body a { color: var(--pbj-link, var(--pbj-sky-bright)); text-decoration: underline; text-decoration-color: var(--pbj-link-decoration, var(--pbj-sky)); text-underline-offset: 0.18em; font-weight: 500; }
    .article-body a:hover { color: var(--pbj-link-hover, var(--pbj-sky-pale)); text-decoration-color: var(--pbj-accent, var(--pbj-sky)); }
    .article-body code { background: var(--pbj-slate-800); color: var(--pbj-slate-200); border-radius: 4px; padding: 0.12rem 0.35rem; font-size: 0.9em; }
    .article-body pre { background: var(--pbj-chrome); color: var(--pbj-slate-200); border: 1px solid var(--pbj-slate-600); border-radius: 8px; padding: 14px; overflow: auto; font-size: 0.88rem; }
    .dashboard-callout {
      margin: 1.35rem 0;
      padding: 1rem 1.1rem;
      border-radius: 12px;
      border: 1px solid var(--pbj-pill-ring-soft);
      background: var(--pbj-veil-deep);
    }
    .dashboard-callout-title { margin: 0 0 0.35rem; font-size: 0.82rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--pbj-text-muted); }
    .dashboard-callout-desc { margin: 0 0 0.75rem; font-size: 0.92rem; color: var(--pbj-text-muted); line-height: 1.5; }
    .dashboard-callout-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-weight: 600;
      font-size: 0.9rem;
      color: var(--pbj-btn-text, var(--pbj-on-light-button));
      background: var(--pbj-btn-surface, linear-gradient(135deg, var(--pbj-btn-primary-top), var(--pbj-btn-primary-bot)));
      text-decoration: none;
      padding: 0.5rem 0.95rem;
      border-radius: 999px;
      border: 1px solid var(--pbj-btn-outline, var(--pbj-btn-border));
    }
    .dashboard-callout-btn:hover { filter: none; background: var(--pbj-btn-surface-hover, var(--pbj-btn-primary-bot)); }
    .niche-reference-box, .niche-evidence {
      margin: 0 0 1.1rem;
      padding: 1rem 1rem 1rem 1.05rem;
      border-radius: 10px;
      border: 1px solid var(--pbj-border-panel-strong);
      background: var(--pbj-veil);
      border-left: 4px solid var(--pbj-accent, var(--pbj-blue-500));
    }
    .niche-reference-box h2, .niche-evidence h2 { margin: 0 0 0.5rem; font-size: 1.05rem; color: var(--pbj-heading-soft); font-weight: 700; }
    .niche-reference-box p, .niche-evidence p { margin: 0; color: var(--pbj-text-muted); font-size: 0.95rem; }
    .niche-reference-box a { color: var(--pbj-link, var(--pbj-sky-bright)); font-weight: 600; }
    .niche-follow { margin: 1rem 0 0; padding-top: 0.85rem; border-top: 1px solid var(--pbj-border-row); font-size: 0.9rem; }
    .niche-follow a { color: var(--pbj-link, var(--pbj-sky-bright)); font-weight: 600; text-decoration: underline; text-underline-offset: 0.15em; }
    .niche-follow a:hover { text-decoration: underline; }
    .niche-follow-muted { color: var(--pbj-text-muted); }
    .niche-evidence-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .niche-evidence-table { width: 100%; border-collapse: collapse; background: var(--pbj-veil); border-radius: 8px; overflow: hidden; }
    .niche-evidence-table th, .niche-evidence-table td { border: 1px solid var(--pbj-slate-700); padding: 0.45rem 0.55rem; font-size: 0.88rem; color: var(--pbj-text); }
    .niche-evidence-table th { background: var(--pbj-slate-800); color: var(--pbj-slate-200); font-weight: 600; }
    .niche-chart-box h3 { margin: 0 0 0.4rem; color: var(--pbj-slate-200); font-size: 0.92rem; font-weight: 700; }
    .niche-bar-row { display: grid; grid-template-columns: 88px 1fr 52px; align-items: center; gap: 8px; margin-bottom: 7px; }
    .niche-bar-track { height: 8px; background: var(--pbj-slate-700); border-radius: 999px; overflow: hidden; }
    .niche-bar-fill { height: 100%; background: linear-gradient(90deg, var(--pbj-blue-600), var(--pbj-sky-400)); }
    .niche-bar-label, .niche-bar-value { font-size: 0.8rem; color: var(--pbj-text-muted); }
    .niche-stars { margin: 0; font-size: 0.9rem; color: var(--pbj-text); line-height: 1.55; }
    .subscribe-cta-sticky { position: fixed; left: 0; right: 0; bottom: 0; z-index: 1200; background: #f6f7f9; border-top: 1px solid rgba(10, 15, 26, 0.08); box-shadow: none; }
    .subscribe-cta-inner { width: min(100%, var(--insights-content-max, 720px)); max-width: var(--insights-content-max, 720px); margin-inline: auto; padding: 0.7rem var(--insights-gutter, clamp(1rem, 3vw, 2rem)); box-sizing: border-box; display: flex; flex-wrap: nowrap; align-items: center; gap: 0.75rem 1.25rem; justify-content: space-between; }
    .subscribe-cta-copy { color: #1e293b; font-weight: 500; font-size: 0.95rem; }
    .subscribe-cta-link {
      color: #ffffff;
      text-decoration: none;
      background: #0a0f1a;
      border: 1px solid #0a0f1a;
      border-radius: 10px;
      padding: 0.58rem 1.15rem;
      font-weight: 600;
      white-space: nowrap;
      box-shadow: 0 1px 2px rgba(10, 15, 26, 0.12), 0 4px 14px rgba(10, 15, 26, 0.18);
    }
    .subscribe-cta-link:hover { filter: none; background: #1e293b; border-color: #1e293b; }
    .breadcrumb { margin: 0 0 0.75rem; font-size: 0.82rem; color: var(--pbj-text-muted); }
    .breadcrumb ol { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; }
    .breadcrumb li { display: inline; }
    .breadcrumb li:not(:last-child)::after { content: "/"; margin-left: 0.35rem; color: var(--pbj-slate-600); }
    .breadcrumb a { color: var(--pbj-link, var(--pbj-sky-bright)); text-decoration: underline; text-underline-offset: 0.15em; font-weight: 500; }
    .breadcrumb a:hover { text-decoration: underline; }
    .breadcrumb .bc-current { color: var(--pbj-text-muted); font-weight: 500; max-width: 42ch; display: inline-block; vertical-align: bottom; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .article-nav-back { margin: 0 0 0.85rem; }
    .article-nav-back a { color: var(--pbj-link, var(--pbj-sky-bright)); text-decoration: underline; text-underline-offset: 0.15em; font-size: 0.88rem; font-weight: 600; }
    .article-nav-back a:hover { text-decoration: underline; }
    .byline { margin: 0 0 0.35rem; font-size: 0.88rem; color: var(--pbj-text-muted); }
    .byline-author { font-weight: 600; color: var(--pbj-text); }
    .byline-org { margin-left: 0.35rem; }
    .meta-sep { margin: 0 0.25rem; opacity: 0.85; }
    .related-insights { margin-top: 2rem; padding-top: 1.25rem; border-top: 1px solid var(--pbj-border-row); }
    .related-insights-title { font-size: 1rem; color: var(--pbj-heading-soft); margin: 0 0 0.65rem; font-weight: 700; }
    .related-insights ul { list-style: none; margin: 0; padding: 0; }
    .related-insights li { margin: 0.45rem 0; }
    .related-insights a { color: var(--pbj-link, var(--pbj-sky-bright)); text-decoration: underline; text-underline-offset: 0.15em; font-weight: 500; }
    .related-insights a:hover { text-decoration: underline; }
    .related-meta { display: block; font-size: 0.78rem; color: var(--pbj-text-muted); margin-top: 0.12rem; }
    @media (max-width: 760px) {
      .nav-links { gap: 12px; font-size: 0.92rem; }
      .article-shell { padding: 1.1rem; }
      .article-body { font-size: 0.98rem; }
      .insight-source-directory__grid { grid-template-columns: 1fr; }
      .niche-evidence-grid { grid-template-columns: 1fr; }
    }
    .insight-fast-callout strong { color: var(--pbj-heading); }
    .insight-source-links {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin: 0 0 1.5rem;
    }
    .insight-source-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 0.86rem;
      color: var(--pbj-btn-text, var(--pbj-on-light-button));
      background: var(--pbj-btn-surface, linear-gradient(135deg, var(--pbj-btn-primary-top), var(--pbj-btn-primary-bot)));
      text-decoration: none;
      padding: 0.45rem 0.85rem;
      border-radius: 999px;
      border: 1px solid var(--pbj-btn-outline, var(--pbj-btn-border));
      white-space: nowrap;
    }
    .insight-source-btn:hover { filter: none; background: var(--pbj-btn-surface-hover, var(--pbj-btn-primary-bot)); text-decoration: none; }
    .insight-source-btn--muted {
      background: var(--pbj-veil);
      color: var(--pbj-text-muted);
      border-color: var(--pbj-border-panel);
      cursor: not-allowed;
      pointer-events: none;
      opacity: 0.85;
    }
    .insight-source-btn--secondary {
      background: transparent;
      color: var(--pbj-text);
      border-color: var(--pbj-btn-outline, var(--pbj-pill-ring));
    }
    .insight-source-btn--secondary:hover { color: var(--pbj-btn-text); background: var(--pbj-btn-surface); }
    .insight-tips-section { display: block; width: 100%; max-width: 100%; }
    .article-body ol.insight-tips-list { list-style: none; counter-reset: insight-tip; margin: 0 0 1.75rem; padding: 0; width: 100%; }
    .article-body ol.insight-tips-list > li { display: block; position: relative; counter-increment: insight-tip; margin: 0 0 1.15rem; padding: 0 0 0 2.25rem; line-height: 1.68; max-width: 100%; }
    .article-body ol.insight-tips-list > li::marker { content: none; }
    .article-body ol.insight-tips-list > li::before { content: counter(insight-tip) "."; position: absolute; left: 0; top: 0; width: 2rem; font-weight: 700; color: #2563eb; }
    .article-body ol.insight-tips-list > li strong { color: #0a0f1a; }
    .pbj-insights-details {
      border: 1px solid rgba(10, 15, 26, 0.09);
      border-radius: 10px;
      background: #eef2f7;
      margin: 1.15rem 0;
      overflow: hidden;
    }
    .pbj-insights-details summary {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      list-style: none;
      cursor: pointer;
      padding: 0.85rem 1rem;
      font-weight: 600;
      font-size: 1.02rem;
      font-style: normal;
      line-height: 1.35;
      color: var(--pbj-heading);
      background: #e8edf3;
      user-select: none;
    }
    .pbj-insights-details summary::-webkit-details-marker { display: none; }
    .pbj-insights-details summary::after {
      content: "";
      flex-shrink: 0;
      width: 0.5rem;
      height: 0.5rem;
      margin-top: -0.15rem;
      border-right: 2px solid var(--pbj-text-muted);
      border-bottom: 2px solid var(--pbj-text-muted);
      transform: rotate(45deg);
      transition: transform 0.15s ease;
    }
    .pbj-insights-details[open] summary::after { transform: rotate(-135deg); margin-top: 0.15rem; }
    .pbj-insights-details summary:hover { background: #dfe6ef; color: var(--pbj-heading); }
    .pbj-insights-details[open] summary { border-bottom: 1px solid var(--pbj-border-row); }
    .pbj-insights-details-body { padding: 0.85rem 1rem 1rem; }
    .pbj-insights-details-body > :first-child { margin-top: 0; }
    .pbj-insights-details-body > :last-child { margin-bottom: 0; }
    .insight-prompt-grid { display: grid; gap: 0.85rem; margin-top: 0.5rem; }
    .insight-prompt-card {
      border: 1px solid var(--pbj-border-panel);
      border-radius: 8px;
      padding: 0.75rem 0.85rem;
      background: rgba(15, 23, 42, 0.35);
    }
    .insight-prompt-card h4 { margin: 0 0 0.35rem; font-size: 0.92rem; color: var(--pbj-heading-soft); }
    .insight-prompt-desc { margin: 0 0 0.5rem; font-size: 0.88rem; color: var(--pbj-text-muted); line-height: 1.45; }
    .insight-prompt-text {
      margin: 0 0 0.55rem;
      padding: 0.65rem 0.75rem;
      font-size: 0.82rem;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
      border-radius: 6px;
      border: 1px solid var(--pbj-slate-700);
      background: var(--pbj-chrome);
      color: var(--pbj-slate-200);
    }
    .insight-prompt-copy {
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--pbj-text);
      background: transparent;
      border: 1px solid var(--pbj-btn-outline, var(--pbj-pill-ring));
      border-radius: 999px;
      padding: 0.28rem 0.65rem;
      cursor: pointer;
    }
    .insight-prompt-copy:hover { background: var(--pbj-btn-surface, var(--pbj-pill-bg)); }
    .insight-prompt-caveat { font-size: 0.84rem; color: var(--pbj-text-muted); margin: 0.75rem 0 0; line-height: 1.5; }
    .insight-sendoff { margin: 2rem 0 0; padding: 1.25rem 0 0; border-top: 1px solid var(--pbj-border-row); }
    .insight-sendoff__text { margin: 0 0 0.85rem; font-size: 1.02rem; line-height: 1.65; color: var(--pbj-text); }
    .insight-sendoff__actions { margin: 0.25rem 0 0; }
    .insight-sendoff__btn { display: inline-block; padding: 0.5rem 0.95rem; font-size: 0.9rem; font-weight: 600; color: #fff; text-decoration: none; background: #0a0f1a; border-radius: 999px; }
    .insight-sendoff__btn:hover { color: #fff; background: #1e293b; }
    @media (max-width: 760px) {
      .insight-source-links { gap: 0.45rem; }
      .insight-source-btn { font-size: 0.82rem; padding: 0.42rem 0.72rem; white-space: normal; text-align: center; }
    }
  </style>
</head>
<body>
  <nav class="navbar" aria-label="Main">
    <div class="nav-container">
      <a class="brand" href="/">
        <img src="/pbj_favicon.png" alt="PBJ320">
        <span><span class="pbj-brand-pbj">PBJ</span><span class="pbj-brand-320">320</span></span>
      </a>
      <div class="nav-links">
        <a href="/about">About</a>
        <a href="/report">Report</a>
        <a href="/insights" class="active" aria-current="page">Insights</a>
        <a href="/phoebe">PBJ Explained</a>
        <a href="/owners">Ownership</a>
      </div>
    </div>
  </nav>
  <main class="wrap">
    <article class="article-shell">
      <header class="article-masthead">
        <div class="article-masthead__top">
          <a class="article-masthead__back" href="{{ site_base }}/insights"><span class="article-masthead__back-icon" aria-hidden="true"></span>Insights</a>
        </div>
        <p class="article-masthead__meta">
          <span>{{ author_name }}</span><span class="article-masthead__sep" aria-hidden="true">·</span><span>320 Consulting</span>{% if read_time %}<span class="article-masthead__sep" aria-hidden="true">·</span><span>{{ read_time }}</span>{% endif %}<span class="article-masthead__sep" aria-hidden="true">·</span><span>{{ formatted_date }}</span>{% if show_updated %}<span class="article-masthead__sep" aria-hidden="true">·</span><span>Updated {{ formatted_updated }}</span>{% endif %}
        </p>
        <h1 class="article-masthead__title">{{ title }}</h1>
        {% if description %}<p class="article-dek">{{ description }}</p>{% endif %}
        {% if show_cover %}
        <figure class="article-cover">
          <img src="{{ cover_image|e }}" alt="{{ cover_alt|e }}" width="1200" height="auto" loading="eager" decoding="async" />
          {% if cover_caption %}<figcaption class="article-cover__caption">{{ cover_caption }}</figcaption>{% endif %}
        </figure>
        {% endif %}
      </header>
      <section class="article-body">{{ content_html|safe }}</section>
      {{ related_html|safe }}
    </article>
  </main>
  <aside class="subscribe-cta-sticky" aria-label="Substack subscription prompt">
    <div class="subscribe-cta-inner">
      <p class="subscribe-cta-copy">Want the story behind the data? Subscribe to our Substack.</p>
      <a class="subscribe-cta-link" href="https://320insight.substack.com/" target="_blank" rel="noopener">Subscribe</a>
    </div>
  </aside>
  <footer class="footer" id="site-footer"></footer>
  <script src="/pbj-site-universal.js?v=13"></script>
  <script>
    (function () {
      document.querySelectorAll('.insight-prompt-copy').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var id = btn.getAttribute('data-copy-target');
          var el = id ? document.getElementById(id) : null;
          if (!el) return;
          var text = (el.textContent || '').trim();
          if (!text) return;
          var done = function () {
            var prev = btn.getAttribute('aria-label') || btn.textContent;
            btn.textContent = 'Copied';
            setTimeout(function () { btn.textContent = prev; }, 1600);
          };
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done).catch(function () {
              try {
                var ta = document.createElement('textarea');
                ta.value = text;
                ta.setAttribute('readonly', '');
                ta.style.position = 'fixed';
                ta.style.left = '-9999px';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                done();
              } catch (e) {}
            });
          }
        });
      });
    })();
  </script>
</body>
</html>
"""


def _strip_html_fragment(raw: str, max_len: int = 480) -> str:
    """Remove HTML tags for a preview snippet; limit length (default 480 chars)."""
    if not raw or not isinstance(raw, str):
        return ''
    # Strip tags and normalize whitespace for a clean preview snippet.
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'\s+', ' ', text).strip()

    # Substack/RSS previews often append "Read more" / "Continue reading".
    # Remove these before truncation so we don't end up with artifacts like "R…".
    text = re.sub(r'\b(read more|continue reading)\b\.?', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) <= max_len:
        return text

    # Truncate on a word boundary when possible to avoid cutting mid-token.
    boundary = text.rfind(' ', 0, max_len)
    if boundary > 0:
        text = text[:boundary].rstrip()
    else:
        text = text[:max_len].rstrip()
    return text + '…'


def _elem_text(el) -> str:
    """Get all text content of an element (including nested). Safe for None."""
    if el is None:
        return ''
    return ''.join(el.itertext()).strip()


def _local_tag(tag: str) -> str:
    """Strip XML namespace from tag: '{http://...}title' -> 'title'."""
    if not tag:
        return ''
    return tag.split('}')[-1] if '}' in tag else tag


def _is_pbj_related_post(row: dict) -> bool:
    """Heuristic filter so newsletter only shows PBJ/nursing-home staffing posts."""
    if not isinstance(row, dict):
        return False
    haystack_parts = [
        row.get('title') or '',
        row.get('description') or '',
        row.get('url') or '',
    ]
    categories = row.get('categories') or []
    if isinstance(categories, list):
        haystack_parts.extend(c for c in categories if isinstance(c, str))
    haystack = ' '.join(haystack_parts).lower()
    return any(keyword in haystack for keyword in NEWSLETTER_PBJ_KEYWORDS)


def _slugify_insights(raw: str) -> str:
    if not raw:
        return ''
    slug = re.sub(r'[^a-z0-9]+', '-', raw.strip().lower())
    return re.sub(r'-{2,}', '-', slug).strip('-')


def _to_sort_date(raw_date: str) -> str:
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw_date or '')
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        if re.match(r'^\d{4}-\d{2}-\d{2}', raw_date or ''):
            return (raw_date or '1970-01-01')[:10] + 'T00:00:00'
        return raw_date or '1970-01-01'


def _parse_rss_item(item_el) -> dict | None:
    """Extract title, link, description, pubDate, image from an RSS <item>. Iterate children so namespaces don't break find()."""
    title = ''
    link = ''
    link_from_href = ''
    description = ''
    raw_date = ''
    image_url = ''
    encoded_full = ''
    categories = []
    for el in item_el:
        local = _local_tag(getattr(el, 'tag', ''))
        txt = (el.text or '').strip() or _elem_text(el)
        if local == 'title':
            title = txt
        elif local == 'link':
            if txt:
                link = txt
            elif el.get('href'):
                link_from_href = (el.get('href') or '').strip()
        elif local == 'description':
            description = _strip_html_fragment(txt or _elem_text(el))
        elif local == 'encoded':
            encoded_full = txt or _elem_text(el)
        elif local == 'enclosure':
            url = (el.get('url') or '').strip()
            if url and ('image' in (el.get('type') or '').lower() or not el.get('type')):
                image_url = url
        elif local.lower() == 'pubdate':
            raw_date = txt
        elif local == 'date':
            if not raw_date:
                raw_date = txt
        elif local == 'category':
            if txt:
                categories.append(txt)
    if not link:
        link = link_from_href
    if not title or not link:
        return None
    if encoded_full and len(encoded_full) > len(description or ''):
        description = _strip_html_fragment(encoded_full)
    return {
        'title': title,
        'url': link,
        'external_url': link,
        'type': 'external',
        'description': description,
        'date': raw_date,
        'source': 'substack',
        'image_url': image_url or None,
        'categories': categories,
    }


def _fetch_substack_posts() -> list:
    """Fetch Substack RSS and return only PBJ/nursing-home staffing items."""
    out = []
    try:
        req = Request(NEWSLETTER_SUBSTACK_FEED, headers={'User-Agent': 'PBJ320-Newsletter/1.0'})
        with urlopen(req, timeout=15) as resp:
            tree = ET.parse(resp)
        root = tree.getroot()
        items = root.findall('.//item')
        if not items:
            items = root.findall('.//{http://purl.org/rss/1.0/}item')
        for item_el in items:
            row = _parse_rss_item(item_el)
            if not row:
                continue
            if not _is_pbj_related_post(row):
                continue
            raw = row.get('date') or ''
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(raw)
                row['sort_date'] = dt.strftime('%Y-%m-%dT%H:%M:%S')
            except Exception:
                row['sort_date'] = raw or '1970-01-01'
            out.append(row)
    except Exception as e:
        print(f'[newsletter] Substack feed error: {e}', flush=True)
    return out


def _star_icons_from_rating(val) -> str:
    if val is None:
        return "—"
    try:
        _n = round_half_up(float(val), 0)
        n = int(_n) if _n is not None else None
        if n is not None and 1 <= n <= 5:
            return "★" * n
    except (TypeError, ValueError):
        pass
    return "—"


def _ensure_pandas_loaded_for_insights() -> bool:
    global pd
    if pd is None:
        pd = get_pd()
    return pd is not None


_INSIGHTS_ALLOWED_TAGS = {
    'p', 'a', 'strong', 'em', 'ul', 'ol', 'li', 'blockquote',
    'code', 'pre', 'h2', 'h3', 'h4', 'hr', 'br',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img', 'figure', 'figcaption',
    'details', 'summary', 'div', 'span', 'aside', 'button',
}
_INSIGHTS_ALLOWED_ATTRS = {
    'a': {'href', 'title', 'class', 'target', 'rel'},
    'th': {'colspan', 'rowspan'},
    'td': {'colspan', 'rowspan'},
    'img': {'src', 'alt', 'width', 'height', 'loading', 'class', 'decoding'},
    'figure': {'class'},
    'figcaption': {'class'},
    'blockquote': {'class'},
    'details': {'class', 'id'},
    'summary': {'class'},
    'div': {'class', 'role', 'id', 'data-audience'},
    'span': {'class', 'aria-hidden'},
    'aside': {'class', 'role'},
    'p': {'class'},
    'pre': {'class', 'id'},
    'button': {'type', 'class', 'data-copy-target', 'aria-label'},
    'ul': {'class'},
    'ol': {'class'},
    'li': {'class'},
    'h2': {'class'},
    'h3': {'class'},
}
_INSIGHTS_BLOCKED_TAGS = {'script', 'style', 'iframe', 'object', 'embed'}


def _sanitize_nav_or_external_url(raw_url: str, allow_relative: bool = True) -> str:
    url = (raw_url or '').strip()
    if not url:
        return ''
    parsed = urlparse(url)
    scheme = (parsed.scheme or '').lower()
    if scheme in ('http', 'https', 'mailto'):
        return url
    if allow_relative and url.startswith('/'):
        return url
    if allow_relative and url.startswith('#'):
        return url
    return ''


class _InsightsHTMLSanitizer(HTMLParser):
    """Allowlist-based sanitizer for author-provided native insight HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        t = (tag or '').lower()
        if t in _INSIGHTS_BLOCKED_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return
        if t not in _INSIGHTS_ALLOWED_TAGS:
            return
        allowed = _INSIGHTS_ALLOWED_ATTRS.get(t, set())
        clean_attrs = []
        for key, value in (attrs or []):
            k = (key or '').lower()
            if k not in allowed:
                continue
            v = '' if value is None else str(value)
            if t == 'a' and k == 'href':
                v = _sanitize_nav_or_external_url(v, allow_relative=True)
                if not v:
                    continue
            if t == 'a' and k in ('target', 'rel'):
                v = re.sub(r'[^a-z_\s-]', '', (v or '').lower())
                if not v:
                    continue
            if t == 'button' and k == 'type':
                v = (v or '').lower()
                if v not in ('button', 'submit'):
                    continue
            if t == 'button' and k == 'data-copy-target':
                v = re.sub(r'[^a-zA-Z0-9_-]', '', v or '')
                if not v:
                    continue
            if t == 'img' and k == 'src':
                v = _sanitize_nav_or_external_url(v, allow_relative=True)
                if not v or not v.startswith('/') or '..' in v:
                    continue
            clean_attrs.append((k, html.escape(v, quote=True)))
        attrs_str = ''.join([f' {k}="{v}"' for (k, v) in clean_attrs])
        self.out.append(f'<{t}{attrs_str}>')

    def handle_endtag(self, tag):
        t = (tag or '').lower()
        if t in _INSIGHTS_BLOCKED_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if self.skip_depth > 0:
            return
        if t in _INSIGHTS_ALLOWED_TAGS:
            self.out.append(f'</{t}>')

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        self.out.append(html.escape(data or ''))

    def handle_entityref(self, name):
        if self.skip_depth == 0:
            self.out.append(f'&{name};')

    def handle_charref(self, name):
        if self.skip_depth == 0:
            self.out.append(f'&#{name};')

    def handle_comment(self, data):
        return


def _sanitize_insights_html(raw_html: str) -> str:
    if not raw_html:
        return ''
    parser = _InsightsHTMLSanitizer()
    try:
        parser.feed(raw_html)
        parser.close()
    except Exception:
        return html.escape(raw_html)
    return ''.join(parser.out)


def _extract_markdown_front_matter(raw_text: str) -> tuple[dict, str]:
    if not raw_text.startswith('---\n'):
        return {}, raw_text
    end_idx = raw_text.find('\n---\n', 4)
    if end_idx < 0:
        return {}, raw_text
    header = raw_text[4:end_idx]
    body = raw_text[end_idx + 5:]
    out = {}
    for line in header.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out, body.strip()


def _parse_tags_field(raw_tags) -> list:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        return [str(t).strip() for t in raw_tags if str(t).strip()]
    txt = str(raw_tags).strip()
    if not txt:
        return []
    return [part.strip() for part in txt.split(',') if part.strip()]


def _latest_quarter_refresh_date_iso() -> str:
    """Best-effort YYYY-MM-DD date from latest_quarter_data.json file update time."""
    path = os.path.join(APP_ROOT, 'latest_quarter_data.json')
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
    except Exception:
        return datetime.utcnow().strftime('%Y-%m-%d')


def _resolve_chain_id_from_name(chain_name: str):
    if not chain_name:
        return None
    if not _ensure_pandas_loaded_for_insights():
        return None
    nm = str(chain_name).strip().lower()
    if not nm:
        return None
    paths = [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
    ]
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception:
            continue
        for name_col, id_col in (('chain_name', 'chain_id'), ('affiliated_entity_name', 'affiliated_entity_id')):
            if name_col not in df.columns or id_col not in df.columns:
                continue
            sub = df[df[name_col].astype(str).str.strip().str.lower() == nm]
            if sub.empty:
                continue
            try:
                return int(float(sub.iloc[0].get(id_col)))
            except (TypeError, ValueError):
                continue
    return None


def _load_native_insights_markdown_posts() -> list:
    posts = []
    if not os.path.isdir(INSIGHTS_NATIVE_DIR):
        return posts
    try:
        filenames = [f for f in os.listdir(INSIGHTS_NATIVE_DIR) if f.lower().endswith('.md') and not f.startswith('_')]
    except Exception:
        return posts
    for filename in filenames:
        path = os.path.join(INSIGHTS_NATIVE_DIR, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read()
        except Exception:
            continue
        front, body_md = _extract_markdown_front_matter(raw)
        title = (front.get('title') or '').strip()
        slug = (front.get('slug') or '').strip() or _slugify_insights(os.path.splitext(filename)[0])
        if not title or not slug:
            continue
        raw_date = (front.get('date') or '').strip()
        dynamic_from_pbj_refresh = str(front.get('dateFromLatestQuarterUpdate') or '').strip().lower() in ('1', 'true', 'yes')
        if dynamic_from_pbj_refresh:
            raw_date = _latest_quarter_refresh_date_iso()
        target_entity = (front.get('targetEntity') or '').strip()
        target_entity_type = (front.get('targetEntityType') or '').strip().lower()
        explicit_url = (front.get('url') or '').strip()
        hide_from_hub = str(front.get('hideFromHub') or '').strip().lower() in ('1', 'true', 'yes')
        published_raw = str(front.get('published') or 'true').strip().lower()
        published = published_raw not in ('0', 'false', 'no')
        show_on_provider_page = str(front.get('showOnProviderPage') or '').strip().lower() in ('1', 'true', 'yes')
        post = {
            'type': 'native',
            'title': title,
            'slug': slug,
            'url': explicit_url or f'/insights/{slug}',
            'description': (front.get('description') or '').strip(),
            'date': raw_date,
            'sort_date': _to_sort_date(raw_date),
            'updated': (front.get('updated') or front.get('lastModified') or '').strip(),
            'author': (front.get('author') or '').strip(),
            'source': 'native-markdown',
            'preview_image': (front.get('previewImage') or '').strip() or '/insights-native-preview.svg',
            'cover_caption': (front.get('coverCaption') or front.get('cover_caption') or '').strip(),
            'cover_alt': (front.get('coverAlt') or front.get('cover_alt') or '').strip(),
            'read_time': (front.get('readTime') or front.get('read_time') or '').strip(),
            'tags': _parse_tags_field(front.get('tags')),
            'reference_title': (front.get('referenceTitle') or '').strip(),
            'reference_url': (front.get('referenceUrl') or '').strip(),
            'targetEntity': target_entity,
            'targetEntityType': target_entity_type,
            'content_markdown': body_md.strip(),
            'hide_from_hub': hide_from_hub,
            'published': published,
            'show_on_provider_page': show_on_provider_page,
        }
        if target_entity and not post['targetEntityType']:
            post['targetEntityType'] = 'provider' if target_entity.isdigit() and len(target_entity) <= 6 else 'chain'
        posts.append(post)
    return posts


def _load_manual_newsletter_posts() -> list:
    """Load manual external/native entries from newsletter_posts.json in project root."""
    path = os.path.join(APP_ROOT, NEWSLETTER_POSTS_JSON)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'[newsletter] manual posts load error: {e}', flush=True)
        return []
    if not isinstance(data, list):
        return []
    out = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        row_type = (entry.get('type') or 'external').strip().lower()
        if row_type not in ('external', 'native'):
            row_type = 'external'
        title = entry.get('title') or ''
        if not title:
            continue
        raw_date = entry.get('date') or ''
        row = {
            'type': row_type,
            'title': title,
            'description': (entry.get('description') or '').strip(),
            'date': raw_date,
            'sort_date': _to_sort_date(raw_date),
            'source': 'manual',
            'image_url': (entry.get('image_url') or '').strip() or None,
            'read_time': (entry.get('read_time') or entry.get('readTime') or '').strip(),
            'tags': _parse_tags_field(entry.get('tags')),
        }
        if row_type == 'native':
            slug = (entry.get('slug') or '').strip() or _slugify_insights(title)
            if not slug:
                continue
            row.update({
                'slug': slug,
                'url': f'/insights/{slug}',
                'preview_image': (entry.get('preview_image') or '').strip() or '/insights-native-preview.svg',
                'content_markdown': (entry.get('content_markdown') or '').strip(),
                'content_html': (entry.get('content_html') or '').strip(),
                'updated': (entry.get('updated') or entry.get('lastModified') or '').strip(),
                'author': (entry.get('author') or '').strip(),
            })
        else:
            url = (entry.get('url') or '').strip()
            if not url:
                continue
            row.update({
                'url': url,
                'external_url': url,
            })
        out.append(row)
    return out


def _get_external_insights_posts() -> list:
    """Merge Substack feed and manual external entries, sorted by date descending. Cached."""
    global _newsletter_cache, _newsletter_cache_time
    now = time.time()
    if _newsletter_cache is not None and (now - _newsletter_cache_time) < NEWSLETTER_CACHE_SECONDS:
        return _newsletter_cache
    substack = _fetch_substack_posts()
    manual = [p for p in _load_manual_newsletter_posts() if p.get('type') == 'external']
    merged = substack + manual
    for row in merged:
        row['type'] = 'external'
        row['external_url'] = row.get('external_url') or row.get('url')
        row['sort_date'] = row.get('sort_date') or _to_sort_date(row.get('date') or '')
    merged.sort(key=lambda x: x.get('sort_date') or '', reverse=True)
    if substack or manual or _newsletter_cache is not None:
        _newsletter_cache = merged
        _newsletter_cache_time = now
    return merged


def _get_native_insights_posts() -> list:
    """Native deep dives from markdown files + manual JSON entries."""
    global _native_insights_cache, _native_insights_cache_time
    now = time.time()
    if _native_insights_cache is not None and (now - _native_insights_cache_time) < _NATIVE_INSIGHTS_CACHE_TTL:
        return _native_insights_cache
    out = []
    manual_native = [p for p in _load_manual_newsletter_posts() if p.get('type') == 'native']
    markdown_native = _load_native_insights_markdown_posts()
    out.extend(markdown_native)
    out.extend(manual_native)
    seen = set()
    deduped = []
    for row in sorted(out, key=lambda x: x.get('sort_date') or '', reverse=True):
        slug = (row.get('slug') or '').strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        deduped.append(row)
    _native_insights_cache = deduped
    _native_insights_cache_time = now
    return deduped


def _resolve_target_entity_context(post: dict) -> dict | None:
    target_entity = (post.get('targetEntity') or '').strip()
    if not target_entity:
        return None
    if not _ensure_pandas_loaded_for_insights():
        return None
    target_type = (post.get('targetEntityType') or '').strip().lower()
    if not target_type:
        target_type = 'provider' if target_entity.isdigit() and len(target_entity) <= 6 else 'chain'

    if target_type == 'provider':
        prov = normalize_ccn(target_entity)
        if not prov:
            return None
        facility_df = load_facility_quarterly_for_provider(prov)
        if facility_df is None or facility_df.empty:
            return None
        provider_info_row = (load_provider_info() or {}).get(prov, {})
        facility_name = capitalize_facility_name((provider_info_row.get('provider_name') or '').strip() or (facility_df.iloc[-1].get('PROVNAME') or '').strip() or prov)
        state_code = (provider_info_row.get('state') or '').strip().upper()[:2]
        if not state_code and 'STATE' in facility_df.columns:
            state_code = str(facility_df.iloc[-1].get('STATE') or '').strip().upper()[:2]
        canonical_q = get_canonical_latest_quarter()
        if canonical_q is not None and 'CY_Qtr' in facility_df.columns:
            match = facility_df[facility_df['CY_Qtr'].astype(str) == str(canonical_q)]
            latest = match.iloc[0] if not match.empty else facility_df.sort_values('CY_Qtr', ascending=False).iloc[0]
        else:
            latest = facility_df.sort_values('CY_Qtr', ascending=False).iloc[0]
        def _fv(key):
            v = latest.get(key)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        reported_total = _fv('Total_Nurse_HPRD')
        reported_rn = _fv('RN_HPRD')
        reported_lpn = _fv('LPN_HPRD')
        if reported_lpn is None:
            reported_lpn = _lpn_hprd_from_facility_quarterly_row(latest)
        reported_na = _fv('Nurse_Assistant_HPRD')
        case_mix_total = None
        state_total = None
        raw_quarter = str(latest.get('CY_Qtr') or '')
        try:
            pi_q = get_provider_info_for_quarter(prov, raw_quarter) if raw_quarter else (provider_info_row or {})
            case_mix_total = float(pi_q.get('case_mix_total_nurse_hrs_per_resident_per_day')) if pi_q and pi_q.get('case_mix_total_nurse_hrs_per_resident_per_day') is not None else None
        except Exception:
            case_mix_total = None
        if state_code and raw_quarter:
            try:
                sd = load_csv_data('state_quarterly_metrics.csv')
                if sd is not None and not sd.empty:
                    m = sd[(sd['STATE'].astype(str).str.upper() == state_code) & (sd['CY_Qtr'].astype(str) == raw_quarter)]
                    if not m.empty and m.iloc[0].get('Total_Nurse_HPRD') is not None:
                        state_total = float(m.iloc[0].get('Total_Nurse_HPRD'))
            except Exception:
                pass
        return {
            'target_type': 'provider',
            'provider_id': prov,
            'display_name': facility_name,
            'state_code': state_code,
            'quarter': raw_quarter,
            'reported_total': reported_total,
            'reported_rn': reported_rn,
            'reported_lpn': reported_lpn,
            'reported_na': reported_na,
            'case_mix_total': case_mix_total,
            'state_total': state_total,
            'staffing_rating': (provider_info_row or {}).get('staffing_rating'),
            'overall_rating': (provider_info_row or {}).get('overall_rating'),
            'report_url': f'/provider/{prov}',
        }

    chain_name = target_entity
    entity_id = _resolve_chain_id_from_name(chain_name)
    if entity_id is None:
        return None
    entity_name, facilities = load_entity_facilities(entity_id)
    if not facilities:
        return None
    total_vals = [float(f.get('Total_Nurse_HPRD')) for f in facilities if f.get('Total_Nurse_HPRD') is not None]
    reported_total = (sum(total_vals) / len(total_vals)) if total_vals else None
    state_avgs = []
    try:
        sd = load_csv_data('state_quarterly_metrics.csv')
        q = facilities[0].get('quarter')
        if sd is not None and not sd.empty and q:
            sub = sd[sd['CY_Qtr'].astype(str) == str(q)]
            for fac in facilities:
                st = (fac.get('state') or '').strip().upper()
                m = sub[sub['STATE'].astype(str).str.upper() == st]
                if not m.empty and m.iloc[0].get('Total_Nurse_HPRD') is not None:
                    state_avgs.append(float(m.iloc[0].get('Total_Nurse_HPRD')))
    except Exception:
        pass
    state_total = (sum(state_avgs) / len(state_avgs)) if state_avgs else None
    chain_perf = load_chain_performance() or {}
    row = chain_perf.get(int(entity_id)) or {}
    def _f_num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    case_mix_total = _f_num(row.get('Average case-mix total nurse hours per resident per day'))
    if reported_total is None:
        reported_total = _f_num(row.get('Average reported total nurse hours per resident per day'))
    return {
        'target_type': 'chain',
        'entity_id': entity_id,
        'display_name': capitalize_entity_name(entity_name or chain_name),
        'quarter': facilities[0].get('quarter') or '',
        'reported_total': reported_total,
        'reported_rn': None,
        'reported_lpn': None,
        'reported_na': None,
        'case_mix_total': case_mix_total,
        'state_total': state_total,
        'staffing_rating': _f_num(row.get('Average staffing 5-star rating')),
        'overall_rating': _f_num(row.get('Average overall 5-star rating')),
        'report_url': f'/entity/{int(entity_id)}',
    }


def _render_niche_insight_sections(post: dict) -> dict:
    ctx = _resolve_target_entity_context(post)
    if not ctx:
        return {'reference': '', 'evidence': ''}
    ref_title = (post.get('reference_title') or 'Source story').strip()
    ref_url = _sanitize_nav_or_external_url((post.get('reference_url') or '').strip(), allow_relative=False)
    reference_box = ''
    if ref_url:
        reference_box = (
            '<section class="niche-reference-box">'
            '<h2>Source</h2>'
            f'<p>Related coverage: <a href="{html.escape(ref_url, quote=True)}" target="_blank" rel="noopener">{html.escape(ref_title)}</a></p>'
            '</section>'
        )
    facility_val = ctx.get('reported_total')
    case_mix_val = ctx.get('case_mix_total')
    state_val = ctx.get('state_total')
    bars = [('Reported', facility_val), ('Case-Mix', case_mix_val), ('State Avg', state_val)]
    max_v = max([v for _, v in bars if isinstance(v, (int, float))] + [1.0])
    bar_html = []
    for label, value in bars:
        display = f'{value:.2f}' if isinstance(value, (int, float)) else '—'
        pct = ((float(value) / max_v) * 100.0) if isinstance(value, (int, float)) and max_v > 0 else 0.0
        bar_html.append(
            '<div class="niche-bar-row">'
            f'<span class="niche-bar-label">{html.escape(label)}</span>'
            f'<div class="niche-bar-track"><div class="niche-bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="niche-bar-value">{display}</span>'
            '</div>'
        )
    staffing_stars = _star_icons_from_rating(ctx.get('staffing_rating'))
    overall_stars = _star_icons_from_rating(ctx.get('overall_rating'))
    evidence_table = (
        '<table class="niche-evidence-table">'
        '<thead><tr><th>Metric</th><th>Entity</th><th>State Avg</th></tr></thead>'
        '<tbody>'
        f'<tr><td>Total HPRD</td><td>{f"{facility_val:.2f}" if isinstance(facility_val, (int, float)) else "—"}</td><td>{f"{state_val:.2f}" if isinstance(state_val, (int, float)) else "—"}</td></tr>'
        f'<tr><td>Case-Mix HPRD</td><td>{f"{case_mix_val:.2f}" if isinstance(case_mix_val, (int, float)) else "—"}</td><td>—</td></tr>'
        f'<tr><td>Staffing Stars</td><td>{html.escape(staffing_stars)}</td><td>—</td></tr>'
        f'<tr><td>Overall Stars</td><td>{html.escape(overall_stars)}</td><td>—</td></tr>'
        '</tbody></table>'
    )
    report_url = ctx.get('report_url') or ''
    follow_label = 'Open facility profile' if ctx.get('target_type') == 'provider' else 'Open chain profile'
    follow_html = ''
    if report_url:
        follow_html = (
            '<p class="niche-follow">'
            f'<a href="{html.escape(report_url, quote=True)}">{html.escape(follow_label)}</a>'
            ' <span class="niche-follow-muted">· CMS PBJ + star ratings</span>'
            '</p>'
        )
    evidence_section = (
        '<section class="niche-evidence">'
        '<h2>Evidence</h2>'
        '<div class="niche-evidence-grid">'
        f'<div>{evidence_table}</div>'
        '<div class="niche-chart-box">'
        '<h3>Reported vs. CMS case-mix</h3>'
        + ''.join(bar_html) +
        '<h3 style="margin-top:14px;">CMS star ratings</h3>'
        f'<p class="niche-stars">Staffing: {html.escape(staffing_stars)}<br>Overall: {html.escape(overall_stars)}</p>'
        '</div></div>'
        + follow_html +
        '</section>'
    )
    return {'reference': reference_box, 'evidence': evidence_section}


def _render_native_content(post: dict) -> str:
    chart_embed_html = (
        '<aside class="dashboard-callout" role="note">'
        '<p class="dashboard-callout-title">Interactive dashboards</p>'
        '<p class="dashboard-callout-desc">Maps and quarter-by-quarter staffing open in a full window—clearer than nesting the whole tool inside this article.</p>'
        '<a class="dashboard-callout-btn" href="/insights-visualizations" target="_blank" rel="noopener">Open dashboards</a>'
        '</aside>'
    )
    content_html = (post.get('content_html') or '').strip()
    if content_html:
        rendered = _sanitize_insights_html(content_html)
    else:
        md_content = (post.get('content_markdown') or post.get('content') or '').strip()
        if HAS_MARKDOWN and markdown is not None and md_content:
            rendered = _sanitize_insights_html(markdown.markdown(md_content, extensions=['extra', 'fenced_code', 'tables']))
        elif md_content:
            chunks = [f'<p>{html.escape(part.strip())}</p>' for part in md_content.split('\n\n') if part.strip()]
            rendered = '\n'.join(chunks)
        else:
            rendered = '<p>This analysis is being prepared.</p>'
    rendered = rendered.replace('[PBJ_CHARTS]', chart_embed_html)
    niche = _render_niche_insight_sections(post)
    # Source → facility evidence → narrative and charts (readability for reporting readers).
    return (niche.get('reference') or '') + (niche.get('evidence') or '') + rendered


def _format_insight_display_date(raw_date: str) -> str:
    """Human-readable date for insight rails (e.g. 2026-04-21 → Apr 21, 2026)."""
    if not raw_date:
        return ''
    s = str(raw_date).strip()
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}', s):
            from datetime import datetime as _dt
            d = _dt.strptime(s[:10], '%Y-%m-%d')
            return d.strftime('%b %d, %Y').replace(' 0', ' ')
    except Exception:
        pass
    return s


def _get_recent_niche_insights_for_provider(ccn: str, limit: int = 4) -> list:
    prov = normalize_ccn(ccn)
    out = []
    for post in _get_native_insights_posts():
        if not _insights_post_is_published(post) or bool(post.get('hide_from_hub')):
            continue
        if not bool(post.get('show_on_provider_page')):
            continue
        target_entity = (post.get('targetEntity') or '').strip()
        target_type = (post.get('targetEntityType') or '').strip().lower()
        if not target_entity:
            continue
        if target_type in ('', 'provider'):
            if normalize_ccn(target_entity) == prov:
                out.append(post)
    out.sort(key=lambda x: x.get('sort_date') or '', reverse=True)
    return out[:limit]


def _render_recent_insights_sidebar_for_provider(ccn: str) -> str:
    # Provider-page niche insights rail is off until posts opt in via showOnProviderPage frontmatter.
    posts = _get_recent_niche_insights_for_provider(ccn, limit=4)
    if not posts:
        return ''
    items = []
    for post in posts:
        title = html.escape(post.get('title') or 'PBJ Insight')
        url = html.escape(post.get('url') or '#', quote=True)
        dt = html.escape(_format_insight_display_date(post.get('date') or ''))
        items.append(
            f'<li><a href="{url}">{title}</a>'
            + (f'<span class="pbj-recent-insights-date">{dt}</span>' if dt else '')
            + '</li>'
        )
    return (
        '<aside class="pbj-recent-insights" aria-label="Recent Niche Insights">'
        '<div class="pbj-recent-insights-title">Recent Insights</div>'
        '<ul>' + ''.join(items) + '</ul>'
        '</aside>'
    )


def _insights_post_is_published(post: dict) -> bool:
    if not isinstance(post, dict):
        return False
    published = post.get('published')
    if published is None:
        return True
    return bool(published)


def _find_native_insight(slug: str) -> dict | None:
    if not slug:
        return None
    for row in _get_native_insights_posts():
        if (row.get('slug') or '').strip() == slug:
            return row if _insights_post_is_published(row) else None
    return None


def _get_dual_track_insights_posts() -> list:
    native = [
        p
        for p in _get_native_insights_posts()
        if _insights_post_is_published(p) and not bool(p.get('hide_from_hub'))
    ]
    merged = _get_external_insights_posts() + native
    merged.sort(key=lambda x: x.get('sort_date') or '', reverse=True)
    return merged


def _public_site_origin() -> str:
    """Public https origin for canonical URLs, OG tags, and JSON-LD (apex pbj320.com)."""
    origin = None
    for key in ('PBJ_PUBLIC_BASE_URL', 'PUBLIC_BASE_URL'):
        v = (os.environ.get(key) or '').strip().rstrip('/')
        if v:
            origin = v
            break
    if not origin:
        try:
            root = getattr(request, 'url_root', None) or ''
            root = str(root).rstrip('/')
            if root:
                origin = root
        except Exception:
            pass
    if not origin:
        origin = 'https://pbj320.com'
    if 'pbj320.com' in origin.lower():
        return 'https://pbj320.com'
    return origin


def _absolute_public_url(base: str, path: str) -> str:
    if not path:
        return ''
    p = str(path).strip()
    if p.lower().startswith(('http://', 'https://')):
        return p
    if not p.startswith('/'):
        p = '/' + p
    return f'{base}{p}'


def _format_insights_hub_date(raw) -> str:
    if not raw:
        return ''
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        return f'{dt.strftime("%b")} {dt.day}, {dt.year}'
    except Exception:
        return str(raw)[:32]


def _infer_insights_read_time(post: dict) -> str:
    rt = (post.get('read_time') or post.get('readTime') or '').strip()
    if rt:
        return rt
    words = len(str(post.get('description') or '').strip().split())
    if words <= 16:
        return '4 min read'
    if words <= 32:
        return '6 min read'
    return '8 min read'


def _infer_insights_industry_tag(post: dict) -> str:
    allowed = {'Owners', 'PBJ Deep Dive', 'PBJ Trends', '90-Day CNA', 'CMS', 'State Trends'}
    ext_url = str(post.get('external_url') or post.get('url') or '').lower()
    if 'the-other-3000-days-at-seagate' in ext_url:
        return 'PBJ Deep Dive'
    tags = post.get('tags') or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    for t in tags:
        if str(t).strip() in allowed:
            return str(t).strip()
    cats = post.get('categories') or []
    cat_str = ' '.join(str(c) for c in cats) if isinstance(cats, list) else ''
    combined = f'{post.get("title") or ""} {post.get("description") or ""} {cat_str}'.lower()
    if re.search(r'owner|ownership|chain|entity|investor', combined):
        return 'Owners'
    if re.search(r'cna|nurse assistant|90-day|90 day', combined):
        return '90-Day CNA'
    if re.search(r'cms|star|care compare', combined):
        return 'CMS'
    if re.search(r'state|states|national|trend|quarter|q[1-4]', combined):
        return 'State Trends'
    return 'PBJ Deep Dive'


def _render_insights_hub_card_html(post: dict) -> str:
    title = html.escape(post.get('title') or '')
    desc_raw = (post.get('description') or '').strip()
    desc = html.escape(html.unescape(desc_raw)) if desc_raw else ''
    date_raw = post.get('date') or post.get('sort_date') or ''
    date_disp = html.escape(_format_insights_hub_date(date_raw))
    read_time = html.escape(_infer_insights_read_time(post))
    image = post.get('image_url') or post.get('preview_image') or '/insights-native-preview.svg'
    image_esc = html.escape(str(image), quote=True)
    ptype = (post.get('type') or 'external').lower()
    tag = html.escape(_infer_insights_industry_tag(post))
    meta_line = f'{date_disp} · {read_time}' if date_disp else read_time
    if ptype == 'native':
        native_url = html.escape(post.get('url') or f'/insights/{post.get("slug") or ""}', quote=True)
        return (
            f'<li class="card native" data-post-type="native"><article class="card-shell">'
            f'<div class="card-media-wrap"><img class="featured" src="{image_esc}" alt="Staffing chart snapshot" loading="lazy"></div>'
            f'<div class="card-body"><div class="tag-row"><span class="card-tag">{tag}</span></div>'
            f'<h2><a href="{native_url}">{title}</a></h2><p class="meta">{meta_line}</p>'
            + (f'<p class="desc">{desc}</p>' if desc else '')
            + f'<div class="card-actions"><a class="read-action" href="{native_url}" aria-label="View this PBJ320 insight">'
            f'<img src="/pbj_favicon.png" alt="" width="20" height="20">View</a></div></div></article></li>'
        )
    ext_url = html.escape(post.get('external_url') or post.get('url') or '#', quote=True)
    return (
        f'<li class="card external" data-post-type="external"><article class="card-shell">'
        f'<div class="card-media-wrap"><img class="featured" src="{image_esc}" alt="Feature story preview" loading="lazy"></div>'
        f'<div class="card-body"><div class="tag-row"><span class="card-tag">{tag}</span></div>'
        f'<h2><a href="{ext_url}" target="_blank" rel="noopener">{title}</a></h2><p class="meta">{meta_line}</p>'
        + (f'<p class="desc">{desc}</p>' if desc else '')
        + f'<div class="card-actions"><a class="read-action substack" href="{ext_url}" target="_blank" rel="noopener" '
        f'aria-label="Open this article on Substack (new tab)"><span class="read-action-icon-wrap">'
        f'<img src="/substack.png" alt="" width="18" height="18"></span>Open article</a></div></div></article></li>'
    )


def _render_insights_hub_feed_html(posts: list) -> str:
    if not posts:
        return '<li class="card"><div class="card-body"><p class="desc">No insights yet. Check back soon.</p></div></li>'
    return ''.join(_render_insights_hub_card_html(p) for p in posts if isinstance(p, dict))


def _insights_hub_item_list_json_ld(posts: list, base_url: str, max_items: int = 24) -> str:
    items = []
    for idx, p in enumerate(posts[:max_items], start=1):
        if not isinstance(p, dict):
            continue
        path = (p.get('url') or p.get('external_url') or '').strip()
        if path.startswith('/'):
            item_url = f'{base_url}{path}'
        else:
            item_url = path or base_url + '/insights'
        items.append({'@type': 'ListItem', 'position': idx, 'name': (p.get('title') or '')[:240], 'url': item_url})
    doc = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': 'PBJ320 Insights',
        'description': 'Nursing home staffing intelligence from PBJ320 and The 320 newsletter.',
        'itemListElement': items,
    }
    return f'<script type="application/ld+json">{json.dumps(doc, ensure_ascii=True)}</script>'


def _insight_datetime_iso(raw: str) -> str | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        try:
            d = datetime.strptime(s[:10], '%Y-%m-%d')
            return d.strftime('%Y-%m-%dT00:00:00Z')
        except Exception:
            return None


def _insights_native_article_json_ld(
    post: dict,
    *,
    base_url: str,
    page_url: str,
    iso_published: str | None,
    iso_modified: str | None,
    author_name: str,
) -> str:
    title = post.get('title') or 'PBJ320 Insight'
    desc = (post.get('description') or '').strip() or 'PBJ320 native insight.'
    img = _absolute_public_url(base_url, post.get('preview_image') or '/insights-native-preview.svg')
    doc: dict = {
        '@context': 'https://schema.org',
        '@type': 'NewsArticle',
        'headline': title[:200],
        'description': desc[:500],
        'url': page_url,
        'mainEntityOfPage': {'@type': 'WebPage', '@id': page_url},
        'image': [img],
        'author': {'@type': 'Person', 'name': author_name},
        'publisher': {
            '@type': 'Organization',
            'name': '320 Consulting',
            'url': 'https://www.320insight.com/',
        },
    }
    if iso_published:
        doc['datePublished'] = iso_published
    if iso_modified:
        doc['dateModified'] = iso_modified
    elif iso_published:
        doc['dateModified'] = iso_published
    return f'<script type="application/ld+json">{json.dumps(doc, ensure_ascii=True)}</script>'


def _json_ld_script(doc: dict) -> str:
    return f'<script type="application/ld+json">{json.dumps(doc, ensure_ascii=True)}</script>'


def _breadcrumb_list_json_ld(items: list) -> str:
    elements = []
    for pos, item in enumerate(items, start=1):
        name, url = item[0], item[1]
        if not name or not url:
            continue
        elements.append({'@type': 'ListItem', 'position': pos, 'name': name[:240], 'item': url})
    if not elements:
        return ''
    return _json_ld_script({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': elements})


def _state_facility_list_for_json_ld(state_code: str, quarter: str, limit: int = 10) -> list:
    if not HAS_PANDAS or not state_code or not quarter:
        return []
    fq = load_csv_data('facility_quarterly_metrics.csv')
    if fq is None or not isinstance(fq, pd.DataFrame) or fq.empty:
        return []
    sub = fq[
        (fq['CY_Qtr'].astype(str) == str(quarter))
        & (fq['STATE'].astype(str).str.strip().str.upper() == str(state_code).strip().upper())
    ]
    if sub.empty:
        return []
    sub = sub.sort_values('Total_Nurse_HPRD', ascending=False).head(limit)
    base = 'https://pbj320.com'
    out = []
    for _, row in sub.iterrows():
        ccn = normalize_ccn(row.get('PROVNUM') or '')
        if not ccn:
            continue
        name = (str(row.get('PROVNAME') or '')).strip() or f'Provider {ccn}'
        out.append((name, f'{base}/provider/{ccn}'))
    return out


def _provider_page_json_ld_scripts(
    *,
    facility_name: str,
    ccn: str,
    city: str,
    state_code: str,
    state_name: str,
    state_slug: str,
    page_url: str,
    total_hprd: str,
    quarter_display: str,
) -> str:
    base = 'https://pbj320.com'
    address = {'@type': 'PostalAddress', 'addressCountry': 'US'}
    if city:
        address['addressLocality'] = city
    if state_code:
        address['addressRegion'] = state_code
    org = {
        '@context': 'https://schema.org',
        '@type': 'MedicalOrganization',
        'name': facility_name,
        'url': page_url,
        'description': f'{facility_name} nursing home staffing from CMS PBJ data ({quarter_display}).',
    }
    if address.get('addressLocality') or address.get('addressRegion'):
        org['address'] = address
    props = []
    if total_hprd and total_hprd != '—':
        props.append({'@type': 'PropertyValue', 'name': 'Total Nurse HPRD', 'value': total_hprd, 'unitText': 'hours per resident day'})
    if quarter_display:
        props.append({'@type': 'PropertyValue', 'name': 'Reporting quarter', 'value': quarter_display})
    if props:
        org['additionalProperty'] = props
    crumbs = [('Home', f'{base}/')]
    if state_name and state_slug:
        crumbs.append((f'{state_name} PBJ Staffing', f'{base}/state/{state_slug}'))
    crumbs.append((facility_name, page_url))
    parts = [_json_ld_script(org), _breadcrumb_list_json_ld(crumbs)]
    return '\n'.join(p for p in parts if p)


def _state_page_json_ld_scripts(
    *,
    state_name: str,
    state_code: str,
    state_slug: str,
    page_url: str,
    quarter: str,
    quarter_display: str,
    total_hprd: str,
) -> str:
    base = 'https://pbj320.com'
    facilities = _state_facility_list_for_json_ld(state_code, quarter, limit=10)
    item_elements = [
        {'@type': 'ListItem', 'position': i, 'name': name[:240], 'url': url}
        for i, (name, url) in enumerate(facilities, start=1)
    ]
    item_list = {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': f'{state_name} nursing homes by reported staffing ({quarter_display})',
        'description': f'Top nursing homes in {state_name} by total nurse HPRD from CMS PBJ ({quarter_display}).',
        'numberOfItems': len(item_elements),
        'itemListElement': item_elements,
    }
    web_page = {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'name': f'{state_name} PBJ Nursing Home Staffing',
        'url': page_url,
        'description': f'{state_name} nursing home staffing data from CMS PBJ ({quarter_display}).',
    }
    if total_hprd and total_hprd != '—':
        web_page['additionalProperty'] = [
            {'@type': 'PropertyValue', 'name': 'State average total nurse HPRD', 'value': total_hprd}
        ]
    crumbs = [('Home', f'{base}/'), (f'{state_name} PBJ Staffing', page_url)]
    parts = [_json_ld_script(web_page)]
    if item_elements:
        parts.append(_json_ld_script(item_list))
    parts.append(_breadcrumb_list_json_ld(crumbs))
    return '\n'.join(p for p in parts if p)


def _entity_page_json_ld_scripts(*, entity_name: str, entity_id: int, page_url: str, facility_count: int) -> str:
    base = 'https://pbj320.com'
    org = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': entity_name,
        'url': page_url,
        'description': f'{entity_name} operates {facility_count} nursing homes. PBJ staffing data for affiliated facilities.',
    }
    crumbs = [('Home', f'{base}/'), (entity_name, page_url)]
    return '\n'.join([_json_ld_script(org), _breadcrumb_list_json_ld(crumbs)])


def _related_native_insights_html(current_slug: str, post: dict, base_url: str, limit: int = 3) -> str:
    slug = (current_slug or '').strip()
    my_tags = set(post.get('tags') or []) if isinstance(post.get('tags'), list) else set()
    scored = []
    for other in _get_native_insights_posts():
        if not isinstance(other, dict):
            continue
        if not _insights_post_is_published(other) or bool(other.get('hide_from_hub')):
            continue
        os_slug = (other.get('slug') or '').strip()
        if not os_slug or os_slug == slug:
            continue
        ot = set(other.get('tags') or []) if isinstance(other.get('tags'), list) else set()
        score = len(my_tags & ot) if my_tags else 0
        scored.append((score, other.get('sort_date') or '', other))
    scored.sort(key=lambda x: (x[0], x[1] or ''), reverse=True)
    picked = [x[2] for x in scored[:limit]]
    if len(picked) < limit:
        seen = {slug} | {((p.get('slug') or '').strip()) for p in picked}
        for other in _get_native_insights_posts():
            if not isinstance(other, dict):
                continue
            os_slug = (other.get('slug') or '').strip()
            if not os_slug or os_slug in seen:
                continue
            picked.append(other)
            seen.add(os_slug)
            if len(picked) >= limit:
                break
    if not picked:
        return ''
    lis = []
    for o in picked[:limit]:
        t = html.escape(o.get('title') or 'Insight')
        u = html.escape(o.get('url') or f'/insights/{o.get("slug") or ""}', quote=True)
        d = html.escape(_format_insights_hub_date(o.get('date') or o.get('sort_date') or ''))
        lis.append(f'<li><a href="{u}">{t}</a><span class="related-meta">{d}</span></li>')
    return (
        '<aside class="related-insights" aria-label="Related on-site insights">'
        '<h2 class="related-insights-title">More on-site insights</h2><ul>'
        + ''.join(lis) + '</ul></aside>'
    )


@app.route('/api/insights')
@app.route('/api/newsletter')
def api_insights():
    """Dual-track insights feed: external newsletter posts + native deep dives."""
    posts = _get_dual_track_insights_posts()
    return jsonify({'posts': posts})


@app.route('/insights/<slug>')
def insights_article(slug):
    post = _find_native_insight((slug or '').strip())
    if not post:
        from flask import abort
        abort(404)
    date_raw = post.get('date') or post.get('sort_date') or ''
    try:
        dt = datetime.fromisoformat(str(date_raw).replace('Z', ''))
        formatted_date = dt.strftime('%B %d, %Y')
    except Exception:
        formatted_date = date_raw or 'Latest update'
    updated_raw = (post.get('updated') or '').strip()
    formatted_updated = ''
    if updated_raw:
        try:
            du = datetime.fromisoformat(str(updated_raw).replace('Z', ''))
            formatted_updated = du.strftime('%B %d, %Y')
        except Exception:
            formatted_updated = updated_raw
    base = _public_site_origin()
    slug_clean = (post.get('slug') or slug or '').strip()
    page_url = f'{base}/insights/{slug_clean}'
    og_image = _absolute_public_url(base, post.get('preview_image') or '/insights-native-preview.svg')
    desc_plain = (post.get('description') or 'PBJ320 native insight.').strip()
    iso_pub = _insight_datetime_iso(str(date_raw)) if date_raw else None
    iso_mod = _insight_datetime_iso(updated_raw) if updated_raw else iso_pub
    author_name = (post.get('author') or '').strip() or 'PBJ320'
    article_json_ld = _insights_native_article_json_ld(
        post,
        base_url=base,
        page_url=page_url,
        iso_published=iso_pub,
        iso_modified=iso_mod or iso_pub,
        author_name=author_name,
    )
    related_html = _related_native_insights_html(slug_clean, post, base, limit=3)
    preview_img = (post.get('preview_image') or '/insights-native-preview.svg').strip()
    cover_caption = (post.get('cover_caption') or '').strip()
    show_cover = bool(cover_caption) or (
        preview_img and 'insights-native-preview' not in preview_img
    )
    cover_alt = (post.get('cover_alt') or post.get('coverAlt') or '').strip()
    if not cover_alt:
        cover_alt = f'Cover illustration: {(post.get("title") or "PBJ320 insight")[:120]}'
    return render_template_string(
        _INSIGHTS_NATIVE_PAGE_TEMPLATE,
        title=(post.get('title') or 'PBJ320 Insight'),
        description=desc_plain,
        formatted_date=formatted_date,
        formatted_updated=formatted_updated,
        show_updated=bool(updated_raw and formatted_updated and formatted_updated != formatted_date),
        content_html=_render_native_content(post),
        slug=slug_clean,
        site_base=base,
        canonical_url=page_url,
        og_url=page_url,
        og_image=og_image,
        og_description=desc_plain[:300],
        article_json_ld=article_json_ld,
        author_name=author_name,
        read_time=(post.get('read_time') or '').strip(),
        related_html=related_html,
        iso_published=iso_pub or '',
        iso_modified=(iso_mod or iso_pub or ''),
        show_cover=show_cover,
        cover_image=preview_img,
        cover_caption=cover_caption,
        cover_alt=cover_alt,
    )


@app.route('/newsletter')
@app.route('/newsletter/')
def newsletter_page():
    """Legacy route maintained for compatibility."""
    return redirect('/insights', code=301)


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


def _owners_api_cors_headers():
    """CORS + Private Network Access so /owners/api/* works from both localhost and LAN IP (e.g. 192.168.0.8)."""
    h = {'Access-Control-Allow-Private-Network': 'true'}
    origin = request.environ.get('HTTP_ORIGIN')
    h['Access-Control-Allow-Origin'] = origin if origin else '*'
    return h


@app.route('/owners/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/owner/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/ownership/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def owner_api_proxy(api_path):
    """Handle /owners/api/* first so POST body is reliably passed to sub-app. Registered before blueprint."""
    _log_mem("route_owner_api_before")
    if request.method == 'OPTIONS':
        resp = app.make_default_options_response()
        resp.status_code = 204
        for k, v in _owners_api_cors_headers().items():
            resp.headers[k] = v
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp
    try:
        owner_app = get_owner_app()
    except Exception:
        r = jsonify({'error': 'Owner dashboard unavailable'})
        r.status_code = 503
        for k, v in _owners_api_cors_headers().items():
            r.headers[k] = v
        return r
    try:
        # Use test_client so the sub-app receives the POST body reliably.
        # For JSON bodies, parse here and pass as json= so the sub-app definitely gets the payload.
        client = owner_app.test_client()
        headers = [(k, v) for k, v in request.headers if k.lower() != 'host']
        if request.method == 'GET':
            qs = request.query_string
            query_string_arg = qs.decode('utf-8') if qs else None
            r = client.get(f'/api/{api_path}', query_string=query_string_arg, headers=headers)
        elif request.method == 'POST':
            is_json = (request.content_type or '').strip().lower().startswith('application/json')
            if is_json:
                payload = request.get_json(silent=True, force=True)
                if payload is None:
                    payload = {}
                r = client.post(f'/api/{api_path}', json=payload, headers=headers)
            else:
                req_body = request.get_data()
                r = client.post(
                    f'/api/{api_path}',
                    data=req_body,
                    content_type=request.content_type or 'application/octet-stream',
                    headers=headers
                )
        elif request.method == 'PUT':
            is_json = (request.content_type or '').strip().lower().startswith('application/json')
            if is_json:
                payload = request.get_json(silent=True, force=True)
                if payload is None:
                    payload = {}
                r = client.put(f'/api/{api_path}', json=payload, headers=headers)
            else:
                req_body = request.get_data()
                r = client.put(
                    f'/api/{api_path}',
                    data=req_body,
                    content_type=request.content_type or 'application/octet-stream',
                    headers=headers
                )
        elif request.method == 'DELETE':
            r = client.delete(f'/api/{api_path}', headers=headers)
        else:
            return jsonify({'error': 'Method not allowed'}), 405
        # Pass through status and body so sub-app JSON/errors are returned correctly
        from flask import Response
        resp = Response(r.get_data(), status=r.status_code, mimetype=r.content_type)
        for k, v in _owners_api_cors_headers().items():
            resp.headers[k] = v
        _log_mem("route_owner_api_after")
        return resp
    except Exception as e:
        from werkzeug.exceptions import BadRequest
        if isinstance(e, BadRequest):
            r = jsonify({'error': getattr(e, 'description', None) or 'Bad request'})
            r.status_code = 400
            for k, v in _owners_api_cors_headers().items():
                r.headers[k] = v
            return r
        print(f"Error in owner_api_proxy for {api_path}: {e}")
        import traceback
        traceback.print_exc()
        r = jsonify({'error': f'Proxy error: {str(e)}'})
        r.status_code = 500
        for k, v in _owners_api_cors_headers().items():
            r.headers[k] = v
        return r


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

def _sitemap_lastmod_for_insight_post(post: dict, fallback: str) -> str:
    raw = (post.get('updated') or post.get('date') or post.get('sort_date') or '').strip()
    if raw:
        iso = _insight_datetime_iso(str(raw))
        if iso:
            return iso[:10]
    return fallback


@app.route('/sitemap.xml')
def sitemap():
    """Dynamic sitemap: static pages + /state/<slug> for all states + provider/entity from search_index."""
    base = PUBLIC_SITE_ORIGIN or 'https://pbj320.com'
    today = datetime.now().strftime('%Y-%m-%d')
    quarter_lastmod = _cy_qtr_to_iso_date(get_canonical_latest_quarter())
    urls = []
    static_pages = [
        ('/', '1.0', 'weekly'),
        ('/report', '0.9', 'weekly'),
        ('/insights', '0.9', 'weekly'),
        ('/insights-visualizations', '0.75', 'monthly'),
        ('/premium', '0.7', 'monthly'),
        ('/press', '0.8', 'monthly'),
        ('/attorneys', '0.8', 'monthly'),
        ('/pbj-sample', '0.6', 'monthly'),
    ]
    seen_paths = {p for p, _, _ in static_pages}
    for path, priority, changefreq in SITEMAP_TRUST_PAGES:
        if path not in seen_paths:
            static_pages.append((path, priority, changefreq))
            seen_paths.add(path)
    for path, priority, changefreq in static_pages:
        lastmod = quarter_lastmod if path == '/report' else today
        urls.append(f'  <url><loc>{base}{path}</loc><lastmod>{lastmod}</lastmod><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>')
    for post in _get_native_insights_posts():
        if not _insights_post_is_published(post):
            continue
        slug = (post.get('slug') or '').strip()
        if slug:
            lm = _sitemap_lastmod_for_insight_post(post, today)
            urls.append(f'  <url><loc>{base}/insights/{slug}</loc><lastmod>{lm}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>')
    # Canonical state/provider/entity pages (pbj320.com/state/pa, /provider/xxx, /entity/123)
    for state_code in sorted(STATE_CODE_TO_NAME.keys()):
        slug = get_canonical_slug(state_code)
        urls.append(f'  <url><loc>{base}/state/{slug}</loc><lastmod>{quarter_lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>')
    search_path = os.path.join(APP_ROOT, 'search_index.json')
    if os.path.isfile(search_path):
        try:
            with open(search_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for fac in (data.get('f') or []):
                if fac and fac.get('c'):
                    urls.append(f'  <url><loc>{base}/provider/{fac.get("c")}</loc><lastmod>{quarter_lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>')
            for ent in (data.get('e') or []):
                if ent and ent.get('id') is not None:
                    urls.append(f'  <url><loc>{base}/entity/{ent.get("id")}</loc><lastmod>{quarter_lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>')
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
        if fq is None or not (HAS_PANDAS and isinstance(fq, pd.DataFrame)):
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


def _normalize_quarter_to_cy_qtr(quarter_str):
    """Map PBJ ``CY_Qtr`` (``2025Q3``) or provider display quarter (``Q3 2025``) to ``YYYYQn``."""
    if not quarter_str:
        return None
    s = str(quarter_str).strip()
    if re.match(r'^\d{4}Q[1-4]$', s):
        return s
    return _quarter_display_to_cy_qtr(s)


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


def _provider_snapshot_candidate_paths():
    """Discover provider snapshots dynamically (ProviderInfoNorm_* and NH_ProviderInfo_*)."""
    out = []
    provider_dir = os.path.join(APP_ROOT, 'provider_info')
    try:
        names = [n for n in os.listdir(provider_dir) if n.lower().endswith('.csv')]
    except Exception:
        names = []
    snapshot_names = [
        n for n in names
        if n.startswith('ProviderInfoNorm_') or n.startswith('NH_ProviderInfo_')
    ]
    # Prefer latest snapshots first by filename sort (newer naming conventions are sortable).
    for n in sorted(snapshot_names, reverse=True):
        out.append(os.path.join(provider_dir, n))
        out.append(f'provider_info/{n}')
    return out

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

def _resolved_provider_info_paths():
    """Prefer ProviderInfoNorm / NH_ProviderInfo snapshots; fall back to combined CSVs only if no snapshot exists."""
    paths = []
    seen = set()
    for p in _provider_snapshot_candidate_paths():
        abs_p = p if os.path.isabs(p) else os.path.join(APP_ROOT, p.replace('/', os.sep))
        if os.path.isfile(abs_p) and abs_p not in seen:
            seen.add(abs_p)
            paths.append(abs_p)
    if paths:
        return paths
    fallbacks = [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        'pbj-wrapped/public/data/provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
        'pbj-wrapped/public/data/provider_info_combined.csv',
    ]
    out = []
    for p in fallbacks:
        abs_p = p if os.path.isabs(p) else os.path.join(APP_ROOT, p.replace('/', os.sep))
        if os.path.isfile(abs_p) and abs_p not in seen:
            seen.add(abs_p)
            out.append(abs_p)
    return out


def load_provider_info():
    """Load provider info for facility details (ownership, entity, residents, city). Cached 15 min."""
    global _LOAD_PROVIDER_INFO_CACHE, _LOAD_PROVIDER_INFO_AT, _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE
    now = time.time()
    if _LOAD_PROVIDER_INFO_CACHE is not None and (now - _LOAD_PROVIDER_INFO_AT) < _LOAD_PROVIDER_INFO_TTL:
        return _LOAD_PROVIDER_INFO_CACHE
    provider_paths = _resolved_provider_info_paths()
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
            header_cols = set(pd.read_csv(path, nrows=0).columns)
            keep_cols = {
                'ccn', 'PROVNUM', 'CCN', 'Provnum', 'CMS Certification Number (CCN)',
                'CY_Qtr', 'quarter',
                'chain_id', 'affiliated_entity_id', 'Chain ID', 'Chain_ID', 'AFFILIATED_ENTITY_ID',
                'entity_name', 'affiliated_entity', 'Entity Name', 'chain_name', 'affiliated_entity_name', 'Chain Name',
                'CITY', 'city', 'City', 'state', 'STATE', 'State',
                'ownership_type', 'Ownership_Type',
                'avg_residents_per_day',
                'provider_name', 'PROVNAME', 'Provider Name',
                'reported_total_nurse_hrs_per_resident_per_day', 'Total_Nurse_HPRD',
                'reported_rn_hrs_per_resident_per_day', 'reported_na_hrs_per_resident_per_day', 'reported_lpn_hrs_per_resident_per_day',
                'case_mix_total_nurse_hrs_per_resident_per_day', 'case_mix_rn_hrs_per_resident_per_day',
                'case_mix_na_hrs_per_resident_per_day', 'case_mix_lpn_hrs_per_resident_per_day',
                'nursing_case_mix_index', 'nursing_case_mix_index_ratio',
                'overall_rating', 'staffing_rating',
                'urban',
            }
            # Keep any chain/entity id/name variants we didn't enumerate explicitly.
            keep_cols.update(
                c for c in header_cols
                if (
                    (('chain' in str(c).lower() or 'entity' in str(c).lower()) and ('id' in str(c).lower() or 'name' in str(c).lower()))
                    or str(c).lower() in ('affiliated_entity', 'chain name')
                )
            )
            usecols = [c for c in header_cols if c in keep_cols]
            # _latest or NH_ProviderInfo snapshot: one snapshot; skip quarter discovery and filtering.
            is_latest_file = (
                'provider_info_combined_latest' in path or path.replace('\\', '/').endswith('_latest.csv')
                or 'NH_ProviderInfo' in path
                or 'ProviderInfoNorm_' in path
            )
            latest_quarters = None if is_latest_file else _get_latest_quarter_values(path, _LATEST_PROVIDER_QUARTERS)
            provider_dict = {}
            provider_dict_by_quarter = {}
            # Stream CSV in chunks and keep only rows from latest quarters
            for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=150000):
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
                        'reported_lpn_hrs_per_resident_per_day': row.get('reported_lpn_hrs_per_resident_per_day'),
                        'case_mix_total_nurse_hrs_per_resident_per_day': row.get('case_mix_total_nurse_hrs_per_resident_per_day'),
                        'case_mix_rn_hrs_per_resident_per_day': row.get('case_mix_rn_hrs_per_resident_per_day'),
                        'case_mix_na_hrs_per_resident_per_day': row.get('case_mix_na_hrs_per_resident_per_day'),
                        'case_mix_lpn_hrs_per_resident_per_day': row.get('case_mix_lpn_hrs_per_resident_per_day'),
                        'nursing_case_mix_index': row.get('nursing_case_mix_index'),
                        'nursing_case_mix_index_ratio': row.get('nursing_case_mix_index_ratio'),
                        'overall_rating': row.get('overall_rating'),
                        'staffing_rating': row.get('staffing_rating'),
                        'urban': row.get('urban'),
                        '_processing_date': row.get('processing_date'),
                    }
                    existing = provider_dict.get(provnum)
                    if existing is None:
                        provider_dict[provnum] = row_dict
                    else:
                        old_dt = pd.to_datetime(existing.get('_processing_date'), errors='coerce')
                        new_dt = pd.to_datetime(row_dict.get('_processing_date'), errors='coerce')
                        if pd.notna(new_dt) and (pd.isna(old_dt) or new_dt >= old_dt):
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


def get_state_median_case_mix_hprd(state_code, raw_quarter):
    """Median CMS case-mix total nurse HPRD among in-state facilities for a quarter (provider info)."""
    if not state_code or not raw_quarter:
        return None
    load_provider_info()
    if not _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE:
        return None
    st = str(state_code).strip().upper()[:2]
    q = str(raw_quarter).strip()
    vals = []
    for (_ccn, kq), row in _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE.items():
        if kq != q:
            continue
        if (row.get('state') or '').strip().upper()[:2] != st:
            continue
        v = row.get('case_mix_total_nurse_hrs_per_resident_per_day')
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        try:
            fv = float(v)
            if fv > 0:
                vals.append(fv)
        except (TypeError, ValueError):
            continue
    if not vals:
        return None
    vals.sort()
    mid = len(vals) // 2
    if len(vals) % 2 == 0:
        return (vals[mid - 1] + vals[mid]) / 2
    return vals[mid]


def get_rank_for_state_case_mix_median(state_code, raw_quarter):
    """National rank by state median case-mix HPRD (1 = highest acuity)."""
    if not state_code or not raw_quarter:
        return None
    medians = []
    for st in STATES_FOR_RANKING:
        m = get_state_median_case_mix_hprd(st, raw_quarter)
        if m is not None:
            medians.append((st, m))
    if not medians:
        return None
    medians.sort(key=lambda x: x[1], reverse=True)
    target = str(state_code).strip().upper()[:2]
    for i, (st, _) in enumerate(medians):
        if st == target:
            return i + 1
    return None


_RURAL_SHARE_BY_QUARTER_CACHE = None
_RURAL_SHARE_BY_QUARTER_AT = 0
_RURAL_SHARE_CACHE_TTL = 300


def _provider_is_rural(urban_val):
    """CMS provider-info urban flag: N = rural, Y = urban."""
    if urban_val is None or (isinstance(urban_val, float) and pd.isna(urban_val)):
        return None
    s = str(urban_val).strip().upper()
    if s in ('N', 'NO', 'R', 'RURAL'):
        return True
    if s in ('Y', 'YES', 'U', 'URBAN'):
        return False
    return None


def _build_rural_shares_for_quarter(raw_quarter):
    """Return (national_pct, {state: pct}) for share of facilities labeled rural (latest CMS snapshot)."""
    national_rural = 0
    national_total = 0
    by_state = {}

    def _accumulate(rows):
        nonlocal national_rural, national_total
        for row in rows:
            is_rural = _provider_is_rural(row.get('urban'))
            if is_rural is None:
                continue
            st = (row.get('state') or '').strip().upper()[:2]
            if not st:
                continue
            bucket = by_state.setdefault(st, [0, 0])
            bucket[1] += 1
            national_total += 1
            if is_rural:
                bucket[0] += 1
                national_rural += 1

    load_provider_info()
    # Rural/urban flag comes from the latest ProviderInfoNorm snapshot, not PBJ quarter alignment.
    if _LOAD_PROVIDER_INFO_CACHE:
        _accumulate(_LOAD_PROVIDER_INFO_CACHE.values())
    if national_total == 0:
        return None, {}
    nat_pct = round(100.0 * national_rural / national_total, 1)
    state_pcts = {
        st: round(100.0 * counts[0] / counts[1], 1)
        for st, counts in by_state.items()
        if counts[1] > 0
    }
    return nat_pct, state_pcts


def get_rural_shares_for_quarter(raw_quarter):
    """Cached national + per-state rural facility share for a quarter."""
    global _RURAL_SHARE_BY_QUARTER_CACHE, _RURAL_SHARE_BY_QUARTER_AT
    if not raw_quarter:
        return None, {}
    q = str(raw_quarter).strip()
    now = time.time()
    if (
        _RURAL_SHARE_BY_QUARTER_CACHE is not None
        and _RURAL_SHARE_BY_QUARTER_CACHE.get('q') == q
        and (now - _RURAL_SHARE_BY_QUARTER_AT) < _RURAL_SHARE_CACHE_TTL
    ):
        return _RURAL_SHARE_BY_QUARTER_CACHE.get('national'), _RURAL_SHARE_BY_QUARTER_CACHE.get('states') or {}
    nat, states = _build_rural_shares_for_quarter(q)
    _RURAL_SHARE_BY_QUARTER_CACHE = {'q': q, 'national': nat, 'states': states}
    _RURAL_SHARE_BY_QUARTER_AT = now
    return nat, states


def get_state_rural_facility_share(state_code, raw_quarter):
    """Percent of in-state nursing homes CMS labels rural (urban=N)."""
    if not state_code:
        return None
    st = str(state_code).strip().upper()[:2]
    _nat, states = get_rural_shares_for_quarter(raw_quarter)
    return states.get(st)


def get_rank_for_state_rural_share(state_code, raw_quarter):
    """National rank by rural facility share (1 = highest share rural)."""
    if not state_code or not raw_quarter:
        return None
    _nat, states = get_rural_shares_for_quarter(raw_quarter)
    if not states:
        return None
    ranked = sorted(states.items(), key=lambda x: x[1], reverse=True)
    target = str(state_code).strip().upper()[:2]
    for i, (st, _) in enumerate(ranked):
        if st == target:
            return i + 1
    return None


def render_state_rural_badge_html(state_code, raw_quarter):
    """Phoebe takeaway chip: % rural facilities with color vs U.S. and mini scale."""
    state_pct = get_state_rural_facility_share(state_code, raw_quarter)
    national_pct = get_rural_shares_for_quarter(raw_quarter)[0]
    if state_pct is None:
        return ''
    national_pct = float(national_pct) if national_pct is not None else None
    state_pct_f = float(state_pct)
    delta = state_pct_f - national_pct if national_pct is not None else 0.0
    if delta >= 15:
        tier = 'high'
        chip_bg = 'rgba(217, 119, 6, 0.18)'
        chip_border = 'rgba(251, 191, 36, 0.55)'
        chip_color = '#fde68a'
        fill_color = 'rgba(251, 191, 36, 0.85)'
        tier_note = 'well above U.S.'
    elif delta >= 5:
        tier = 'above'
        chip_bg = 'rgba(180, 83, 9, 0.14)'
        chip_border = 'rgba(251, 191, 36, 0.4)'
        chip_color = '#fef3c7'
        fill_color = 'rgba(245, 158, 11, 0.75)'
        tier_note = 'above U.S.'
    elif delta <= -15:
        tier = 'low'
        chip_bg = 'rgba(79, 70, 229, 0.2)'
        chip_border = 'rgba(129, 140, 248, 0.55)'
        chip_color = '#e0e7ff'
        fill_color = 'rgba(129, 140, 248, 0.9)'
        tier_note = 'well below U.S. (more urban)'
    elif delta <= -5:
        tier = 'below'
        chip_bg = 'rgba(99, 102, 241, 0.14)'
        chip_border = 'rgba(129, 140, 248, 0.42)'
        chip_color = '#e0e7ff'
        fill_color = 'rgba(99, 102, 241, 0.75)'
        tier_note = 'below U.S. (more urban)'
    else:
        tier = 'near'
        chip_bg = 'rgba(39, 39, 42, 0.65)'
        chip_border = 'rgba(113, 113, 122, 0.55)'
        chip_color = '#e4e4e7'
        fill_color = 'rgba(148, 163, 184, 0.85)'
        tier_note = 'near U.S.'
    state_w = max(4.0, min(96.0, state_pct_f))
    nat_w = max(2.0, min(98.0, national_pct)) if national_pct is not None else None
    title = (
        f'{state_pct_f:.0f}% of nursing homes in this state are in rural areas (CMS urban=N label). '
        f'U.S. average is about {national_pct:.0f}% for this quarter ({tier_note}). '
        'Bar shows state share; tick marks the U.S. average.'
    )
    nat_tick = (
        f'<span class="pbj-rural-meter-nat" style="left:{nat_w:.1f}%;" title="U.S. average {national_pct:.0f}% rural"></span>'
        if nat_w is not None
        else ''
    )
    return (
        f'<span class="pbj-rural-badge pbj-rural-badge--{tier}" style="display:inline-flex;align-items:center;gap:8px;'
        f'padding:4px 10px;border-radius:8px;font-size:0.82rem;font-weight:600;white-space:nowrap;'
        f'color:{chip_color};background:{chip_bg};border:1px solid {chip_border};" '
        f'title="{html.escape(title, quote=True)}">'
        f'<span>{state_pct_f:.0f}% rural</span>'
        f'<span class="pbj-rural-meter" aria-hidden="true" style="display:inline-flex;align-items:center;width:52px;height:8px;">'
        f'<span class="pbj-rural-meter-track" style="position:relative;display:block;width:52px;height:6px;'
        f'border-radius:999px;background:rgba(15,23,42,0.55);overflow:hidden;">'
        f'<span style="display:block;height:100%;width:{state_w:.1f}%;background:{fill_color};border-radius:999px;"></span>'
        f'{nat_tick}'
        f'</span></span></span>'
    )


def format_hprd_hours_minutes_phrase(hprd):
    """e.g. 2.96 HPRD → '2 hours and 58 minutes' (rounded to nearest minute)."""
    try:
        h = float(hprd)
    except (TypeError, ValueError):
        return ''
    if h <= 0:
        return ''
    total_min = int(round(h * 60))
    hrs, mins = divmod(total_min, 60)
    if hrs and mins:
        h_lbl = 'hour' if hrs == 1 else 'hours'
        m_lbl = 'minute' if mins == 1 else 'minutes'
        return f'{hrs} {h_lbl} and {mins} {m_lbl}'
    if hrs:
        return f'{hrs} {"hour" if hrs == 1 else "hours"}'
    if mins:
        return f'{mins} {"minute" if mins == 1 else "minutes"}'
    return '0 minutes'


_FACILITY_CORPORATE_SUFFIXES = (
    ' Rehabilitation and Nursing Center',
    ' Rehabilitation & Nursing Center',
    ' Nursing and Rehabilitation Center',
    ' Nursing & Rehabilitation Center',
    ' Rehab and Nursing Center',
    ' Rehabilitation and Nursing',
    ' Rehabilitation Center',
    ' Health and Rehabilitation',
    ' Rehabilitation',
    ' Nursing Home',
    ' Nursing Center',
    ' Health Center',
    ' Care Center',
    ' Skilled Nursing',
    ' SNF',
)
_BAD_STRIPPED_NAME_ENDINGS = (' and', ' &', ' of', ' at', ' the', ' a', ' an')
_ENTITY_CORPORATE_SUFFIXES = (
    ' Corporation',
    ' Incorporated',
    ' Company',
    ' LLC',
    ' L.L.C.',
    ' Inc.',
    ' Inc',
    ' Corp.',
    ' Corp',
)


def _normalize_display_name(name):
    return ' '.join(str(name or '').split())


def strip_corporate_suffix(name, suffixes):
    """Remove trailing corporate suffix when match leaves a plausible proper name (≥3 chars)."""
    n = _normalize_display_name(name)
    if not n:
        return n
    low = n.lower()
    for sep in suffixes:
        sep_low = sep.lower()
        idx = low.find(sep_low)
        if idx > 0:
            candidate = n[:idx].strip()
            low_c = candidate.lower()
            if (
                len(candidate) >= 3
                and low_c not in ('the', 'a', 'an', 'of', 'at')
                and not any(low_c.endswith(end) for end in _BAD_STRIPPED_NAME_ENDINGS)
            ):
                return candidate
    return n


def facility_hprd_place_labels(full_name):
    """First reference (e.g. Seagate Rehabilitation) and short reference (e.g. Seagate) for HPRD explainer."""
    name = _normalize_display_name(full_name)
    if not name:
        return 'Residents here', 'this facility'
    short = strip_corporate_suffix(name, _FACILITY_CORPORATE_SUFFIXES)
    if short == name and len(name.split()) > 5:
        short = ' '.join(name.split()[:2])
    short = short.strip() or name
    first = short
    lower_full = name.lower()
    if (
        'rehabilitation' in lower_full
        and 'rehabilitation' not in short.lower()
        and len(short.split()) <= 3
        and ' at ' not in f' {short.lower()} '
    ):
        first = f'{short} Rehabilitation'
    return first, short


def shorten_facility_display_name(full_name, max_len=40):
    """
    Conservative UI shortening for facility labels. Returns (display, full).
    Keeps full name when shortening would be unclear or the name is already short.
    """
    name = _normalize_display_name(full_name)
    if not name:
        return name, name
    if len(name) <= 32 and len(name.split()) <= 4:
        return name, name
    stripped = strip_corporate_suffix(name, _FACILITY_CORPORATE_SUFFIXES)
    if stripped == name:
        return name, name
    first, short = facility_hprd_place_labels(name)
    display = first if len(first) <= max_len else short
    if len(display) < 3 or len(display) >= len(name) - 2:
        return name, name
    return display, name


def shorten_entity_display_name(full_name, max_len=36):
    """Conservative shortening for entity/chain names in takeaway header."""
    name = _normalize_display_name(full_name)
    if not name:
        return name, name
    if len(name) <= 36 and len(name.split()) <= 4:
        return name, name
    stripped = strip_corporate_suffix(name, _ENTITY_CORPORATE_SUFFIXES)
    if stripped == name or len(stripped) < 3:
        return name, name
    display = stripped if len(stripped) <= max_len else stripped
    if len(display) >= len(name) - 2:
        return name, name
    return display, name


def takeaway_title_name_html(place_name, kind='facility'):
    """': Name' span for PBJ Takeaway header; title attr when shortened."""
    name = _normalize_display_name(place_name)
    if not name:
        return ''
    if kind == 'entity':
        display, full = shorten_entity_display_name(name)
    elif kind == 'facility':
        display, full = shorten_facility_display_name(name)
    else:
        display, full = name, name
    esc_display = html.escape(display)
    if display == full:
        return f'<span class="pbj-takeaway-title-name">: {esc_display}</span>'
    esc_full = html.escape(full)
    return (
        f'<span class="pbj-takeaway-title-name" title="{esc_full}">: {esc_display}</span>'
    )


def build_hprd_floor_analogy_body(hprd, na_hprd, place_name, census=None, context='facility'):
    """Plain-language HPRD explainer: daily staff time, 30-bed floor, and facility totals."""
    try:
        h = float(hprd)
    except (TypeError, ValueError):
        return ''
    if h <= 0:
        return ''
    time_phrase = format_hprd_hours_minutes_phrase(h)
    if not time_phrase:
        return ''
    _fs = round_half_up(30 * h / 24, 1)
    floor_staff = max(0.1, _fs if _fs is not None else 30 * h / 24)
    na = 0.0
    if na_hprd is not None:
        try:
            na = float(na_hprd)
        except (TypeError, ValueError):
            na = 0.0
    _fa = round_half_up(30 * na / 24, 1)
    floor_aides = max(0.0, _fa if _fa is not None else 0.0)
    if context == 'state':
        place_first = html.escape(f'{str(place_name or "This state").strip()} nursing home residents')
        floor_at = ''
    else:
        first_lbl, short_lbl = facility_hprd_place_labels(place_name)
        place_first = html.escape(f'{first_lbl} residents')
        floor_at = f' at {html.escape(short_lbl)}'
    parts = [
        f'{place_first} receive an average of <strong>{html.escape(time_phrase)}</strong> of staff time per day.',
        f'On a 30-bed floor{floor_at}, that works out to about <strong>{floor_staff:.1f} staff</strong> on duty, '
        f'including {floor_aides:.1f} nurse aides.',
    ]
    try:
        cen = int(census) if census is not None else 0
    except (TypeError, ValueError):
        cen = 0
    if cen > 0:
        _fst = round_half_up(cen * h / 24, 1)
        fac_staff = max(1.0, _fst if _fst is not None else cen * h / 24)
        fac_aides = 0.0
        if h > 0 and na > 0:
            _fai = round_half_up(fac_staff * na / h, 1)
            fac_aides = max(0.0, _fai if _fai is not None else 0.0)
        parts.append(
            f'Across the full {cen:,}-resident facility, that&rsquo;s roughly <strong>{fac_staff:.1f} total staff</strong>, '
            f'including {fac_aides:.1f} nurse aides.'
        )
    return f'<p class="pbj-hprd-means-body">{" ".join(parts)}</p>'


def _render_hprd_means_modal(hprd_label: str, body_html: str, uid: str) -> str:
    mid = f'pbjHprdMeansModal-{uid}'
    cid = f'pbjHprdMeansClose-{uid}'
    bid = f'pbjHprdMeansBtn-{uid}'
    title = f'What does {hprd_label} HPRD mean?'
    return (
        f'<div class="pbj-casemix-modal pbj-hprd-means-modal" id="{mid}" aria-hidden="true">'
        f'<div class="pbj-casemix-modal-card" role="dialog" aria-modal="true" aria-labelledby="{mid}Title">'
        f'<button type="button" class="pbj-casemix-modal-close" id="{cid}" aria-label="Close">&times;</button>'
        f'<h3 id="{mid}Title">{title}</h3>'
        f'<div class="pbj-casemix-aux-body">{body_html}</div>'
        f'</div></div>'
        f'<script>(function(){{'
        f'var b=document.getElementById("{bid}");var m=document.getElementById("{mid}");var c=document.getElementById("{cid}");'
        f'if(!b||!m)return;function x(){{m.setAttribute("aria-hidden","true");}}'
        f'b.addEventListener("click",function(e){{e.preventDefault();e.stopPropagation();m.setAttribute("aria-hidden","false");}});'
        f'if(c)c.addEventListener("click",x);m.addEventListener("click",function(e){{if(e.target===m)x();}});'
        f'document.addEventListener("keydown",function(e){{if(e.key==="Escape"&&m.getAttribute("aria-hidden")==="false")x();}});'
        f'}})();</script>'
    )


def render_hprd_badge_with_info(
    hprd_display,
    badge_style: str,
    badge_title: str,
    body_html,
    uid: str = 'default',
    badge_class: str = '',
    *,
    display_text: str = '',
    display_text_desktop: str = '',
) -> tuple[str, str]:
    """HPRD badge with subtle help affordance (mobile + desktop). Returns (badge_html, modal_html)."""
    if not hprd_display or str(hprd_display).strip() in ('', '—', 'N/A'):
        return '', ''
    hprd_label = html.escape(str(hprd_display).strip())
    compact = html.escape((display_text or f'{hprd_display} HPRD').strip())
    wide = html.escape((display_text_desktop or display_text or f'{hprd_display} HPRD').strip())
    extra_cls = f' {badge_class.strip()}' if badge_class and badge_class.strip() else ''
    if not body_html:
        return (
            f'<span class="pbj-hprd-badge{extra_cls}" style="{badge_style}" '
            f'title="{html.escape(badge_title, quote=True)}">'
            f'<span class="pbj-hprd-badge__val pbj-hprd-badge__val--compact">{compact}</span>'
            f'<span class="pbj-hprd-badge__val pbj-hprd-badge__val--wide">{wide}</span></span>',
            '',
        )
    bid = f'pbjHprdMeansBtn-{uid}'
    esc_title = html.escape(badge_title, quote=True)
    info_label = html.escape(f'What does {hprd_label} HPRD mean?', quote=True)
    badge = (
        f'<button type="button" class="pbj-hprd-badge pbj-hprd-badge--help{extra_cls}" '
        f'style="{badge_style}" id="{bid}" title="{esc_title}" '
        f'aria-haspopup="dialog" aria-controls="pbjHprdMeansModal-{uid}" aria-label="{info_label}">'
        f'<span class="pbj-hprd-badge__val pbj-hprd-badge__val--compact">{compact}</span>'
        f'<span class="pbj-hprd-badge__val pbj-hprd-badge__val--wide">{wide}</span>'
        '<span class="pbj-hprd-badge__hint" aria-hidden="true">'
        '<span class="pbj-hprd-badge__hint-mark">i</span>'
        '</span>'
        f'</button>'
    )
    return badge, _render_hprd_means_modal(hprd_label, body_html, uid)


def render_hprd_means_explainer(hprd_display, body_html, uid='default'):
    """Trigger button + modal for “What X.XX HPRD means”. Returns (trigger_html, modal_html)."""
    if not body_html or not hprd_display or str(hprd_display).strip() in ('', '—', 'N/A'):
        return '', ''
    hprd_label = html.escape(str(hprd_display).strip())
    mid = f'pbjHprdMeansModal-{uid}'
    bid = f'pbjHprdMeansBtn-{uid}'
    cid = f'pbjHprdMeansClose-{uid}'
    title = f'What does {hprd_label} HPRD mean?'
    trigger = (
        f'<button type="button" class="pbj-hprd-means-trigger" id="{bid}" '
        f'aria-haspopup="dialog" aria-controls="{mid}" '
        f'aria-label="{html.escape(title, quote=True)}">'
        f'<span class="pbj-hprd-means-text">What does '
        f'<span class="pbj-hprd-means-val">{hprd_label}</span> HPRD mean?</span>'
        f'</button>'
    )
    return trigger, _render_hprd_means_modal(hprd_label, body_html, uid)


def render_takeaway_share_button(page_url, place_label, uid='default'):
    """Compact Share control for takeaway card (Web Share API or copy link)."""
    url = str(page_url or '').strip()
    if not url:
        return ''
    label = str(place_label or 'this dashboard').strip()
    esc_url = html.escape(url, quote=True)
    share_title = html.escape(f'{label} | PBJ320', quote=True)
    share_text = html.escape(f'Nursing home staffing dashboard: {label}', quote=True)
    esc_label = html.escape(label, quote=True)
    bid = f'pbjShareBtn-{uid}'
    share_icon = (
        '<svg class="pbj-takeaway-share-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>'
        '<polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>'
    )
    return (
        f'<button type="button" class="pbj-takeaway-share-btn" id="{bid}" '
        f'data-share-url="{esc_url}" data-share-title="{share_title}" data-share-text="{share_text}" '
        f'aria-label="Share link to {esc_label} dashboard">'
        f'{share_icon}<span class="pbj-takeaway-share-label">Share</span></button>'
    )


def render_takeaway_actions_row(hprd_html='', share_html='', ai_html=''):
    """Bottom row: HPRD explainer (left) + AI icons + Share (right)."""
    hprd_html = (hprd_html or '').strip()
    share_html = (share_html or '').strip()
    ai_html = (ai_html or '').strip()
    if not hprd_html and not share_html and not ai_html:
        return ''
    mod = ' pbj-takeaway-actions--share-only' if share_html and not hprd_html else ''
    tools = ''
    if ai_html or share_html:
        tools = f'<div class="pbj-takeaway-actions__tools">{ai_html}{share_html}</div>'
    return (
        f'<div class="pbj-takeaway-actions{mod}">'
        f'<div class="pbj-takeaway-actions__hprd">{hprd_html}</div>'
        f'{tools}'
        f'</div>'
    )


def get_latest_provider_info_for_ccn(ccn):
    """Return (quarter_cy, row_dict) for the latest provider-info quarter available for a CCN."""
    if not ccn:
        return None, None
    load_provider_info()
    if not _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE:
        return None, None
    prov = str(ccn).strip().zfill(6)
    best_q = None
    best_row = None
    for (k_ccn, k_q), row in _LOAD_PROVIDER_INFO_BY_QUARTER_CACHE.items():
        if k_ccn != prov:
            continue
        if best_q is None or str(k_q) > str(best_q):
            best_q = k_q
            best_row = row
    return best_q, best_row

def get_pbj_site_layout(page_title, meta_description, canonical_url, extra_head=''):
    """Return dict with head, nav, content_open, content_close for provider/entity/state pages. Matches index.html tone, colors, and footer."""
    base = 'https://pbj320.com'
    canon = canonical_url or base
    head = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0a0f1a">
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
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0f1a; color: #e2e8f0; line-height: 1.6; min-height: 100vh; color-scheme: dark; }}
.pbj-content {{ padding: 40px 20px; max-width: 1100px; margin: 0 auto; border-top: 1px solid rgba(71, 85, 105, 0.45); }}
.pbj-content-box {{ background: #111827; border-radius: 16px; padding: 40px 48px; margin-bottom: 24px; border: 1px solid rgba(51, 65, 85, 0.55); box-shadow: 0 12px 40px -20px rgba(15, 23, 42, 0.75); color: #e2e8f0; transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease; }}
.pbj-content-box:hover {{ box-shadow: 0 16px 44px -18px rgba(15, 23, 42, 0.85); border-color: rgba(71, 85, 105, 0.7); }}
.pbj-takeaway {{ background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border: 1px solid rgba(99, 102, 241, 0.2) !important; box-shadow: 0 12px 36px -16px rgba(15, 23, 42, 0.75); }}
.pbj-takeaway:hover {{ border-color: rgba(129, 140, 248, 0.35) !important; box-shadow: 0 16px 40px -14px rgba(99, 102, 241, 0.12); }}
.pbj-content-box h1 {{ font-size: 2rem; color: #818cf8; margin-bottom: 0.5rem; font-weight: 700; }}
.pbj-content-box h2 {{ font-size: 1.4rem; color: #818cf8; margin-top: 1.5rem; margin-bottom: 0.75rem; font-weight: 600; }}
.pbj-content-box p {{ color: #e2e8f0; margin-bottom: 0.75rem; }}
.pbj-content-box a {{ color: #818cf8; text-decoration: none; font-weight: 500; transition: color 0.2s ease, opacity 0.2s ease; }}
.pbj-content-box a:hover {{ color: #a5b4fc; text-decoration: underline; }}
.pbj-content-box a:focus {{ outline: 2px solid #818cf8; outline-offset: 2px; }}
.pbj-content-box table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; background: rgba(15, 23, 42, 0.45); border-radius: 12px; overflow: hidden; border: 1px solid rgba(30, 41, 59, 0.6); }}
.pbj-content-box th, .pbj-content-box td {{ padding: 14px 18px; text-align: left; border-bottom: 1px solid rgba(30, 41, 59, 0.6); }}
.pbj-content-box th {{ background: rgba(30, 41, 59, 0.55); color: #e2e8f0; font-weight: 600; font-size: 0.9rem; letter-spacing: 0.04em; text-transform: uppercase; }}
.pbj-content-box td {{ color: #e2e8f0; font-size: 0.95rem; }}
.pbj-content-box tr:hover td {{ background: rgba(30, 41, 59, 0.35); }}
.pbj-content-box tr:last-child td {{ border-bottom: none; }}
.pbj-staffing-stars {{ color: #fbbf24; letter-spacing: 0.06em; }}
.pbj-infobox {{ width: 280px; float: right; margin: 0 0 1em 1.5em; border: 1px solid rgba(30, 41, 59, 0.6); background: rgba(15, 23, 42, 0.55); border-radius: 8px; overflow: hidden; }}
.pbj-infobox th {{ background: rgba(30, 41, 59, 0.55); padding: 0.5em 0.6em; font-weight: bold; border-bottom: 1px solid rgba(30, 41, 59, 0.6); color: #e2e8f0; font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; }}
.pbj-infobox td {{ padding: 0.5em 0.6em; border-bottom: 1px solid rgba(30, 41, 59, 0.6); color: #e2e8f0; }}
.section-header {{ margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1.35em; font-weight: 700; color: #818cf8; border-bottom: 1px solid rgba(30, 41, 59, 0.6); padding-bottom: 4px; letter-spacing: 0.02em; }}
.section-header:first-of-type {{ margin-top: 0; }}
.pbj-subtitle {{ font-size: 0.9em; color: #a8b4c4; margin-top: 4px; }}
.pbj-subtitle-mobile {{ display: none; }}
.pbj-meta-line {{ font-size: 0.9em; color: #a8b4c4; margin-top: 6px; }}
.pbj-orientation {{ margin-bottom: 18px; font-size: 0.95rem; color: #e2e8f0; max-width: 700px; }}
.pbj-percentile, .pbj-entity-summary {{ font-size: 0.85rem; color: #a8b4c4; margin-top: 6px; }}
.pbj-details {{ border: 1px solid rgba(148, 163, 184, 0.32); border-radius: 10px; background: rgba(15, 23, 42, 0.55); margin: 1.25rem 0; overflow: hidden; box-shadow: 0 2px 14px rgba(2, 6, 23, 0.28); }}
.pbj-details-methodology {{ max-width: 42rem; }}
.pbj-details summary {{ list-style: none; cursor: pointer; display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; font-weight: 600; font-size: 0.9375rem; color: #c7d2fe; background: rgba(30, 41, 59, 0.45); transition: background 0.2s ease, color 0.2s ease; user-select: none; }}
.pbj-details summary::-webkit-details-marker {{ display: none; }}
.pbj-details summary:hover {{ background: rgba(51, 65, 85, 0.55); color: #e0e7ff; }}
.pbj-details summary:focus-visible {{ outline: 2px solid rgba(129, 140, 248, 0.7); outline-offset: 2px; }}
.pbj-details[open] summary {{ border-bottom: 1px solid rgba(129, 140, 248, 0.28); background: rgba(30, 41, 59, 0.65); }}
.pbj-details-icon {{ display: inline-block; transition: transform 0.2s ease; font-size: 0.55em; opacity: 0.85; color: #94a3b8; }}
.pbj-details[open] .pbj-details-icon {{ transform: rotate(180deg); color: #a5b4fc; }}
.pbj-high-risk-help-wrap {{ position: relative; display: inline; }}
.pbj-high-risk-help {{ cursor: help; text-decoration: none; border-bottom: 1px dotted rgba(148,163,184,0.6); transition: border-color 0.2s ease, color 0.2s ease; }}
.pbj-high-risk-help:hover {{ border-bottom-color: rgba(129, 140, 248, 0.85); color: #a5b4fc; }}
.pbj-high-risk-tooltip {{ position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 6px; padding: 8px 12px; background: #0f172a; border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 6px; font-size: 0.8rem; line-height: 1.4; color: #e2e8f0; white-space: normal; min-width: 260px; max-width: 320px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); opacity: 0; pointer-events: none; transition: opacity 0.2s; z-index: 1000; }}
.entity-section-tooltip {{ max-width: 360px; max-height: 200px; overflow-y: auto; }}
.pbj-high-risk-help-wrap:hover .pbj-high-risk-tooltip {{ opacity: 1; }}
.pbj-risk-badge-with-info {{
  display: inline-flex; align-items: center; gap: 0.22rem; flex-wrap: nowrap;
}}
.pbj-risk-badge-info-wrap {{ margin-left: 0.12rem; }}
.pbj-risk-badge-info {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.05rem; height: 1.05rem; flex-shrink: 0;
  font: inherit; font-size: 0.62em; font-weight: 700; font-style: italic; line-height: 1;
  font-family: Georgia, "Times New Roman", serif;
  padding: 0; margin: 0; border: 1px solid currentColor; border-radius: 50%; cursor: help;
  color: inherit; background: rgba(15, 23, 42, 0.35); opacity: 0.9;
  vertical-align: middle;
}}
.pbj-risk-badge-with-info .pbj-risk-badge-info:hover {{
  opacity: 1; text-decoration: underline; text-underline-offset: 2px;
}}
.pbj-risk-badge-info-wrap.is-open .pbj-high-risk-tooltip {{
  opacity: 1; pointer-events: auto;
}}
.pbj-details-content {{ padding: 1rem 1.1rem 1.15rem; border-top: none; background: rgba(15, 23, 42, 0.35); }}
.pbj-details-content p:first-child {{ margin-top: 0; }}
.pbj-details-content p:last-child {{ margin-bottom: 0; }}
.pbj-details-content ul {{ margin: 0.5rem 0 1rem; padding-left: 1.25rem; }}
.pbj-details-content li {{ margin-bottom: 0.25rem; }}
.pbj-metrics-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 1rem 0; }}
.pbj-metric-card {{ background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(30, 41, 59, 0.6); border-radius: 8px; padding: 1rem; color: #e2e8f0; transition: border-color 0.2s ease, box-shadow 0.2s ease; }}
.pbj-metric-card:hover {{ border-color: rgba(51, 65, 85, 0.85); box-shadow: 0 0 18px -12px rgba(129, 140, 248, 0.12); }}
.pbj-metric-card .label {{ font-size: 0.72em; color: #94a3b8; margin-bottom: 4px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }}
.pbj-metric-card .value {{ font-size: 1.25rem; font-weight: 700; color: #e2e8f0; }}
.pbj-metric-card .delta {{ font-size: 0.8em; color: #94a3b8; margin-top: 2px; }}
.pbj-chart-container {{ margin: 20px 0; border: 1px solid rgba(100, 116, 139, 0.52); border-radius: 8px; padding: 20px; background: #0f172a; box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.35), 0 0 20px -12px rgba(129, 140, 248, 0.1); }}
.pbj-chart-wrapper {{ height: 260px; position: relative; width: 100%; }}
.pbj-chart-container.pbj-casemix-card {{ margin: 20px 0; padding: 0.55rem 0.65rem 0.5rem; background: #0f172a; border: 1px solid rgba(148, 163, 184, 0.58); border-radius: 8px; box-shadow: 0 0 0 1px rgba(51, 65, 85, 0.45), 0 0 20px -12px rgba(129, 140, 248, 0.1); width: 100%; box-sizing: border-box; }}
.pbj-casemix-card-head {{ margin-bottom: 0.35rem; }}
.pbj-casemix-section-header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; flex-wrap: wrap; }}
.pbj-casemix-section-title {{ margin: 0; flex: 1 1 auto; min-width: 0; font-size: 1.35em; font-weight: 700; color: #818cf8; letter-spacing: 0.02em; line-height: 1.25; }}
.pbj-casemix-card-body {{ display: flex; flex-direction: column; gap: 20px; width: 100%; min-width: 0; }}
.pbj-casemix-summary {{ width: 100%; max-width: 100%; min-width: 0; }}
.pbj-casemix-card-eyebrow {{ flex-shrink: 0; font-size: 0.58rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #94a3b8; line-height: 1.15; }}
.pbj-casemix-interpret {{ margin: 0.22rem 0 0; font-size: 0.6rem; line-height: 1.32; color: rgba(203, 213, 225, 0.88); font-weight: 400; }}
button.pbj-casemix-help-trigger {{ display: inline-flex; align-items: center; gap: 0.35rem; margin-left: auto; padding: 0.28rem 0.5rem 0.28rem 0.62rem; border-radius: 6px; background: rgba(124, 145, 255, 0.10); border: 1px solid rgba(124, 145, 255, 0.28); flex-shrink: 0; cursor: pointer; font-family: inherit; line-height: 1.2; color: #d7defe; }}
button.pbj-casemix-help-trigger:hover {{ background: rgba(124, 145, 255, 0.16); border-color: rgba(124, 145, 255, 0.4); }}
button.pbj-casemix-help-trigger:focus-visible {{ outline: 2px solid rgba(129, 140, 248, 0.55); outline-offset: 2px; }}
button.pbj-hprd-means-trigger {{
  display: inline-flex; align-items: center; margin: 0; padding: 0.45rem 0.9rem;
  border-radius: 8px; background: rgba(30, 41, 59, 0.72);
  border: 1px solid rgba(129, 140, 248, 0.5);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06) inset, 0 2px 10px rgba(2, 6, 23, 0.35);
  cursor: pointer; font-family: inherit; font-size: 0.8125rem; font-weight: 600;
  line-height: 1.3; color: #e0e7ff;
  text-decoration: underline; text-decoration-color: rgba(165, 180, 252, 0.65);
  text-underline-offset: 3px; text-decoration-thickness: 1px;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
}}
button.pbj-hprd-means-trigger:hover {{
  background: rgba(49, 46, 129, 0.45); border-color: rgba(165, 180, 252, 0.72);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.08) inset, 0 4px 14px rgba(99, 102, 241, 0.22);
  color: #f8fafc; text-decoration-color: rgba(199, 210, 254, 0.95);
}}
button.pbj-hprd-means-trigger:active {{
  transform: translateY(1px); box-shadow: 0 1px 4px rgba(2, 6, 23, 0.4);
}}
button.pbj-hprd-means-trigger:focus-visible {{
  outline: 2px solid rgba(129, 140, 248, 0.75); outline-offset: 2px;
}}
.pbj-hprd-means-val {{ font-weight: 700; color: #fff; font-variant-numeric: tabular-nums; }}
.pbj-takeaway-top {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
.pbj-takeaway-top-main {{ flex: 1; min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem 0.75rem; }}
.pbj-takeaway-header {{ font-size: 16px; font-weight: bold; color: #e2e8f0; min-width: 0; line-height: 1.25; flex: 1; }}
.pbj-takeaway-title-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.pbj-takeaway-actions {{ margin-top: 0.55rem; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem 0.75rem; }}
.pbj-takeaway-actions__hprd {{ flex: 1; min-width: 0; display: flex; align-items: center; }}
.pbj-takeaway-actions__share {{ flex-shrink: 0; }}
.pbj-takeaway-actions--share-only {{ justify-content: flex-end; }}
.pbj-takeaway-actions--share-only .pbj-takeaway-actions__hprd {{ display: none; }}
button.pbj-takeaway-share-btn {{
  display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem; margin: 0;
  padding: 0.38rem 0.72rem; border-radius: 8px; font-family: inherit; font-size: 0.75rem; font-weight: 600;
  line-height: 1.25; color: #94a3b8; background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(71, 85, 105, 0.8);
  cursor: pointer; transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}}
.pbj-takeaway-share-icon {{ width: 1rem; height: 1rem; flex-shrink: 0; }}
button.pbj-takeaway-share-btn:hover {{
  color: #e2e8f0; background: rgba(30, 41, 59, 0.75); border-color: rgba(129, 140, 248, 0.45);
}}
  button.pbj-takeaway-share-btn:focus-visible {{ outline: 2px solid rgba(129, 140, 248, 0.65); outline-offset: 2px; }}
.pbj-takeaway-actions__tools {{ display: inline-flex; align-items: center; gap: 0.35rem; flex-shrink: 0; }}
.pbj-ai-chip {{ position: relative; display: inline-flex; align-items: center; }}
.pbj-ai-chip__icons {{ display: inline-flex; align-items: center; gap: 0.2rem; }}
.pbj-ai-icon-btn {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.85rem; height: 1.85rem; padding: 0.2rem; border-radius: 7px;
  border: 1px solid rgba(203, 213, 225, 0.55); background: #f8fafc;
  cursor: pointer; transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}}
.pbj-ai-icon-btn:hover {{
  border-color: rgba(129, 140, 248, 0.65); background: #fff;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.2);
}}
.pbj-ai-icon-btn:focus-visible {{ outline: 2px solid rgba(129, 140, 248, 0.65); outline-offset: 2px; }}
.pbj-ai-chip__menu span {{ font-size: 1rem; line-height: 1; color: #475569; font-weight: 700; }}
.pbj-ai-brand-icon {{ display: block; width: 14px; height: 14px; flex-shrink: 0; }}
.pbj-ai-popover {{
  position: absolute; right: 0; bottom: calc(100% + 6px); z-index: 50;
  min-width: 9.5rem; padding: 0.3rem; border-radius: 8px;
  background: #1e293b; border: 1px solid rgba(129, 140, 248, 0.35);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  display: flex; flex-direction: column; gap: 0.15rem;
}}
.pbj-ai-popover[hidden] {{ display: none !important; }}
.pbj-ai-popover__item, .pbj-ai-popover__link {{
  display: block; width: 100%; text-align: left; font: inherit; font-size: 0.72rem; font-weight: 600;
  padding: 0.38rem 0.5rem; border: none; border-radius: 5px; background: transparent;
  color: #e2e8f0; cursor: pointer; text-decoration: none; line-height: 1.3;
}}
.pbj-ai-popover__item:hover, .pbj-ai-popover__link:hover {{ background: rgba(49, 46, 129, 0.45); color: #f8fafc; }}
.pbj-ai-launch {{ padding: 0; }}
.pbj-ai-helper-compact {{
  margin-top: 0.55rem; padding: 0.55rem 0.65rem; border-radius: 8px;
  border: 1px solid rgba(71, 85, 105, 0.55); background: rgba(15, 23, 42, 0.35);
  font-size: 0.78rem; line-height: 1.45; color: rgba(226, 232, 240, 0.88);
}}
.pbj-ai-helper-compact__title {{ margin: 0 0 0.2rem; font-size: 0.8rem; font-weight: 600; color: #e2e8f0; }}
.pbj-ai-helper-compact__body, .pbj-ai-helper-compact__hint {{ margin: 0 0 0.3rem; color: rgba(203, 213, 225, 0.9); }}
.pbj-ai-helper-compact__hint {{ font-size: 0.72rem; color: rgba(148, 163, 184, 0.95); }}
.pbj-ai-helper-compact__btns {{ display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.25rem; }}
.pbj-ai-helper-compact__btn {{
  font: inherit; font-size: 0.72rem; font-weight: 600; padding: 0.32rem 0.55rem; border-radius: 6px;
  border: 1px solid rgba(129, 140, 248, 0.4); background: rgba(30, 41, 59, 0.65); color: #e2e8f0; cursor: pointer;
}}
.pbj-ai-helper-compact__btn:hover {{ border-color: rgba(129, 140, 248, 0.65); background: rgba(49, 46, 129, 0.35); }}
.pbj-ai-helper-compact__btn--link {{ text-decoration: none; display: inline-flex; align-items: center; }}
.pbj-ai-helper-compact__btn--primary {{
  border-color: rgba(129, 140, 248, 0.75); background: rgba(49, 46, 129, 0.55); color: #f8fafc;
}}
.pbj-ai-page-helper__controls {{
  display: flex; flex-wrap: wrap; gap: 0.45rem 0.75rem; align-items: center; margin: 0.3rem 0 0.15rem;
}}
.pbj-ai-page-helper__actions {{
  display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center; margin-top: 0.2rem;
}}
.pbj-ai-page-helper__icons {{ display: inline-flex; align-items: center; gap: 0.25rem; flex-shrink: 0; }}
.pbj-ai-page-helper__footer {{
  margin-top: 0.35rem; padding-top: 0.3rem; border-top: 1px solid rgba(71, 85, 105, 0.45);
  font-size: 0.68rem; color: rgba(148, 163, 184, 0.95);
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.15rem 0.3rem;
}}
.pbj-ai-page-helper__footer-link {{
  font: inherit; font-size: inherit; font-weight: 500; padding: 0; border: none; background: none;
  color: rgba(148, 163, 184, 0.98); cursor: pointer; text-decoration: underline; text-underline-offset: 2px;
}}
.pbj-ai-page-helper__footer-link:hover {{ color: #e2e8f0; }}
.pbj-ai-page-helper__footer-sep {{ opacity: 0.6; user-select: none; }}
.pbj-ai-page-helper__more {{ position: relative; display: inline-flex; }}
.pbj-ai-page-helper .pbj-ai-popover {{ bottom: calc(100% + 4px); min-width: 10rem; }}
.pbj-ai-lens-wrap, .pbj-ai-length-wrap {{
  display: flex; align-items: center; gap: 0.35rem; font-size: 0.72rem; margin: 0;
}}
.pbj-ai-lens-label, .pbj-ai-length-label {{ color: rgba(148, 163, 184, 0.95); white-space: nowrap; }}
.pbj-ai-lens-select, .pbj-ai-length-select {{
  font: inherit; font-size: 0.72rem; font-weight: 600; padding: 0.22rem 0.4rem; border-radius: 6px;
  border: 1px solid rgba(100, 116, 139, 0.55); background: rgba(15, 23, 42, 0.65); color: #e2e8f0;
  max-width: 100%;
}}
.pbj-ai-provider-bar {{
  margin-top: 0.4rem; display: flex; flex-wrap: nowrap; align-items: center; gap: 0.35rem 0.45rem;
  font-size: 0.72rem;
}}
.pbj-ai-provider-bar__row--top,
.pbj-ai-provider-bar__row--actions {{
  display: contents;
}}
.pbj-ai-provider-bar__sep {{
  color: rgba(100, 116, 139, 0.8); user-select: none; flex-shrink: 0; font-weight: 300;
}}
.pbj-ai-provider-bar__spacer {{
  flex: 1 1 auto; min-width: 0.35rem;
}}
.pbj-ai-provider-bar__share {{
  display: inline-flex; align-items: center; flex-shrink: 0; margin-left: auto;
}}
.pbj-ai-provider-bar__actions {{
  display: inline-flex; align-items: center; gap: 0.35rem 0.4rem; flex-shrink: 0; flex-wrap: nowrap;
}}
.pbj-ai-provider-bar__cta {{
  display: inline-flex; align-items: center; gap: 0.3rem; flex-shrink: 0; flex-wrap: nowrap;
}}
.pbj-ai-pbjai-info {{
  display: inline-flex; align-items: center; gap: 0.28rem; flex-shrink: 0;
  font: inherit; font-size: 0.7rem; font-weight: 700; line-height: 1;
  padding: 0.32rem 0.55rem; border-radius: 7px; cursor: pointer;
  border: 1px solid rgba(148, 163, 184, 0.72); background: rgba(30, 41, 59, 0.92);
  color: #f8fafc; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.22);
}}
.pbj-ai-pbjai-info:hover {{
  border-color: rgba(203, 213, 225, 0.88); background: rgba(51, 65, 85, 0.98);
}}
.pbj-ai-pbjai-mark {{ display: inline-flex; align-items: baseline; gap: 0; letter-spacing: 0.01em; }}
.pbj-ai-pbjai-pbj {{ color: #f8fafc; font-weight: 700; }}
.pbj-ai-pbjai-ai {{ color: #a5b4fc; font-weight: 700; }}
.pbj-ai-beta-modal .pbj-ai-pbjai-pbj {{ color: #f8fafc; }}
.pbj-ai-beta-modal .pbj-ai-pbjai-ai {{ color: #a78bfa; }}
.pbj-ai-beta-modal h3 {{
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.35rem 0.4rem; line-height: 1.2;
}}
.pbj-ai-pbjai-hint {{
  display: none;
}}
.pbj-ai-length-mode {{
  display: inline-flex; align-items: center; gap: 0.2rem; flex-shrink: 0;
  padding: 0.12rem; border-radius: 7px; border: 1px solid rgba(71, 85, 105, 0.75);
  background: rgba(15, 23, 42, 0.55);
}}
.pbj-ai-length-mode__btn {{
  font: inherit; font-size: 0.64rem; font-weight: 700; line-height: 1;
  padding: 0.28rem 0.45rem; border-radius: 5px; cursor: pointer; border: none;
  background: transparent; color: rgba(203, 213, 225, 0.88);
}}
.pbj-ai-length-mode__btn:hover {{ color: #f1f5f9; background: rgba(51, 65, 85, 0.55); }}
.pbj-ai-length-mode__btn.is-active {{
  background: rgba(51, 65, 85, 0.9); color: #f8fafc;
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.35);
}}
.pbj-takeaway-badges {{
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
}}
.pbj-hprd-badge {{
  display: inline-flex; align-items: center; gap: 0.28rem; font: inherit;
  align-self: center; line-height: 1.25; box-sizing: border-box;
}}
.pbj-hprd-badge--help {{
  font: inherit; margin: 0; cursor: pointer; vertical-align: middle;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}}
.pbj-hprd-badge--help:hover {{
  border-color: rgba(148, 163, 184, 0.75) !important;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.2);
}}
.pbj-hprd-badge__val--wide {{ display: none; }}
.pbj-hprd-badge__hint {{
  display: inline-flex; align-items: center; justify-content: center; align-self: center;
  margin-left: 0.28rem; margin-top: 0;
  color: rgba(148, 163, 184, 0.88); transition: color 0.15s;
}}
.pbj-hprd-badge__hint-mark {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.05rem; height: 1.05rem;
  font: 700 0.62em/1 Georgia, "Times New Roman", serif;
  font-style: italic; color: rgba(226, 232, 240, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.65); border-radius: 50%;
  background: rgba(15, 23, 42, 0.35); padding: 0; box-sizing: border-box;
}}
.pbj-hprd-badge--help:hover .pbj-hprd-badge__hint {{
  color: rgba(226, 232, 240, 0.98);
}}
.pbj-hprd-badge--help:hover .pbj-hprd-badge__hint-mark {{
  color: rgba(248, 250, 252, 0.98);
}}
.pbj-hprd-badge--help:focus-visible {{
  outline: 2px solid rgba(148, 163, 184, 0.55); outline-offset: 2px;
}}
@media (min-width: 769px) {{
  .pbj-hprd-badge__val--compact {{ display: none; }}
  .pbj-hprd-badge__val--wide {{ display: inline; }}
}}
.pbj-ai-provider-bar__share .pbj-takeaway-share-btn {{
  margin-left: 0;
}}
.pbj-ai-provider-bar__microcopy,
.pbj-ai-provider-bar__state-note {{
  flex: 1 1 100%; margin: 0; padding: 0; line-height: 1.42; font-size: 0.66rem;
}}
.pbj-ai-provider-bar__microcopy {{ color: rgba(203, 213, 225, 0.88); }}
.pbj-ai-provider-bar__state-note--muted {{
  color: rgba(148, 163, 184, 0.95);
  border-left: 2px solid rgba(99, 102, 241, 0.35); padding-left: 0.45rem;
}}
.pbj-ai-provider-bar .pbj-ai-lens-wrap {{ margin: 0; flex: 0 1 auto; min-width: 0; gap: 0.28rem; }}
.pbj-ai-provider-bar .pbj-ai-lens-label {{ font-size: 0.68rem; letter-spacing: 0.03em; }}
.pbj-ai-provider-bar .pbj-ai-lens-select {{
  padding: 0.18rem 1.45rem 0.18rem 0.34rem; font-size: 0.7rem;
}}
.pbj-ai-provider-bar .pbj-ai-length-mode {{
  flex-shrink: 0; margin-left: 0;
}}
.pbj-ai-provider-bar .pbj-ai-pbjai-info {{
  flex-shrink: 0; margin-left: 0;
}}
.pbj-ai-provider-chip {{
  font: inherit; font-size: 0.68rem; font-weight: 600; line-height: 1;
  padding: 0.32rem 0.55rem; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(100, 116, 139, 0.55);
  background: rgba(15, 23, 42, 0.55); color: rgba(226, 232, 240, 0.92);
}}
.pbj-ai-provider-chip:hover {{
  border-color: rgba(148, 163, 184, 0.7); background: rgba(30, 41, 59, 0.85);
}}
.pbj-ai-provider-chip.is-copied {{
  border-color: rgba(52, 211, 153, 0.55); color: #a7f3d0;
}}
.pbj-ai-provider-ai {{
  display: inline-flex; align-items: center; gap: 0.32rem;
  font: inherit; font-size: 0.68rem; font-weight: 700; line-height: 1;
  padding: 0.32rem 0.55rem; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(71, 85, 105, 0.85); background: rgba(15, 23, 42, 0.65);
  color: #f1f5f9;
}}
.pbj-ai-provider-ai--cta {{
  padding: 0.36rem 0.62rem; font-size: 0.7rem;
  background: rgba(30, 41, 59, 0.92);
  border-color: rgba(100, 116, 139, 0.75);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}}
.pbj-ai-provider-ai:hover {{
  border-color: rgba(129, 140, 248, 0.5); background: rgba(30, 41, 59, 0.9);
  box-shadow: 0 0 10px -4px rgba(99, 102, 241, 0.25);
}}
.pbj-ai-provider-ai--cta:hover {{
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}}
.pbj-ai-provider-ai[data-ai="claude"] {{
  border-color: rgba(201, 100, 66, 0.45);
}}
.pbj-ai-provider-ai[data-ai="claude"]:hover {{
  border-color: rgba(201, 100, 66, 0.75); background: rgba(67, 32, 20, 0.35);
}}
.pbj-ai-provider-bar .pbj-ai-brand-icon {{
  filter: brightness(0) invert(0.88); opacity: 0.95; display: block;
}}
.pbj-ai-brief-toggle {{
  font: inherit; font-size: 0.66rem; font-weight: 700; line-height: 1;
  padding: 0.3rem 0.5rem; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(100, 116, 139, 0.55); background: rgba(15, 23, 42, 0.55);
  color: rgba(203, 213, 225, 0.92);
}}
.pbj-ai-brief-toggle:hover {{
  border-color: rgba(148, 163, 184, 0.7); background: rgba(30, 41, 59, 0.85);
}}
.pbj-ai-brief-toggle.is-active {{
  border-color: rgba(129, 140, 248, 0.65); background: rgba(49, 46, 129, 0.45); color: #e0e7ff;
}}
.pbj-ai-beta-info {{
  font: inherit; font-size: 0.66rem; font-weight: 600; line-height: 1;
  padding: 0.28rem 0.45rem; border-radius: 6px; cursor: pointer;
  border: 1px dashed rgba(129, 140, 248, 0.45); background: transparent;
  color: rgba(203, 213, 225, 0.95);
}}
.pbj-ai-beta-info:hover {{
  border-color: rgba(165, 180, 252, 0.75); background: rgba(30, 41, 59, 0.55);
}}
.pbj-ai-beta-info__label {{ font-weight: 700; }}
.pbj-ai-beta-tag {{
  display: inline-block; margin-left: 0.15rem; padding: 0.04rem 0.32rem; border-radius: 4px;
  font-size: 0.56rem; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase;
  vertical-align: middle; line-height: 1.15;
  color: rgba(203, 213, 225, 0.78); background: rgba(148, 163, 184, 0.14);
  border: 1px solid rgba(148, 163, 184, 0.28);
}}
.pbj-ai-pbjai-info .pbj-ai-beta-tag {{
  align-self: center;
}}
.pbj-casemix-modal.pbj-ai-beta-modal {{
  z-index: 10200 !important;
  background: rgba(2, 6, 23, 0.88) !important;
}}
.pbj-casemix-modal.pbj-ai-beta-modal .pbj-casemix-modal-card {{
  margin-bottom: max(1.25rem, env(safe-area-inset-bottom, 0px));
  max-height: min(78vh, 480px);
  box-shadow: 0 20px 56px rgba(0, 0, 0, 0.55);
}}
.pbj-ai-beta-list-item--desktop-only {{ display: list-item; }}
.pbj-ai-beta-modal .pbj-ai-beta-lead {{ margin-top: 0; color: rgba(203, 213, 225, 0.95); }}
.pbj-ai-beta-verify {{
  margin: 0.55rem 0 0.65rem; padding: 0.5rem 0.6rem; border-radius: 6px; font-size: 0.78rem; line-height: 1.45;
  color: #fecaca; background: rgba(127, 29, 29, 0.35); border: 1px solid rgba(248, 113, 113, 0.45);
}}
.pbj-ai-beta-verify a {{ color: #fca5a5; }}
.pbj-ai-beta-verify a:hover {{ color: #fee2e2; }}
.pbj-ai-beta-list {{ margin: 0.25rem 0 0.5rem 1rem; padding: 0; font-size: 0.8rem; line-height: 1.42; color: rgba(226,232,240,0.9); }}
.pbj-ai-beta-list li {{ margin: 0.2rem 0; }}
.pbj-ai-beta-foot {{
  margin-top: 0.75rem; padding-top: 0.65rem; text-align: right;
  border-top: 1px solid rgba(51, 65, 85, 0.65);
  background: linear-gradient(180deg, transparent 0%, rgba(15, 23, 42, 0.92) 28%);
  position: sticky; bottom: 0; margin-left: -1rem; margin-right: -1rem; margin-bottom: -0.85rem;
  padding-left: 1rem; padding-right: 1rem; padding-bottom: 0.85rem;
}}
.pbj-ai-beta-got-it {{
  font: inherit; font-size: 0.78rem; font-weight: 700; padding: 0.35rem 0.85rem; border-radius: 6px;
  border: 1px solid rgba(129, 140, 248, 0.55); background: rgba(67, 56, 202, 0.35); color: #e0e7ff; cursor: pointer;
}}
.pbj-ai-beta-got-it:hover {{ background: rgba(79, 70, 229, 0.45); }}
body.pbj-ai-beta-modal-open {{ overflow: hidden; }}
.pbj-care-footer-row {{
  margin: 0.35rem 0 0 0; display: flex; flex-wrap: nowrap; align-items: center; gap: 0.35rem 0.5rem;
  font-size: 0.75rem; line-height: 1.45;
}}
.pbj-page-source {{
  margin: 0.35rem 0 0 0; font-size: 0.8rem; color: rgba(226, 232, 240, 0.6); line-height: 1.45;
}}
.pbj-page-source a {{
  color: #818cf8; text-decoration: underline; text-underline-offset: 2px;
}}
.pbj-page-source a:hover {{ color: #a5b4fc; }}
.pbj-care-footer-sep {{ opacity: 0.45; user-select: none; }}
.pbj-footer-csv-bundle {{
  font: inherit; font-size: inherit; font-weight: 500; padding: 0; margin: 0; border: none; background: none;
  color: rgba(148, 163, 184, 0.88); cursor: pointer; text-decoration: underline; text-underline-offset: 2px;
}}
.pbj-footer-csv-bundle:hover {{ color: #cbd5e1; }}
.pbj-ai-handoff-data, .pbj-ai-context-data, .pbj-ai-prefill-data, .pbj-ai-extended-data, .pbj-ai-prompt-data, .pbj-ai-prompt-template, .pbj-ai-csv-data {{ display: none !important; }}
.visually-hidden {{
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}}
.pbj-ai-toast {{
  position: fixed; bottom: 1rem; left: 50%; transform: translateX(-50%) translateY(0.5rem); z-index: 10001;
  background: #0f172a; color: #e2e8f0; padding: 0.55rem 1rem; border-radius: 8px; font-size: 0.85rem;
  box-shadow: 0 8px 24px rgba(0,0,0,0.35); opacity: 0; transition: opacity 0.2s, transform 0.2s;
}}
.pbj-ai-toast--visible {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
.pbj-takeaway-footer {{ margin-top: 0; padding-top: 0; border-top: none; }}
.pbj-takeaway-brand-pill {{
  display: inline-block; padding: 0.28rem 0.6rem; border-radius: 999px; font-size: 0.7rem; font-weight: 600;
  letter-spacing: 0.02em; color: rgba(148, 163, 184, 0.9); background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(71, 85, 105, 0.75); flex-shrink: 0; white-space: nowrap;
}}
@media (max-width: 768px) {{
  .pbj-takeaway-actions {{ flex-wrap: nowrap; align-items: stretch; }}
  .pbj-takeaway-actions__hprd {{ min-width: 0; }}
  .pbj-ai-popover {{ right: auto; left: 0; }}
  button.pbj-hprd-means-trigger {{ width: 100%; justify-content: center; text-align: center; }}
  button.pbj-takeaway-share-btn {{
    padding: 0.45rem; min-width: 2.75rem; min-height: 2.75rem; align-self: center;
  }}
  .pbj-takeaway-share-label {{ display: none; }}
  .pbj-takeaway-share-icon {{ width: 1.125rem; height: 1.125rem; }}
  .pbj-takeaway-top-main {{ gap: 0.35rem 0.5rem; }}
  .pbj-takeaway-brand-pill {{ font-size: 0.65rem; padding: 0.22rem 0.5rem; }}
  .pbj-ai-page-helper__controls {{ flex-direction: column; align-items: stretch; gap: 0.35rem; }}
  .pbj-ai-lens-wrap, .pbj-ai-length-wrap {{ justify-content: space-between; }}
  .pbj-ai-lens-select, .pbj-ai-length-select {{ flex: 1; min-width: 0; }}
  .pbj-ai-provider-bar {{
    display: flex; flex-direction: column; align-items: stretch; gap: 0.38rem;
  }}
  .pbj-ai-provider-bar__row--top,
  .pbj-ai-provider-bar__row--actions {{
    display: flex;
  }}
  .pbj-ai-provider-bar__row--top {{
    display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; width: 100%;
  }}
  .pbj-ai-provider-bar__row--actions {{
    display: flex; align-items: center; width: 100%;
  }}
  .pbj-ai-provider-bar__share {{ display: none !important; }}
  .pbj-ai-provider-bar__sep {{ display: none; }}
  .pbj-ai-provider-bar .pbj-ai-lens-wrap {{
    flex: 1 1 auto; min-width: 0; justify-content: flex-end;
  }}
  .pbj-ai-provider-bar .pbj-ai-lens-select {{ flex: 1; min-width: 0; max-width: 13.25rem; padding-right: 1.35rem; }}
  .pbj-ai-provider-bar .pbj-ai-lens-label {{ font-size: 0.6rem; letter-spacing: 0.04em; }}
  .pbj-ai-provider-bar .pbj-ai-pbjai-info {{
    padding: 0.28rem 0.48rem; font-size: 0.66rem;
  }}
  .pbj-takeaway-badges {{
    gap: 6px 5px;
  }}
  .pbj-risk-badge-with-info {{
    max-width: 100%;
  }}
  .pbj-ai-provider-bar__actions {{
    display: flex; flex-wrap: nowrap; align-items: center;
    justify-content: space-between; gap: 0.28rem; width: 100%; min-width: 0;
  }}
  .pbj-ai-provider-bar__cta {{
    display: flex; flex: 1 1 auto; flex-wrap: nowrap; gap: 0.28rem; min-width: 0;
  }}
  .pbj-ai-provider-bar__spacer {{ display: none; }}
  .pbj-ai-provider-bar__cta .pbj-ai-provider-ai {{
    flex: 1 1 0; min-width: 0; padding: 0.34rem 0.42rem; justify-content: center;
    font-size: 0.66rem;
  }}
  .pbj-ai-provider-bar__cta .pbj-ai-provider-ai span {{ white-space: nowrap; }}
  .pbj-ai-provider-bar .pbj-ai-length-mode {{
    flex: 0 0 auto; margin-left: 0.15rem;
  }}
  .pbj-ai-provider-bar .pbj-ai-length-mode__btn {{
    padding: 0.26rem 0.38rem; font-size: 0.62rem;
  }}
  .pbj-ai-beta-list-item--desktop-only {{ display: none; }}
}}
.pbj-casemix-help-label {{ font-size: 0.72rem; font-weight: 500; color: inherit; white-space: nowrap; }}
.pbj-casemix-info-icon {{ display: inline-flex; align-items: center; justify-content: center; width: 1.15rem; height: 1.15rem; font-size: 0.72rem; font-weight: 700; font-style: italic; font-family: Georgia, 'Times New Roman', serif; color: rgba(226,232,240,0.9); flex-shrink: 0; }}
.pbj-casemix-hero {{ margin-bottom: 0; }}
.pbj-casemix-hero-panel {{ border: 1px solid rgba(51, 65, 85, 0.65); border-radius: 8px; background: rgba(15, 23, 42, 0.55); padding: 0.38rem 0.52rem 0.36rem; }}
.pbj-casemix-hero-line {{ margin: 0 0 0.28rem; font-size: 0.68rem; line-height: 1.32; color: rgba(203, 213, 225, 0.94); font-variant-numeric: tabular-nums; }}
.pbj-casemix-hero-line .tag {{ font-size: 0.58rem; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; color: rgba(148, 163, 184, 0.95); margin-right: 0.28rem; }}
.pbj-casemix-hero-line .primary {{ font-weight: 700; color: #f8fafc; font-size: 0.82rem; }}
.pbj-casemix-hero-line .sep {{ color: rgba(100, 116, 139, 0.9); margin: 0 0.22rem; }}
.pbj-casemix-hero-line .secondary {{ color: rgba(148, 163, 184, 0.96); }}
.pbj-casemix-hero-line .secondary .h {{ color: rgba(226, 232, 240, 0.95); font-weight: 700; }}
.pbj-casemix-hero-line .pct--low {{ color: rgba(252, 165, 165, 0.95); font-weight: 600; }}
.pbj-casemix-hero-line .pct-em {{ font-weight: 700; font-size: 0.88rem; color: #f8fafc; letter-spacing: 0.01em; }}
.pbj-casemix-sub-line .pct-em {{ font-weight: 700; color: #f8fafc; font-size: 0.68rem; }}
.pbj-casemix-breakdown-aside .h {{ color: rgba(226, 232, 240, 0.94); font-weight: 700; }}
.pbj-casemix-hero-main {{ display: flex; align-items: center; gap: 0.45rem 0.55rem; flex-wrap: wrap; }}
.pbj-casemix-hero-copy {{ flex: 1 1 58%; min-width: 10rem; max-width: 62%; }}
.pbj-casemix-hero-cmi-col {{ flex: 0 0 auto; display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 0.28rem 0.35rem; margin-left: auto; }}
.pbj-casemix-hero-cmi-col.pbj-casemix-cmi-strip {{ margin: 0; padding: 0; border: 0; }}
.pbj-casemix-pct-bar {{ margin: 0; }}
.pbj-casemix-pct-caption {{ display: none; }}
.pbj-casemix-pct-track {{ position: relative; height: 9px; border-radius: 4px; background: rgba(30, 41, 59, 0.9); border: 1px solid rgba(51, 65, 85, 0.8); overflow: hidden; }}
.pbj-casemix-pct-fill {{ position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; min-width: 2px; z-index: 1; transition: width 0.2s ease; }}
.pbj-casemix-pct-fill--to-bench {{ background: rgba(100, 116, 139, 0.88); border-radius: 3px 0 0 3px; }}
.pbj-casemix-pct-fill--over {{ background: linear-gradient(90deg, rgba(34, 197, 94, 0.72) 0%, rgba(45, 212, 191, 0.92) 100%); z-index: 2; border-radius: 0 3px 3px 0; box-shadow: inset 2px 0 0 rgba(255, 255, 255, 0.28); }}
.pbj-casemix-pct-fill--under {{ background: rgba(248, 113, 113, 0.78); }}
.pbj-casemix-pct-fill--under.pbj-casemix-sev-warn {{ background: rgba(251, 146, 60, 0.78) !important; }}
.pbj-casemix-pct-fill--under.pbj-casemix-sev-critical {{ background: rgba(248, 113, 113, 0.82) !important; }}
.pbj-casemix-pct-bench {{ position: absolute; top: -1px; bottom: -1px; width: 2px; background: rgba(226, 232, 240, 0.88); border-radius: 1px; z-index: 3; transform: translateX(-50%); box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.9); }}
.pbj-casemix-pct-track--over .pbj-casemix-pct-bench {{ background: rgba(255, 255, 255, 0.95); }}
.pbj-casemix-pct-bar--compact .pbj-casemix-pct-track {{ height: 7px; }}
.pbj-casemix-breakdown-row {{ display: flex; align-items: center; gap: 0.4rem 0.55rem; padding: 0.16rem 0; border-top: 1px solid rgba(51, 65, 85, 0.4); flex-wrap: wrap; }}
.pbj-casemix-breakdown-row:first-child {{ border-top: 0; padding-top: 0.08rem; }}
.pbj-casemix-breakdown-main {{ flex: 1 1 52%; min-width: 9rem; max-width: 58%; display: flex; flex-direction: column; gap: 0.1rem; }}
.pbj-casemix-breakdown-main .pbj-casemix-sub-line {{ margin: 0; justify-content: flex-start; }}
.pbj-casemix-breakdown-aside {{ flex: 1 1 auto; margin-left: auto; font-size: 0.58rem; line-height: 1.28; color: rgba(148, 163, 184, 0.96); text-align: right; font-variant-numeric: tabular-nums; min-width: 0; }}
.pbj-casemix-cmi-strip {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem 0.5rem; margin: 0.22rem 0 0.06rem; padding: 0.22rem 0 0; border-top: 1px solid rgba(51, 65, 85, 0.45); }}
.pbj-casemix-cmi-strip--inline {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.3rem 0.45rem; margin: 0.12rem 0 0 0; padding: 0; border: 0; width: 100%; justify-content: flex-start; }}
.pbj-casemix-cmi-strip--intoprow {{ display: inline-flex; flex-wrap: wrap; align-items: center; gap: 0.28rem 0.35rem; margin: 0; padding: 0; border: 0; flex: 0 0 auto; min-width: 0; }}
.pbj-casemix-total-toprow {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: flex-start; gap: 0.3rem 0.45rem; width: 100%; }}
.pbj-casemix-total-toprow .pbj-casemix-total-vs {{ flex: 0 1 auto; min-width: 0; }}
.pbj-casemix-cmi-strip[hidden] {{ display: none !important; }}
button.pbj-casemix-cmi-trigger {{ display: inline-flex; align-items: baseline; gap: 0.28rem; font-size: 0.62rem; line-height: 1.2; padding: 0.22rem 0.48rem; border-radius: 6px; border: 1px solid rgba(100, 116, 139, 0.45); background: rgba(30, 41, 59, 0.65); color: rgba(226,232,240,0.96); cursor: pointer; font-variant-numeric: tabular-nums; max-width: 100%; box-sizing: border-box; font-family: inherit; text-align: left; transition: background 0.12s ease, border-color 0.12s ease; }}
button.pbj-casemix-cmi-trigger:hover {{ background: rgba(51, 65, 85, 0.75); border-color: rgba(148, 163, 184, 0.4); }}
button.pbj-casemix-cmi-trigger:focus-visible {{ outline: 2px solid rgba(129, 140, 248, 0.65); outline-offset: 2px; }}
button.pbj-casemix-cmi-trigger .k {{ font-weight: 700; color: #cbd5e1; letter-spacing: 0.02em; }}
button.pbj-casemix-cmi-trigger .v {{ font-weight: 700; color: #f8fafc; }}
.pbj-casemix-details {{ margin-top: 0; width: 100%; }}
.pbj-casemix-details > summary {{ list-style: none; cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 0.55rem; width: 100%; box-sizing: border-box; border: 1px solid rgba(51, 65, 85, 0.55); border-radius: 6px; background: rgba(30,41,59,0.5); padding: 0.34rem 0.48rem; min-height: 40px; user-select: none; -webkit-tap-highlight-color: transparent; transition: background 0.12s ease, border-color 0.12s ease; }}
.pbj-casemix-details .pbj-casemix-sum-wrap {{ flex-direction: row; align-items: center; gap: 0; flex: 1; min-width: 0; }}
.pbj-casemix-sum-rowlabel {{ font-size: 0.72rem; font-weight: 600; color: #cbd5e1; letter-spacing: 0.01em; line-height: 1.25; }}
.pbj-casemix-details > summary::-webkit-details-marker {{ display: none; }}
.pbj-casemix-details > summary:hover {{ background: rgba(51,65,85,0.48); border-color: rgba(148,163,184,0.34); }}
.pbj-casemix-details[open] > summary {{ border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom-color: rgba(30,41,59,0.65); }}
.pbj-casemix-sum-wrap {{ display: flex; flex-direction: column; align-items: flex-start; gap: 0.1rem; min-width: 0; flex: 1; text-align: left; }}
.pbj-casemix-sum-main {{ font-size: 0.72rem; font-weight: 700; color: #f8fafc; letter-spacing: 0.05em; text-transform: uppercase; }}
.pbj-casemix-sum-detail {{ font-size: 0.6rem; font-weight: 500; color: rgba(148,163,184,0.92); line-height: 1.2; }}
.pbj-casemix-sum-chev {{ font-size: 0.62rem; color: rgba(165, 180, 252, 0.85); flex-shrink: 0; line-height: 1; transition: transform 0.18s ease; }}
.pbj-casemix-details[open] > summary .pbj-casemix-sum-chev {{ transform: rotate(-180deg); }}
.pbj-casemix-details-body {{ padding: 0.32rem 0.45rem 0.12rem; border: 1px solid rgba(148,163,184,0.24); border-top: none; border-radius: 0 0 6px 6px; background: rgba(15,23,42,0.4); margin-top: -1px; }}
.pbj-casemix-modal-ref {{ margin: 0.35rem 0 0 0; font-size: 0.8rem; line-height: 1.42; color: rgba(226,232,240,0.9); display: none; }}
.pbj-casemix-modal-ref-p {{ margin: 0.4rem 0 0 0; padding: 0; }}
.pbj-casemix-modal-ref-p:first-child {{ margin-top: 0; }}
.pbj-casemix-stat-highlight {{ color: #a5b4fc; font-weight: 600; }}
.pbj-casemix-bars {{ display: grid; gap: 0.22rem; }}
.pbj-casemix-metric {{ min-width: 0; width: 100%; }}
.pbj-casemix-metric.total {{ width: 100%; }}
.pbj-casemix-metric.total .pbj-casemix-metric-head-block {{ width: 100%; }}
.pbj-casemix-metric--rn.pbj-casemix-metric--shortfall {{ padding-left: 0.4rem; margin-left: -0.4rem; border-left: 2px solid rgba(251, 113, 133, 0.45); }}
.pbj-casemix-total-compact {{ margin: 0 0 0.06rem 0; }}
.pbj-casemix-total-line {{ line-height: 1.35; font-size: 0.72rem; font-weight: 500; color: rgba(203,213,225,0.96); font-variant-numeric: tabular-nums; }}
.pbj-casemix-total-line .h {{ font-weight: 700; color: #f8fafc; }}
.pbj-casemix-total-line .cm {{ color: #94a3b8; font-weight: 600; }}
.pbj-casemix-total-stack {{ display: flex; flex-direction: column; gap: 0.12rem; align-items: flex-start; text-align: left; width: 100%; }}
.pbj-casemix-total-role {{ font-size: 0.58rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: rgba(148, 163, 184, 0.9); }}
.pbj-casemix-total-vs {{ font-size: 0.74rem; font-weight: 500; color: rgba(212, 212, 216, 0.95); line-height: 1.3; font-variant-numeric: tabular-nums; }}
.pbj-casemix-total-vs .h {{ font-weight: 700; color: #f4f4f5; font-size: 0.82rem; }}
.pbj-casemix-total-vs .muted {{ color: #94a3b8; font-weight: 500; font-size: 0.68rem; }}
.pbj-casemix-total-pctline {{ font-size: 0.76rem; font-weight: 600; color: #e7e5e4; letter-spacing: 0.02em; line-height: 1.22; font-variant-numeric: tabular-nums; }}
.pbj-casemix-bar-rail-wrap {{ width: 100%; }}
.pbj-casemix-metric.total .pbj-casemix-bar-rail-wrap {{ max-width: 100%; }}
.pbj-casemix-sub-line--total {{ justify-content: flex-start; gap: 0.35rem 0.55rem; }}
.pbj-casemix-sub-line--total .pbj-casemix-sub-vals {{ text-align: left; flex: 1 1 auto; }}
.pbj-casemix-bar-fill--cms-target {{ background: rgba(100, 116, 139, 0.72) !important; z-index: 1; }}
.pbj-casemix-bar-fill--reported-over {{ background: rgba(45, 212, 191, 0.62) !important; z-index: 2; border-radius: 0 2px 2px 0; }}
.pbj-casemix-bar-fill--reported-under {{ z-index: 2; }}
.pbj-casemix-bar-target-edge {{ position: absolute; top: 2px; bottom: 2px; width: 2px; margin-left: 0; background: rgba(203, 213, 225, 0.55); border-radius: 1px; z-index: 3; transform: translateX(-50%); pointer-events: none; }}
.pbj-casemix-bar-wrap--split .pbj-casemix-bar-marker {{ display: none; }}
.pbj-casemix-bar-legend {{ margin-top: 0.22rem; font-size: 0.55rem; line-height: 1.28; color: rgba(203, 213, 225, 0.88); }}
.pbj-casemix-bar-legend-oneline {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.25rem 0.65rem; column-gap: 0.65rem; row-gap: 0.12rem; }}
.pbj-casemix-bar-legend-oneline .sep {{ color: rgba(100, 116, 139, 0.95); font-weight: 500; }}
.pbj-casemix-bar-legend-gap {{ font-weight: 600; color: rgba(212, 212, 216, 0.95); }}
.pbj-casemix-flag-line {{ margin: 0; font-size: 0.6rem; font-weight: 500; color: rgba(252, 165, 165, 0.92); line-height: 1.32; }}
.pbj-casemix-caveat {{ margin: 0.18rem 0 0 0; font-size: 0.54rem; line-height: 1.28; color: rgba(113, 113, 122, 0.98); font-weight: 400; }}
.pbj-casemix-caveat-foot {{ margin: 0.35rem 0 0; font-size: 0.54rem; line-height: 1.32; color: rgba(113, 113, 122, 0.98); font-weight: 400; }}
.pbj-casemix-interpret--breakdown {{ margin: 0.28rem 0 0.12rem; }}
.pbj-casemix-details:not([open]) .pbj-casemix-interpret--breakdown {{ display: none !important; }}
.pbj-casemix-metric-head-block {{ display: flex; flex-direction: column; gap: 0.02rem; min-width: 0; }}
button.pbj-casemix-cmi-trigger.pbj-cmi-tier--low {{ border-color: rgba(100,116,139,0.7); background: rgba(30, 41, 59, 0.55); }}
button.pbj-casemix-cmi-trigger.pbj-cmi-tier--mid {{ border-color: rgba(99,102,241,0.55); background: rgba(49,46,129,0.35); }}
button.pbj-casemix-cmi-trigger.pbj-cmi-tier--high {{ border-color: rgba(45,212,191,0.5); background: rgba(15,118,110,0.25); }}
.pbj-casemix-sub-line {{ display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 0.3rem 0.6rem; font-size: 0.64rem; line-height: 1.18; margin: 0 0 0.04rem 0; }}
.pbj-casemix-sub-label {{ font-weight: 600; color: rgba(226,232,240,0.94); }}
.pbj-casemix-sub-label.rn {{ font-weight: 700; }}
.pbj-casemix-sub-vals {{ font-variant-numeric: tabular-nums; color: rgba(148,163,184,0.95); text-align: right; flex: 1 1 auto; min-width: 0; }}
.pbj-casemix-sub-vals .h {{ font-weight: 700; color: #f8fafc; }}
.pbj-casemix-sub-vals .cm {{ color: #94a3b8; font-weight: 500; }}
.pbj-casemix-metric-muted {{ color: rgba(148,163,184,0.95); font-weight: 500; font-size: 0.68rem; }}
.pbj-casemix-bar-cell {{ display: flex; flex-direction: column; gap: 0.04rem; min-width: 0; }}
.pbj-casemix-bar-wrap {{ position: relative; width: 100%; border-radius: 4px; background: rgba(30, 41, 59, 0.65); border: 1px solid rgba(100, 116, 139, 0.45); overflow: hidden; box-sizing: border-box; }}
.pbj-casemix-bar-fill {{ position: absolute; left: 0; top: 0; bottom: 0; border-radius: 2px; z-index: 1; min-width: 0; transition: width 0.25s ease; background: rgba(180, 83, 9, 0.62); }}
.pbj-casemix-sev-critical {{ background: rgba(185, 28, 28, 0.68) !important; opacity: 1; }}
.pbj-casemix-sev-warn {{ background: rgba(194, 65, 12, 0.72) !important; opacity: 1; }}
.pbj-casemix-sev-neutral {{ background: rgba(180, 83, 9, 0.58) !important; opacity: 1; }}
.pbj-casemix-sev-meets {{ background: rgba(87, 83, 78, 0.88) !important; opacity: 1; }}
.pbj-casemix-bar-marker {{ position: absolute; top: 0; bottom: 0; width: 0; margin-left: 0; border-left: 3px dashed rgba(228, 228, 231, 0.82); background: transparent; border-radius: 0; z-index: 2; box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.85); transform: translateX(-50%); }}
.pbj-casemix-bar-rail-h {{ height: 24px; }}
.pbj-casemix-metric.total .pbj-casemix-bar-rail-h {{ height: 26px; }}
.pbj-casemix-metric--rn .pbj-casemix-bar-rail-h {{ height: 18px; }}
.pbj-casemix-metric--lpn .pbj-casemix-bar-rail-h, .pbj-casemix-metric--aide .pbj-casemix-bar-rail-h {{ height: 14px; }}
.pbj-casemix-modal {{ position: fixed; inset: 0; background: rgba(2,6,23,0.72); z-index: 10020; display: none; align-items: center; justify-content: center; padding: 1rem; }}
.pbj-casemix-metric.total .pbj-casemix-bar-cell {{ max-width: 100%; width: 100%; align-self: stretch; }}
@media (min-width: 769px) {{
  .pbj-casemix-section-header {{ flex-wrap: nowrap; }}
  .pbj-casemix-summary .pbj-casemix-metric.total .pbj-casemix-bar-rail-wrap,
  .pbj-casemix-summary .pbj-casemix-metric.total .pbj-casemix-bar-cell {{ max-width: 100%; }}
}}
@media (max-width: 768px) {{
  .pbj-casemix-section-header {{
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0.35rem;
    flex-wrap: nowrap;
  }}
  .pbj-casemix-section-title {{
    font-size: 1.02em;
    margin: 0;
    min-width: 0;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  button.pbj-casemix-help-trigger {{
    margin-left: 0;
    align-self: flex-start;
    padding: 0.22rem 0.5rem;
    font-size: 0.62rem;
    border-radius: 999px;
    white-space: nowrap;
  }}
  .pbj-casemix-help-label {{ font-size: inherit; }}
  .pbj-casemix-info-icon {{ display: none !important; }}
  .pbj-casemix-summary {{ max-width: 100%; }}
  .pbj-casemix-hero-line {{
    font-size: 0.625rem;
    line-height: 1.28;
    white-space: nowrap;
    margin: 0 0 0.32rem;
    overflow: visible;
  }}
  .pbj-casemix-hero-line .tag {{ font-size: 0.55rem; margin-right: 0.15rem; }}
  .pbj-casemix-hero-line .pct-em {{ font-size: 0.72rem; }}
  .pbj-casemix-hero-line .secondary {{ font-size: 0.58rem; }}
  .pbj-casemix-hero-main {{
    flex-direction: column;
    align-items: stretch;
    gap: 0.35rem;
  }}
  .pbj-casemix-hero-copy {{
    flex: 1 1 100%;
    max-width: 100%;
    min-width: 0;
  }}
  .pbj-casemix-hero-cmi-col {{
    margin-left: 0;
    justify-content: flex-start;
  }}
  .pbj-casemix-breakdown-main {{ max-width: 100%; }}
  .pbj-casemix-breakdown-row {{ align-items: flex-start; }}
  .pbj-casemix-breakdown-aside {{ display: none; }}
  .pbj-casemix-breakdown-main .pbj-casemix-sub-label {{
    line-height: 1.38; white-space: normal; font-size: 0.62rem;
  }}
  .pbj-casemix-breakdown-main .pbj-casemix-sub-label .secondary {{
    font-weight: 500; color: rgba(148, 163, 184, 0.96); font-variant-numeric: tabular-nums;
  }}
}}
.pbj-casemix-modal.pbj-casemix-modal--aux {{ z-index: 10025; }}
.pbj-casemix-modal[aria-hidden="true"] {{ display: none !important; }}
.pbj-casemix-modal[aria-hidden="false"] {{ display: flex; }}
.pbj-casemix-modal-card {{ width: min(560px, calc(100vw - 2rem)); max-height: calc(100vh - 2rem); overflow: auto; border-radius: 10px; background: #0f172a; border: 1px solid rgba(30, 41, 59, 0.6); box-shadow: 0 16px 48px rgba(0,0,0,0.45); padding: 1rem 1rem 0.85rem; position: relative; }}
.pbj-casemix-modal-close {{ position: absolute; top: 0.5rem; right: 0.6rem; border: 0; background: transparent; color: rgba(226,232,240,0.85); font-size: 1.45rem; cursor: pointer; width: 36px; height: 36px; border-radius: 8px; }}
.pbj-casemix-modal-close:hover {{ background: rgba(51,65,85,0.5); color: #e2e8f0; }}
.pbj-casemix-modal-card h3 {{ margin: 0 2rem 0.45rem 0; font-size: 1rem; color: #e2e8f0; font-weight: 600; }}
.pbj-casemix-modal-card h4 {{ margin: 0.65rem 0 0.25rem 0; font-size: 0.82rem; font-weight: 600; color: #cbd5e1; }}
.pbj-casemix-modal-card p {{ margin: 0.4rem 0; font-size: 0.83rem; line-height: 1.45; color: rgba(226,232,240,0.9); }}
.pbj-casemix-aux-body p:first-child {{ margin-top: 0; }}
.pbj-casemix-aux-body p:last-child {{ margin-bottom: 0; }}
.pbj-hprd-means-modal .pbj-casemix-aux-body .pbj-hprd-means-body {{
  margin: 0; font-size: 0.9rem; line-height: 1.65; color: rgba(226, 232, 240, 0.93);
}}
.pbj-casemix-modal-card code {{ color: #c7d2fe; background: rgba(30,41,59,0.9); border: 1px solid rgba(148,163,184,0.2); border-radius: 6px; padding: 1px 6px; }}
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
.pbj-table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(30, 41, 59, 0.6); }}
.pbj-table-wrap table {{ margin: 0; min-width: 400px; }}
/* State page H1: desktop show full only; mobile shows short only (via @media) */
.pbj-state-title .pbj-state-title-full {{ display: inline; }}
.pbj-state-title .pbj-state-title-mobile {{ display: none !important; }}
.pbj-cta-premium {{ margin-top: 1.5rem; padding: 1rem 1.25rem; background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(30, 41, 59, 0.6); border-radius: 10px; font-size: 0.95rem; color: #e2e8f0; }}
.pbj-cta-premium a {{ color: #818cf8; font-weight: 600; transition: color 0.2s ease; }}
.pbj-cta-premium a:hover {{ color: #a5b4fc; }}
.pbj-state-min-badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; color: #fecaca; background: rgba(127, 29, 29, 0.38); border: 1px solid rgba(248, 113, 113, 0.55); }}
a.custom-report-cta {{
  display: block; margin: 1.75rem 0; padding: 1rem 1.2rem; max-width: 42rem; font-size: 0.9375rem; font-weight: 500;
  line-height: 1.5; color: #e2e8f0; text-decoration: none; cursor: pointer; box-sizing: border-box;
  background: linear-gradient(135deg, rgba(49, 46, 129, 0.28) 0%, rgba(15, 23, 42, 0.92) 55%, rgba(15, 23, 42, 0.96) 100%);
  border: 1px solid rgba(129, 140, 248, 0.42); border-left: 4px solid rgba(129, 140, 248, 0.85); border-radius: 10px;
  box-shadow: 0 4px 20px rgba(2, 6, 23, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease, color 0.2s ease, transform 0.15s ease;
}}
a.custom-report-cta:hover {{
  color: #f8fafc; border-color: rgba(165, 180, 252, 0.55);
  box-shadow: 0 6px 26px rgba(49, 46, 129, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  background: linear-gradient(135deg, rgba(67, 56, 202, 0.38) 0%, rgba(30, 41, 59, 0.88) 55%, rgba(15, 23, 42, 0.94) 100%);
  transform: translateY(-1px);
}}
a.custom-report-cta:active {{ transform: translateY(0); box-shadow: 0 2px 12px rgba(2, 6, 23, 0.35); }}
a.custom-report-cta:focus-visible {{ outline: 2px solid rgba(129, 140, 248, 0.75); outline-offset: 3px; }}
.custom-report-cta-mobile {{ display: none; }}
@media (max-width: 768px) {{ .custom-report-cta-desktop {{ display: none; }} .custom-report-cta-mobile {{ display: inline; }} a.custom-report-cta {{ max-width: none; padding: 0.9rem 1rem; font-size: 0.9rem; }} }}
.pbj-care-compare-badge {{ display: inline-block; margin-top: 0.25rem; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(129, 140, 248, 0.35); color: #a5b4fc; text-decoration: none; }}
.pbj-care-compare-badge:hover {{ background: rgba(99, 102, 241, 0.2); color: #c7d2fe; }}
.custom-report-cta .custom-report-cta-sms {{ margin-top: 0.4rem; font-size: 0.8rem; color: rgba(226,232,240,0.75); }}
.custom-report-cta .custom-report-cta-sms a {{ color: #818cf8; font-weight: 500; text-decoration: none; }}
.custom-report-cta .custom-report-cta-sms a:hover {{ color: #a5b4fc; text-decoration: underline; text-underline-offset: 3px; }}
.navbar {{ background: rgba(2, 6, 23, 0.92); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); padding: 0; position: sticky; top: 0; z-index: 1000; box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.08); border-bottom: 1px solid rgba(148, 163, 184, 0.22); }}
.nav-container {{ max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; height: 60px; }}
.nav-brand {{ display: flex; align-items: center; color: #e2e8f0; font-size: 1.2rem; font-weight: 700; }}
.nav-brand a {{ color: inherit; text-decoration: none; display: flex; align-items: center; transition: opacity 0.2s ease; }}
.nav-brand a:hover {{ opacity: 0.92; }}
.nav-menu {{ display: flex; gap: 30px; align-items: center; }}
.nav-link {{ color: rgba(255, 255, 255, 0.88); text-decoration: none; font-weight: 500; padding: 8px 0; transition: color 0.2s ease; }}
.nav-link:hover {{ color: #93c5fd; }}
.nav-link.active {{ color: #60a5fa; font-weight: 600; }}
.nav-toggle {{ display: none; flex-direction: column; cursor: pointer; gap: 4px; }}
.nav-toggle span {{ width: 25px; height: 3px; background: #e2e8f0; }}
.footer-section-hr {{ border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); height: 0; margin: clamp(20px, 3vw, 32px) 0 0 0; width: 100%; }}
.footer-section-hr + .footer {{ border-top: none; }}
.footer {{ text-align: center; padding: 32px 20px 40px; color: #a8b4c4; font-size: 0.9rem; background: #0d121f; margin-top: 0; border-top: 1px solid rgba(148, 163, 184, 0.18); width: 100%; box-sizing: border-box; }}
.footer a {{ color: #cbd5e1; text-decoration: none; transition: color 0.2s ease, opacity 0.2s ease; }}
.footer a:hover {{ color: #f8fafc; opacity: 1; }}
.footer a:hover img {{ opacity: 1; }}
@media (max-width: 768px) {{
  .footer {{ padding: 22px 12px 28px; font-size: 0.85rem; }}
}}
.pbj-badge-mobile-only {{ display: none !important; }}
@media (max-width: 768px) {{
  .pbj-metrics-row {{ grid-template-columns: repeat(2, 1fr); gap: 0.75rem; }}
  .pbj-content {{ padding: 20px 16px; }}
  .pbj-content-box {{ padding: 24px 20px; margin-bottom: 20px; }}
  .pbj-content-box h1 {{ font-size: 1.5rem; }}
  .pbj-content-box h2 {{ font-size: 1.2rem; }}
  .section-header {{ font-size: 1.2em; }}
  .nav-menu {{ display: none; flex-direction: column; position: absolute; top: 60px; left: 0; right: 0; background: rgba(2, 6, 23, 0.98); backdrop-filter: blur(12px); padding: 1rem; gap: 12px; border-bottom: 1px solid rgba(30, 41, 59, 0.5); }}
  .nav-menu.active {{ display: flex; }}
  .nav-link {{ padding: 12px 0; min-height: 44px; display: flex; align-items: center; }}
  .nav-toggle {{ display: flex; min-width: 44px; min-height: 44px; align-items: center; justify-content: center; cursor: pointer; }}
  .nav-toggle span {{ width: 25px; height: 3px; background: #e2e8f0; }}
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
  .pbj-rural-meter-track {{ position: relative; }}
  .pbj-rural-meter-nat {{ position: absolute; top: -1px; bottom: -1px; width: 2px; margin-left: -1px; background: rgba(248, 250, 252, 0.92); box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.55); z-index: 2; pointer-events: none; }}
  .pbj-badge-mobile-only {{ display: none !important; }}
  @media (max-width: 768px) {{
    .pbj-overall-badge {{ display: none !important; }}
    .pbj-badge-mobile-only {{ display: inline-block !important; }}
  }}
  /* High-risk tooltip: less narrow on mobile; position clamped by JS so it never bleeds off left or right */
  .pbj-high-risk-tooltip {{ min-width: 280px; max-width: min(320px, calc(100vw - 24px)); width: max-content; padding: 12px 14px; font-size: 0.875rem; line-height: 1.45; }}
  .pbj-subtitle {{ font-size: 0.85em; }}
  /* State page subtitle on mobile: "590 providers • 97,999 residents • 3.57 HPRD (Q3 2025)" - allow wrap, smaller */
  .pbj-subtitle-state {{ font-size: 0.8em; line-height: 1.4; }}
  /* Provider page: on mobile show subtitle in two rows (row1: location • residents; row2: For Profit • Entity) */
  .pbj-subtitle-desktop {{ display: none; }}
  .pbj-subtitle-mobile {{ display: block; }}
  .pbj-subtitle-mobile-row1, .pbj-subtitle-mobile-row2 {{ display: block; }}
  .pbj-subtitle-mobile-row2 {{ margin-top: 0.2em; }}
  /* State page H1: on mobile show short "New York PBJ Staffing" only */
  .pbj-state-title .pbj-state-title-full {{ display: none !important; }}
  .pbj-state-title .pbj-state-title-mobile {{ display: inline !important; }}
  .pbj-page-footer {{ margin-top: 1.5rem; padding-top: 0.4rem; }}
  .entity-chain-metrics {{ grid-template-columns: repeat(2, 1fr) !important; gap: 0.75rem !important; }}
  .pbj-chart-container {{ padding: 12px; }}
  .pbj-chart-container.pbj-casemix-card {{ padding: 0.48rem 0.52rem 0.42rem; margin: 12px 0; }}
  .pbj-casemix-total-nums {{ font-size: 0.64rem; }}
  .pbj-casemix-total-k {{ font-size: 0.6rem; }}
  .pbj-casemix-sub-line {{ font-size: 0.6rem; }}
  .pbj-casemix-interpret {{ font-size: 0.62rem; }}
  .pbj-casemix-cmi-trigger {{ font-size: 0.62rem; padding: 0.22rem 0.48rem; }}
  /* Entity page: hide " – Genesis Healthcare" (etc.) in subsection headers on mobile */
  .pbj-section-header-entity-name {{ display: none !important; }}
}}
/* Contact popup (entity/state/facility pages) */
.contact-overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 10000; display: none; align-items: center; justify-content: center; padding: 1rem; box-sizing: border-box; }}
.contact-overlay[aria-hidden="false"] {{ display: flex; }}
.contact-popup {{ position: relative; background: #0f172a; border: 1px solid rgba(30, 41, 59, 0.6); border-radius: 12px; width: 100%; max-width: 440px; max-height: calc(100vh - 2rem); overflow: auto; box-shadow: 0 0 28px -8px rgba(99, 102, 241, 0.12); -webkit-overflow-scrolling: touch; }}
.contact-popup h2 {{ margin: 0; padding: 1.25rem 1.25rem 0; font-size: 1.25rem; color: #818cf8; }}
.contact-popup .contact-popup-close {{ position: absolute; top: 0.75rem; right: 0.75rem; width: 44px; height: 44px; padding: 0; border: none; background: transparent; cursor: pointer; font-size: 1.5rem; line-height: 1; color: rgba(148,163,184,0.9); border-radius: 8px; }}
.contact-popup .contact-popup-close:hover {{ color: #e2e8f0; background: rgba(99, 102, 241, 0.15); }}
.contact-popup .contact-popup-close:focus-visible {{ outline: 2px solid #818cf8; outline-offset: 2px; }}
.contact-popup-form {{ padding: 1rem 1.25rem 1.5rem; }}
.contact-popup-form .f-group {{ margin-bottom: 1rem; }}
.contact-popup-form .f-group label {{ display: block; font-weight: 500; color: #cbd5e1; margin-bottom: 0.3rem; font-size: 0.9rem; }}
.contact-popup-form .f-group input[type="text"], .contact-popup-form .f-group input[type="email"], .contact-popup-form .f-group textarea {{ width: 100%; padding: 0.6rem 0.75rem; border: 1px solid rgba(51, 65, 85, 0.65); border-radius: 8px; font: inherit; font-size: 1rem; min-height: 44px; box-sizing: border-box; background: rgba(15,23,42,0.6); color: #e2e8f0; }}
.contact-popup-form .f-group textarea {{ min-height: 100px; resize: vertical; }}
.contact-popup-form .f-group input:focus, .contact-popup-form .f-group textarea:focus {{ outline: none; border-color: rgba(129, 140, 248, 0.55); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }}
.contact-popup-form .f-group input:-webkit-autofill, .contact-popup-form .f-group input:-webkit-autofill:hover, .contact-popup-form .f-group input:-webkit-autofill:focus, .contact-popup-form .f-group input:-webkit-autofill:active, .contact-popup-form .f-group textarea:-webkit-autofill, .contact-popup-form .f-group textarea:-webkit-autofill:hover, .contact-popup-form .f-group textarea:-webkit-autofill:focus, .contact-popup-form .f-group textarea:-webkit-autofill:active {{ -webkit-text-fill-color: #e2e8f0; -webkit-box-shadow: 0 0 0 1000px rgba(15,23,42,0.95) inset; box-shadow: 0 0 0 1000px rgba(15,23,42,0.95) inset; transition: background-color 5000s ease-in-out 0s; }}
.contact-popup-form .f-row-submit {{ display: flex; align-items: center; justify-content: center; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; }}
.contact-popup-form .cb-wrap {{ display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }}
.contact-popup-form .cb-wrap input {{ width: 1.25rem; height: 1.25rem; cursor: pointer; flex-shrink: 0; }}
.contact-popup-form .cb-wrap span {{ color: #cbd5e1; }}
.contact-popup-form button[type="submit"] {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(129, 140, 248, 0.45); padding: 0.7rem 1.25rem; border-radius: 8px; font: inherit; font-size: 1rem; font-weight: 500; cursor: pointer; min-height: 44px; }}
.contact-popup-form button[type="submit"]:hover {{ background: rgba(99, 102, 241, 0.3); color: #c7d2fe; }}
.contact-toast {{ position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); background: rgba(30, 41, 59, 0.95); color: #e2e8f0; padding: 0.875rem 1.5rem; border-radius: 12px; font-size: 0.9375rem; font-weight: 500; z-index: 10001; box-shadow: 0 8px 32px rgba(0,0,0,0.24); border: 1px solid rgba(148, 163, 184, 0.2); backdrop-filter: blur(8px); }}
.contact-toast.error {{ background: rgba(30, 41, 59, 0.95); color: #fca5a5; border-color: rgba(248, 113, 113, 0.25); }}
</style>
{extra_head}
</head>
<body>'''
    nav = '''
  <nav class="navbar">
    <div class="nav-container">
      <div class="nav-brand">
        <a href="/">
          <img src="/pbj_favicon.png" alt="" width="32" height="32" decoding="async" fetchpriority="high" style="height: 32px; width: 32px; margin-right: 8px;">
          <span><span style="color:#e2e8f0;">PBJ</span><span style="color:#818cf8;">320</span></span>
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
  <hr class="footer-section-hr" aria-hidden="true">
  <footer class="footer" id="site-footer"></footer>
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
  <script src="/pbj-site-universal.js?v=13"></script>
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
  <script>
  (function() {
    function shareToast(msg) {
      var existing = document.querySelector('.contact-toast.pbj-share-toast');
      if (existing) existing.remove();
      var toast = document.createElement('div');
      toast.className = 'contact-toast pbj-share-toast';
      toast.setAttribute('role', 'status');
      toast.textContent = msg;
      document.body.appendChild(toast);
      setTimeout(function() { toast.remove(); }, 2800);
    }
    function copyShareLink(url, text, btn) {
      var payload = (text ? text + '\\n\\n' : '') + url;
      function done() {
        shareToast('Link copied');
        if (btn) btn.focus();
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(payload).then(done).catch(function() { fallbackCopy(payload, btn, done); });
      } else {
        fallbackCopy(payload, btn, done);
      }
    }
    function fallbackCopy(payload, btn, done) {
      var ta = document.createElement('textarea');
      ta.value = payload;
      ta.setAttribute('readonly', '');
      ta.style.position = 'absolute';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        if (done) done();
      } catch (e) { shareToast('Could not copy link'); }
      document.body.removeChild(ta);
    }
    function isMobileShareContext() {
      return window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
    }
    function buildSharePayload(url, title, text) {
      var payload = isMobileShareContext()
        ? { title: title || 'PBJ320', url: url }
        : { title: title, text: text, url: url };
      if (!navigator.canShare) return payload;
      try {
        if (navigator.canShare(payload)) return payload;
      } catch (e) {}
      var minimal = { url: url };
      try {
        if (navigator.canShare(minimal)) return minimal;
      } catch (e2) {}
      return payload;
    }
    function handleShareClick(btn) {
      var url = btn.getAttribute('data-share-url') || window.location.href;
      var title = btn.getAttribute('data-share-title') || document.title;
      var text = btn.getAttribute('data-share-text') || '';
      if (navigator.share) {
        var payload = buildSharePayload(url, title, text);
        navigator.share(payload).then(function() {
          if (!isMobileShareContext()) shareToast('Shared');
        }).catch(function(err) {
          if (err && err.name === 'AbortError') return;
          copyShareLink(url, text, btn);
        });
      } else {
        copyShareLink(url, text, btn);
      }
    }
    function bindShare() {
      document.addEventListener('click', function(e) {
        var btn = e.target && e.target.closest ? e.target.closest('.pbj-takeaway-share-btn') : null;
        if (!btn) return;
        e.preventDefault();
        handleShareClick(btn);
      });
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bindShare);
    } else {
      bindShare();
    }
  })();
  </script>
  <script>
  (function(){
    var MARGIN = 12;
    function clampTooltipToViewport(tooltip) {
      if (!tooltip || !tooltip.offsetParent) return;
      var rect = tooltip.getBoundingClientRect();
      var vw = window.innerWidth || document.documentElement.clientWidth;
      var desiredLeft = Math.max(MARGIN, Math.min(rect.left, vw - MARGIN - rect.width));
      var shift = desiredLeft - rect.left;
      tooltip.style.transform = shift === 0 ? 'translateX(-50%)' : 'translateX(calc(-50% + ' + shift + 'px))';
    }
    function clearTooltipShift(tooltip) {
      if (tooltip) tooltip.style.transform = '';
    }
    document.addEventListener('DOMContentLoaded', function() {
      document.querySelectorAll('.pbj-high-risk-help-wrap').forEach(function(wrap) {
        var tooltip = wrap.querySelector('.pbj-high-risk-tooltip');
        if (!tooltip) return;
        wrap.addEventListener('mouseenter', function() {
          requestAnimationFrame(function() { requestAnimationFrame(function() { clampTooltipToViewport(tooltip); }); });
        });
        wrap.addEventListener('mouseleave', function() { clearTooltipShift(tooltip); });
      });
      document.querySelectorAll('.pbj-risk-badge-info').forEach(function(btn) {
        var wrap = btn.closest('.pbj-risk-badge-info-wrap');
        if (!wrap) return;
        var tooltip = wrap.querySelector('.pbj-high-risk-tooltip');
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          var open = wrap.classList.toggle('is-open');
          if (open && tooltip) {
            requestAnimationFrame(function() { clampTooltipToViewport(tooltip); });
          } else if (tooltip) {
            clearTooltipShift(tooltip);
          }
        });
      });
      document.addEventListener('click', function(e) {
        if (e.target && e.target.closest && e.target.closest('.pbj-risk-badge-info-wrap')) return;
        document.querySelectorAll('.pbj-risk-badge-info-wrap.is-open').forEach(function(wrap) {
          wrap.classList.remove('is-open');
          var tooltip = wrap.querySelector('.pbj-high-risk-tooltip');
          if (tooltip) clearTooltipShift(tooltip);
        });
      });
    });
  })();
  </script>
</body>
</html>'''
    if pbj_ai_dashboards_enabled():
        _fw_json = ai_helper_framework_json_for_js().replace('</', '<\\/')
        content_close = content_close.replace(
            '</body>\n</html>',
            f'  <script>window.__PBJ_REVIEW_FRAMEWORK__={_fw_json};</script>\n'
            '  <script src="/pbj-review-framework.js?v=15"></script>\n'
            '  <script src="/pbj-ai-support.js?v=48"></script>\n</body>\n</html>',
            1,
        )
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
    link_attrs = (
        f'href="#" class="custom-report-cta pbj-contact-trigger" data-topic="{topic_attr}" '
        f'aria-label="Open contact form to request custom PBJ analysis"'
    )
    return (
        f'<a {link_attrs}>'
        f'<span class="custom-report-cta-desktop">{html.escape(sub_text_desktop)}</span>'
        f'<span class="custom-report-cta-mobile">{html.escape(sub_text_mobile)}</span>'
        f'</a>'
    )


def render_methodology_block():
    """Return collapsible Methodology & Data Transparency block for facility, state, entity pages."""
    return '''<details class="pbj-details pbj-details-methodology">
<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Methodology</summary>
<div class="pbj-details-content">
<p style="margin: 0 0 0.6rem 0; font-size: 0.9rem; color: rgba(226,232,240,0.9);">This dashboard uses CMS Payroll-Based Journal (PBJ) data (2017–2025), along with other public datasets (Provider Information, Affiliated Entity). State staffing standards via MACPAC (2022).</p>
<p style="margin: 0 0 0.35rem 0; font-weight: 600; font-size: 0.9rem; color: #818cf8;">Metrics</p>
<ul style="font-size: 0.875rem; color: rgba(226,232,240,0.88); margin: 0 0 0.75rem 0;">
<li><strong>Hours Per Resident Day (HPRD):</strong> Total staff hours ÷ average residents. Example: 350 hours for 100 residents = 3.5 HPRD.</li>
<li><strong>Direct Care</strong> (excl. Admin, DON): Hours per resident day for direct care staff only (RN, LPN, CNA, NAtrn, MedAide), excluding administrative and supervisory roles.</li>
<li><strong>Contract Staff %:</strong> Share of hours provided by contract staff.</li>
<li><strong>Census:</strong> Average number of residents during the period.</li>
</ul>
<p style="margin: 0 0 0.75rem 0; font-size: 0.85rem; color: rgba(226,232,240,0.8);">Note: Some states set minimums (e.g., NJ, CA, NY at 3.5 HPRD); a federal 3.48 minimum was recently overturned (2025). A 2001 federal study linked 4.1 HPRD to better outcomes in that study. Staffing needs vary by resident acuity (case-mix), day, and shift. Estimates on PBJ Takeaway assume roughly 60% of staff are CNAs.</p>
<p style="margin: 0 0 0.35rem 0; font-weight: 600; font-size: 0.9rem; color: #818cf8;">Data transparency</p>
<p style="margin: 0; font-size: 0.875rem; color: rgba(226,232,240,0.88);">The PBJ Dashboard pulls directly from CMS data and is carefully vetted for accuracy. Still, sometimes a bug sneaks into the jelly. That could mean: a systemic CMS data reporting issue (e.g., Q2 2017 contract staffing, missing data in 2020 due to COVID) or there could be a coding error on our part. If you spot something that looks off, please <a href="#" class="pbj-contact-trigger" data-topic="Data issue or possible bug (please describe what looks wrong and where)." data-subject-type="data_issue" style="color: #818cf8;" role="button">let me know via the contact form</a> so I can set things right.</p>
</div>
</details>'''


def normalize_ccn(ccn):
    """Ensure CCN is 6-digit string (audit: zfill(6)).
    Handles pandas NA, float NaN, and CSV float artifacts (e.g. 65225.0) consistently with PROVNUM parsing."""
    if ccn is None or ccn == '':
        return ''
    try:
        pdm = get_pd()
        if pdm is not None and bool(pdm.isna(ccn)):
            return ''
    except Exception:
        pass
    try:
        if isinstance(ccn, float) and ccn != ccn:  # NaN
            return ''
    except (TypeError, ValueError):
        pass
    s = str(ccn).strip()
    if not s or s.lower() in ('nan', 'none', '<na>', 'nat'):
        return ''
    if '.' in s:
        s = s.split('.')[0]
    if not s:
        return ''
    return s.zfill(6)


def _normalize_provnum_series(series):
    """Vectorized PROVNUM → 6-digit CCN strings; matches normalize_ccn for float/string cells."""
    pdm = get_pd()
    if pdm is None or series is None or not hasattr(series, 'astype'):
        return series
    s = series.astype(str).str.strip().str.split('.').str[0]
    s = s.replace({'nan': '', 'None': '', '<NA>': '', 'NaT': ''}, regex=False)
    mask = s.ne('')
    out = pdm.Series([''] * len(series), index=series.index, dtype=object)
    out.loc[mask] = s.loc[mask].str.zfill(6)
    return out

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
ENTITY_NAME_ACRONYMS = {'NHS', 'CMS', 'RN', 'LPN', 'CCRC', 'PBJ', 'HPRD', 'SNF', 'ALF', 'LTAC', 'ID/DD', 'PACS'}


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

def _facility_quarterly_csv_path():
    """Resolve path for facility_quarterly_metrics (same order as load_csv_data). Returns path or None."""
    for filename in ('facility_quarterly_metrics.csv', 'facility_quarterly_metrics_latest.csv'):
        for path in [
            os.path.join(APP_ROOT, filename),
            filename,
            os.path.join('pbj-wrapped', 'public', 'data', filename),
            os.path.join('pbj-wrapped', 'dist', 'data', filename),
            os.path.join('data', filename),
        ]:
            if os.path.exists(path):
                return path
    return None


def load_facility_quarterly_for_provider(ccn):
    """Load facility quarterly metrics for one provider (PROVNUM). Returns DataFrame or None.
    Prefers full facility_quarterly_metrics.csv so we include 2025Q3 when present; _latest may only have through Q2 2025.
    This is the source for provider page longitudinal charts (staffing, census, contract); all quarters are kept.
    Streams CSV in chunks so the full file is never loaded; peak memory stays low."""
    pdm = get_pd()
    if pdm is None:
        return None
    prov = normalize_ccn(ccn)
    if not prov:
        return None
    path = _facility_quarterly_csv_path()
    if not path:
        return None
    _log_mem("facility_quarterly_stream_start")
    chunks_list = []
    try:
        for chunk in pdm.read_csv(path, low_memory=False, chunksize=100000):
            if 'PROVNUM' not in chunk.columns:
                continue
            normalized = _normalize_provnum_series(chunk['PROVNUM'])
            if normalized.empty:
                continue
            # File is sorted by PROVNUM; skip irrelevant chunks and stop once we've passed target.
            chunk_min = normalized.iloc[0]
            chunk_max = normalized.iloc[-1]
            if chunk_max < prov:
                continue
            if chunk_min > prov:
                break
            match = chunk.loc[normalized == prov]
            if not match.empty:
                out_match = match.copy()
                out_match['PROVNUM'] = _normalize_provnum_series(out_match['PROVNUM'])
                chunks_list.append(out_match)
                # Contiguous provider rows are complete after this chunk in sorted data.
                break
    except Exception as e:
        print(f"Error streaming facility_quarterly from {path}: {e}")
        _log_mem("facility_quarterly_stream_end")
        return None
    out = pdm.concat(chunks_list, axis=0, ignore_index=True) if chunks_list else pdm.DataFrame()
    _log_mem("facility_quarterly_stream_end")
    return out if not out.empty else None


def _state_facility_metrics_slice_for_percentiles(state_code):
    """One filtered copy of facility_quarterly_metrics for a state (for percentiles). Same CSV source as provider pages."""
    pdm = get_pd()
    if pdm is None or not state_code:
        return None
    df = load_csv_data('facility_quarterly_metrics.csv')
    if df is None or not isinstance(df, pd.DataFrame):
        df = load_csv_data('facility_quarterly_metrics_latest.csv')
    if df is None or not isinstance(df, pd.DataFrame):
        return None
    if 'STATE' not in df.columns or 'CY_Qtr' not in df.columns or 'Total_Nurse_HPRD' not in df.columns:
        return None
    sc = str(state_code).strip().upper()[:2]
    st = df['STATE'].astype(str).str.strip().str.upper().str[:2]
    sub = df.loc[st == sc].copy()
    if sub.shape[0] < 2:
        return None
    sub['_qstr'] = sub['CY_Qtr'].astype(str).str.strip()
    return sub


def _percentiles_from_state_slice(state_slice, quarter, facility_hprd_total, facility_hprd_rn=None):
    """Within-state percentile for one quarter using a pre-built state slice (see _state_facility_metrics_slice_for_percentiles)."""
    if state_slice is None or not quarter or facility_hprd_total is None:
        return None, None
    q = str(quarter).strip()
    sub = state_slice[state_slice['_qstr'] == q]
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


def get_facility_state_percentile(ccn, state_code, quarter, facility_hprd_total, facility_hprd_rn=None):
    """Compute facility percentile within state for given quarter. Returns (pct_total, pct_rn) 0-100 or (None, None) if unavailable.
    ``ccn`` is accepted for API parity; percentiles are within-state for the quarter and do not filter by facility."""
    if get_pd() is None or not state_code or not quarter or facility_hprd_total is None:
        return None, None
    _ = normalize_ccn(ccn)
    sl = _state_facility_metrics_slice_for_percentiles(state_code)
    return _percentiles_from_state_slice(sl, quarter, facility_hprd_total, facility_hprd_rn)


_CMI_REF_STATS_CACHE = {}


def get_provider_info_cmi_reference_stats(quarter_str):
    """Median and quartiles for nursing CMI and CMI ratio from a CMS provider snapshot CSV.

    Scans the same ProviderInfoNorm / combined files used elsewhere, filtered to the same
    calendar quarter as ``quarter_str`` (``YYYYQn`` or ``Qn YYYY`` in the file). Values are **empirical peers in that
    file**, not a separately published CMS national table.

    Returns a JSON-serializable dict or None.
    """
    global _CMI_REF_STATS_CACHE
    if not HAS_PANDAS or not quarter_str:
        return None
    target_cy = _normalize_quarter_to_cy_qtr(str(quarter_str).strip())
    if not target_cy:
        return None
    paths = _provider_snapshot_candidate_paths() + [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
    ]
    path = next((p for p in paths if os.path.exists(p)), None)
    if not path:
        return None
    try:
        mtime = int(os.path.getmtime(path))
    except OSError:
        mtime = 0
    cache_key = (os.path.abspath(path), mtime, target_cy)
    if cache_key in _CMI_REF_STATS_CACHE:
        return _CMI_REF_STATS_CACHE[cache_key]
    try:
        head = pd.read_csv(path, nrows=0)
    except Exception:
        return None
    qcol = 'CY_Qtr' if 'CY_Qtr' in head.columns else ('quarter' if 'quarter' in head.columns else None)
    if not qcol or 'nursing_case_mix_index' not in head.columns or 'nursing_case_mix_index_ratio' not in head.columns:
        return None
    usecols = [qcol, 'nursing_case_mix_index', 'nursing_case_mix_index_ratio']
    cmi_parts = []
    ratio_parts = []
    try:
        for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=120000):
            qc = chunk[qcol].astype(str).str.strip()
            qc = qc.replace({'nan': '', 'None': '', '<NA>': ''})
            if qcol == 'CY_Qtr':
                row_cy = qc
            else:
                m_cy = qc.str.match(r'^\d{4}Q[1-4]$', na=False)
                row_cy = qc.where(m_cy, qc.map(_quarter_display_to_cy_qtr))
            chunk = chunk[row_cy == target_cy]
            if chunk.empty:
                continue
            # pd.to_numeric is overloaded (scalar | Series); wrap so boolean indexing type-checks.
            cmi = pd.Series(
                pd.to_numeric(chunk['nursing_case_mix_index'], errors='coerce'),
                copy=False,
            )
            ratio = pd.Series(
                pd.to_numeric(chunk['nursing_case_mix_index_ratio'], errors='coerce'),
                copy=False,
            )
            cmi_ok = cmi[(cmi > 0) & (cmi < 5)]
            ratio_ok = ratio[(ratio > 0) & (ratio < 5)]
            if not cmi_ok.empty:
                cmi_parts.append(cmi_ok)
            if not ratio_ok.empty:
                ratio_parts.append(ratio_ok)
    except Exception as e:
        print(f'CMI reference stats failed ({path}): {e}')
        return None
    if not cmi_parts:
        return None
    cmi_s = pd.concat(cmi_parts, ignore_index=True)
    ratio_s = pd.concat(ratio_parts, ignore_index=True) if ratio_parts else pd.Series(dtype=float)

    def _qstats(s):
        s = s.dropna()
        n = int(len(s))
        if n < 30:
            return None, None, None, n
        return (
            round_half_up(float(s.quantile(0.25)), 2),
            round_half_up(float(s.quantile(0.5)), 2),
            round_half_up(float(s.quantile(0.75)), 2),
            n,
        )

    c25, cmed, c75, cn = _qstats(cmi_s)
    r25, rmed, r75, rn = _qstats(ratio_s) if not ratio_s.empty else (None, None, None, 0)
    out = {
        'quarter': target_cy,
        'quarterDisplay': format_quarter(target_cy),
        'cmiP25': c25,
        'cmiMedian': cmed,
        'cmiP75': c75,
        'cmiN': cn,
        'ratioP25': r25,
        'ratioMedian': rmed,
        'ratioP75': r75,
        'ratioN': rn,
    }
    if len(_CMI_REF_STATS_CACHE) > 32:
        _CMI_REF_STATS_CACHE.clear()
    _CMI_REF_STATS_CACHE[cache_key] = out
    return out


_CMI_STATE_REF_STATS_CACHE = {}
_CMI_STATE_SORTED_CACHE = {}


def _percentile_rank_1_100(sorted_vals, x):
    """Empirical percentile rank 1–100: share of values ≤ x (rounded). None if unavailable."""
    if not sorted_vals or x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    n = len(sorted_vals)
    if n < 15:
        return None
    import bisect

    k = bisect.bisect_right(sorted_vals, xf)
    pr = int(round(100 * k / n))
    return max(1, min(100, pr))


def _apply_cmi_state_facility_percentiles(base: dict, cache_key: tuple, facility_cmi, facility_ratio) -> None:
    """Mutate base dict with facilityCmiPercentile, facilityRatioPercentile, stateDisplayName."""
    st = (base.get('state') or '').strip().upper()[:2]
    base['stateDisplayName'] = STATE_CODE_TO_NAME.get(st, st or '')
    base['facilityCmiPercentile'] = None
    base['facilityRatioPercentile'] = None
    pair = _CMI_STATE_SORTED_CACHE.get(cache_key)
    if not pair:
        return
    cmi_sorted, ratio_sorted = pair
    if facility_cmi is not None and base.get('cmiN') and int(base['cmiN']) >= 15 and cmi_sorted:
        base['facilityCmiPercentile'] = _percentile_rank_1_100(cmi_sorted, facility_cmi)
    if facility_ratio is not None and base.get('ratioN') and int(base['ratioN']) >= 15 and ratio_sorted:
        base['facilityRatioPercentile'] = _percentile_rank_1_100(ratio_sorted, facility_ratio)


def get_provider_info_cmi_state_reference_stats(state_code, quarter_str, facility_cmi=None, facility_ratio=None):
    """Median and quartiles for nursing CMI and CMI ratio, same quarter, same state, from CMS provider snapshot.
    Optional facility_cmi / facility_ratio add facilityCmiPercentile and facilityRatioPercentile (1–100) vs same-state peers."""
    global _CMI_STATE_REF_STATS_CACHE, _CMI_STATE_SORTED_CACHE
    st = (state_code or '').strip().upper()[:2]
    if not st or not quarter_str or not HAS_PANDAS:
        return None
    target_cy = _normalize_quarter_to_cy_qtr(str(quarter_str).strip())
    if not target_cy:
        return None
    paths = _provider_snapshot_candidate_paths() + [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
    ]
    path = next((p for p in paths if os.path.exists(p)), None)
    if not path:
        return None
    try:
        mtime = int(os.path.getmtime(path))
    except OSError:
        mtime = 0
    cache_key = (os.path.abspath(path), mtime, target_cy, st)
    if cache_key in _CMI_STATE_REF_STATS_CACHE:
        out = dict(_CMI_STATE_REF_STATS_CACHE[cache_key])
        _apply_cmi_state_facility_percentiles(out, cache_key, facility_cmi, facility_ratio)
        return out
    try:
        head = pd.read_csv(path, nrows=0)
    except Exception:
        return None
    qcol = 'CY_Qtr' if 'CY_Qtr' in head.columns else ('quarter' if 'quarter' in head.columns else None)
    st_col = 'state' if 'state' in head.columns else ('State' if 'State' in head.columns else None)
    if not qcol or not st_col or 'nursing_case_mix_index' not in head.columns or 'nursing_case_mix_index_ratio' not in head.columns:
        return None
    usecols = [qcol, 'nursing_case_mix_index', 'nursing_case_mix_index_ratio', st_col]
    cmi_parts = []
    ratio_parts = []
    try:
        for chunk in pd.read_csv(path, usecols=usecols, low_memory=False, chunksize=120000):
            qc = chunk[qcol].astype(str).str.strip()
            qc = qc.replace({'nan': '', 'None': '', '<NA>': ''})
            if qcol == 'CY_Qtr':
                row_cy = qc
            else:
                m_cy = qc.str.match(r'^\d{4}Q[1-4]$', na=False)
                row_cy = qc.where(m_cy, qc.map(_quarter_display_to_cy_qtr))
            stv = chunk[st_col].astype(str).str.strip().str.upper().str[:2]
            chunk = chunk[(row_cy == target_cy) & (stv == st)]
            if chunk.empty:
                continue
            cmi = pd.Series(
                pd.to_numeric(chunk['nursing_case_mix_index'], errors='coerce'),
                copy=False,
            )
            ratio = pd.Series(
                pd.to_numeric(chunk['nursing_case_mix_index_ratio'], errors='coerce'),
                copy=False,
            )
            cmi_ok = cmi[(cmi > 0) & (cmi < 5)]
            ratio_ok = ratio[(ratio > 0) & (ratio < 5)]
            if not cmi_ok.empty:
                cmi_parts.append(cmi_ok)
            if not ratio_ok.empty:
                ratio_parts.append(ratio_ok)
    except Exception as e:
        print(f'CMI state reference stats failed ({path}): {e}')
        return None
    if not cmi_parts:
        return None
    cmi_s = pd.concat(cmi_parts, ignore_index=True)
    ratio_s = pd.concat(ratio_parts, ignore_index=True) if ratio_parts else pd.Series(dtype=float)
    cmi_sorted = sorted(float(x) for x in cmi_s.dropna().tolist())
    ratio_sorted = sorted(float(x) for x in ratio_s.dropna().tolist()) if not ratio_s.empty else []

    def _qstats(s):
        s = s.dropna()
        n = int(len(s))
        if n < 15:
            return None, None, None, n
        return (
            round_half_up(float(s.quantile(0.25)), 2),
            round_half_up(float(s.quantile(0.5)), 2),
            round_half_up(float(s.quantile(0.75)), 2),
            n,
        )

    c25, cmed, c75, cn = _qstats(cmi_s)
    r25, rmed, r75, rn = _qstats(ratio_s) if not ratio_s.empty else (None, None, None, 0)
    out = {
        'state': st,
        'stateDisplayName': STATE_CODE_TO_NAME.get(st, st),
        'quarter': target_cy,
        'quarterDisplay': format_quarter(target_cy),
        'cmiP25': c25,
        'cmiMedian': cmed,
        'cmiP75': c75,
        'cmiN': cn,
        'ratioP25': r25,
        'ratioMedian': rmed,
        'ratioP75': r75,
        'ratioN': rn,
    }
    _CMI_STATE_SORTED_CACHE[cache_key] = (cmi_sorted, ratio_sorted)
    if len(_CMI_STATE_REF_STATS_CACHE) > 48:
        _CMI_STATE_REF_STATS_CACHE.clear()
        _CMI_STATE_SORTED_CACHE.clear()
    _CMI_STATE_REF_STATS_CACHE[cache_key] = out
    merged = dict(out)
    _apply_cmi_state_facility_percentiles(merged, cache_key, facility_cmi, facility_ratio)
    return merged


def get_macpac_hprd_for_state(state_code):
    """Return state minimum staffing HPRD (float), or None. Used for state page min phrase; for provider chart line/label use get_macpac_chart_info."""
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


def get_macpac_chart_info(state_code):
    """Return dict with line_value (float for chart line; use max when range), label_short (no MACPAC), label_long (with MACPAC), or None."""
    if not state_code:
        return None
    state_code_upper = (state_code or '').strip().upper()[:2]
    state_code_lower = state_code_upper.lower()
    for path in ['pbj-wrapped/public/data/json/state_standards.json', 'state_standards.json']:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    s = data.get(state_code_upper) or data.get(state_code_lower)
                    if s and isinstance(s, dict):
                        min_raw = s.get('Min_Staffing')
                        max_raw = s.get('Max_Staffing')
                        value_type = (s.get('Value_Type') or '').strip().lower()
                        try:
                            min_val = float(str(min_raw).replace(' HPRD', '').strip()) if min_raw is not None else None
                            max_val = float(str(max_raw).replace(' HPRD', '').strip()) if max_raw is not None else None
                        except (TypeError, ValueError):
                            min_val = max_val = None
                        if min_val is None:
                            continue
                        # For range states, draw line at upper (max); for single use min
                        line_value = max_val if (value_type == 'range' and max_val is not None) else min_val
                        min_str = f'~{round_half_up(min_val, 2):.2f}' if min_val is not None else ''
                        if value_type == 'range' and max_val is not None and max_val != min_val:
                            label_val = f'{min_str}-{round_half_up(max_val, 2):.2f}'
                        else:
                            label_val = min_str
                        label_base = f'{state_code_upper} Min. {label_val}'
                        return {
                            'line_value': line_value,
                            'label_short': label_base,
                            'label_long': label_base + ' (MACPAC)',
                            'min_display_str': label_val,  # e.g. "~1.56-2.31" or "~3.42" for state page footer/SEO
                        }
            except Exception:
                continue
    macpac_df = load_csv_data('macpac_state_standards_clean.csv')
    if macpac_df is not None and not macpac_df.empty and 'State_Code' in macpac_df.columns:
        row = macpac_df[macpac_df['State_Code'].str.upper().str.strip() == state_code_upper]
        if not row.empty and 'Min_Staffing' in macpac_df.columns:
            raw = row.iloc[0].get('Min_Staffing', '')
            try:
                v = float(str(raw).replace(' HPRD', '').strip())
                label_val = f'~{round_half_up(v, 2):.2f}'
                label_base = f'{state_code_upper} Min. {label_val}'
                return {'line_value': v, 'label_short': label_base, 'label_long': label_base + ' (MACPAC)', 'min_display_str': label_val}
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

def _provider_charts_chartjs_data(facility_df, state_code, reported_total, reported_rn, reported_lpn, reported_na, case_mix_total, case_mix_rn, case_mix_lpn, case_mix_na, case_mix_index=None, case_mix_index_ratio=None):
    """Build JSON-serializable chart data for Chart.js. Use null (None) for missing; never substitute 0. Order: Total, RN, LPN, Nurse aide."""
    def _round_val(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return round_half_up(float(v), 2)
    out = {}
    out['reportedCaseMix'] = {
        'labels': ['Total', 'RN', 'LPN', 'Nurse aide'],
        'reported': [_round_val(reported_total), _round_val(reported_rn), _round_val(reported_lpn), _round_val(reported_na)],
        'caseMix': None,
        'caseMixIndex': _round_val(case_mix_index),
        'caseMixIndexRatio': _round_val(case_mix_index_ratio),
    }
    if case_mix_total is not None or case_mix_rn is not None or case_mix_lpn is not None or case_mix_na is not None:
        out['reportedCaseMix']['caseMix'] = [
            _round_val(case_mix_total),
            _round_val(case_mix_rn),
            _round_val(case_mix_lpn),
            _round_val(case_mix_na)
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
        macpac_info = get_macpac_chart_info(state_code)
        out['totalHprd'] = {
            'quarters': quarters,
            'total': _series_to_list_with_none(df['Total_Nurse_HPRD']),
            'direct': _series_to_list_with_none(df['Nurse_Care_HPRD'] if 'Nurse_Care_HPRD' in df.columns else pd.Series(dtype=float)),
            'macpac': macpac_info['line_value'] if macpac_info else None,
            'macpacLabelShort': macpac_info['label_short'] if macpac_info else None,
            'macpacLabelLong': macpac_info['label_long'] if macpac_info else None,
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

def _provider_charts_html(chart_data, facility_name='', casemix_title=''):
    """Render all provider charts with Chart.js: bar (Reported vs Case-Mix) + 4 line charts. Title: metric name centered, facility name smaller below.
    casemix_title: heading for the CMS Case-Mix card (e.g. CMS Case-Mix (Q4 2025))."""
    import json
    try:
        data_esc = json.dumps(chart_data).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    except Exception:
        data_esc = '{}'
    # Centered title: desktop = one line "Census: Facility Name"; mobile = title row + facility name row
    facility_esc = html.escape(str(facility_name)) if facility_name else ''
    facility_sub = ('<p class="pbj-chart-facility" style="text-align:center;margin:0.25rem 0 0.75rem 0;font-size:0.85rem;color:#a1a1aa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + facility_esc + '</p>') if facility_esc else ''
    def chart_header(main_title):
        one_line = ('<div class="pbj-chart-header-oneline section-header" style="margin-bottom:0;">' + main_title + ': ' + facility_esc + '</div>') if facility_esc else ('<div class="pbj-chart-header-oneline section-header" style="margin-bottom:0;">' + main_title + '</div>')
        two_line = '<div class="pbj-chart-header-twoline"><div class="section-header" style="margin-bottom:0;">' + main_title + '</div>' + facility_sub + '</div>'
        return '<div class="pbj-chart-header" style="text-align:center;margin-bottom:0.25rem;">' + one_line + two_line + '</div>'
    # One bordered box per chart: title + facility name, canvas, optional footer (e.g. Total Staffing MACPAC note)
    macpac_url = 'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
    total_staffing_footer = '''<p class="pbj-chart-footnote" style="margin:0.5rem 0 0 0;font-size:0.7rem;line-height:1.35;color:#a1a1aa;">
<span class="pbj-chart-footnote-desktop">Direct staff excludes Admin/DON. State minimums via <a href="''' + macpac_url + '''" target="_blank" rel="noopener" style="color:#818cf8;">MACPAC (2022)</a> may reflect calculated HPRD equivalents.</span>
<span class="pbj-chart-footnote-mobile">Direct staff excludes Admin/DON. State minimums via <a href="''' + macpac_url + '''" target="_blank" rel="noopener" style="color:#818cf8;">MACPAC</a> may reflect calculated HPRD equivalents.</span>
</p>'''
    def chart_block(title, canvas_id, footer=''):
        out = '<div class="pbj-chart-container" style="margin-bottom:1.5rem;">' + chart_header(title) + '<div class="pbj-chart-wrapper"><canvas id="' + canvas_id + '"></canvas></div>'
        if footer:
            out += footer
        return out + '</div>'
    return '''
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
''' + chart_block('Total Staffing', 'chartTotalHprd', total_staffing_footer) + '''
<!-- pbj-casemix-ui:13 -->
<div class="pbj-chart-container pbj-casemix-card" data-pbj-casemix-ui="13">
<div class="pbj-casemix-card-head">
  <div class="pbj-casemix-section-header">
    <h2 class="pbj-casemix-section-title">''' + html.escape(str(casemix_title or 'CMS Case-Mix')) + '''</h2>
    <button type="button" class="pbj-casemix-help-trigger" id="pbjCaseMixInfoBtn" aria-label="What is case-mix? Definitions and distributions" title="What is case-mix?">
      <span class="pbj-casemix-help-label">What is case-mix?</span>
    </button>
  </div>
</div>
<div class="pbj-casemix-card-body">
  <div class="pbj-casemix-summary">
    <div class="pbj-casemix-hero">
      <div id="pbjCaseMixHeroBars" class="pbj-casemix-bars"></div>
    </div>
  </div>
  <details class="pbj-casemix-details" id="pbjCaseMixSkillMix">
    <summary><span class="pbj-casemix-sum-wrap"><span class="pbj-casemix-sum-rowlabel">Case-Mix by Position</span></span><span class="pbj-casemix-sum-chev" aria-hidden="true">▼</span></summary>
    <div class="pbj-casemix-details-body">
      <p class="pbj-casemix-interpret pbj-casemix-interpret--breakdown" id="pbjCaseMixBreakdownFlag" hidden></p>
      <div id="pbjCaseMixBreakdownBars" class="pbj-casemix-bars"></div>
    </div>
  </details>
  <p class="pbj-casemix-caveat-foot" id="pbjCaseMixCaveat">CMS case-mix is an acuity metric based on PDPM. It is not a state or federal minimum; the ratio is a reference point, not a measure of whether staffing is sufficient.</p>
</div>
<div class="pbj-casemix-modal" id="pbjCaseMixModal" aria-hidden="true">
  <div class="pbj-casemix-modal-card" role="dialog" aria-modal="true" aria-labelledby="pbjCaseMixModalTitle">
    <button type="button" class="pbj-casemix-modal-close" id="pbjCaseMixModalClose" aria-label="Close">×</button>
    <h3 id="pbjCaseMixModalTitle">Reported vs. CMS case-mix</h3>
    <p><strong>Reported HPRD</strong> comes from PBJ staffing. <strong>CMS case-mix HPRD</strong> is modeled from the facility&rsquo;s resident mix (PDPM) for the same quarter and role.</p>
    <p>The <strong>bar scale is percent of CMS case-mix</strong>: 100% equals the case-mix HPRD for that role. Reported staffing is the filled portion. Case-mix is an acuity benchmark from PDPM, not a state or federal staffing minimum.</p>
    <p style="margin-top:0.45rem;font-size:0.78rem;line-height:1.4;color:#94a3b8;">PBJ user guide (PDF): <a href="https://www.cms.gov/medicare/provider-enrollment-and-certification/certificationandcomplianc/downloads/usersguide.pdf" target="_blank" rel="noopener" style="color:#a5b4fc;">CMS</a>.</p>
  </div>
</div>
<div class="pbj-casemix-modal pbj-casemix-modal--aux" id="pbjCaseMixAuxModal" aria-hidden="true">
  <div class="pbj-casemix-modal-card" role="dialog" aria-modal="true" aria-labelledby="pbjCaseMixAuxModalTitle">
    <button type="button" class="pbj-casemix-modal-close" id="pbjCaseMixAuxModalClose" aria-label="Close">×</button>
    <h3 id="pbjCaseMixAuxModalTitle"></h3>
    <div id="pbjCaseMixAuxModalBody" class="pbj-casemix-aux-body"></div>
  </div>
</div>
</div>
''' + chart_block('RN Staffing', 'chartRN') + '''
''' + chart_block('Census', 'chartCensus') + '''
''' + chart_block('Contract Staff %', 'chartContract') + '''
<script>
(function(){
  var d = ''' + data_esc + ''';
  var textColor = 'rgba(228, 228, 231, 0.95)';
  var gridColor = 'rgba(100, 116, 139, 0.38)';
  var axisColor = 'rgba(148, 163, 184, 0.58)';
  if (typeof Chart !== 'undefined') { Chart.defaults.color = textColor; Chart.defaults.borderColor = axisColor; }
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
    return function(value, index, ticks) {
      var d = new Date(value);
      if (showQuarters) {
        var yq = d.getFullYear();
        var q = Math.floor(d.getMonth() / 3) + 1;
        return yq + ' Q' + q;
      }
      // Year-only: show the calendar year when it advances vs the previous tick (no Jan-1-only filter).
      var y = d.getFullYear();
      if (typeof index !== 'number' || index === 0) return '' + y;
      if (!ticks || !ticks[index - 1]) return '';
      var prevY = ticks[index - 1].value != null ? new Date(ticks[index - 1].value).getFullYear() : null;
      if (prevY !== y) return '' + y;
      return '';
    };
  }
  function hprd(v) {
    return (v == null || isNaN(v)) ? '—' : Number(v).toFixed(2);
  }
  function fmtInt(n) {
    if (n == null || n === '' || isNaN(Number(n))) return String(n);
    return Number(n).toLocaleString('en-US');
  }
  function stateTierClass(val, p25, p75) {
    if (val == null || isNaN(val) || p25 == null || p75 == null) return 'pbj-cmi-tier--mid';
    var v = Number(val);
    if (v < Number(p25)) return 'pbj-cmi-tier--low';
    if (v > Number(p75)) return 'pbj-cmi-tier--high';
    return 'pbj-cmi-tier--mid';
  }
  function escHtml(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function ordinalEn(n) {
    if (n == null || isNaN(n)) return '';
    var x = Math.floor(Number(n));
    var v = x % 100;
    if (v >= 11 && v <= 13) return x + 'th';
    switch (x % 10) {
      case 1: return x + 'st';
      case 2: return x + 'nd';
      case 3: return x + 'rd';
      default: return x + 'th';
    }
  }
  function possessiveNameHtml(name) {
    var t = String(name || '').trim();
    if (!t) return 'This facility&#8217;s';
    return escHtml(t) + '&#8217;s';
  }
  function caseMixModalFootnote() {
    return '<p style="margin-top:0.5rem;font-size:0.78rem;line-height:1.4;color:#94a3b8;">Case-mix is context, not a staffing minimum. It does not determine whether staffing is sufficient.</p>';
  }
  function cmiModalBodyHtml(val, rc) {
    if (val == null || isNaN(Number(val))) return '<p>Not available.</p>';
    var v = Number(val).toFixed(2);
    var fn = rc && rc.facilityName ? String(rc.facilityName).trim() : '';
    var stRef = rc && rc.cmiStateRef;
    var stateNm = (stRef && stRef.stateDisplayName) ? String(stRef.stateDisplayName) : ((d.totalHprd && d.totalHprd.stateCode) ? String(d.totalHprd.stateCode) : 'this state');
    var pct = stRef ? stRef.facilityCmiPercentile : null;
    var p1 = '<p>Case-Mix Index is a CMS acuity metric based on PDPM resident data. Higher values mean residents are modeled as needing more nursing care.</p>';
    var p2;
    if (pct != null && !isNaN(pct) && stateNm) {
      p2 = '<p>' + possessiveNameHtml(fn) + ' Case-Mix Index is <strong>' + v + '</strong>, placing it in the <strong>' + ordinalEn(pct) + '</strong> percentile among ' + escHtml(stateNm) + ' facilities this quarter.</p>';
    } else {
      p2 = '<p>' + possessiveNameHtml(fn) + ' Case-Mix Index is <strong>' + v + '</strong>. State percentile is not available for this quarter.</p>';
    }
    var p3 = '';
    if (pct != null && !isNaN(pct)) {
      if (pct >= 75) p3 = '<p>This suggests the facility&#8217;s residents are modeled as more nursing-intensive than most ' + escHtml(stateNm) + ' facilities.</p>';
      else if (pct > 25 && pct < 75) p3 = '<p>This suggests the facility&#8217;s resident acuity is near the middle of ' + escHtml(stateNm) + ' facilities.</p>';
      else if (pct <= 25) p3 = '<p>This suggests the facility&#8217;s residents are modeled as less nursing-intensive than most ' + escHtml(stateNm) + ' facilities.</p>';
    }
    return p1 + p2 + p3 + caseMixModalFootnote();
  }
  function ratioModalBodyHtml(val, rc) {
    if (val == null || isNaN(Number(val))) return '<p>Not available.</p>';
    var v = Number(val).toFixed(2);
    var r = Number(val);
    var fn = rc && rc.facilityName ? String(rc.facilityName).trim() : '';
    var stRef = rc && rc.cmiStateRef;
    var stateNm = (stRef && stRef.stateDisplayName) ? String(stRef.stateDisplayName) : ((d.totalHprd && d.totalHprd.stateCode) ? String(d.totalHprd.stateCode) : 'this state');
    var pct = stRef ? stRef.facilityRatioPercentile : null;
    var p1 = '<p>Case-Mix Index Ratio compares a facility&#8217;s nursing case-mix acuity to the national average. Values above 1.00 mean residents are modeled as needing more nursing care than the national average; values below 1.00 mean less than the national average.</p>';
    var p2;
    if (pct != null && !isNaN(pct) && stateNm) {
      p2 = '<p>' + possessiveNameHtml(fn) + ' Case-Mix Index Ratio is <strong>' + v + '</strong>, placing it in the <strong>' + ordinalEn(pct) + '</strong> percentile among ' + escHtml(stateNm) + ' facilities this quarter.</p>';
    } else {
      p2 = '<p>' + possessiveNameHtml(fn) + ' Case-Mix Index Ratio is <strong>' + v + '</strong>. State percentile is not available for this quarter.</p>';
    }
    var p3 = '';
    if (r >= 1.05) {
      p3 = '<p>This means the facility&#8217;s residents are modeled as more nursing-intensive than the national average and higher than most ' + escHtml(stateNm) + ' facilities.</p>';
    } else if (r > 0.95 && r < 1.05) {
      if (pct != null && !isNaN(pct) && pct >= 75) {
        p3 = '<p>This means the facility is roughly in line with the national average, but its residents are modeled as more nursing-intensive than most ' + escHtml(stateNm) + ' facilities.</p>';
      } else {
        p3 = '<p>This means the facility is roughly in line with the national average, while its state percentile shows how it compares with other ' + escHtml(stateNm) + ' facilities.</p>';
      }
    } else {
      p3 = '<p>This means the facility&#8217;s residents are modeled as less nursing-intensive than the national average, though its state percentile may still be high or low depending on ' + escHtml(stateNm) + '&#8217;s facility mix.</p>';
    }
    return p1 + p2 + p3 + caseMixModalFootnote();
  }
  function openCaseMixAuxModal(title, htmlBody) {
    var auxM = document.getElementById('pbjCaseMixAuxModal');
    var mainM = document.getElementById('pbjCaseMixModal');
    var tEl = document.getElementById('pbjCaseMixAuxModalTitle');
    var bEl = document.getElementById('pbjCaseMixAuxModalBody');
    if (!auxM || !tEl || !bEl) return;
    if (mainM) mainM.setAttribute('aria-hidden', 'true');
    tEl.textContent = title || '';
    bEl.innerHTML = htmlBody || '';
    auxM.setAttribute('aria-hidden', 'false');
  }
  function closeCaseMixAuxModal() {
    var auxM = document.getElementById('pbjCaseMixAuxModal');
    if (auxM) auxM.setAttribute('aria-hidden', 'true');
  }
  function renderCaseMixCmiStrip(rc) {
    var host = document.getElementById('pbjCaseMixCmiStrip');
    if (!host) return;
    host.innerHTML = '';
    host.hidden = true;
    if (!rc) return;
    var cmi = rc.caseMixIndex, rat = rc.caseMixIndexRatio;
    var hasCmi = cmi != null && !isNaN(cmi);
    var hasRat = rat != null && !isNaN(rat);
    if (!hasCmi && !hasRat) return;
    host.hidden = false;
    var stRef = rc.cmiStateRef || null;
    function addChip(label, valStr, tierClass, title, bodyFn) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'pbj-casemix-cmi-trigger ' + (tierClass || 'pbj-cmi-tier--mid');
      btn.setAttribute('aria-haspopup', 'dialog');
      btn.setAttribute('aria-controls', 'pbjCaseMixAuxModal');
      var k = document.createElement('span'); k.className = 'k'; k.textContent = label;
      var vv = document.createElement('span'); vv.className = 'v'; vv.textContent = valStr;
      btn.appendChild(k); btn.appendChild(document.createTextNode(' ')); btn.appendChild(vv);
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        openCaseMixAuxModal(title, bodyFn());
      });
      host.appendChild(btn);
    }
    if (hasCmi) {
      var tc = stRef ? stateTierClass(cmi, stRef.cmiP25, stRef.cmiP75) : 'pbj-cmi-tier--mid';
      addChip('CMI', Number(cmi).toFixed(2), tc, 'Case-Mix Index', function() { return cmiModalBodyHtml(cmi, rc); });
    }
    if (hasRat) {
      var tr = stRef ? stateTierClass(rat, stRef.ratioP25, stRef.ratioP75) : 'pbj-cmi-tier--mid';
      addChip('CMI ratio', Number(rat).toFixed(2), tr, 'Case-Mix Index Ratio', function() { return ratioModalBodyHtml(rat, rc); });
    }
  }
  function severityClassFromRatio(ratio) {
    if (ratio == null || isNaN(ratio)) return 'pbj-casemix-sev-neutral';
    if (ratio >= 1) return 'pbj-casemix-sev-meets';
    if (ratio >= 0.9) return 'pbj-casemix-sev-neutral';
    if (ratio >= 0.75) return 'pbj-casemix-sev-warn';
    return 'pbj-casemix-sev-critical';
  }
  function appendCaseMixPctBar(parent, actual, caseMix, compact) {
    if (caseMix == null || isNaN(caseMix) || Number(caseMix) <= 0 || actual == null || isNaN(actual)) return;
    var rep = Number(actual);
    var cm = Number(caseMix);
    var ratio = rep / cm;
    var pctOf = ratio * 100;
    var scaleMax = Math.max(rep, cm, 0.01);
    var repW = Math.max(0, Math.min(100, (rep / scaleMax) * 100));
    var benchW = Math.max(0, Math.min(100, (cm / scaleMax) * 100));
    var sev = '';
    if (ratio < 0.75) sev = ' pbj-casemix-sev-critical';
    else if (ratio < 0.9) sev = ' pbj-casemix-sev-warn';
    var isOver = rep >= cm - 0.0001;
    var wrap = document.createElement('div');
    wrap.className = 'pbj-casemix-pct-bar' + (compact ? ' pbj-casemix-pct-bar--compact' : '');
    var track = document.createElement('div');
    track.className = 'pbj-casemix-pct-track' + (isOver ? ' pbj-casemix-pct-track--over' : ' pbj-casemix-pct-track--under');
    track.setAttribute('role', 'img');
    track.setAttribute('aria-label', 'Reported ' + hprd(rep) + ' HPRD (' + Math.round(pctOf) + '% of CMS case-mix ' + hprd(cm) + ' HPRD)');
    track.title = 'Reported ' + hprd(rep) + ' HPRD · CMS case-mix ' + hprd(cm) + ' HPRD (' + Math.round(pctOf) + '%)';
    if (isOver) {
      var toBench = document.createElement('div');
      toBench.className = 'pbj-casemix-pct-fill pbj-casemix-pct-fill--to-bench';
      toBench.style.width = benchW.toFixed(2) + '%';
      toBench.title = 'Reported through CMS case-mix (' + hprd(cm) + ' HPRD)';
      track.appendChild(toBench);
      if (repW > benchW + 0.35) {
        var over = document.createElement('div');
        over.className = 'pbj-casemix-pct-fill pbj-casemix-pct-fill--over';
        over.style.left = benchW.toFixed(2) + '%';
        over.style.width = (repW - benchW).toFixed(2) + '%';
        over.title = 'Above CMS case-mix (+' + hprd(rep - cm) + ' HPRD)';
        track.appendChild(over);
      }
    } else {
      var under = document.createElement('div');
      under.className = 'pbj-casemix-pct-fill pbj-casemix-pct-fill--under' + sev;
      under.style.width = repW.toFixed(2) + '%';
      under.title = 'Reported ' + hprd(rep) + ' HPRD (' + Math.round(pctOf) + '% of case-mix)';
      track.appendChild(under);
    }
    if (benchW > 0.5) {
      var bench = document.createElement('div');
      bench.className = 'pbj-casemix-pct-bench';
      var benchLeft = isOver ? benchW : Math.min(benchW, 99.6);
      bench.style.left = benchLeft.toFixed(2) + '%';
      bench.title = 'CMS case-mix ' + hprd(cm) + ' HPRD';
      track.appendChild(bench);
    }
    wrap.appendChild(track);
    parent.appendChild(wrap);
  }
  function renderCaseMixHero(actual, caseMix) {
    var panel = document.createElement('div');
    panel.className = 'pbj-casemix-hero-panel';
    if (actual == null || isNaN(actual)) {
      panel.innerHTML = '<p class="pbj-casemix-hero-line"><span class="tag">Total</span><span class="secondary">Reported HPRD not available.</span></p>';
      return panel;
    }
    var hasCaseMix = caseMix != null && !isNaN(caseMix) && Number(caseMix) > 0;
    var line = document.createElement('p');
    line.className = 'pbj-casemix-hero-line';
    if (hasCaseMix) {
      var ratio = Number(actual) / Number(caseMix);
      var pct = Math.round(100 * ratio);
      var pctHtml = ratio < 0.9 ? '<span class="pct-em pct--low">' + pct + '%</span>' : ('<span class="pct-em">' + pct + '%</span>');
      var compact = typeof window !== 'undefined' && window.innerWidth <= 768;
      if (compact) {
        line.innerHTML = '<span class="tag">Total ratio</span> ' + pctHtml + ' <span class="secondary">(' + hprd(actual) + ' / ' + hprd(caseMix) + ' CMS)</span>';
      } else {
        line.innerHTML = '<span class="tag">Total case-mix ratio:</span> ' + pctHtml + ' <span class="secondary">(' + hprd(actual) + ' reported, ' + hprd(caseMix) + ' CMS case-mix)</span>';
      }
    } else {
      line.innerHTML = '<span class="tag">Total</span><span class="primary">' + hprd(actual) + ' HPRD reported</span>';
    }
    panel.appendChild(line);
    var main = document.createElement('div');
    main.className = 'pbj-casemix-hero-main';
    var copy = document.createElement('div');
    copy.className = 'pbj-casemix-hero-copy';
    if (hasCaseMix) appendCaseMixPctBar(copy, actual, caseMix, false);
    var cmiHost = document.createElement('div');
    cmiHost.id = 'pbjCaseMixCmiStrip';
    cmiHost.className = 'pbj-casemix-cmi-strip pbj-casemix-hero-cmi-col';
    cmiHost.setAttribute('hidden', '');
    main.appendChild(copy);
    main.appendChild(cmiHost);
    panel.appendChild(main);
    return panel;
  }
  function renderCaseMixBreakdownRow(label, actual, caseMix, maxScale) {
    var titles = { 'RN': 'RN', 'LPN': 'LPN', 'Aide': 'Nurse aide' };
    var wrap = document.createElement('div');
    var roleClass = (label === 'RN') ? ' pbj-casemix-metric--rn' : (label === 'LPN' ? ' pbj-casemix-metric--lpn' : (label === 'Aide' ? ' pbj-casemix-metric--aide' : ''));
    wrap.className = 'pbj-casemix-breakdown-row' + roleClass;
    if (actual == null || isNaN(actual)) {
      wrap.innerHTML = '<div class="pbj-casemix-sub-line"><span class="pbj-casemix-sub-label">' + (titles[label] || label) + '</span><span class="pbj-casemix-sub-vals">—</span></div>';
      return wrap;
    }
    var hasCaseMix = caseMix != null && !isNaN(caseMix) && Number(caseMix) > 0;
    var main = document.createElement('div');
    main.className = 'pbj-casemix-breakdown-main';
    var row = document.createElement('div');
    row.className = 'pbj-casemix-sub-line';
    var lab = document.createElement('span');
    lab.className = 'pbj-casemix-sub-label' + (label === 'RN' ? ' rn' : '');
    var roleLbl = (titles[label] || label);
    var compact = typeof window !== 'undefined' && window.innerWidth <= 768;
    if (hasCaseMix) {
      var pct2 = Math.round(100 * Number(actual) / Number(caseMix));
      var pctCls = pct2 < 90 ? 'pct-em pct--low' : 'pct-em';
      var hprdPair = ' <span class="secondary">(' + hprd(actual) + ' HPRD / ' + hprd(caseMix) + ' Case-Mix)</span>';
      lab.innerHTML = roleLbl + ' case-mix ratio: <span class="' + pctCls + '">' + pct2 + '%</span>' + (compact ? hprdPair : '');
    } else {
      lab.textContent = roleLbl + ' staffing' + (compact ? ' (' + hprd(actual) + ' HPRD reported)' : '');
    }
    row.appendChild(lab);
    main.appendChild(row);
    if (hasCaseMix) appendCaseMixPctBar(main, actual, caseMix, true);
    wrap.appendChild(main);
    if (hasCaseMix && !compact) {
      var aside = document.createElement('span');
      aside.className = 'pbj-casemix-breakdown-aside';
      aside.innerHTML = '<span class="h">' + hprd(actual) + '</span> ' + roleLbl + ' HPRD, <span class="h">' + hprd(caseMix) + '</span> ' + roleLbl + ' case-mix HPRD';
      wrap.appendChild(aside);
    } else if (!hasCaseMix && !compact) {
      var asideNa = document.createElement('span');
      asideNa.className = 'pbj-casemix-breakdown-aside';
      asideNa.textContent = hprd(actual) + ' HPRD reported';
      wrap.appendChild(asideNa);
    }
    if (label === 'RN' && hasCaseMix && Number(actual) / Number(caseMix) < 0.75) wrap.classList.add('pbj-casemix-metric--shortfall');
    return wrap;
  }
  function buildCaseMixFlagText(rc) {
    if (!rc || !rc.reported) return '';
    var r = rc.reported, c = rc.caseMix || [];
    function materiallyBelow(idx) {
      if (!c[idx] || isNaN(c[idx]) || Number(c[idx]) <= 0 || r[idx] == null || isNaN(r[idx])) return false;
      var pct = 100 * Number(r[idx]) / Number(c[idx]);
      return pct < 75;
    }
    var rnMat = materiallyBelow(1);
    var totMat = materiallyBelow(0);
    if (!rnMat && !totMat) return '';
    if (rnMat && totMat) return 'RN and total nurse staffing are materially below CMS case-mix hours this quarter.';
    if (rnMat) return 'RN staffing is materially below CMS case-mix hours this quarter.';
    return 'Total nurse staffing is materially below CMS case-mix hours this quarter.';
  }
  function makeLineTime(id, quarters, datasets, yTitle, quartersRef) {
    var ctx = document.getElementById(id);
    if (!ctx || !quarters || !quarters.length) return;
    var spanYears = getSpanYears(quarters);
    var maxTicks = window.innerWidth < 768 ? Math.min(12, Math.max(6, Math.ceil(spanYears) + 1)) : Math.min(15, Math.max(6, Math.ceil(spanYears) + 2));
    var timeDatasets = datasets.map(function(ds) {
      var data = buildTimeSeriesData(quarters, ds.data);
      var out = { label: ds.label, borderColor: ds.borderColor, borderDash: ds.borderDash, tension: ds.tension !== undefined ? ds.tension : 0.3, fill: false, spanGaps: false, data: data };
      if (ds.borderWidth != null) out.borderWidth = ds.borderWidth;
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
            label: function(context) {
              if (context.dataset && context.dataset._macpacNote) return context.dataset.label;
              var v = context.parsed.y;
              if (typeof v === 'number' && !isNaN(v)) return context.dataset.label + ': ' + (Math.round(v * 100) / 100).toFixed(2);
              return context.dataset.label + ': ' + (v != null ? v : '');
            },
            afterBody: function(context) { return []; }
          }
        }
      },
      scales: {
        y: { beginAtZero: false, ticks: { color: textColor }, grid: { color: gridColor }, border: { color: axisColor, width: 1 }, title: { display: !!yTitle, text: yTitle || '', color: textColor } },
        x: {
          type: 'time',
          time: { unit: 'quarter', displayFormats: { year: 'yyyy', quarter: 'yyyy Qq', month: 'MMM yyyy' }, tooltipFormat: 'yyyy Qq' },
          ticks: { color: textColor, maxTicksLimit: maxTicks, autoSkip: true, font: { size: 11 }, callback: timeTickCallback(quartersRef || quarters) },
          grid: { color: gridColor },
          border: { color: axisColor, width: 1 }
        }
      }
    };
    new Chart(ctx.getContext('2d'), { type: 'line', data: { datasets: timeDatasets }, options: opts });
  }
  var rc = d.reportedCaseMix;
  var heroWrap = document.getElementById('pbjCaseMixHeroBars');
  var breakdownWrap = document.getElementById('pbjCaseMixBreakdownBars');
  if (heroWrap) heroWrap.innerHTML = '';
  if (breakdownWrap) breakdownWrap.innerHTML = '';
  if (rc && rc.reported && rc.reported.length >= 4) {
    var reportedAll = rc.reported;
    var caseMixAll = (rc.caseMix && rc.caseMix.length >= 4) ? rc.caseMix : [null, null, null, null];
    var totalMax = Math.max(caseMixAll[0] || 0, reportedAll[0] || 0, 0.1);
    var breakdownVals = [caseMixAll[1], caseMixAll[2], caseMixAll[3], reportedAll[1], reportedAll[2], reportedAll[3]].filter(function(v){ return v != null && !isNaN(v); });
    var breakdownMax = breakdownVals.length ? Math.max.apply(null, breakdownVals) : totalMax;
    if (heroWrap) heroWrap.appendChild(renderCaseMixHero(reportedAll[0], caseMixAll[0]));
    if (breakdownWrap) {
      breakdownWrap.appendChild(renderCaseMixBreakdownRow('RN', reportedAll[1], caseMixAll[1], breakdownMax));
      breakdownWrap.appendChild(renderCaseMixBreakdownRow('LPN', reportedAll[2], caseMixAll[2], breakdownMax));
      breakdownWrap.appendChild(renderCaseMixBreakdownRow('Aide', reportedAll[3], caseMixAll[3], breakdownMax));
    }
  }
  var flagEl = document.getElementById('pbjCaseMixBreakdownFlag');
  var skillMixDetails = document.getElementById('pbjCaseMixSkillMix');
  var flagTxt = (rc && rc.reported && rc.reported.length >= 4) ? buildCaseMixFlagText(rc) : '';
  function syncCaseMixBreakdownFlag() {
    if (!flagEl) return;
    var open = skillMixDetails && skillMixDetails.open;
    if (open && flagTxt) {
      flagEl.textContent = flagTxt;
      flagEl.className = 'pbj-casemix-interpret pbj-casemix-interpret--breakdown pbj-casemix-flag-line';
      flagEl.hidden = false;
    } else {
      flagEl.textContent = '';
      flagEl.className = 'pbj-casemix-interpret pbj-casemix-interpret--breakdown';
      flagEl.hidden = true;
    }
  }
  syncCaseMixBreakdownFlag();
  if (skillMixDetails) skillMixDetails.addEventListener('toggle', syncCaseMixBreakdownFlag);
  renderCaseMixCmiStrip(rc);
  var modal = document.getElementById('pbjCaseMixModal');
  var auxModal = document.getElementById('pbjCaseMixAuxModal');
  var modalBtn = document.getElementById('pbjCaseMixInfoBtn');
  var modalClose = document.getElementById('pbjCaseMixModalClose');
  var auxModalClose = document.getElementById('pbjCaseMixAuxModalClose');
  function closeCaseMixModal() { if (modal) modal.setAttribute('aria-hidden', 'true'); }
  if (modalBtn && modal) modalBtn.addEventListener('click', function(){ closeCaseMixAuxModal(); modal.setAttribute('aria-hidden', 'false'); });
  if (modalClose) modalClose.addEventListener('click', closeCaseMixModal);
  if (auxModalClose) auxModalClose.addEventListener('click', closeCaseMixAuxModal);
  if (modal) {
    modal.addEventListener('click', function(e){ if (e.target === modal) closeCaseMixModal(); });
  }
  if (auxModal) {
    auxModal.addEventListener('click', function(e){ if (e.target === auxModal) closeCaseMixAuxModal(); });
  }
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Escape') return;
    if (auxModal && auxModal.getAttribute('aria-hidden') === 'false') { closeCaseMixAuxModal(); return; }
    if (modal && modal.getAttribute('aria-hidden') === 'false') closeCaseMixModal();
  });
  var th = d.totalHprd;
  if (th && th.quarters && th.quarters.length) {
    var ds = [{ label: 'Total', data: th.total, borderColor: '#2dd4bf', tension: 0.3, fill: false, spanGaps: false },
               { label: 'Direct', data: th.direct, borderColor: 'rgba(161,161,170,0.9)', borderDash: [6, 4], tension: 0.3, fill: false, spanGaps: false }];
    if (th.macpac != null && typeof th.macpac === 'number') {
      var macpacArr = th.quarters.map(function(){ return th.macpac; });
      var stateMinLabel = (th.macpacLabelLong && th.macpacLabelShort) ? (window.innerWidth >= 640 ? th.macpacLabelLong : th.macpacLabelShort) : ((th.stateCode || 'State') + ' Min: ~' + (Math.round(Number(th.macpac) * 100) / 100).toFixed(2) + ' (MACPAC)');
      ds.push({ label: stateMinLabel, data: macpacArr, borderColor: 'rgba(248, 113, 113, 0.95)', borderWidth: 2, borderDash: [6, 4], tension: 0, fill: false, spanGaps: false, _macpacNote: true });
    }
    makeLineTime('chartTotalHprd', th.quarters, ds, 'Hours per resident day', th.quarters);
  }
  var rn = d.rnHprd;
  if (rn && rn.quarters && rn.quarters.length) makeLineTime('chartRN', rn.quarters, [
    { label: 'Total RN', data: rn.rn, borderColor: '#2dd4bf', tension: 0.3, fill: false, spanGaps: false },
    { label: 'RN (excl. Admin/DON)', data: rn.rnDirect, borderColor: 'rgba(161,161,170,0.9)', borderDash: [6, 4], tension: 0.3, fill: false, spanGaps: false }
  ], 'Hours per resident day', rn.quarters);
  var ce = d.census;
  if (ce && ce.quarters && ce.quarters.length) makeLineTime('chartCensus', ce.quarters, [{ label: 'Avg daily census', data: ce.census, borderColor: '#2dd4bf', tension: 0.3, fill: false, spanGaps: false }], 'Census', ce.quarters);
  var co = d.contract;
  if (co && co.quarters && co.quarters.length) {
    var cds = [{ label: '% Contract Staff', data: co.facility, borderColor: '#2dd4bf', tension: 0.3, fill: false, spanGaps: false }];
    makeLineTime('chartContract', co.quarters, cds, 'Contract %', co.quarters);
  }
})();
</script>'''

def _provider_certified_beds(provider_info_row):
    """Certified beds from provider info when available."""
    if not isinstance(provider_info_row, dict):
        return None
    for key in (
        'number_of_certified_beds',
        'certified_beds',
        'Number of Certified Beds',
        'number_of_certified_beds',
    ):
        v = provider_info_row.get(key)
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            try:
                n = int(float(v))
                if n > 0:
                    return n
            except (TypeError, ValueError):
                if str(v).strip():
                    return str(v).strip()
    return None


def _provider_ai_facility_snapshot_context(
    pi_metrics: dict | None,
    *,
    census_int: int | None = None,
    certified_beds=None,
    ownership_short: str = '',
    cms_overall_line: str = '',
    cms_staffing_line: str = '',
) -> str:
    """Care Compare / provider snapshot lines for AI context (census scale, ownership, SFF, abuse, stars)."""
    pi = dict(pi_metrics or {})
    lines: list[str] = []

    def _census_band(n: int) -> str:
        if n < 70:
            return (
                'informal “smaller” census band for reader context (this page: under ~70 avg residents/day in the '
                'displayed quarter — not a regulatory size class)'
            )
        if n < 125:
            return (
                'informal “mid-sized” census band (~70–124 avg residents/day this quarter — not a regulatory size class)'
            )
        return (
            'informal “larger” census band (~125+ avg residents/day this quarter — not a regulatory size class)'
        )

    if census_int is not None and int(census_int) > 0:
        n = int(census_int)
        lines.append(
            f'Reported average daily census (displayed quarter, from same provider/census fields used on this page): '
            f'~{n:,} residents/day — {_census_band(n)}.'
        )
    beds_disp = ''
    if certified_beds is not None:
        try:
            bn = int(float(str(certified_beds).replace(',', '')))
            if bn > 0:
                beds_disp = f'{bn:,}'
        except (TypeError, ValueError):
            s = str(certified_beds).strip()
            if s:
                beds_disp = s
    if beds_disp and not census_int:
        lines.append(f'Certified beds (Care Compare / provider field on this page): {beds_disp}')
    elif beds_disp and census_int:
        lines.append(f'Certified beds (Care Compare / provider field on this page): {beds_disp} (compare to census above).')

    ot = (ownership_short or str(pi.get('ownership_type') or '')).strip()
    if ot:
        lines.append(f'Ownership type (Care Compare / provider field echoed on page): {ot}')

    sff = str(pi.get('sff_status') or '').strip()
    if sff:
        lines.append(f'CMS Special Focus / survey status (Care Compare field on this page): {sff}')

    ab = str(pi.get('abuse_icon') or '').strip().upper()
    ha = str(pi.get('has_abuse_icon') or '').strip().upper()
    abuse_yes = ab in ('Y', 'YES', '1', 'TRUE') or ha in ('Y', 'YES', '1', 'TRUE')
    if abuse_yes:
        lines.append(
            'CMS abuse icon (Care Compare): flagged yes on this snapshot — confirm on live Care Compare before asserting to a resident or regulator.'
        )
    elif ab in ('N', 'NO', '0', 'FALSE') or ha in ('N', 'NO', '0', 'FALSE'):
        lines.append('CMS abuse icon (Care Compare): not flagged yes on this snapshot (re-check live Care Compare if timing-sensitive).')

    if (cms_overall_line or '').strip():
        lines.append((cms_overall_line or '').strip())
    if (cms_staffing_line or '').strip():
        lines.append((cms_staffing_line or '').strip())

    return '\n'.join(lines).strip()


def _cms_risk_screening_line_for_ai(
    *,
    risk_reason: str = '',
    risk_flag: int = 0,
    is_sff: bool = False,
    is_sff_candidate: bool = False,
    pi_metrics: dict | None = None,
    overall_rating_raw=None,
    staffing_rating_raw=None,
) -> str:
    """PBJ320 screening flags for AI context (Care Compare fields + PBJ320 high-risk badge)."""
    flags: list[str] = []
    pi = dict(pi_metrics or {})

    sff = str(pi.get('sff_status') or '').strip()
    if sff:
        flags.append(f'SFF status (Care Compare on page): {sff}')
    elif is_sff_candidate:
        flags.append('SFF Candidate (PBJ320 SFF list)')
    elif is_sff:
        flags.append('Special Focus Facility (PBJ320 SFF list)')

    ab = str(pi.get('abuse_icon') or '').strip().upper()
    ha = str(pi.get('has_abuse_icon') or '').strip().upper()
    if ab in ('Y', 'YES', '1', 'TRUE') or ha in ('Y', 'YES', '1', 'TRUE'):
        flags.append('Abuse icon (Care Compare on page): flagged yes')

    rr = (risk_reason or '').strip()
    if rr:
        flags.append(f'PBJ320 high-risk badge: {_sort_risk_reason_display(rr)}')
    elif risk_flag:
        flags.append('PBJ320 high-risk badge: shown on page')

    def _star_n(raw):
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return None
        try:
            n = int(round_half_up(float(raw), 0))
            if n is not None and 1 <= n <= 5:
                return n
        except (TypeError, ValueError):
            return None
        return None

    on = _star_n(overall_rating_raw)
    if on == 1:
        flags.append('Overall Five-Star (Care Compare on page): 1')
    sn = _star_n(staffing_rating_raw)
    if sn == 1:
        flags.append('Staffing Five-Star (Care Compare on page): 1')

    if not flags:
        return ''
    sff_note = (
        ' Star ratings may be omitted on the page for some SFFs — do not invent ratings.'
        if (sff or is_sff or is_sff_candidate) and on is None and sn is None
        else ''
    )
    return (
        'PBJ320 screening flags on this page (mention briefly early; PBJ staffing stays primary; '
        'screening signals from Care Compare / PBJ320 rules — not proof of harm or violations): '
        + '; '.join(flags)
        + '.'
        + sff_note
    )


def _state_total_nurse_hprd_for_quarter(state_code, q_raw):
    """State average/metric total nurse HPRD for a CY_Qtr from state_quarterly_metrics."""
    if not HAS_PANDAS or not state_code or not q_raw:
        return None
    try:
        state_df = load_csv_data('state_quarterly_metrics.csv')
        if state_df is None or state_df.empty:
            return None
        if 'STATE' not in state_df.columns or 'CY_Qtr' not in state_df.columns:
            return None
        if 'Total_Nurse_HPRD' not in state_df.columns:
            return None
        state_df = state_df.copy()
        state_df['STATE'] = state_df['STATE'].astype(str).str.strip().str.upper()
        match = state_df[
            (state_df['STATE'] == str(state_code).strip().upper()[:2])
            & (state_df['CY_Qtr'].astype(str) == str(q_raw))
        ]
        if match.empty:
            return None
        v = match.iloc[0].get('Total_Nurse_HPRD')
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None


def _lpn_hprd_from_facility_quarterly_row(row) -> float | None:
    """Reported LPN HPRD from a facility_quarterly_metrics row only (no Provider Info).

    When ``LPN_HPRD`` is present on ``facility_quarterly_metrics.csv`` rows, this reads it first.
    If the CSV includes an explicit ``LPN_HPRD`` column with a numeric value, use it.
    Otherwise derive the same residual used in ``pbj-wrapped`` (BasicsCard):
    ``max(0, Total_Nurse_HPRD - RN_HPRD - Nurse_Assistant_HPRD)``, which bundles any
    nurse hours not split out as RN or nurse aide in this extract (often includes LPN).
    """
    import math

    def _is_na(v) -> bool:
        if v is None:
            return True
        return isinstance(v, float) and math.isnan(v)

    if row is None:
        return None
    try:
        idx = row.index
    except AttributeError:
        idx = row.keys() if hasattr(row, 'keys') else []
    if 'LPN_HPRD' in idx:
        v = row.get('LPN_HPRD') if hasattr(row, 'get') else row['LPN_HPRD']
        if v is not None and not _is_na(v):
            try:
                out = float(v)
                if out >= 0:
                    return out
            except (TypeError, ValueError):
                pass

    def _cell(key: str) -> float | None:
        if key not in idx:
            return None
        v = row.get(key) if hasattr(row, 'get') else row[key]
        if _is_na(v):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    total = _cell('Total_Nurse_HPRD')
    rn = _cell('RN_HPRD')
    na = _cell('Nurse_Assistant_HPRD')
    if total is None or rn is None or na is None:
        return None
    return max(0.0, total - rn - na)


def _facility_quarterly_census_display(row, pi_q, format_metric_value):
    """Average daily census for a facility quarter (PBJ quarterly metrics or provider info)."""
    col = 'avg_daily_census' if 'avg_daily_census' in row.index else 'Avg_Daily_Census'
    v = row.get(col) if col in row.index else None
    if v is None or (isinstance(v, float) and pd.isna(v)):
        v = (pi_q or {}).get('avg_residents_per_day')
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return format_metric_value(float(v), 'avg_daily_census')
    except (TypeError, ValueError):
        return None


def _build_facility_snapshot_csv_rows(
    prov,
    facility_df,
    facility_name,
    state_code,
    state_name,
    city,
    base_url,
    format_metric_value,
    format_quarter_display,
    ownership_type,
    fallback_latest_provider_row,
):
    """One CSV row per quarter — full SNAPSHOT_CSV_COLUMNS for longitudinal uploads."""
    rows = []
    if facility_df is None or facility_df.empty or not HAS_PANDAS:
        return rows
    page_url = f'{base_url}/provider/{prov}'
    st_label = state_name or state_code or ''
    state_slice = _state_facility_metrics_slice_for_percentiles(state_code) if state_code else None
    try:
        sorted_df = facility_df.sort_values('CY_Qtr')
    except Exception:
        sorted_df = facility_df
    for _, row in sorted_df.iterrows():
        q_raw = str(row.get('CY_Qtr', '') or '').strip()
        if not q_raw:
            continue
        q_disp = format_quarter_display(q_raw)
        pi_q = get_provider_info_for_quarter(prov, q_raw) or {}

        def _row_float(key, pi_key=None):
            v = row.get(key) if key in row.index else None
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = pi_q.get(pi_key or key)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        rt = _row_float('Total_Nurse_HPRD', 'reported_total_nurse_hrs_per_resident_per_day')
        rn = _row_float('RN_HPRD', 'reported_rn_hrs_per_resident_per_day')
        lpn = _lpn_hprd_from_facility_quarterly_row(row)
        na = _row_float('Nurse_Assistant_HPRD', 'reported_na_hrs_per_resident_per_day')
        cmi = _row_float('nursing_case_mix_index')
        if cmi is None:
            v = pi_q.get('nursing_case_mix_index')
            try:
                cmi = float(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            except (TypeError, ValueError):
                cmi = None
        cmir = _row_float('nursing_case_mix_index_ratio')
        if cmir is None:
            v = pi_q.get('nursing_case_mix_index_ratio')
            try:
                cmir = float(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            except (TypeError, ValueError):
                cmir = None
        cm_total = _row_float('case_mix_total_nurse_hrs_per_resident_per_day')
        if cm_total is None:
            v = pi_q.get('case_mix_total_nurse_hrs_per_resident_per_day')
            try:
                cm_total = float(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            except (TypeError, ValueError):
                cm_total = None
        pct_total = None
        if rt is not None and state_code:
            pct_total, _ = _percentiles_from_state_slice(state_slice, q_raw, rt, rn)
        state_hprd_numeric = _state_total_nurse_hprd_for_quarter(state_code, q_raw)
        _state_hprd_csv = (
            format_metric_value(state_hprd_numeric, 'Total_Nurse_HPRD')
            if state_hprd_numeric is not None
            else None
        )
        beds = _provider_certified_beds(pi_q if isinstance(pi_q, dict) else None)
        if beds is None and isinstance(fallback_latest_provider_row, dict):
            beds = _provider_certified_beds(fallback_latest_provider_row)
        casemix_str = format_metric_value(cm_total, 'Total_Nurse_HPRD') if cm_total is not None else None
        census_disp = _facility_quarterly_census_display(row, pi_q, format_metric_value)
        rows.append(
            build_facility_snapshot_csv_row(
                ccn=prov,
                facility_name=facility_name,
                state=st_label,
                city=city or '',
                quarter_display=q_disp,
                pbj320_url=page_url,
                avg_daily_census=census_disp,
                rn_hprd=format_metric_value(rn, 'RN_HPRD') if rn is not None else None,
                lpn_hprd=format_metric_value(lpn, 'LPN_HPRD') if lpn is not None else None,
                nurse_aide_hprd=format_metric_value(na, 'Nurse_Assistant_HPRD') if na is not None else None,
                total_nurse_hprd=format_metric_value(rt, 'Total_Nurse_HPRD') if rt is not None else None,
                state_total_nurse_hprd=_state_hprd_csv,
                state_percentile=pct_total,
                case_mix_index=format_metric_value(cmi, 'nursing_case_mix_index') if cmi is not None else None,
                case_mix_index_ratio=format_metric_value(cmir, 'nursing_case_mix_index_ratio')
                if cmir is not None
                else None,
                cms_case_mix_total_nurse_hprd=casemix_str if casemix_str and casemix_str != '—' else None,
                ownership_type=ownership_type or '',
                certified_beds=beds,
            )
        )
    return rows


def _build_facility_quarterly_trend_csv_rows(
    prov,
    facility_df,
    facility_name,
    state_code,
    state_name,
    base_url,
    format_metric_value,
    format_quarter_display,
):
    """One CSV row per quarter in facility_df — quarterly free layer only."""
    rows = []
    if facility_df is None or facility_df.empty or not HAS_PANDAS:
        return rows
    page_url = f'{base_url}/provider/{prov}'
    st_label = state_name or state_code or ''
    state_slice = _state_facility_metrics_slice_for_percentiles(state_code) if state_code else None
    try:
        sorted_df = facility_df.sort_values('CY_Qtr')
    except Exception:
        sorted_df = facility_df
    for _, row in sorted_df.iterrows():
        q_raw = str(row.get('CY_Qtr', '') or '').strip()
        if not q_raw:
            continue
        q_disp = format_quarter_display(q_raw)
        pi_q = get_provider_info_for_quarter(prov, q_raw) or {}

        def _row_float(key, pi_key=None):
            v = row.get(key) if key in row.index else None
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = pi_q.get(pi_key or key)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        rt = _row_float('Total_Nurse_HPRD', 'reported_total_nurse_hrs_per_resident_per_day')
        rn = _row_float('RN_HPRD', 'reported_rn_hrs_per_resident_per_day')
        lpn = _lpn_hprd_from_facility_quarterly_row(row)
        na = _row_float('Nurse_Assistant_HPRD', 'reported_na_hrs_per_resident_per_day')
        cmi = _row_float('nursing_case_mix_index')
        if cmi is None:
            v = pi_q.get('nursing_case_mix_index')
            try:
                cmi = float(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            except (TypeError, ValueError):
                cmi = None
        cmir = _row_float('nursing_case_mix_index_ratio')
        if cmir is None:
            v = pi_q.get('nursing_case_mix_index_ratio')
            try:
                cmir = float(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            except (TypeError, ValueError):
                cmir = None
        cm_total = _row_float('case_mix_total_nurse_hrs_per_resident_per_day')
        if cm_total is None:
            v = pi_q.get('case_mix_total_nurse_hrs_per_resident_per_day')
            try:
                cm_total = float(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None
            except (TypeError, ValueError):
                cm_total = None
        pct_total = None
        if rt is not None and state_code:
            pct_total, _ = _percentiles_from_state_slice(state_slice, q_raw, rt, rn)
        census_disp = _facility_quarterly_census_display(row, pi_q, format_metric_value)
        rows.append(
            build_facility_trend_csv_row(
                ccn=prov,
                facility_name=facility_name,
                state=st_label,
                quarter_display=q_disp,
                pbj320_url=page_url,
                avg_daily_census=census_disp,
                rn_hprd=format_metric_value(rn, 'RN_HPRD') if rn is not None else None,
                lpn_hprd=format_metric_value(lpn, 'LPN_HPRD') if lpn is not None else None,
                nurse_aide_hprd=format_metric_value(na, 'Nurse_Assistant_HPRD') if na is not None else None,
                total_nurse_hprd=format_metric_value(rt, 'Total_Nurse_HPRD') if rt is not None else None,
                case_mix_index=format_metric_value(cmi, 'nursing_case_mix_index') if cmi is not None else None,
                case_mix_index_ratio=format_metric_value(cmir, 'nursing_case_mix_index_ratio') if cmir is not None else None,
                cms_case_mix_total_nurse_hprd=format_metric_value(cm_total, 'Total_Nurse_HPRD') if cm_total is not None else None,
                state_percentile=pct_total,
            )
        )
    return rows


def generate_provider_page_html(ccn, facility_df, provider_info_row):
    """Generate HTML for facility (provider) page per pbj-page-guide: header block, key metrics, longitudinal chart, basic info, full table, summary."""
    if not HAS_PANDAS:
        return "Pandas not available. Provider pages require pandas."
    try:
        from pbj_format import format_metric_value, format_quarter_display
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{round_half_up(float(v), 2):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
        format_quarter_display = format_quarter
    # Defensive fallback so direct callers don't crash on missing provider rows.
    if facility_df is None or not isinstance(facility_df, pd.DataFrame):
        facility_df = pd.DataFrame()
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
    # Use canonical latest quarter so we match state/entity pages. If facility PBJ rows do not
    # include canonical quarter, still prefer canonical quarter when provider-info has a match.
    canonical_q = get_canonical_latest_quarter()
    pi_quarter = None
    if canonical_q is not None and not facility_df.empty and 'CY_Qtr' in facility_df.columns:
        match = facility_df[facility_df['CY_Qtr'].astype(str) == str(canonical_q)]
        if not match.empty:
            latest = match.iloc[0]
            raw_quarter = canonical_q
        else:
            latest = facility_df.sort_values('CY_Qtr', ascending=False).iloc[0]
            raw_quarter = latest.get('CY_Qtr', '') if latest is not None else ''
            # If provider_info has canonical quarter, use that for the narrative card.
            # (Charts still reflect available PBJ longitudinal quarters in facility_df.)
            pi_quarter = get_provider_info_for_quarter(prov, canonical_q)
            if pi_quarter:
                raw_quarter = canonical_q
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
    if pi_quarter is None:
        pi_quarter = get_provider_info_for_quarter(prov, raw_quarter) if raw_quarter else None
    pi_latest_q, pi_latest_row = (None, None)
    # If exact quarter row is unavailable, prefer snapshot provider row first (often the newest refresh),
    # then quarter-index fallback.
    if pi_quarter is None:
        pi_latest_q, pi_latest_row = get_latest_provider_info_for_ccn(prov)
    pi_metrics = (pi_quarter or pi or pi_latest_row)
    if isinstance(pi_metrics, dict):
        pi_metrics = {k: v for k, v in pi_metrics.items() if k != '_processing_date'}
    def _safe(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    reported_total = get_val('Total_Nurse_HPRD') if get_val('Total_Nurse_HPRD') is not None else _safe(pi_metrics.get('reported_total_nurse_hrs_per_resident_per_day'))
    reported_rn = get_val('RN_HPRD') if get_val('RN_HPRD') is not None else _safe(pi_metrics.get('reported_rn_hrs_per_resident_per_day'))
    reported_lpn = get_val('LPN_HPRD')
    if reported_lpn is None and latest is not None:
        reported_lpn = _lpn_hprd_from_facility_quarterly_row(latest)
    reported_na = get_val('Nurse_Assistant_HPRD') if get_val('Nurse_Assistant_HPRD') is not None else _safe(pi_metrics.get('reported_na_hrs_per_resident_per_day'))
    case_mix_total = _safe(pi_metrics.get('case_mix_total_nurse_hrs_per_resident_per_day'))
    case_mix_rn = _safe(pi_metrics.get('case_mix_rn_hrs_per_resident_per_day'))
    case_mix_lpn = _safe(pi_metrics.get('case_mix_lpn_hrs_per_resident_per_day'))
    case_mix_na = _safe(pi_metrics.get('case_mix_na_hrs_per_resident_per_day'))
    case_mix_index = _safe(pi_metrics.get('nursing_case_mix_index'))
    case_mix_index_ratio = _safe(pi_metrics.get('nursing_case_mix_index_ratio'))
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
    chart_data = _provider_charts_chartjs_data(facility_df, state_code, reported_total, reported_rn, reported_lpn, reported_na, case_mix_total, case_mix_rn, case_mix_lpn, case_mix_na, case_mix_index, case_mix_index_ratio)
    _rcm_cd = chart_data.get('reportedCaseMix')
    if isinstance(_rcm_cd, dict) and raw_quarter:
        _cref = get_provider_info_cmi_reference_stats(str(raw_quarter))
        if _cref:
            _rcm_cd['cmiRef'] = _cref
        if state_code:
            _sref = get_provider_info_cmi_state_reference_stats(
                state_code, str(raw_quarter), case_mix_index, case_mix_index_ratio
            )
            if _sref:
                _rcm_cd['cmiStateRef'] = _sref
    if isinstance(_rcm_cd, dict):
        _rcm_cd['facilityName'] = (facility_name or '').strip()
    state_percentile_total, _ = get_facility_state_percentile(
        prov, state_code, raw_quarter, reported_total or 0, reported_rn
    )
    _casemix_title = f'CMS Case-Mix ({html.escape(str(quarter_display))})' if quarter_display else 'CMS Case-Mix'
    chart_section = _provider_charts_html(chart_data, facility_name=facility_name, casemix_title=_casemix_title)
    hprd_val = format_metric_value(reported_total or get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')
    casemix_str = format_metric_value(case_mix_total, 'Total_Nurse_HPRD') if case_mix_total is not None else '—'
    above_below_state = _classify(reported_total or 0, None)
    above_below_casemix = _classify(reported_total or 0, case_mix_total)
    _fn_esc = html.escape(facility_name, quote=False)
    narrative = (
        f'<strong>{_fn_esc}</strong> reported <strong>{hprd_val} HPRD</strong> in {quarter_display}. '
        f'This level is {above_below_casemix} the CMS case-mix benchmark ({casemix_str} HPRD).'
    )
    if case_mix_total is None:
        narrative = f'<strong>{_fn_esc}</strong> reported <strong>{hprd_val} HPRD</strong> in {quarter_display}. CMS Case-Mix (acuity) is not reported for this quarter.'
    elif pi_quarter is None and not pi and pi_latest_q and str(pi_latest_q) != str(raw_quarter):
        narrative += f' <span style="color: rgba(226,232,240,0.72);">Case-mix hours shown from latest available provider-info quarter ({format_quarter_display(pi_latest_q)}).</span>'
    risk_flag, risk_reason = get_facility_risk_from_search_index(prov)
    sff_facilities_list = load_sff_facilities()
    sff_entry = next((f for f in (sff_facilities_list or []) if (str(f.get('provider_number') or '').strip().zfill(6)) == prov), None)
    is_sff = sff_entry is not None
    is_sff_candidate = is_sff and (str(sff_entry.get('category') or '').strip() == 'Candidate')
    if risk_flag and risk_reason:
        risk_badge_label = _sort_risk_reason_display(risk_reason)
    elif risk_flag:
        risk_badge_label = 'Meets high-risk criteria'
    elif is_sff:
        risk_badge_label = 'SFF Candidate' if is_sff_candidate else 'SFF'
    else:
        risk_badge_label = ''
    badge_style_abuse = 'display:inline-flex;align-items:center;padding:2px 10px;border-radius:6px;font-weight:600;font-size:0.85rem;margin-right:6px;transition:all 0.2s ease;color:#fb7185;background:rgba(251,113,133,0.1);border:1px solid rgba(251,113,133,0.2);'
    badge_style_sff = 'display:inline-flex;align-items:center;padding:2px 10px;border-radius:6px;font-weight:600;font-size:0.85rem;margin-right:6px;transition:all 0.2s ease;color:#fbbf24;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.28);'
    _risk_reason_lower = (risk_reason or '').strip().lower()
    badge_style = badge_style_abuse if (risk_badge_label and 'abuse' in _risk_reason_lower) else badge_style_sff
    sff_candidate_spans = '<span class="pbj-badge-mobile-hide">SFF Candidate</span><span class="pbj-badge-mobile-only">SFF Cand.</span>'
    use_sff_candidate_badge = (risk_badge_label == 'SFF Candidate')
    _risk_tip = html.escape(FACILITY_RISK_BADGE_TOOLTIP)
    _risk_info_inner = (
        '<span class="pbj-high-risk-help-wrap pbj-risk-badge-info-wrap">'
        '<button type="button" class="pbj-risk-badge-info" aria-label="High-risk criteria">i</button>'
        f'<span class="pbj-high-risk-tooltip" role="tooltip">{_risk_tip}</span>'
        '</span>'
    )

    def _risk_badge_with_info(inner_html: str) -> str:
        if not inner_html:
            return ''
        return (
            f'<span class="pbj-risk-badge-with-info" style="{badge_style}">'
            f'{inner_html}{_risk_info_inner}</span>'
        )

    if use_sff_candidate_badge:
        risk_badge = _risk_badge_with_info(sff_candidate_spans)
    elif is_sff_candidate and risk_badge_label and 'SFF' in risk_badge_label:
        # Combined reason (e.g. "1 star, SFF") – show SFF as SFF Candidate responsively
        risk_badge_content = risk_badge_label.replace('SFF', sff_candidate_spans)
        risk_badge = _risk_badge_with_info(risk_badge_content)
    else:
        risk_badge = _risk_badge_with_info(risk_badge_label) if risk_badge_label else ''
    contract_pct = format_metric_value(get_val("Contract_Percentage"), "Contract_Percentage")
    direct_hprd_val = format_metric_value(get_val('Nurse_Care_HPRD'), 'Nurse_Care_HPRD')
    residents_str = f"{census_int:,} residents" if census_int else "Census not reported"
    total_direct_badge = f"{hprd_val} HPRD (Direct: {direct_hprd_val})"
    total_hprd_badge_title = html.escape(
        'Total nurse staffing hours per resident day (HPRD), including direct care and admin/supervisory nursing roles.',
        quote=True
    )
    direct_hprd_badge_title = html.escape(
        'Shows total nurse HPRD, with direct care HPRD in parentheses (direct care excludes admin and Director of Nursing time).',
        quote=True
    )
    residents_badge_title = html.escape(
        'Average daily resident census reported by CMS for this quarter.',
        quote=True
    )
    staffing_badge_title = html.escape(
        'CMS staffing star rating (1-5), where more stars indicate stronger staffing performance.',
        quote=True
    )
    overall_badge_title = html.escape(
        'CMS overall star rating (1-5), based on health inspections, staffing, and quality measures.',
        quote=True
    )
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
    badge_span = 'display: inline-block; padding: 3px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; white-space: nowrap; color: #e4e4e7; background: rgba(39,39,42,0.65); border: 1px solid #3f3f46; transition: all 0.2s ease;'
    badge_span_red = 'display: inline-block; padding: 3px 10px; border-radius: 6px; font-weight: 600; font-size: 0.82rem; white-space: nowrap; color: #fb7185; background: rgba(251,113,133,0.1); border: 1px solid rgba(251,113,133,0.22); transition: all 0.2s ease;'
    # Omit separate risk badge when the only risk is 1-star overall (we show that via red Overall badge)
    _skip_risk_badge = _risk_reason_lower in ('1-star overall', '1 star overall', '1-star', '1 star')
    risk_badge_conditional = risk_badge if (risk_badge and not _skip_risk_badge) else ''
    try:
        _on = round_half_up(float(_overall_raw), 0) if _overall_raw is not None else None
        is_1_star_overall = (_on is not None and int(_on) == 1)
    except (TypeError, ValueError):
        is_1_star_overall = False
    overall_badge_style = badge_span_red if is_1_star_overall else badge_span
    overall_badge_html = (
        f'<span style="{overall_badge_style}" title="{overall_badge_title}">{overall_star_label}</span>'
        if overall_star_icons != '—' else ''
    )
    _staff_stars_html = f'<span class="pbj-staffing-stars">{staffing_star_icons}</span>' if staffing_star_icons != '—' else staffing_star_icons
    staffing_badge_html = (
        f'<span style="{badge_span}" title="{staffing_badge_title}">Staffing: {_staff_stars_html}</span>'
        if staffing_star_icons != '—' else ''
    )
    casemix_badge_html = ''
    if case_mix_total is not None and casemix_str and casemix_str != '—':
        casemix_badge_title = html.escape(
            'CMS case-mix total nurse HPRD (acuity benchmark) for this quarter.',
            quote=True,
        )
        casemix_badge_html = (
            f'<span class="pbj-badge-mobile-hide" style="{badge_span}" title="{casemix_badge_title}">'
            f'Case-Mix: {casemix_str}</span>'
        )
    percentile_line = ''
    state_pct_phrase = format_percentile_phrase(state_percentile_total, state_name)
    if state_pct_phrase:
        state_ratio_str = f' ({state_hprd_placeholder} HPRD)' if state_hprd_placeholder and state_hprd_placeholder != '—' else ''
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
    _fac_hprd_body = build_hprd_floor_analogy_body(
        reported_total, reported_na, facility_name, census=census_int
    )
    _facility_hprd_badge, facility_hprd_modal = render_hprd_badge_with_info(
        hprd_val,
        badge_span,
        total_hprd_badge_title,
        _fac_hprd_body,
        uid=f'fac-{prov}',
        display_text=f'{hprd_val} HPRD',
        display_text_desktop=total_direct_badge,
    )
    _takeaway_title_span = takeaway_title_name_html(facility_name, 'facility')
    _facility_page_url = f'{base_url}/provider/{prov}'
    _facility_share = render_takeaway_share_button(_facility_page_url, facility_name, uid=f'fac-{prov}')
    _cmi_ratio_str = (
        format_metric_value(case_mix_index_ratio, 'nursing_case_mix_index_ratio')
        if case_mix_index_ratio is not None else None
    )
    _cmi_idx_str = (
        format_metric_value(case_mix_index, 'nursing_case_mix_index')
        if case_mix_index is not None else None
    )
    care_compare_facility_url = (
        f'https://www.medicare.gov/care-compare/details/nursing-home/{prov}/view-all/?state={state_code}'
        if state_code
        else ''
    )
    _macpac_chart = get_macpac_chart_info(state_code) if state_code else None
    _macpac_factset_line = ''
    if _macpac_chart and (_macpac_chart.get('label_long') or _macpac_chart.get('label_short')):
        _macpac_factset_line = (
            (_macpac_chart.get('label_long') or _macpac_chart.get('label_short') or '').strip()
            + ' — Estimate from MACPAC state policy summary; '
            'would need to verify against current statute/admin code and facility-specific staffing definitions.'
        )
        if (state_code or '').strip().upper() == 'CT':
            _macpac_factset_line += (
                ' Connecticut MACPAC detail: ~3.00 HPRD combined RN/LPN/CNA direct-care minimum '
                '(Public Act 21-2 / SB 1030) plus ~0.06 HPRD DON in DPH regs — different definitions '
                'than PBJ role lines; verify DPH before compliance claims.'
            )
    def _cms_star_line(label: str, raw) -> str:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return ''
        try:
            n = int(round_half_up(float(raw), 0))
        except (TypeError, ValueError):
            return ''
        if n < 1 or n > 5:
            return ''
        return f'{label}: {n} of 5 (CMS Care Compare snapshot; not a staffing hours measure).'

    _cms_overall_line = _cms_star_line('CMS overall Five-Star rating', _overall_raw)
    _cms_staffing_star_line = _cms_star_line('CMS staffing Five-Star rating', _staffing_raw)
    _contract_pct_raw = get_val('Contract_Percentage')
    _contract_ai = (
        format_metric_value(_contract_pct_raw, 'Contract_Percentage')
        if _contract_pct_raw is not None and not (isinstance(_contract_pct_raw, float) and pd.isna(_contract_pct_raw))
        else None
    )
    _entity_portfolio_ai = _entity_portfolio_ai_line(entity_id) if entity_id else ''
    _facility_entity_page_url = ''
    if entity_id and entity_name:
        try:
            _facility_entity_page_url = f'{base_url}/entity/{int(entity_id)}'
        except (TypeError, ValueError):
            _eid = str(entity_id).strip()
            if _eid.isdigit():
                _facility_entity_page_url = f'{base_url}/entity/{_eid}'
    _certified_beds = _provider_certified_beds(provider_info_row or pi_metrics)
    _facility_snapshot_ai = _provider_ai_facility_snapshot_context(
        pi_metrics if isinstance(pi_metrics, dict) else {},
        census_int=census_int,
        certified_beds=_certified_beds,
        ownership_short=ownership_short or ownership_raw or '',
        cms_overall_line=_cms_overall_line,
        cms_staffing_line=_cms_staffing_star_line,
    )
    _cms_risk_ai = _cms_risk_screening_line_for_ai(
        risk_reason=risk_reason or '',
        risk_flag=int(risk_flag or 0),
        is_sff=is_sff,
        is_sff_candidate=is_sff_candidate,
        pi_metrics=pi_metrics if isinstance(pi_metrics, dict) else {},
        overall_rating_raw=_overall_raw,
        staffing_rating_raw=_staffing_raw,
    )
    _facility_ai_ctx = build_dashboard_context(
        page_type='facility',
        page_url=_facility_page_url,
        period=quarter_display or '',
        page_kind='PBJ320 provider page (quarterly)',
        summary=narrative,
        facility_name=facility_name or '',
        ccn=prov,
        state_name=state_name or state_code or '',
        entity_name=entity_name or '',
        entity_page_url=_facility_entity_page_url,
        rn_hprd=format_metric_value(reported_rn, 'RN_HPRD') if reported_rn is not None else None,
        lpn_hprd=format_metric_value(reported_lpn, 'LPN_HPRD') if reported_lpn is not None else None,
        na_hprd=format_metric_value(reported_na, 'Nurse_Assistant_HPRD') if reported_na is not None else None,
        total_hprd=hprd_val,
        case_mix_index=_cmi_idx_str,
        case_mix_index_ratio=_cmi_ratio_str,
        case_mix_hprd=casemix_str if casemix_str and casemix_str != '—' else None,
        staffing_percentile=state_pct_phrase if state_pct_phrase else None,
        state_comparison=state_pct_phrase if state_pct_phrase else None,
        above_below_casemix=above_below_casemix if case_mix_total is not None else None,
        county_name=county or '',
        ownership_type=ownership_short or ownership_raw or '',
        care_compare_url=care_compare_facility_url,
        macpac_reference_line=_macpac_factset_line,
        cms_overall_star_line=_cms_overall_line,
        cms_staffing_star_line=_cms_staffing_star_line,
        premium_dashboard_note='Premium PBJ320 daily-staffing dashboards and exports are not included in this page URL.',
        contract_staff_pct=_contract_ai,
        entity_portfolio_summary=_entity_portfolio_ai,
        facility_snapshot_context=_facility_snapshot_ai,
        cms_risk_screening_line=_cms_risk_ai,
    )
    _state_hprd_csv = (
        format_metric_value(state_hprd_numeric, 'Total_Nurse_HPRD')
        if state_hprd_numeric is not None
        else None
    )
    _snapshot_row = build_facility_snapshot_csv_row(
        ccn=prov,
        facility_name=facility_name or '',
        state=state_name or state_code or '',
        city=city or '',
        quarter_display=quarter_display or '',
        pbj320_url=_facility_page_url,
        rn_hprd=format_metric_value(reported_rn, 'RN_HPRD') if reported_rn is not None else None,
        lpn_hprd=format_metric_value(reported_lpn, 'LPN_HPRD') if reported_lpn is not None else None,
        nurse_aide_hprd=format_metric_value(reported_na, 'Nurse_Assistant_HPRD') if reported_na is not None else None,
        total_nurse_hprd=hprd_val,
        state_total_nurse_hprd=_state_hprd_csv,
        state_percentile=state_percentile_total,
        case_mix_index=_cmi_idx_str,
        case_mix_index_ratio=_cmi_ratio_str,
        cms_case_mix_total_nurse_hprd=casemix_str if casemix_str and casemix_str != '—' else None,
        ownership_type=ownership_short or ownership_raw or '',
        certified_beds=_certified_beds,
    )
    _trend_rows = _build_facility_quarterly_trend_csv_rows(
        prov,
        facility_df,
        facility_name or '',
        state_code,
        state_name,
        base_url,
        format_metric_value,
        format_quarter_display,
    )
    _snapshot_hist = _build_facility_snapshot_csv_rows(
        prov,
        facility_df,
        facility_name or '',
        state_code,
        state_name,
        city or '',
        base_url,
        format_metric_value,
        format_quarter_display,
        ownership_short or ownership_raw or '',
        provider_info_row or pi_metrics,
    )
    _snapshot_rows = _snapshot_hist if _snapshot_hist else [_snapshot_row]
    _snapshot_csv = build_facility_snapshot_csv(_snapshot_rows)
    _trends_csv = build_facility_trends_csv(_trend_rows) if _trend_rows else ''
    _snapshot_fn = facility_snapshot_csv_filename(prov, facility_name or '', str(raw_quarter or ''))
    _trends_fn = facility_trends_csv_filename(prov, facility_name or '')
    _facility_ai_helper = render_ai_facility_helper(
        _facility_ai_ctx,
        helper_uid=f'fac-{prov}',
        page_url=_facility_page_url,
        facility_name=facility_name or '',
        ccn=prov,
        state_label=state_name or state_code or '',
        state_code=state_code or '',
        state_standard_available=bool(_macpac_factset_line.strip()),
        snapshot_csv=_snapshot_csv,
        snapshot_csv_filename=_snapshot_fn,
        trends_csv=_trends_csv,
        trends_csv_filename=_trends_fn,
        trend_rows=_trend_rows,
        share_html=_facility_share,
    )
    _facility_csv_footer = render_facility_csv_page_footer(
        helper_uid=f'fac-{prov}',
        snapshot_csv=_snapshot_csv,
        snapshot_csv_filename=_snapshot_fn,
        trends_csv=_trends_csv,
        trends_csv_filename=_trends_fn,
        care_compare_url=care_compare_facility_url,
        state_code=state_code or '',
        state_label=state_name or state_code or '',
    )
    _facility_actions = ''
    pbj_takeaway_card = f'''
<div id="pbj-takeaway" class="pbj-content-box pbj-takeaway" style="margin: 1rem 0; padding: 1rem;">
<div class="pbj-takeaway-top">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(129,140,248,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-top-main">
<div class="pbj-takeaway-header">PBJ Takeaway{_takeaway_title_span}</div>
<span class="pbj-takeaway-brand-pill">320 Consulting</span>
</div>
</div>
<div class="pbj-takeaway-badges" style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0.5rem 0 0.4rem 0;">{risk_badge_conditional}{_facility_hprd_badge}{casemix_badge_html}<span class="pbj-badge-mobile-hide" style="{badge_span}" title="{residents_badge_title}">{residents_str}</span>{staffing_badge_html}<span class="pbj-overall-badge">{overall_badge_html}</span></div>
{percentile_line}
<p class="pbj-takeaway-narrative" style="margin: 0.5rem 0 0.35rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{narrative}</p>
{_facility_ai_helper}
{_facility_actions}
{facility_hprd_modal}
</div>'''
    seo_desc = f"{facility_name} nursing home staffing: {format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')} HPRD total nurse staffing in {quarter_display}."
    page_title = f"{facility_name} | Nursing Home Staffing | PBJ320"
    provider_json_ld = _provider_page_json_ld_scripts(
        facility_name=facility_name,
        ccn=prov,
        city=city,
        state_code=state_code,
        state_name=state_name,
        state_slug=canonical_slug,
        page_url=f"{base_url}/provider/{prov}",
        total_hprd=hprd_val,
        quarter_display=quarter_display,
    )
    layout = get_pbj_site_layout(page_title, seo_desc, f"{base_url}/provider/{prov}", extra_head=provider_json_ld)
    facility_page_url = f"{base_url}/provider/{prov}"
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
    subtitle_one_line = _loc_sub + (f' &bull; {entity_link}' if (entity_id and entity_name) else '')
    # Mobile: row 1 = location • residents; row 2 = ownership • entity when chain present; else all on one row
    _row1_parts = []
    if _city_state.strip():
        _row1_parts.append(_city_state)
    if entity_id and entity_name:
        _row1_parts.append(_residents_sub)
        _row1 = ' &bull; '.join(_row1_parts) if _row1_parts else _residents_sub
        _row2_parts = []
        if ownership_short and ownership_short.strip():
            _row2_parts.append(ownership_short)
        _row2_parts.append(entity_link)
        subtitle_mobile = (
            f'<span class="pbj-subtitle-mobile-row1">{_row1}</span>'
            f'<span class="pbj-subtitle-mobile-row2">{" &bull; ".join(_row2_parts)}</span>'
        )
    else:
        if ownership_short and ownership_short.strip():
            _row1_parts.append(ownership_short)
        _row1_parts.append(_residents_sub)
        _row1 = ' &bull; '.join(_row1_parts) if _row1_parts else _residents_sub
        subtitle_mobile = f'<span class="pbj-subtitle-mobile-row1">{_row1}</span>'
    inner = f"""
<h1>{facility_name}</h1>
<p class="pbj-subtitle"><span class="pbj-subtitle-desktop">{subtitle_one_line}</span><span class="pbj-subtitle-mobile">{subtitle_mobile}</span></p>

{pbj_takeaway_card}

{chart_section}

{custom_report_cta_html}

{render_methodology_block()}

<div class="pbj-page-footer" style="margin-top: 1.75rem; padding-top: 0.5rem; border-top: 1px solid rgba(129,140,248,0.15);">
<p style="margin: 0 0 0.4rem 0; font-size: 0.875rem; color: rgba(226,232,240,0.85); line-height: 1.5;"><a href="/">Home</a> &middot; <a href="/state/{canonical_slug}">{state_name}</a>{' &middot; ' + entity_breadcrumb_link if entity_breadcrumb_link else ''}</p>
{_facility_csv_footer}
<p class="pbj-page-source">Source: <a href="https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing" target="_blank" rel="noopener">CMS Payroll-Based Journal</a> (PBJ) data.</p>
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
    # Prefer latest provider snapshot for current facility roster/counts; fall back to combined files.
    # Combined files can include broader longitudinal/entity memberships and overstate current roster counts.
    paths = _provider_snapshot_candidate_paths() + [
        os.path.join(APP_ROOT, 'provider_info_combined_latest.csv'),
        'provider_info_combined_latest.csv',
        'pbj-wrapped/public/data/provider_info_combined_latest.csv',
        os.path.join(APP_ROOT, 'provider_info_combined.csv'),
        'provider_info_combined.csv',
        'pbj-wrapped/public/data/provider_info_combined.csv',
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
        # Canonicalize by entity ID to avoid alias drift between snapshots
        canonical_name = get_entity_name_from_search_index(entity_id)
        if canonical_name:
            entity_name = canonical_name
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
            fq['PROVNUM'] = _normalize_provnum_series(fq['PROVNUM'])
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
_CHAIN_PERF_SOURCE_LABEL = ''
_CHAIN_PERF_SOURCE_PATH = ''

def load_chain_performance():
    """Load chain/entity performance data from CMS Chain Performance CSV.
    Auto-selects the latest local CMS chain performance CSV (prefers official
    Nursing_Home_Chain_Performance_Measures* naming when present). Used for
    entity PBJ takeaway and key metrics.
    Returns dict mapping entity_id (int) -> row dict with keys matching CSV columns (strip-spaced)."""
    global _CHAIN_PERF_CACHE, _CHAIN_PERF_AT, _CHAIN_PERF_TTL, _CHAIN_PERF_SOURCE_LABEL, _CHAIN_PERF_SOURCE_PATH
    now = time.time()
    if _CHAIN_PERF_CACHE is not None and _CHAIN_PERF_SOURCE_LABEL and (now - _CHAIN_PERF_AT) < _CHAIN_PERF_TTL:
        return _CHAIN_PERF_CACHE
    if not HAS_PANDAS:
        return {}
    import glob

    def _parse_chain_file_date(path):
        """Best-effort date extraction from chain-performance filename."""
        base = os.path.basename(path)
        # Pattern: *_20260218.csv
        m = re.search(r'(\d{8})', base)
        if m:
            try:
                return datetime.strptime(m.group(1), '%Y%m%d')
            except Exception:
                pass
        # Pattern: *_Feb_2026.csv or *_February_2026.csv
        m = re.search(r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)[\s_-]*(\d{4})', base, re.IGNORECASE)
        if m:
            month_map = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
                'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
                'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
            }
            mon = month_map.get(m.group(1).lower())
            yr = int(m.group(2))
            if mon:
                try:
                    return datetime(yr, mon, 1)
                except Exception:
                    pass
        # Fallback to mtime
        try:
            return datetime.fromtimestamp(os.path.getmtime(path))
        except Exception:
            return datetime.min

    def _chain_file_priority(path):
        base = os.path.basename(path).lower()
        if base.startswith('nursing_home_chain_performance_measures'):
            return 2
        if base.startswith('chain_performance'):
            return 1
        return 0

    def _chain_source_label(path):
        base = os.path.basename(path or '')
        m = re.search(r'(\d{8})', base)
        if m:
            try:
                dt = datetime.strptime(m.group(1), '%Y%m%d')
                return dt.strftime('%B %Y')
            except Exception:
                pass
        m = re.search(r'(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)[\s_-]*(\d{4})', base, re.IGNORECASE)
        if m:
            month_map = {
                'jan': 'January', 'january': 'January', 'feb': 'February', 'february': 'February',
                'mar': 'March', 'march': 'March', 'apr': 'April', 'april': 'April', 'may': 'May',
                'jun': 'June', 'june': 'June', 'jul': 'July', 'july': 'July', 'aug': 'August', 'august': 'August',
                'sep': 'September', 'sept': 'September', 'september': 'September', 'oct': 'October', 'october': 'October',
                'nov': 'November', 'november': 'November', 'dec': 'December', 'december': 'December',
            }
            mon = month_map.get(m.group(1).lower())
            return f'{mon} {m.group(2)}' if mon else ''
        return ''

    paths = []
    for g in [
        os.path.join(APP_ROOT, 'ownership', 'Nursing_Home_Chain_Performance_Measures*.csv'),
        os.path.join(APP_ROOT, 'ownership', 'Chain_Performance_*.csv'),
        os.path.join(APP_ROOT, 'ownership', 'Chain*.csv'),
        os.path.join(APP_ROOT, '2025-11', 'Nursing_Home_Chain_Performance_Measures*.csv'),
        os.path.join(APP_ROOT, '2025-11', 'Chain_Performance_*.csv'),
        os.path.join(APP_ROOT, '2025-11', 'Chain*.csv'),
        os.path.join(APP_ROOT, 'Nursing_Home_Chain_Performance_Measures*.csv'),
        os.path.join(APP_ROOT, 'Chain_Performance_*.csv'),
        os.path.join(APP_ROOT, 'chain_performance.csv'),
    ]:
        paths.extend(glob.glob(g))
    seen = set()
    paths = [p for p in paths if p not in seen and not seen.add(p) and os.path.isfile(p)]
    paths.sort(key=lambda p: (_chain_file_priority(p), _parse_chain_file_date(p)), reverse=True)
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
            _CHAIN_PERF_SOURCE_PATH = path
            _CHAIN_PERF_SOURCE_LABEL = _chain_source_label(path)
            return out
        except Exception as e:
            print(f"Error loading chain performance from {path}: {e}")
            continue
    return {}


def get_chain_performance_source_label() -> str:
    # Ensure cache/source metadata is initialized.
    if _CHAIN_PERF_CACHE is None:
        load_chain_performance()
    return _CHAIN_PERF_SOURCE_LABEL or ''

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
    _entity_takeaway_title_span = takeaway_title_name_html(entity_name or 'Chain', 'entity')
    try:
        from pbj_format import format_metric_value, get_metric_label
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{round_half_up(float(v), 2):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
        get_metric_label = lambda k: k.replace('_', ' ')
    base_url = 'https://pbj320.com'
    _entity_share_btn = render_takeaway_share_button(
        f'{base_url}/entity/{entity_id}',
        entity_name or 'Chain',
        uid=f'ent-{entity_id}',
    )
    _entity_share_actions = ''
    _entity_page_url = f'{base_url}/entity/{entity_id}'
    n = len(facilities)
    subtitle = f"{n} nursing home{'s' if n != 1 else ''}"
    provider_info = load_provider_info() or {}

    def _facility_census_numeric(fac_dict):
        """Avg. daily census: prefer provider file (Care Compare / latest combined row), else PBJ quarter."""
        ccn_k = str(fac_dict.get('ccn') or '').strip().zfill(6)
        if ccn_k:
            raw_pi = (provider_info.get(ccn_k) or {}).get('avg_residents_per_day')
            if raw_pi is not None and str(raw_pi).strip() != '':
                try:
                    if not (isinstance(raw_pi, float) and pd.isna(raw_pi)):
                        return float(raw_pi)
                except (TypeError, ValueError):
                    pass
        raw_pbj = fac_dict.get('avg_daily_census')
        if raw_pbj is not None and not (isinstance(raw_pbj, float) and pd.isna(raw_pbj)):
            try:
                return float(raw_pbj)
            except (TypeError, ValueError):
                pass
        return None

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
        cnum = _facility_census_numeric(fac)
        if cnum is not None:
            try:
                _c = round_half_up(cnum, 0)
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
        _b = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(67,56,202,0.22);color:#818cf8;border:1px solid rgba(129,140,248,0.35);'
        _scope = f'<span style="{_b}">{n:,} Facilities</span><span style="{_b}">{num_states} States</span>'
        if avg_total is not None:
            _scope += f'<span style="{_b}">Avg Total HPRD: {format_metric_value(avg_total, "Total_Nurse_HPRD")}</span>'
        _entity_esc = html.escape(entity_name or "This chain")
        _p_ops = f"<strong>{_entity_esc}</strong> operates <strong>{n:,}</strong> nursing home{'s' if n != 1 else ''} across <strong>{num_states}</strong> state{'s' if num_states != 1 else ''}."
        _p_value = ""
        if avg_total is not None:
            _p_value = f" Average total nurse HPRD this quarter: <strong>{format_metric_value(avg_total, 'Total_Nurse_HPRD')}</strong>."
        _entity_share_actions = render_takeaway_actions_row('', _entity_share_btn, '')
        pbj_takeaway_ownership = f'''
<div id="pbj-takeaway" class="pbj-content-box pbj-takeaway" style="margin: 1rem 0; padding: 1rem;">
<div class="pbj-takeaway-top">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(129,140,248,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-top-main">
<div class="pbj-takeaway-header">PBJ Takeaway{_entity_takeaway_title_span}</div>
<span class="pbj-takeaway-brand-pill">320 Consulting</span>
</div>
</div>
<p style="margin: 0.5rem 0 0.25rem 0;">{_scope}</p>
<p style="margin: 0.5rem 0 0; font-size: 0.95rem; color: rgba(226,232,240,0.95);">{_p_ops}{_p_value}</p>
{_entity_share_actions}
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
        # Prefer provider roster count for entity page/titles/table consistency.
        # Keep CMS chain count as an optional secondary reference for context.
        n_fac_provider = n if n else 0
        n_fac_cms = int(n_chain) if n_chain is not None else None
        n_fac = n_fac_provider if n_fac_provider else (n_fac_cms if n_fac_cms is not None else 0)
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
        _badge = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(39,39,42,0.75);color:#e4e4e7;border:1px solid #3f3f46;transition:all 0.2s ease;'
        _badge_risk = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;color:#fbbf24;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.28);'
        _badge_severe = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;color:#fbbf24;background:rgba(251,191,36,0.14);border:1px solid rgba(251,191,36,0.32);'
        _badge_abuse = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;color:#f87171;background:rgba(248,113,113,0.1);border:1px solid rgba(248,113,113,0.2);'
        _badge_neutral = 'display:inline-block;padding:4px 10px;border-radius:6px;font-size:0.8rem;font-weight:600;margin-right:6px;margin-bottom:6px;background:rgba(39,39,42,0.55);color:#a1a1aa;border:1px solid #3f3f46;'
        _fp = round_half_up(for_profit, 0) if for_profit is not None else None
        fp_pct = int(_fp) if _fp is not None else None
        tier1_badges = f'<span style="{_badge}">{n_fac:,} Facilities</span><span style="{_badge}">{n_st} States</span>'
        if fp_pct is not None:
            tier1_badges += f'<span style="{_badge}">{fp_pct}% For-Profit</span>'
        staff_val = (f"{staff_rating:.1f}" if staff_rating is not None else "—")
        overall_val = (f"{overall_rating:.1f}" if overall_rating is not None else "—")
        tier1_badges += f'<span class="pbj-overall-badge" style="{_badge}">Avg. Overall Rating: {overall_val}</span>'
        if staff_val != '—':
            tier1_badges += (
                f'<span class="pbj-badge-mobile-hide" style="{_badge}">Avg. Staffing Rating: {staff_val}</span>'
                f'<span class="pbj-badge-mobile-only" style="{_badge}">Staffing Rating: {staff_val}</span>'
            )

        risk_parts = []
        if sff is not None and sff > 0:
            risk_parts.append(('SFF: ' + str(int(sff)), _badge_severe if sff >= 3 else _badge_risk))
        if sff_cand is not None and sff_cand > 0:
            risk_parts.append(('SFF Candidates: ' + str(int(sff_cand)), _badge_risk))
        if abuse_pct is not None and abuse_pct > 0:
            risk_parts.append((f'Abuse icon: {abuse_pct:.0f}% of facilities', _badge_abuse if abuse_pct > 10 else _badge_neutral))
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

        _entity_share_actions = render_takeaway_actions_row('', _entity_share_btn, '')
        pbj_takeaway_ownership = f'''
<div id="pbj-takeaway" class="pbj-content-box pbj-takeaway" style="margin: 1rem 0; padding: 1rem;">
<div class="pbj-takeaway-top">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(129,140,248,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-top-main">
<div class="pbj-takeaway-header">PBJ Takeaway{_entity_takeaway_title_span}</div>
<span class="pbj-takeaway-brand-pill">320 Consulting</span>
</div>
</div>
<p style="margin: 0.5rem 0 0.25rem 0;">{tier1_badges}</p>
<p class="pbj-takeaway-narrative" style="margin: 0.5rem 0 0.25rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{p1_simple}</p>
<p class="pbj-takeaway-narrative" style="margin: 0.25rem 0 0.25rem 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{p2}</p>
<p class="pbj-takeaway-narrative" style="margin: 0.25rem 0 0 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(226,232,240,0.92);">{p3}</p>
{_entity_share_actions}
</div>'''

        chain_metrics_html = '<div class="section-header">Key metrics</div>'
        chain_metrics_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0;">'
        providers_label = 'Providers'
        if n_fac_cms is not None and n_fac_provider and n_fac_cms != n_fac_provider:
            providers_label += (
                ' <span class="pbj-high-risk-help-wrap" style="position:relative;display:inline-flex;align-items:center;vertical-align:middle;">'
                '<span class="pbj-high-risk-help" style="font-size:0.75rem;cursor:help;">ⓘ</span>'
                f'<span class="pbj-high-risk-tooltip" role="tooltip">Provider roster shows {n_fac_provider:,} facilities; CMS chain performance file lists {n_fac_cms:,}.</span>'
                '</span>'
            )
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">{providers_label}</div><div class="value">{n_fac:,}</div></div>'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">States</div><div class="value">{n_st}</div></div>'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Avg. Rating</div><div class="value">{(f"{overall_rating:.1f}" if overall_rating is not None else "—")}</div></div>'
        if fines_dollars is not None:
            if fines_dollars >= 1e6:
                fines_str = f'${fines_dollars/1e6:.1f} million'
            else:
                fines_str = f'${fines_dollars:,.0f}'
        else:
            fines_str = '—'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Total Fines</div><div class="value">{fines_str}</div></div>'
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
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Special Focus Facilities (SFFs)</div><div class="value">{int(sff) if sff is not None else "—"}</div></div>'
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">SFF Candidates</div><div class="value">{int(sff_cand) if sff_cand is not None else "—"}</div></div>'
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">1-Star Overall</div><div class="value">{int(one_star_count) if one_star_count is not None else "—"}</div></div>'
        abuse_display = f'{int(abuse_count)}' if abuse_count is not None else '—'
        high_risk_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Cited for Abuse</div><div class="value">{abuse_display}</div></div>'
        high_risk_html += '</div>'
        cms_stars_html = f'<div class="section-header">Avg. CMS 5-Star Rating<span class="pbj-section-header-entity-name"> – {html.escape(entity_name)}</span></div>'
        cms_stars_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0;">'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Overall</div><div class="value">{(f"{overall_rating:.1f}" if overall_rating is not None else "—")}</div></div>'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Health Inspection</div><div class="value">{(f"{hi_rating:.1f}" if hi_rating is not None else "—")}</div></div>'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Staffing</div><div class="value">{(f"{staff_rating:.1f}" if staff_rating is not None else "—")}</div></div>'
        cms_stars_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Quality Measures</div><div class="value">{(f"{quality_rating:.1f}" if quality_rating is not None else "—")}</div></div>'
        cms_stars_html += '</div>'
        fp = for_profit or 0
        np_ = non_profit or 0
        gov = govt or 0
    if not chain_metrics_html and (quarter_display or avg_total is not None or total_residents or avg_contract is not None):
        chain_metrics_html = '<div class="section-header">Key metrics' + (f' ({quarter_display})' if quarter_display else '') + '</div>'
        chain_metrics_html += '<div class="entity-chain-metrics" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin:1rem 0;">'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Facilities</div><div class="value">{n:,}</div></div>'
        chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">States</div><div class="value">{num_states}</div></div>'
        if total_residents:
            chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Residents (approx.)</div><div class="value">{total_residents:,}</div></div>'
        if avg_total is not None:
            chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Avg Total HPRD</div><div class="value">{format_metric_value(avg_total, "Total_Nurse_HPRD")}</div></div>'
        if avg_contract is not None:
            chain_metrics_html += f'<div class="pbj-metric-card" style="background:rgba(15,23,42,0.6);border:1px solid rgba(129,140,248,0.2);border-radius:8px;padding:1rem;"><div class="label">Avg Contract %</div><div class="value">{format_metric_value(avg_contract, "Contract_Percentage")}%</div></div>'
        chain_metrics_html += '</div>'

    PAGE_SIZE = 20
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
        census_num = _facility_census_numeric(fac)
        census_disp = '—'
        census_sort = ''
        if census_num is not None:
            _ci = int(round_half_up(census_num, 0))
            census_disp = f'{_ci:,}'
            census_sort = str(_ci)
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
        cells = [state_cell, facility_cell, city or '—', census_disp]
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
        data_attrs = f' data-facility="{name}" data-city="{city or ""}" data-state="{state}" data-ccn="{ccn}" data-census="{census_sort}" data-total-hprd="{tn_num if tn_num is not None else ""}" data-rn-hprd="{rn_num if rn_num is not None else ""}" data-overall-rating="{overall_num if overall_num is not None else ""}" data-staffing-rating="{staff_num if staff_num is not None else ""}"'
        rows.append('<tr class="' + row_class + '"' + data_attrs + '><td>' + '</td><td>'.join(cells) + '</td></tr>')
    thead = '<tr><th scope="col" data-sort="state">State</th><th scope="col" data-sort="facility">Provider</th><th scope="col" data-sort="city">City</th><th scope="col" class="entity-col-census" data-sort="census">Census</th><th scope="col" data-sort="total-hprd">Total HPRD</th><th scope="col" data-sort="rn-hprd">RN HPRD</th><th scope="col" data-sort="overall-rating">Overall Rating</th><th scope="col" data-sort="staffing-rating">Staffing Rating</th></tr>'
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
    entity_json_ld = _entity_page_json_ld_scripts(
        entity_name=entity_name,
        entity_id=int(entity_id),
        page_url=f"{base_url}/entity/{entity_id}",
        facility_count=n,
    )
    layout = get_pbj_site_layout(page_title, seo_desc, f"{base_url}/entity/{entity_id}", extra_head=entity_json_ld)
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
<div class="pbj-cms-data-block" style="margin: 1rem 0; border: 1px solid rgba(129,140,248,0.25); border-radius: 8px; background: rgba(15,23,42,0.4); padding: 0 1rem 1rem 1rem;">
<div class="section-header" style="margin-top: 0; padding-top: 0.75rem;">{_entity_esc} Key Metrics</div>
''' + _chain_metrics_body + high_risk_html + cms_stars_html + '''
</div>'''
    elif chain_metrics_html:
        all_chain_data_html = chain_metrics_html

    inner = f"""
<h1>{html.escape(entity_name)}</h1>
{pbj_takeaway_ownership}
{all_chain_data_html}

<div class="section-header">{html.escape(entity_name)} Facilities</div>
<p class="pbj-subtitle">Nursing homes affiliated with this entity. Latest quarter staffing from CMS PBJ data. Click column headers to sort.</p>
<style>.entity-facilities-table {{ font-size: 0.875rem; border-collapse: collapse; }} .entity-facilities-table th.entity-col-census, .entity-facilities-table td:nth-child(4) {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }} .entity-facilities-table tr.high-risk {{ background: rgba(220,38,38,0.08); }} .entity-facilities-table tr.high-risk a {{ color: #fca5a5; text-decoration: none; }} .entity-facilities-table tr.high-risk a:hover {{ color: #fecaca; text-decoration: none; }} .entity-facility-risk-wrap {{ position: relative; display: inline-flex; }} .entity-facility-risk-wrap:hover .entity-facility-risk-tooltip {{ opacity: 1; }} .entity-facility-risk-tooltip {{ position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 6px; min-width: 120px; max-width: 200px; padding: 6px 10px; font-size: 0.75rem; line-height: 1.35; white-space: normal; z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.2s; background: #1e293b; border: 1px solid rgba(59,130,246,0.4); border-radius: 6px; color: #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }} @media (max-width: 768px) {{ .entity-facilities-table {{ font-size: 0.78rem; }} .entity-facilities-table th, .entity-facilities-table td {{ padding: 0.38rem 0.28rem; }} .entity-facilities-table th:nth-child(2), .entity-facilities-table td:nth-child(2) {{ max-width: 38vw; overflow: hidden; text-overflow: ellipsis; }} .pbj-table-wrap {{ -webkit-overflow-scrolling: touch; overflow-x: auto; }} }}</style>
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

<div class="pbj-page-footer" style="margin-top: 1.75rem; padding-top: 0.5rem; border-top: 1px solid rgba(129,140,248,0.15);">
<p style="margin: 0 0 0.4rem 0; font-size: 0.875rem; color: rgba(226,232,240,0.85); line-height: 1.5;"><a href="/">Home</a></p>
<p style="margin: 0; font-size: 0.8rem; color: rgba(226,232,240,0.6); line-height: 1.45;">Source: CMS Payroll-Based Journal (PBJ) data for facility list and staffing. Chain-level metrics (ratings, fines, SFF, ownership) from CMS Care Compare chain performance data (<a href="https://data.cms.gov/quality-of-care/nursing-home-chain-performance-measures/data" target="_blank" rel="noopener" style="color: #818cf8; text-decoration: underline; text-underline-offset: 2px;">CMS{f' ({get_chain_performance_source_label()})' if get_chain_performance_source_label() else ''}</a>). <a href="{care_compare_entity_url}" target="_blank" rel="noopener" style="color: #818cf8; text-decoration: underline; text-underline-offset: 2px;">View on CMS Care Compare</a></p>
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

_SFF_MONTH_TO_NUM = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}
_SFF_NUM_TO_LABEL = {
    1: 'Jan.', 2: 'Feb.', 3: 'Mar.', 4: 'Apr.',
    5: 'May', 6: 'Jun.', 7: 'Jul.', 8: 'Aug.',
    9: 'Sep.', 10: 'Oct.', 11: 'Nov.', 12: 'Dec.',
}


def _extract_sff_pdf_parts(filename: str) -> tuple[int, int] | None:
    """Extract (year, month_num) from SFF PDF names."""
    name = (filename or '').lower()
    match = re.search(r'candidate-list-([a-z]+)-(\d{4})', name)
    if not match:
        return None
    month_name, year_str = match.group(1), match.group(2)
    month_num = _SFF_MONTH_TO_NUM.get(month_name)
    if not month_num:
        return None
    return (int(year_str), month_num)


def _find_latest_sff_pdf_filename() -> str | None:
    """Find the newest SFF candidate list PDF in pbj-wrapped/public by month/year in filename."""
    public_dir = Path(__file__).resolve().parent / 'pbj-wrapped' / 'public'
    if not public_dir.exists():
        return None
    candidates = [p for p in public_dir.glob('sff-posting*candidate-list*.pdf') if p.is_file()]
    if not candidates:
        return None
    parsed = [(p, _extract_sff_pdf_parts(p.name)) for p in candidates]
    valid = [(p, parts) for p, parts in parsed if parts is not None]
    if valid:
        latest = max(valid, key=lambda x: x[1])[0]
        return latest.name
    # Fallback if naming format changes: pick most recently modified matching file.
    latest_by_mtime = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest_by_mtime.name


def get_sff_posting_display() -> str:
    """Return SFF posting display like 'Feb. 2026' based on latest local PDF."""
    latest_name = _find_latest_sff_pdf_filename()
    if not latest_name:
        return 'Unknown'
    parts = _extract_sff_pdf_parts(latest_name)
    if not parts:
        return latest_name
    year, month_num = parts
    return f"{_SFF_NUM_TO_LABEL.get(month_num, 'Unknown')} {year}"


def get_sff_source_url() -> str:
    """Return link to latest local SFF PDF when available; fallback to CMS SFF program page."""
    latest_name = _find_latest_sff_pdf_filename()
    if latest_name:
        return f"/{latest_name}"
    return 'https://www.cms.gov/medicare/health-safety-standards/certification-compliance/special-focus-facility-program'

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
    macpac_info = get_macpac_chart_info(state_code) if state_code else None
    if macpac_info is not None and macpac_info.get('line_value') is not None and macpac_info['line_value'] >= 1.5:
        min_display = macpac_info.get('min_display_str') or f'~{macpac_info["line_value"]:.2f}'
        state_min_phrase = f' State min. ({min_display} HPRD) may reflect calculated equivalents by <a href="{macpac_url}" target="_blank" rel="noopener" style="color:#818cf8;">MACPAC</a>.'
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
    
    # State standard (MACPAC) as badge only when relevant (> 1.5 HPRD); use range display (e.g. ~1.56-2.31) for range states
    state_standard_badge = ""
    state_standard_footer = ""
    _macpac_info = get_macpac_chart_info(state_code) if state_code else None
    if _macpac_info is not None and _macpac_info.get('line_value') is not None and _macpac_info['line_value'] > 1.5:
        label_short = _macpac_info.get('label_short') or f"{state_code} Min. ~{_macpac_info['line_value']:.2f}"
        state_standard_badge = f'<span class="pbj-state-min-badge" title="State minimum staffing benchmark (MACPAC estimate).">{label_short} HPRD</span>'

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
    rank_contract = get_rank_for_metric('Contract_Percentage')
    state_median_case_mix = get_state_median_case_mix_hprd(state_code, raw_quarter)
    rank_case_mix_median = get_rank_for_state_case_mix_median(state_code, raw_quarter)
    case_mix_median_display = format_metric_value(state_median_case_mix, 'Total_Nurse_HPRD', 'N/A') if state_median_case_mix is not None else 'N/A'
    state_rural_pct = get_state_rural_facility_share(state_code, raw_quarter)
    national_rural_pct = get_rural_shares_for_quarter(raw_quarter)[0]
    rank_rural_share = get_rank_for_state_rural_share(state_code, raw_quarter)
    rural_share_display = f'{state_rural_pct:.0f}%' if state_rural_pct is not None else 'N/A'
    rural_vs_us_display = (
        f'U.S. {national_rural_pct:.0f}%'
        if national_rural_pct is not None
        else 'N/A'
    )
    rural_rank_display = (
        f'#{rank_rural_share} of {total_states}'
        if rank_rural_share and total_states
        else 'N/A'
    )
    
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
            sff_section += f'<button type="button" role="tab" id="{tid}" aria-controls="{pid}" aria-selected="{aria_val}" class="sff-tab-btn" data-panel="{pid}" style="padding:0.4rem 0.75rem; font-size:0.875rem; background:rgba(15,23,42,0.6); color:rgba(226,232,240,0.85); border:1px solid rgba(129,140,248,0.35); border-radius:6px; cursor:pointer;">{tab_label} ({count})</button>'
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
                    residents_cell = '—'
                    try:
                        if residents and str(residents).strip():
                            residents_val = float(residents)
                            # float('nan') can appear in provider data; display em dash instead of crashing.
                            residents_cell = str(int(residents_val)) if residents_val == residents_val else '—'
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
    .sff-facilities-table th, .sff-facilities-table td {{ padding: 0.5rem 0.4rem; border: 1px solid rgba(129,140,248,0.25); text-align:left; }}
    .sff-facilities-table th {{ background: rgba(67, 56, 202, 0.22); color: #818cf8; font-weight:600; }}
    .sff-facilities-table tbody tr:nth-child(even) {{ background: rgba(15,23,42,0.4); }}
    .sff-tab-btn[aria-selected="true"] {{ background: rgba(99, 102, 241, 0.45) !important; border-color: #818cf8 !important; color: #e2e8f0 !important; font-weight: 600; box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.45); }}
    @media (max-width: 640px) {{ .sff-facilities-table {{ font-size: 0.8rem; }} .sff-facilities-table th, .sff-facilities-table td {{ padding: 0.35rem 0.25rem; }} }}
    </style>
    <p style="margin-top:0.75rem; font-size:0.85rem;"><a href="{html.escape(get_sff_source_url())}" target="_blank" rel="noopener">Source: CMS Special Focus Facility program</a></p>
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
        parts = [f"<strong>{html.escape(state_name)}</strong> reported <strong>{total_hprd_val} HPRD</strong> in {quarter}."]
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
    _state_hprd_body = build_hprd_floor_analogy_body(
        cur_hprd, state_na_hprd, state_name, census=avg_facility_census, context='state'
    )
    state_hprd_trigger, state_hprd_modal = render_hprd_means_explainer(
        total_hprd_val, _state_hprd_body, uid='state'
    )
    _state_share = render_takeaway_share_button(
        _state_page_url,
        f'{state_name} nursing home staffing',
        uid=str(state_code or 'state'),
    )
    # Badge order: HPRD (rank), RN HPRD, contract %, then state min
    rn_hprd_val = format_metric_value(get_val('RN_HPRD'), 'RN_HPRD', 'N/A')
    _bs = 'display: inline-block; padding: 2px 8px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; color: #e4e4e7; background: rgba(39,39,42,0.65); border: 1px solid #3f3f46; transition: all 0.2s ease;'
    state_total_hprd_badge_title = html.escape(
        'Average total nurse staffing hours per resident day (HPRD) for this state, including rank among states.',
        quote=True
    )
    state_rn_hprd_badge_title = html.escape(
        'Average registered nurse (RN) staffing hours per resident day (HPRD) for this state.',
        quote=True
    )
    state_contract_badge_title = html.escape(
        'Share of reported nursing hours delivered by contract staff in this state.',
        quote=True
    )
    state_rural_badge_html = render_state_rural_badge_html(state_code, raw_quarter)
    badges_line = (
        f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;">'
        f'<span style="{_bs}" title="{state_total_hprd_badge_title}">{total_hprd_val} HPRD (rank: {rank_total_nurse or "—"})</span>'
        f'<span class="pbj-badge-mobile-hide" style="{_bs}" title="{state_rn_hprd_badge_title}">{rn_hprd_val} RN HPRD</span>'
        f'<span class="pbj-badge-mobile-hide" style="{_bs}" title="{state_contract_badge_title}">{format_metric_value(get_val("Contract_Percentage"), "Contract_Percentage", "N/A")}% contract</span>'
        f'{state_standard_badge}{state_rural_badge_html}'
        f'</span>'
    )
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
          d3.select(svgEl).append("g").append("path").datum(feat).attr("d", path).attr("fill", "none").attr("stroke", "currentColor").attr("stroke-width", "2").attr("stroke-linecap", "round").attr("stroke-linejoin", "round").style("color", "#818cf8");
        }}).catch(fallback);
      }}).catch(fallback);
    }})();
    </script>
    '''
    _state_rank_phrase = (
        f'#{rank_total_nurse} of {total_states} states (total nurse HPRD)'
        if rank_total_nurse and total_states else None
    )
    _na_state = format_metric_value(get_val('Nurse_Assistant_HPRD'), 'Nurse_Assistant_HPRD', 'N/A')
    _state_contract = format_metric_value(get_val('Contract_Percentage'), 'Contract_Percentage', 'N/A')
    _lpn_state = format_metric_value(get_val('LPN_HPRD'), 'LPN_HPRD', 'N/A')
    _state_actions = render_takeaway_actions_row(state_hprd_trigger, _state_share, '')
    state_takeaway_card = f'''
<div id="pbj-takeaway" class="pbj-content-box pbj-takeaway" style="margin: 1rem 0; padding: 1rem; position: relative;">
{state_outline_inset}
<div class="pbj-takeaway-top">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(129,140,248,0.4); flex-shrink: 0;">
<div class="pbj-takeaway-top-main">
<div class="pbj-takeaway-header">PBJ Takeaway<span class="pbj-takeaway-title-name">: {html.escape(state_name)}</span></div>
<span class="pbj-takeaway-brand-pill">320 Consulting</span>
</div>
</div>
<p style="margin: 0.5rem 0 0.5rem 0;">{badges_line}</p>
{state_narrative}
{_state_actions}
{state_hprd_modal}
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
        <tr><td>Contract Staff Percentage</td><td>{format_metric_value(get_val('Contract_Percentage'), 'Contract_Percentage', 'N/A')}%</td><td>#{rank_contract} of {total_states if rank_contract and total_states else 'N/A'}</td></tr>
        <tr><td>Median Case-Mix HPRD (Acuity)</td><td>{case_mix_median_display}</td><td>#{rank_case_mix_median} of {total_states if rank_case_mix_median and total_states else 'N/A'}</td></tr>
        <tr><td>Rural facilities (share)</td><td>{rural_share_display}</td><td>{rural_vs_us_display} · {rural_rank_display}</td></tr>
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
    if _macpac_info is not None and _macpac_info.get('min_display_str'):
        seo_description_parts.append(f"State minimum: {_macpac_info['min_display_str']} HPRD.")
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
                    <span><span style="color:#e2e8f0;">PBJ</span><span style="color:#818cf8;">320</span></span>
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


# Per-CCN provider page HTML cache (TTL overridable for prod vs local tuning)
_PROVIDER_PAGE_CACHE = {}


def _provider_page_cache_ttl_seconds() -> int:
    """Seconds to keep rendered provider HTML in memory. Set PBJ_PROVIDER_PAGE_CACHE_TTL (0 = no caching when combined with skip flag off)."""
    raw = (os.environ.get('PBJ_PROVIDER_PAGE_CACHE_TTL') or '').strip()
    if raw:
        try:
            v = int(raw)
            return max(0, v)
        except ValueError:
            pass
    return 120


def _provider_page_cache_enabled():
    """Disable with env PBJ_SKIP_PROVIDER_PAGE_CACHE=1 so local edits show without waiting on TTL.
    Optional: PBJ_PROVIDER_PAGE_CACHE_TTL seconds (default 120) when cache is enabled."""
    v = (os.environ.get('PBJ_SKIP_PROVIDER_PAGE_CACHE') or '').strip().lower()
    return v not in ('1', 'true', 'yes', 'on')


PBJ_CASEMIX_UI_REV = '13'


def _provider_page_html_headers(*, cache_hit=False):
    h = {
        'Content-Type': 'text/html; charset=utf-8',
        # Provider HTML is generated from app logic + CSVs; avoid sticky browser disk cache while iterating locally.
        'Cache-Control': 'no-store, must-revalidate',
        'Pragma': 'no-cache',
        'X-PBJ-Provider-Cache': 'HIT' if cache_hit else 'MISS',
        'X-PBJ-CaseMix-UI': PBJ_CASEMIX_UI_REV,
    }
    try:
        h['X-PBJ-App-Mtime'] = str(int(os.path.getmtime(os.path.abspath(__file__))))
    except OSError:
        pass
    return h


def clear_provider_page_cache():
    """Drop in-memory provider HTML (e.g. after deploy or when debugging copy). Safe to call anytime."""
    _PROVIDER_PAGE_CACHE.clear()


# Canonical provider/state/entity pages (pbj320.com/provider/xxx, /state/pa, /entity/123)
def _provider_page_impl(ccn):
    from flask import abort
    if not HAS_PANDAS:
        return "Pandas not available. Provider pages require pandas.", 503
    prov = normalize_ccn(ccn)
    if not prov:
        abort(404)
    now = time.time()
    use_cache = _provider_page_cache_enabled()
    if use_cache:
        cached = _PROVIDER_PAGE_CACHE.get(prov)
        if cached is not None:
            cached_at, html = cached
            if now - cached_at < _provider_page_cache_ttl_seconds():
                return html, 200, _provider_page_html_headers(cache_hit=True)
    facility_df = load_facility_quarterly_for_provider(prov)
    if facility_df is None or facility_df.empty:
        abort(404)
    provider_info = load_provider_info()
    provider_info_row = provider_info.get(prov, {}) if isinstance(provider_info, dict) else {}
    html = generate_provider_page_html(prov, facility_df, provider_info_row)
    if use_cache:
        _PROVIDER_PAGE_CACHE[prov] = (now, html)
    _log_mem("route_provider_after")
    return html, 200, _provider_page_html_headers(cache_hit=False)

def _state_page_impl(state_slug):
    _log_mem("route_state_before")
    canonical_slug, state_code = resolve_state_slug(state_slug)
    if not canonical_slug or not state_code:
        from flask import abort
        abort(404)
    out = generate_state_page(state_code)
    _log_mem("route_state_after")
    return out

def _entity_page_impl(entity_id):
    from flask import abort
    _log_mem("route_entity_before")
    if not HAS_PANDAS:
        return "Pandas not available. Entity pages require pandas.", 503
    entity_name, facilities = load_entity_facilities(entity_id)
    # Final canonical guardrail at render edge: entity ID -> canonical display name.
    canonical_name = get_entity_name_from_search_index(entity_id)
    if canonical_name:
        entity_name = canonical_name
    if not facilities:
        abort(404)
    chain_perf = load_chain_performance()
    chain_row = chain_perf.get(int(entity_id)) if chain_perf else None
    html = generate_entity_page_html(entity_id, entity_name, facilities, chain_row=chain_row)
    _log_mem("route_entity_after")
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
    if _is_blocked_public_filename(state_slug):
        from flask import abort
        abort(404)
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
    known_routes = [
        'pbjpedia', 'wrapped', 'api', 'static', 'favicon.ico', 'robots.txt', 'sitemap.xml',
        'owner', 'owners', 'ownership', 'provider', 'state', 'entity', 'premium',
    ]
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
    _log_mem("generate_state_page_start")
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
    try:
        from pbj_format import format_metric_value as _fmt_metric
        state_hprd_display = _fmt_metric(latest_data.get('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')
    except Exception:
        state_hprd_display = str(latest_data.get('Total_Nurse_HPRD') or '')
    state_json_ld = _state_page_json_ld_scripts(
        state_name=state_name,
        state_code=state_code,
        state_slug=get_canonical_slug(state_code),
        page_url=canonical_url,
        quarter=str(latest_quarter or ''),
        quarter_display=formatted_quarter,
        total_hprd=state_hprd_display,
    )
    layout = get_pbj_site_layout(page_title, seo_description, canonical_url, extra_head=state_json_ld)
    html_content = layout['head'] + layout['nav'] + layout['content_open'] + content + layout['content_close']
    if HAS_CSRF and generate_csrf:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', generate_csrf())
    else:
        html_content = html_content.replace('__CSRF_TOKEN_PLACEHOLDER__', '')
    _log_mem("generate_state_page_end")
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
    if _is_blocked_public_filename(filename):
        from flask import abort
        abort(404)
    # Don't handle routes that are already defined (exact or prefix)
    if filename in [
        'insights', 'insights.html', 'about', 'newsletter', 'newsletter.html', 'pbj-sample',
        'pbj-ai-support', 'report', 'report.html', 'sitemap.xml', 'robots.txt', 'pbj-wrapped',
        'wrapped', 'sff', 'data', 'pbjpedia', 'owner', 'downloads', 'premium', 'contact',
        'data-sources', 'privacy', 'terms', 'public-trust.css',
    ]:
        from flask import abort
        abort(404)
    # Fallback: premium marketing assets (Render-safe paths; see premium_redirect_routes.py)
    if filename.startswith('premium-assets/'):
        from premium_redirect_routes import try_serve_premium_asset
        sub = filename[len('premium-assets/'):]
        served = try_serve_premium_asset(APP_ROOT, sub)
        if served is not None:
            return served
        from flask import abort
        abort(404)
    if filename.startswith('premium-samples/'):
        from premium_redirect_routes import try_serve_premium_asset
        sub = filename[len('premium-samples/'):]
        served = try_serve_premium_asset(APP_ROOT, f'samples/{sub}')
        if served is not None:
            return served
        from flask import abort
        abort(404)
    if filename.startswith('premium/'):
        from premium_redirect_routes import try_serve_premium_asset
        sub = filename[len('premium/'):]
        served = try_serve_premium_asset(APP_ROOT, sub)
        if served is not None:
            return served
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
_BLOCKED_PUBLIC_FILENAMES = {
    'provider_info_combined.csv',
    'provider_info_combined_latest.csv',
    'provider_info_combined_latest-old.csv',
    'data-sources.html',
    'privacy.html',
    'terms.html',
    'public-trust.css',
}


def _is_blocked_public_filename(path_value: str) -> bool:
    """Return True when filename is explicitly blocked from public serving."""
    try:
        base = os.path.basename(str(path_value or '')).strip().lower()
    except Exception:
        return False
    return base in _BLOCKED_PUBLIC_FILENAMES

@app.after_request
def apply_public_security_headers(response):
    """Baseline security headers for public pages (conservative; no CSP)."""
    try:
        proto = (request.headers.get('X-Forwarded-Proto') or request.scheme or '').lower()
        if proto == 'https':
            for name, value in SECURITY_HEADER_VALUES.items():
                if name not in response.headers:
                    response.headers[name] = value
    except Exception:
        pass
    return response


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


# Premium marketing page + assets — register after other /<slug> routes so /premium is not treated as a state.
register_premium_routes(app, APP_ROOT)

_log_mem("app_startup")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    # Keep local dev responsive when one expensive route is loading.
    app.run(host='0.0.0.0', port=port, threaded=True)
