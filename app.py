#!/usr/bin/env python3
# pyright: basic, reportGeneralTypeIssues=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportOptionalSubscript=false, reportCallIssue=false, reportAttributeAccessIssue=false, reportOperatorIssue=false
"""
Simple Flask app to serve static files with proper headers for Facebook scraper
Now with dynamic date support
"""
from flask import Flask, send_from_directory, send_file, render_template_string, render_template, jsonify, request, redirect
import os
import sys
import re
import csv
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
import time

try:
    import markdown  # type: ignore
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    markdown = None  # type: ignore
    print("Warning: markdown module not found. PBJpedia pages will not be available.")
    print("Install with: pip install markdown")

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas module not found. Dynamic PBJpedia pages will not be available.")
    print("Install with: pip install pandas")

# Import date utilities from local utils package (run from pbj-root so utils is on path)
from utils.date_utils import get_latest_data_periods, get_latest_update_month_year  # type: ignore[reportMissingImports]
from utils.seo_utils import get_seo_metadata  # type: ignore[reportMissingImports]

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

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
    """Get dynamic date information"""
    try:
        return get_latest_data_periods()
    except Exception as e:
        print(f"Warning: Could not get dynamic dates: {e}")
        return {
            'data_range': '2017-2025',
            'quarter_count': 33,
            'provider_info_latest': 'September 2025',
            'provider_info_previous': 'June 2025',
            'affiliated_entity_latest': 'July 2025',
            'current_year': 2025
        }

@app.route('/api/dates')
def api_dates():
    """API endpoint to get dynamic date information (used by SFF page for source text)"""
    data = get_dynamic_dates()
    # Add PBJ quarter and SFF posting for SFF page source line
    try:
        quarter_path = os.path.join(os.path.dirname(__file__), 'latest_quarter_data.json')
        if os.path.exists(quarter_path):
            with open(quarter_path, 'r', encoding='utf-8') as f:
                q = json.load(f)
            data['pbj_quarter_display'] = q.get('quarter_display', 'Q3 2025')
        else:
            data['pbj_quarter_display'] = 'Q3 2025'
    except Exception:
        data['pbj_quarter_display'] = 'Q3 2025'
    data['sff_posting'] = 'Dec. 2025'  # CMS SFF posting date; update when new list is published
    return jsonify(data)

@app.route('/search_index.json')
def search_index():
    """Serve search index for home page autocomplete (facility, entity, state)"""
    path = os.path.join(os.path.dirname(__file__), 'search_index.json')
    if os.path.isfile(path):
        return send_file(path, mimetype='application/json')
    return jsonify({'f': [], 'e': [], 's': []})


_SEARCH_INDEX_CACHE = None
_SEARCH_INDEX_AT = 0
_SEARCH_INDEX_TTL = 120

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

@app.route('/health')
def health():
    """Lightweight health check for Render. Side-effect free (best practice for public sites)."""
    return 'ok', 200

@app.route('/')
def index():
    return send_file('index.html', mimetype='text/html')

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


@app.route('/substack.png')
def serve_substack():
    return send_from_directory(APP_ROOT, 'substack.png', mimetype='image/png')


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
        with owner_app.test_request_context(f'/api/{api_path}',
                                             method=request.method,
                                             query_string=request.query_string.decode(),
                                             data=request.get_data(),
                                             content_type=request.content_type,
                                             headers=list(request.headers)):
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

@app.route('/owners/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/owner/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route('/ownership/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def owner_api_proxy(api_path):
    try:
        owner_app = get_owner_app()
    except Exception:
        return jsonify({'error': 'Owner dashboard unavailable'}), 503
    try:
        request_data = None
        if request.method in ['POST', 'PUT']:
            if request.is_json:
                request_data = request.get_json()
            else:
                request_data = request.get_data()
        headers = {k: v for k, v in request.headers if k.lower() != 'host'}
        with owner_app.test_request_context(
            f'/api/{api_path}',
            method=request.method,
            query_string=request.query_string.decode() if request.query_string else '',
            json=request_data if request.is_json and request_data else None,
            data=request_data if not request.is_json and request_data else None,
            content_type=request.content_type,
            headers=headers
        ):
            return owner_app.full_dispatch_request()
    except Exception as e:
        print(f"Error in owner_api_proxy for {api_path}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Proxy error: {str(e)}'}), 500

print("✓ Owner donor dashboard will load on first /owners visit (lazy); / and /health respond immediately")

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
    # State pages: canonical is /<slug>, but we list /state/<slug> so crawlers find them (redirect to canonical)
    for state_code in sorted(STATE_CODE_TO_NAME.keys()):
        slug = get_canonical_slug(state_code)
        urls.append(f'  <url><loc>{base}/state/{slug}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    # Provider and entity URLs from search_index.json (subset to keep sitemap reasonable)
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

def load_state_agency_contact():
    """Load state agency contact information from JSON"""
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
                        return contact_dict
                    elif isinstance(data, dict):
                        return data
            except Exception as e:
                print(f"Error loading state contact data from {path}: {e}")
                continue
    return {}

_LOAD_CSV_CACHE = {}
_LOAD_CSV_TTL = 120  # seconds

def load_csv_data(filename):
    """Load CSV data, trying multiple locations. Cached 2 min for provider/state/entity page speed."""
    now = time.time()
    if filename in _LOAD_CSV_CACHE:
        cached_at, data = _LOAD_CSV_CACHE[filename]
        if now - cached_at < _LOAD_CSV_TTL:
            return data
    possible_paths = [
        filename,
        os.path.join('pbj-wrapped', 'public', 'data', filename),
        os.path.join('pbj-wrapped', 'dist', 'data', filename),
        os.path.join('data', filename),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                if HAS_PANDAS:
                    out = pd.read_csv(path)
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

def format_quarter(quarter_str):
    """Convert quarter format from 2025Q2 to Q2 2025"""
    if not quarter_str:
        return "N/A"
    match = re.match(r'(\d{4})Q(\d)', str(quarter_str))
    if match:
        return f"Q{match.group(2)} {match.group(1)}"
    return str(quarter_str)

_LOAD_PROVIDER_INFO_CACHE = None
_LOAD_PROVIDER_INFO_AT = 0
_LOAD_PROVIDER_INFO_TTL = 120

def load_provider_info():
    """Load provider info data for facility details (ownership, entity, residents, city). Cached 2 min."""
    global _LOAD_PROVIDER_INFO_CACHE, _LOAD_PROVIDER_INFO_AT
    now = time.time()
    if _LOAD_PROVIDER_INFO_CACHE is not None and (now - _LOAD_PROVIDER_INFO_AT) < _LOAD_PROVIDER_INFO_TTL:
        return _LOAD_PROVIDER_INFO_CACHE
    provider_paths = [
        'provider_info_combined_latest.csv',
        'provider_info_combined.csv',
        'pbj-wrapped/public/data/provider_info_combined.csv',
    ]
    
    if not HAS_PANDAS:
        return {}
    
    for path in provider_paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                # Create lookup dict by PROVNUM (use latest quarter if multiple)
                provider_dict = {}
                # Sort by quarter to get latest
                if 'CY_Qtr' in df.columns:
                    df = df.sort_values('CY_Qtr', ascending=False)
                for _, row in df.iterrows():
                    raw = row.get('ccn', row.get('PROVNUM', ''))
                    provnum = str(raw).strip().replace('.0', '')
                    if provnum:
                        provnum = provnum.zfill(6)
                        # Only keep first (latest) entry per PROVNUM
                        if provnum not in provider_dict:
                            eid_raw = row.get('chain_id', row.get('affiliated_entity_id', ''))
                            try:
                                entity_id = int(float(eid_raw)) if eid_raw else None
                            except (TypeError, ValueError):
                                entity_id = None
                            _sv = row.get('state', row.get('STATE', ''))
                            state_val = (str(_sv) if _sv else '').strip().upper()[:2]
                            provider_dict[provnum] = {
                                'city': row.get('CITY', row.get('city', '')),
                                'ownership_type': row.get('ownership_type', ''),
                                'avg_residents_per_day': row.get('avg_residents_per_day', ''),
                                'entity_name': row.get('entity_name', row.get('affiliated_entity', '')),
                                'provider_name': row.get('provider_name', row.get('PROVNAME', '')),
                                'state': state_val.strip().upper()[:2],
                                'entity_id': entity_id,
                                'reported_total_nurse_hrs_per_resident_per_day': row.get('reported_total_nurse_hrs_per_resident_per_day'),
                                'reported_rn_hrs_per_resident_per_day': row.get('reported_rn_hrs_per_resident_per_day'),
                                'reported_na_hrs_per_resident_per_day': row.get('reported_na_hrs_per_resident_per_day'),
                                'case_mix_total_nurse_hrs_per_resident_per_day': row.get('case_mix_total_nurse_hrs_per_resident_per_day'),
                                'case_mix_rn_hrs_per_resident_per_day': row.get('case_mix_rn_hrs_per_resident_per_day'),
                                'case_mix_na_hrs_per_resident_per_day': row.get('case_mix_na_hrs_per_resident_per_day'),
                            }
                _LOAD_PROVIDER_INFO_CACHE = provider_dict
                _LOAD_PROVIDER_INFO_AT = time.time()
                return provider_dict
            except Exception as e:
                print(f"Error loading provider info from {path}: {e}")
                continue
    return {}

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
<meta property="og:title" content="{page_title}">
<meta property="og:description" content="{meta_description}">
<meta property="og:url" content="{canon}">
<meta property="og:type" content="website">
<link rel="canonical" href="{canon}">
<link rel="icon" type="image/png" href="/pbj_favicon.png">
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
.pbj-table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 1rem 0; border-radius: 8px; border: 1px solid rgba(59,130,246,0.2); }}
.pbj-table-wrap table {{ margin: 0; min-width: 400px; }}
.pbj-cta-premium {{ margin-top: 1.5rem; padding: 1rem 1.25rem; background: rgba(30,64,175,0.2); border: 1px solid rgba(96,165,250,0.3); border-radius: 10px; font-size: 0.95rem; color: rgba(226,232,240,0.9); }}
.pbj-cta-premium a {{ color: #93c5fd; font-weight: 600; }}
.custom-report-cta {{ margin: 1.5rem 0; padding: 0.9rem 1.1rem; background: rgba(15,23,42,0.5); border: 1px solid rgba(59,130,246,0.2); border-radius: 8px; max-width: 640px; font-size: 0.875rem; color: rgba(226,232,240,0.9); line-height: 1.45; }}
.custom-report-cta .custom-report-cta-header {{ margin: 0; font-size: 0.9rem; font-weight: 600; color: #e2e8f0; }}
.custom-report-cta .custom-report-cta-sub {{ margin: 0.35rem 0 0.6rem 0; font-size: 0.8rem; color: rgba(226,232,240,0.8); }}
.custom-report-cta .custom-report-cta-links {{ margin: 0.4rem 0; font-size: 0.85rem; }}
.custom-report-cta .custom-report-cta-links a {{ color: #93c5fd; font-weight: 500; text-decoration: none; }}
.custom-report-cta .custom-report-cta-links a:hover {{ text-decoration: underline; color: #bfdbfe; }}
.custom-report-cta .custom-report-cta-dot {{ color: rgba(226,232,240,0.5); margin: 0 0.2rem; font-weight: 400; }}
.custom-report-cta .custom-report-cta-footer {{ margin: 0.5rem 0 0 0; font-size: 0.75rem; color: rgba(226,232,240,0.6); }}
.custom-report-cta .custom-report-cta-sms {{ margin-top: 0.4rem; font-size: 0.8rem; color: rgba(226,232,240,0.75); }}
.custom-report-cta .custom-report-cta-sms a {{ color: #93c5fd; font-weight: 500; }}
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
}}
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
        <a href="https://pbjdashboard.com/" class="nav-link">Dashboard</a>
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
    <p><strong>320 Consulting</strong> — Turning Spreadsheets into Stories</p>
    <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin-top: 0.5rem;">
      <a href="mailto:eric@320insight.com" title="Email: eric@320insight.com"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity: 0.8;"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#60a5fa"/></svg></a>
      <a href="sms:+19298084996" title="SMS: (929) 804-4996"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity: 0.8;"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" fill="#60a5fa"/></svg></a>
      <a href="https://www.linkedin.com/in/eric-goldwein/" target="_blank" rel="noopener" title="LinkedIn"><img src="/LI-In-Bug.png" alt="LinkedIn" style="width: 24px; height: 24px; object-fit: contain; opacity: 0.8;"></a>
      <a href="https://320insight.substack.com/" target="_blank" rel="noopener" title="The 320 Newsletter"><img src="/substack.png" alt="Substack" style="width: 24px; height: 24px; object-fit: contain; opacity: 0.8;"></a>
    </div>
  </footer>
  <script>
  (function(){ var t=document.getElementById('navToggle'); var m=document.getElementById('navMenu'); if(t&&m){ t.addEventListener('click',function(){ m.classList.toggle('active'); t.classList.toggle('active'); document.body.style.overflow=m.classList.contains('active')?'hidden':''; }); } })();
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
    header_text = "Need deeper staffing context?"
    sub_text = "Independent analysis from CMS payroll-based journal (PBJ) data for legal, media, and policy use."
    footer_text = ""

    def mailto(subject, body):
        return f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"

    if context == 'facility':
        facility_name = kwargs.get('facility_name', '') or 'This facility'
        ccn = kwargs.get('ccn', '') or ''
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
        link_att = mailto(subj_att, body_att)
        link_media = mailto(subj_media, body_media)
        link_adv = mailto(subj_adv, body_adv)
        sms_body = f"I'm reviewing {facility_name} (CCN {ccn}) and would like to connect regarding its staffing data. {page_url}"
        sms_href = f"sms:+19298044996?body={quote(sms_body)}"
        show_email_text_row = True

    elif context == 'state':
        state_name = kwargs.get('state_name', '') or 'this state'
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
        link_att = mailto(subj_att, body_att)
        link_media = mailto(subj_media, body_media)
        link_adv = mailto(subj_adv, body_adv)
        sms_href = None
        show_email_text_row = True

    elif context == 'entity':
        entity_name = kwargs.get('entity_name', '') or 'this entity'
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
        link_att = mailto(subj_att, body_att)
        link_media = mailto(subj_media, body_media)
        link_adv = mailto(subj_adv, body_adv)
        sms_href = None
        show_email_text_row = True

    else:
        return ''

    links_html = f'<a href="{link_att}">Attorney</a><span class="custom-report-cta-dot"> · </span><a href="{link_media}">Media</a><span class="custom-report-cta-dot"> · </span><a href="{link_adv}">Advocate</a>'
    email_text_row = ''
    if show_email_text_row:
        if sms_href:
            email_text_row = f'<div class="custom-report-cta-sms"><a href="mailto:{email}">Email</a><span class="custom-report-cta-dot"> · </span><a href="{sms_href}">Text</a></div>'
        else:
            email_text_row = f'<div class="custom-report-cta-sms"><a href="mailto:{email}">Email</a><span class="custom-report-cta-dot"> · </span>Text</div>'

    footer_block = f'<p class="custom-report-cta-footer">{footer_text}</p>' if footer_text else ''
    return f'''<div class="custom-report-cta">
<p class="custom-report-cta-header">{header_text}</p>
<p class="custom-report-cta-sub">{sub_text}</p>
<div class="custom-report-cta-links">{links_html}</div>
{email_text_row}
{footer_block}</div>'''


def render_methodology_block():
    """Return collapsible Methodology & Data Transparency block for facility, state, entity pages."""
    return '''<details class="pbj-details">
<summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Methodology &amp; data</summary>
<div class="pbj-details-content">
<p style="margin: 0 0 0.6rem 0; font-size: 0.9rem; color: rgba(226,232,240,0.9);">This dashboard uses CMS Payroll-Based Journal (PBJ) data (2017–2025), along with other public datasets (Provider Information, Affiliated Entity). State staffing standards via MACPAC (2022).</p>
<p style="margin: 0 0 0.35rem 0; font-weight: 600; font-size: 0.9rem; color: #93c5fd;">Metrics</p>
<ul style="font-size: 0.875rem; color: rgba(226,232,240,0.88); margin: 0 0 0.75rem 0;">
<li><strong>Hours Per Resident Day (HPRD):</strong> Total staff hours ÷ average residents. Example: 350 hours for 100 residents = 3.5 HPRD.</li>
<li><strong>Direct Care</strong> (excl. Admin, DON): Hours per resident day for direct care staff only (RN, LPN, CNA, NAtrn, MedAide), excluding administrative and supervisory roles.</li>
<li><strong>Contract Staff %:</strong> Share of hours provided by contract staff.</li>
<li><strong>Census:</strong> Average number of residents during the period.</li>
</ul>
<p style="margin: 0 0 0.75rem 0; font-size: 0.85rem; color: rgba(226,232,240,0.8);">Note: Some states set minimums (e.g., NJ, CA, NY at 3.5 HPRD) while a federal 3.48 minimum was recently overturned (2025). A 2001 federal study found 4.1 HPRD linked to better outcomes. Staffing needs vary by resident acuity (case-mix), day, and shift. Estimates on PBJ Takeaway assume roughly 60% of staff are CNAs.</p>
<p style="margin: 0 0 0.35rem 0; font-weight: 600; font-size: 0.9rem; color: #93c5fd;">Data transparency</p>
<p style="margin: 0; font-size: 0.875rem; color: rgba(226,232,240,0.88);">The PBJ Dashboard pulls directly from CMS data and is carefully vetted for accuracy. Still, sometimes a bug sneaks into the jelly. That could mean: a systemic CMS data reporting issue (e.g., Q2 2017 contract staffing, missing data in 2020 due to COVID) or there could be a coding error on our part. If you spot something that looks off, please let me know <a href="mailto:eric@320insight.com" style="color: #93c5fd;">eric@320insight.com</a> so I can set things right.</p>
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

def load_facility_quarterly_for_provider(ccn):
    """Load facility quarterly metrics for one provider (PROVNUM). Returns DataFrame or None."""
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
    pct_total = int(round(100 * count_le_total / n))
    if pct_total > 100:
        pct_total = 100
    pct_rn = None
    if facility_hprd_rn is not None and 'RN_HPRD' in sub.columns:
        rn_vals = sub['RN_HPRD'].dropna()
        if len(rn_vals) >= 2:
            count_le_rn = (rn_vals <= facility_hprd_rn).sum()
            pct_rn = int(round(100 * count_le_rn / len(rn_vals)))
            if pct_rn > 100:
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

def _provider_charts_chartjs_data(facility_df, state_code, reported_total, reported_rn, reported_na, case_mix_total, case_mix_rn, case_mix_na):
    """Build JSON-serializable chart data for Chart.js: reported vs case-mix bar + 4 longitudinal line charts."""
    out = {}
    out['reportedCaseMix'] = {
        'labels': ['Total', 'RN', 'Nurse aide'],
        'reported': [float(reported_total or 0), float(reported_rn or 0), float(reported_na or 0)],
        'caseMix': None
    }
    if case_mix_total is not None or case_mix_rn is not None or case_mix_na is not None:
        out['reportedCaseMix']['caseMix'] = [float(case_mix_total or 0), float(case_mix_rn or 0), float(case_mix_na or 0)]
    if facility_df is None or facility_df.empty or not HAS_PANDAS:
        return out
    df = facility_df.sort_values('CY_Qtr').copy()
    quarters = df['CY_Qtr'].astype(str).tolist()
    out['totalHprd'] = {
        'quarters': quarters,
        'total': df['Total_Nurse_HPRD'].fillna(0).tolist(),
        'direct': (df['Nurse_Care_HPRD'] if 'Nurse_Care_HPRD' in df.columns else pd.Series(0, index=df.index)).fillna(0).tolist(),
        'macpac': get_macpac_hprd_for_state(state_code)
    }
    out['rnHprd'] = {
        'quarters': quarters,
        'rn': df['RN_HPRD'].fillna(0).tolist(),
        'rnDirect': (df['RN_Care_HPRD'] if 'RN_Care_HPRD' in df.columns else pd.Series(0, index=df.index)).fillna(0).tolist()
    }
    out['contract'] = {'quarters': quarters, 'facility': df['Contract_Percentage'].fillna(0).tolist(), 'stateMedian': []}
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
                out['contract']['stateMedian'] = [float(medians.get(q)) if q in medians.index and pd.notna(medians.get(q)) else None for q in quarters]
    col = 'avg_daily_census' if 'avg_daily_census' in df.columns else 'Avg_Daily_Census'
    out['census'] = {'quarters': quarters, 'census': (df[col] if col in df.columns else pd.Series(0, index=df.index)).fillna(0).tolist()}
    return out

def _provider_charts_html(chart_data, facility_name=''):
    """Render all provider charts with Chart.js: bar (Reported vs Case-Mix) + 4 line charts. Facility name in titles for screenshot/share."""
    import json
    try:
        data_esc = json.dumps(chart_data).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    except Exception:
        data_esc = '{}'
    title_prefix = (facility_name + ' – ') if facility_name else ''
    return '''
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="chartReportedCaseMix" height="260"></canvas></div>
<div class="section-header">''' + title_prefix + '''Total staffing over time</div>
<p class="pbj-subtitle">Total and direct care hours per resident day.</p>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="chartTotalHprd" height="260"></canvas></div>
<div class="section-header">''' + title_prefix + '''RN staffing over time</div>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="chartRN" height="260"></canvas></div>
<div class="section-header">''' + title_prefix + '''Census over time</div>
<p class="pbj-subtitle">Average daily census by quarter.</p>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="chartCensus" height="260"></canvas></div>
<div class="section-header">''' + title_prefix + '''Contract staff % over time</div>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="chartContract" height="260"></canvas></div>
<script>
(function(){
  var d = ''' + data_esc + ''';
  var textColor = 'rgba(226,232,240,0.9)';
  var gridColor = 'rgba(148,163,184,0.2)';
  if (typeof Chart !== 'undefined') { Chart.defaults.color = textColor; Chart.defaults.borderColor = gridColor; }
  function xLabels(quarters) {
    if (!quarters || !quarters.length) return [];
    var n = quarters.length;
    return quarters.map(function(q, i) {
      var y = q.substring(0,4), qtr = (q.substring(4) || '').toUpperCase();
      if (qtr === 'Q1') return y;
      var prevY = i > 0 ? quarters[i-1].substring(0,4) : null;
      if (y !== prevY) return y;
      return '';
    });
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
        plugins: { title: { display: true, text: 'Reported vs Case-Mix (Acuity)', color: textColor }, legend: { labels: { color: textColor } } },
        scales: { y: { beginAtZero: true, ticks: { color: textColor }, grid: { color: gridColor } }, x: { ticks: { color: textColor, maxTicksLimit: 10, autoSkip: true, font: { size: 11 } }, grid: { color: gridColor } } }
      }
    });
  }
  function makeLine(id, labels, datasets, yTitle, quarters) {
    var ctx = document.getElementById(id);
    if (!ctx) return;
    var opts = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor } },
        tooltip: {
          callbacks: {
            title: function(context) {
              if (quarters && context[0] && context[0].dataIndex < quarters.length) {
                var q = quarters[context[0].dataIndex];
                if (q && q.length >= 6) return q.substring(5) + ' ' + q.substring(0,4);
              }
              return context[0].label || '';
            }
          }
        }
      },
        scales: {
        y: { beginAtZero: false, ticks: { color: textColor }, grid: { color: gridColor }, title: { display: !!yTitle, text: yTitle || '', color: textColor } },
        x: { ticks: { color: textColor, maxTicksLimit: 14, autoSkip: true, font: { size: 11 } }, grid: { color: gridColor } }
      }
    };
    new Chart(ctx.getContext('2d'), { type: 'line', data: { labels: labels, datasets: datasets }, options: opts });
  }
  var rc = d.reportedCaseMix;
  if (rc && rc.labels) makeBar('chartReportedCaseMix', rc.labels, rc.reported || [0,0,0], rc.caseMix);
  var th = d.totalHprd;
  if (th && th.quarters && th.quarters.length) {
    var ds = [{ label: 'Total HPRD', data: th.total, borderColor: '#1e40af', tension: 0.3, fill: false },
               { label: 'Direct care HPRD', data: th.direct, borderColor: '#6366f1', borderDash: [5,5], tension: 0.3, fill: false }];
    if (th.macpac != null && typeof th.macpac === 'number') {
      var macpacArr = th.quarters.map(function(){ return th.macpac; });
      ds.push({ label: 'State standard', data: macpacArr, borderColor: '#dc2626', borderDash: [4,4], tension: 0, fill: false });
    }
    makeLine('chartTotalHprd', xLabels(th.quarters), ds, 'Hours per resident day', th.quarters);
  }
  var rn = d.rnHprd;
  if (rn && rn.quarters && rn.quarters.length) makeLine('chartRN', xLabels(rn.quarters), [
    { label: 'RN HPRD', data: rn.rn, borderColor: '#1e40af', tension: 0.3, fill: false },
    { label: 'Direct care RN HPRD', data: rn.rnDirect, borderColor: '#6366f1', borderDash: [5,5], tension: 0.3, fill: false }
  ], 'Hours per resident day', rn.quarters);
  var ce = d.census;
  if (ce && ce.quarters && ce.quarters.length) makeLine('chartCensus', xLabels(ce.quarters), [{ label: 'Avg daily census', data: ce.census, borderColor: '#1e40af', tension: 0.3, fill: false }], 'Census', ce.quarters);
  var co = d.contract;
  if (co && co.quarters && co.quarters.length) {
    var cds = [{ label: 'Facility contract %', data: co.facility, borderColor: '#1e40af', tension: 0.3, fill: false }];
    makeLine('chartContract', xLabels(co.quarters), cds, 'Contract %', co.quarters);
  }
})();
</script>'''

def generate_provider_page_html(ccn, facility_df, provider_info_row):
    """Generate HTML for facility (provider) page per pbj-page-guide: header block, key metrics, longitudinal chart, basic info, full table, summary."""
    try:
        from pbj_format import format_metric_value, format_quarter_display
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{float(v):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
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
        facility_name = f"Facility {prov}"
    facility_name = capitalize_facility_name(facility_name)
    city = (provider_info_row or {}).get('city', '') or ''
    city = capitalize_city_name(city) if city else ''
    if not facility_df.empty and 'COUNTY_NAME' in facility_df.columns:
        county = (str(facility_df.iloc[0].get('COUNTY_NAME') or '')).strip() or '—'
    state_name = STATE_CODE_TO_NAME.get(state_code, state_code)
    canonical_slug = get_canonical_slug(state_code) if state_code else ''
    latest = facility_df.sort_values('CY_Qtr', ascending=False).iloc[0] if not facility_df.empty else None
    raw_quarter = latest.get('CY_Qtr', '') if latest is not None else ''
    quarter_display = format_quarter_display(raw_quarter)
    def get_val(key, default=None):
        if latest is None:
            return default
        v = latest.get(key, default)
        return default if (v is None or (isinstance(v, float) and pd.isna(v))) else v
    entity_name = (provider_info_row or {}).get('entity_name', '') or ''
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
    ownership_short = abbreviate_ownership(ownership_raw) or '—'
    base_url = 'https://pbj320.com'
    state_link = f'<a href="/{canonical_slug}">{state_name}</a>' if canonical_slug else state_name
    entity_link = f'<a href="/entity/{entity_id}">{entity_name}</a>' if entity_id and entity_name else (entity_name or '')
    location_subtitle = f"{city}, {state_link} &bull; {ownership_short}" if city else f"{state_link} &bull; {ownership_short}"
    meta_parts = [p for p in [f'Operator: {entity_link}' if entity_id and entity_name else None] if p and p != '—']
    meta_line = ' &bull; '.join(meta_parts) if meta_parts else ''
    # Case-mix and reported from most recent provider info only (no provider_info_combined for this public tool)
    pi = provider_info_row or {}
    def _safe(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    reported_total = get_val('Total_Nurse_HPRD') if get_val('Total_Nurse_HPRD') is not None else _safe(pi.get('reported_total_nurse_hrs_per_resident_per_day'))
    reported_rn = get_val('RN_HPRD') if get_val('RN_HPRD') is not None else _safe(pi.get('reported_rn_hrs_per_resident_per_day'))
    reported_na = get_val('Nurse_Assistant_HPRD') if get_val('Nurse_Assistant_HPRD') is not None else _safe(pi.get('reported_na_hrs_per_resident_per_day'))
    case_mix_total = _safe(pi.get('case_mix_total_nurse_hrs_per_resident_per_day'))
    case_mix_rn = _safe(pi.get('case_mix_rn_hrs_per_resident_per_day'))
    case_mix_na = _safe(pi.get('case_mix_na_hrs_per_resident_per_day'))
    census_num = _safe(pi.get('avg_residents_per_day'))
    if census_num is None and latest is not None:
        census_num = _safe(latest.get('avg_daily_census'))
    census_int = int(round(census_num)) if census_num is not None else None
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
    methodology = 'Case-mix (acuity) HPRD is the staffing level expected for this facility’s acuity. Positive delta = above; negative = below.'
    casemix_deviation_line = ''
    if case_mix_total is not None and (reported_total or 0) is not None and case_mix_total > 0:
        pct_of_casemix = round(100 * (reported_total or 0) / case_mix_total)
        casemix_deviation_line = f'Reported staffing is {pct_of_casemix}% of case-mix (acuity).'
    reported_vs_casemix_section = f'<div class="section-header">Reported vs. Case-Mix (Acuity)</div><p class="pbj-subtitle" style="font-style: italic; margin-bottom: 8px;">{methodology}</p>'
    if casemix_deviation_line:
        reported_vs_casemix_section += f'<p class="pbj-percentile" style="margin-bottom: 8px;">{casemix_deviation_line}</p>'
    chart_section = _provider_charts_html(chart_data, facility_name=facility_name)
    hprd_val = format_metric_value(reported_total or get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')
    casemix_str = format_metric_value(case_mix_total, 'Total_Nurse_HPRD') if case_mix_total is not None else '—'
    above_below_state = _classify(reported_total or 0, None)
    above_below_casemix = _classify(reported_total or 0, case_mix_total)
    residents_per_staff = round((1 / (reported_total or 0)), 1) if reported_total and reported_total > 0 else '—'
    put_another_way = ''
    if census_int and reported_total and reported_total > 0:
        # FTE-equivalent staff: total hours per day = HPRD * census; staff ≈ hours / 8 per day
        total_staff = max(1, int(round((census_int * (reported_total or 0)) / 8)))
        aides = max(0, int(round(total_staff * (float(reported_na or 0) / (reported_total or 1)))))
        floor_staff = max(1, int(round(30 * (reported_total or 0) / 8)))
        floor_aides = max(0, int(round(30 * (reported_na or 0) / 8)))
        put_another_way = f'On a typical <strong>30-bed floor</strong> at {facility_name} you’d see about <strong>{floor_staff}</strong> staff, including ~{floor_aides} nurse aides. For the entire {census_int:,}-resident facility, that’s about {total_staff:,} total staff, including ~{aides:,} nurse aides.'
    else:
        put_another_way = f'Staffing counts depend on census and HPRD; see key metrics above for this facility’s reported hours per resident day.'
    narrative = f'<strong>{facility_name}</strong>’s reported <strong>{hprd_val} hours per resident day</strong> (≈ {residents_per_staff} residents per total staff) in {quarter_display}. This level is {above_below_casemix} its case-mix (acuity) {casemix_str} HPRD.'
    if case_mix_total is None:
        narrative = f'<strong>{facility_name}</strong>’s reported <strong>{hprd_val} hours per resident day</strong> in {quarter_display}. CMS did not report case-mix data for this quarter.'
    risk_flag, risk_reason = get_facility_risk_from_search_index(prov)
    sff_facilities_list = load_sff_facilities()
    is_sff = any((str(f.get('provider_number') or '').strip().zfill(6)) == prov for f in (sff_facilities_list or []))
    if risk_flag and risk_reason:
        risk_badge_label = risk_reason
    elif risk_flag:
        risk_badge_label = 'High risk'
    elif is_sff:
        risk_badge_label = 'SFF'
    else:
        risk_badge_label = ''
    risk_badge = ('<span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(220,38,38,0.25); color: #fca5a5; border: 1px solid rgba(220,38,38,0.4);">' + risk_badge_label + '</span>') if risk_badge_label else ''
    contract_pct = format_metric_value(get_val("Contract_Percentage"), "Contract_Percentage")
    residents_str = f"{census_int} Residents" if census_int else "— Residents"
    state_percentile_total, _ = get_facility_state_percentile(prov, state_code, raw_quarter, reported_total or 0, reported_rn)
    percentile_line = ''
    if state_percentile_total is not None:
        if state_percentile_total <= 50:
            percentile_line = f'<div class="pbj-percentile">State percentile (Total Nurse): Bottom {state_percentile_total}%</div>'
        else:
            percentile_line = f'<div class="pbj-percentile">State percentile (Total Nurse): Top {100 - state_percentile_total}%</div>'
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
                        yoy_line = f'<div class="pbj-percentile">Year-over-year change (Total Nurse HPRD): {sign}{abs(yoy_change):.2f} ({sign}{abs(yoy_pct):.0f}%)</div>'
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
                facility_count = len(ent_facilities)
                state_count = len(states_seen)
                entity_summary_html = f'<div class="pbj-entity-summary">Part of a {facility_count}-facility network operating in {state_count} state{"s" if state_count != 1 else ""}. {below_count} facilities report staffing below their respective state averages this quarter.</div>'
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
    pbj_takeaway_card = f'''
<div id="pbj-takeaway" class="pbj-content-box" style="margin: 1rem 0; padding: 1rem; border: 1px solid rgba(59,130,246,0.3); border-radius: 8px;">
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(96,165,250,0.4); flex-shrink: 0;">
<div style="font-size: 16px; font-weight: bold; color: #e2e8f0;">PBJ Takeaway: {facility_name}</div>
</div>
<p style="margin: 0.5rem 0 0.5rem 0;">{risk_badge}<span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #e2e8f0;">{hprd_val} HPRD</span><span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #e2e8f0;">{state_code}: {state_hprd_placeholder} HPRD</span><span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #e2e8f0;">{residents_str}</span><span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #e2e8f0;">{contract_pct}% contract</span>{'<span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.2);"><a href="/entity/' + str(entity_id) + '" style="color: #93c5fd;">' + (entity_name or 'Entity') + '</a></span>' if entity_id and entity_name else ''}</p>
{percentile_line}
{entity_summary_html}
<p style="margin: 0.5rem 0; font-size: 0.95rem; color: rgba(226,232,240,0.95);">{narrative}</p>
<p style="margin: 0.5rem 0 0 0; color: #e2e8f0;"><strong>Put another way…</strong> {put_another_way}</p>
<div style="margin-top: 0.35rem; margin-bottom: 0.15rem; display: flex; justify-content: flex-end;"><span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(96,165,250,0.4);">320 Consulting</span></div>
</div>'''
    seo_desc = f"{facility_name} nursing home staffing: {format_metric_value(get_val('Total_Nurse_HPRD'), 'Total_Nurse_HPRD')} HPRD total nurse staffing in {quarter_display}."
    page_title = f"{facility_name} | Nursing Home Staffing | PBJ320"
    layout = get_pbj_site_layout(page_title, seo_desc, f"{base_url}/provider/{prov}")
    facility_page_url = f"{base_url}/provider/{prov}"
    care_compare_facility_url = f'https://www.medicare.gov/care-compare/details/nursing-home/{prov}/view-all/?state={state_code}' if state_code else ''
    custom_report_cta_html = render_custom_report_cta('facility', facility_page_url, facility_name=facility_name, ccn=prov, state_name=state_name, entity_name=entity_name or '')
    subtitle_one_line = f"{location_subtitle}{' • ' + meta_line if meta_line else ''}"
    inner = f"""
<h1>{facility_name}</h1>
<p class="pbj-subtitle">{subtitle_one_line}</p>

{pbj_takeaway_card}

{reported_vs_casemix_section}

{chart_section}

{custom_report_cta_html}

{render_methodology_block()}

<p style="margin-top: 1.5rem; color: rgba(226,232,240,0.85);"><a href="/">Home</a> &middot; <a href="/{canonical_slug}">{state_name} staffing</a>{(' &middot; ' + entity_link) if entity_id and entity_name else ''}</p>
<p style="margin-top: 0.5rem; font-size: 0.8rem; color: rgba(226,232,240,0.6);">Staffing from CMS payroll-based journal (PBJ) data.{' <a href="' + care_compare_facility_url + '" target="_blank" rel="noopener" style="color: rgba(148,163,184,0.95);">View on Medicare Care Compare</a>' if care_compare_facility_url else ''}</p>"""
    return layout['head'] + layout['nav'] + layout['content_open'] + inner + layout['content_close']

def load_entity_facilities(entity_id):
    """Load entity name and list of facilities (ccn, name, city, state, latest metrics) for chain_id/affiliated_entity_id.
    Returns (entity_name, list of dicts). Empty list if not found."""
    if not HAS_PANDAS:
        return '', []
    for path in ['provider_info_combined_latest.csv', 'provider_info_combined.csv', 'pbj-wrapped/public/data/provider_info_combined.csv']:
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path)
            eid_col = 'chain_id' if 'chain_id' in df.columns else 'affiliated_entity_id'
            name_col = 'chain_name' if 'chain_id' in df.columns else 'affiliated_entity_name'
            if eid_col not in df.columns:
                continue
            df = df.copy()
            df[eid_col] = pd.to_numeric(df[eid_col], errors='coerce')
            sub = df[df[eid_col] == int(entity_id)]
            if sub.empty:
                return '', []
            entity_name = (sub[name_col].iloc[0] if name_col in sub.columns else '') or f"Entity {entity_id}"
            entity_name = str(entity_name).strip()
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
            # Attach latest-quarter metrics from facility_quarterly_metrics
            fq = load_csv_data('facility_quarterly_metrics.csv')
            if fq is not None and isinstance(fq, pd.DataFrame) and 'PROVNUM' in fq.columns:
                fq = fq.copy()
                fq['PROVNUM'] = fq['PROVNUM'].astype(str).str.strip().str.zfill(6)
                latest_q = fq['CY_Qtr'].max() if 'CY_Qtr' in fq.columns else None
                if latest_q:
                    fq_latest = fq[fq['CY_Qtr'] == latest_q]
                    for fac in facilities:
                        row = fq_latest[fq_latest['PROVNUM'] == fac['ccn']]
                        if not row.empty:
                            r = row.iloc[0]
                            fac['Total_Nurse_HPRD'] = r.get('Total_Nurse_HPRD')
                            fac['RN_HPRD'] = r.get('RN_HPRD')
                            fac['Contract_Percentage'] = r.get('Contract_Percentage')
                            fac['quarter'] = latest_q
            return entity_name, facilities
        except Exception as e:
            print(f"Error loading entity {entity_id} from {path}: {e}")
            continue
    return '', []

def generate_entity_page_html(entity_id, entity_name, facilities):
    """Generate HTML for entity (chain) page. facilities: list of dicts with ccn, name, city, state, optional metrics."""
    try:
        from pbj_format import format_metric_value, get_metric_label
    except ImportError:
        format_metric_value = lambda v, k, d='N/A': f"{float(v):.2f}" if v is not None and not (isinstance(v, float) and __import__('math').isnan(v)) else d
        get_metric_label = lambda k: k.replace('_', ' ')
    base_url = 'https://pbj320.com'
    n = len(facilities)
    subtitle = f"{n} nursing home{'s' if n != 1 else ''}"
    rows = []
    for fac in facilities:
        ccn = fac.get('ccn', '')
        name = (fac.get('name') or '').strip() or f"Facility {ccn}"
        city = (fac.get('city') or '').strip()
        state = (fac.get('state') or '').strip().upper()[:2]
        state_name = STATE_CODE_TO_NAME.get(state, state)
        canonical_slug = get_canonical_slug(state) if state else ''
        state_cell = f'<a href="/{canonical_slug}">{state_name}</a>' if canonical_slug else state_name
        tn = fac.get('Total_Nurse_HPRD')
        rn = fac.get('RN_HPRD')
        contract = fac.get('Contract_Percentage')
        cells = [f'<a href="/provider/{ccn}">{name}</a>', city or '—', state_cell, ccn]
        if tn is not None:
            cells.append(format_metric_value(tn, 'Total_Nurse_HPRD'))
        else:
            cells.append('—')
        if rn is not None:
            cells.append(format_metric_value(rn, 'RN_HPRD'))
        else:
            cells.append('—')
        if contract is not None:
            cells.append(format_metric_value(contract, 'Contract_Percentage') + '%')
        else:
            cells.append('—')
        rows.append('<tr><td>' + '</td><td>'.join(cells) + '</td></tr>')
    thead = '<tr><th>Facility</th><th>City</th><th>State</th><th>CCN</th><th>Total Nurse HPRD</th><th>RN HPRD</th><th>Contract %</th></tr>'
    tbody = '\n'.join(rows)
    seo_desc = f"{entity_name} operates {subtitle}. PBJ staffing data for affiliated nursing homes."
    page_title = f"{entity_name} | Nursing Home Staffing | PBJ320"
    layout = get_pbj_site_layout(page_title, seo_desc, f"{base_url}/entity/{entity_id}")
    entity_page_url = f"{base_url}/entity/{entity_id}"
    care_compare_entity_url = f'https://www.medicare.gov/care-compare/details/chains/{entity_id}'
    custom_report_cta_html = render_custom_report_cta('entity', entity_page_url, entity_name=entity_name)
    inner = f"""
<h1>{entity_name}</h1>
<p class="pbj-subtitle">{subtitle}</p>

<div class="section-header">Facilities</div>
<p class="pbj-subtitle">Nursing homes affiliated with this entity. Latest quarter staffing metrics.</p>
<table>
<thead>{thead}</thead>
<tbody>
{tbody}
</tbody>
</table>

{render_methodology_block()}

{custom_report_cta_html}

<p style="margin-top: 1.5rem;"><a href="/">Home</a></p>
<p style="margin-top: 0.5rem; font-size: 0.8rem; color: rgba(226,232,240,0.6);">Data from CMS payroll-based journal (PBJ). <a href="{care_compare_entity_url}" target="_blank" rel="noopener" style="color: rgba(148,163,184,0.95);">View on Medicare Care Compare</a></p>"""
    return layout['head'] + layout['nav'] + layout['content_open'] + inner + layout['content_close']

_SFF_CACHE = None
_SFF_CACHE_AT = 0
_SFF_CACHE_TTL = 120

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
    """Get historical quarterly data for a state. Returns dict with raw_quarters, total, direct, rn, census, contract for state charts."""
    if not HAS_PANDAS:
        return None
    try:
        state_df = load_csv_data('state_quarterly_metrics.csv')
        if state_df is None or state_df.empty:
            return None
        state_rows = state_df[state_df['STATE'] == state_code].sort_values('CY_Qtr')
        if state_rows.empty:
            return None
        raw_quarters = []
        total_data = []
        direct_data = []
        rn_data = []
        census_data = []
        contract_data = []
        cols = state_rows.columns
        for _, row in state_rows.iterrows():
            q_str = str(row['CY_Qtr'])
            raw_quarters.append(q_str)
            total_data.append(round(float(row['Total_Nurse_HPRD']) if pd.notna(row.get('Total_Nurse_HPRD')) else 0, 3))
            direct_data.append(round(float(row['Nurse_Care_HPRD']) if 'Nurse_Care_HPRD' in cols and pd.notna(row.get('Nurse_Care_HPRD')) else 0, 3))
            rn_data.append(round(float(row['RN_HPRD']) if pd.notna(row.get('RN_HPRD')) else 0, 3))
            census_col = 'avg_daily_census' if 'avg_daily_census' in cols else 'Avg_Daily_Census'
            census_data.append(round(float(row[census_col]) if census_col in cols and pd.notna(row.get(census_col)) else 0, 1))
            contract_data.append(round(float(row['Contract_Percentage']) if 'Contract_Percentage' in cols and pd.notna(row.get('Contract_Percentage')) else 0, 2))
        return {
            'raw_quarters': raw_quarters,
            'total': total_data,
            'direct': direct_data,
            'rn': rn_data,
            'census': census_data,
            'contract': contract_data,
        }
    except Exception as e:
        print(f"Error loading historical data for {state_code}: {e}")
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
        return int(sub['PROVNUM'].nunique()) if not sub.empty else 0
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
                hprd_data.append(round(hprd, 3))
        else:
            for row in national_rows:
                q_str = str(row.get('CY_Qtr', ''))
                match = re.match(r'(\d{4})Q(\d)', q_str)
                if match:
                    quarters.append(f"Q{match.group(2)} {match.group(1)}")
                else:
                    quarters.append(q_str)
                
                hprd = float(row.get('Total_Nurse_HPRD', 0)) if row.get('Total_Nurse_HPRD') else 0
                hprd_data.append(round(hprd, 3))
        
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
                <a href="https://pbjdashboard.com/" target="_blank" style="color: #0645ad; text-decoration: none;">Explore US PBJ Data ↗</a>
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
                    ctx.fillText(value.toFixed(2), paddingLeft - 10, y + 4);
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
    """Generate Chart.js state staffing charts (Total+Direct, RN, Census, Contract) — dark theme, matches facility page."""
    d = get_state_historical_data(state_code)
    if not d or not d.get('raw_quarters') or not d.get('total'):
        return ""
    data_esc = json.dumps(d).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return f'''
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<div class="section-header">Total staffing over time</div>
<p class="pbj-subtitle">Statewide total and direct care hours per resident day by quarter.</p>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="stateChartTotal" height="260"></canvas></div>
<div class="section-header">RN staffing over time</div>
<p class="pbj-subtitle">Statewide RN hours per resident day by quarter.</p>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="stateChartRN" height="260"></canvas></div>
<div class="section-header">Census over time</div>
<p class="pbj-subtitle">Statewide average daily census by quarter.</p>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="stateChartCensus" height="260"></canvas></div>
<div class="section-header">Contract staff % over time</div>
<div class="pbj-chart-container" style="margin-bottom:1.5rem;"><canvas id="stateChartContract" height="260"></canvas></div>
<script>
(function(){{
  var d = {data_esc};
  var textColor = 'rgba(226,232,240,0.9)';
  var gridColor = 'rgba(148,163,184,0.2)';
  if (typeof Chart !== 'undefined') {{ Chart.defaults.color = textColor; Chart.defaults.borderColor = gridColor; }}
  function xLabels(quarters) {{
    if (!quarters || !quarters.length) return [];
    return quarters.map(function(q, i) {{
      var y = String(q).substring(0,4), qtr = String(q).substring(4);
      if (qtr === 'Q1') return y;
      var prev = i > 0 ? quarters[i-1] : null;
      if (prev && String(prev).substring(0,4) !== y) return y;
      return '';
    }});
  }}
  function makeLine(id, labels, datasets, yTitle) {{
    var ctx = document.getElementById(id);
    if (!ctx || !d.raw_quarters || !d.raw_quarters.length) return;
    new Chart(ctx.getContext('2d'), {{
      type: 'line',
      data: {{ labels: labels, datasets: datasets }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ color: textColor }} }}, tooltip: {{ callbacks: {{ title: function(c) {{ var q = d.raw_quarters[c[0].dataIndex]; return q ? (q.substring(5) + ' ' + q.substring(0,4)) : ''; }} }} }} }},
        scales: {{ y: {{ beginAtZero: false, ticks: {{ color: textColor }}, grid: {{ color: gridColor }}, title: {{ display: !!yTitle, text: yTitle || '', color: textColor }} }}, x: {{ ticks: {{ color: textColor, maxTicksLimit: 12 }}, grid: {{ color: gridColor }} }} }}
      }}
    }});
  }}
  var labels = xLabels(d.raw_quarters);
  if (d.total && d.total.length) {{
    var ds = [{{ label: 'Total HPRD', data: d.total, borderColor: '#1e40af', tension: 0.3, fill: false }}, {{ label: 'Direct care HPRD', data: d.direct || [], borderColor: '#6366f1', borderDash: [5,5], tension: 0.3, fill: false }}];
    makeLine('stateChartTotal', labels, ds, 'Hours per resident day');
  }}
  if (d.rn && d.rn.length) makeLine('stateChartRN', labels, [{{ label: 'RN HPRD', data: d.rn, borderColor: '#1e40af', tension: 0.3, fill: false }}], 'Hours per resident day');
  if (d.census && d.census.length) makeLine('stateChartCensus', labels, [{{ label: 'Avg daily census', data: d.census, borderColor: '#1e40af', tension: 0.3, fill: false }}], 'Census');
  if (d.contract && d.contract.length) makeLine('stateChartContract', labels, [{{ label: 'Contract %', data: d.contract, borderColor: '#1e40af', tension: 0.3, fill: false }}], 'Contract %');
}})();
</script>
'''

def generate_state_page_html(state_name, state_code, state_data, macpac_standard, region_info, quarter, rank_total=None, rank_rn=None, total_states=None, sff_facilities=None, raw_quarter=None, contact_info=None):
    """Generate state page content. Returns (content, page_title, seo_description, canonical_url) for use with get_pbj_site_layout (state page is separate from PBJpedia)."""
    # Format data values
    def fmt(val, decimals=2):
        try:
            if pd.isna(val) or val is None:
                return "N/A"
            return f"{float(val):.{decimals}f}"
        except:
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
            latest_all = state_df[state_df['CY_Qtr'] == raw_quarter]
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
    
    # State standard (MACPAC) folded into takeaway footnote when present — no standalone section
    state_standard_line = ""
    if macpac_standard is not None:
        try:
            min_staffing_raw = macpac_standard.get('Min_Staffing', '') if isinstance(macpac_standard, dict) else getattr(macpac_standard, 'Min_Staffing', '')
            min_staffing_val = str(min_staffing_raw).replace(' HPRD', '').strip()
            try:
                min_staffing_num = float(min_staffing_val)
                state_standard_line = f"State standard: {fmt(min_staffing_num, 2)} HPRD (MACPAC)."
            except (TypeError, ValueError):
                pass
        except Exception:
            pass

    # Get basics: prefer facility count from facility_quarterly (state_quarterly can be wrong e.g. PA)
    _fcount = get_state_facility_count_from_facility_quarterly(state_code, raw_quarter)
    facility_count = int(_fcount) if _fcount is not None else int(float(get_val('facility_count', 0)))
    avg_daily_census_val = get_val('avg_daily_census', 0)
    try:
        avg_daily_census_float = float(avg_daily_census_val) if avg_daily_census_val != 'N/A' else 0
    except:
        avg_daily_census_float = 0
    
    # Calculate total residents: nursing homes × average daily census
    total_residents = int(facility_count * avg_daily_census_float) if avg_daily_census_float > 0 and facility_count > 0 else 0
    total_residents_display = f"{total_residents:,}" if total_residents > 0 else "N/A"
    
    total_resident_days = get_val('total_resident_days', 0)
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
    
    # Get Total HPRD with rank for overview table
    total_hprd_val = fmt(get_val('Total_Nurse_HPRD'))
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
                prev_facility_count = int(float(prev.get('facility_count', 0)))
                prev_residents = int(float(prev.get('facility_count', 0)) * float(prev.get('avg_daily_census', 0))) if prev.get('avg_daily_census') else None
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
            <div class="value">{facility_count:,}</div>
            <div class="delta">{delta_str(facility_count, prev_facility_count)} vs prior quarter</div>
        </div>
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Resident Census</div>
            <div class="value">{total_residents_display}</div>
            <div class="delta">{delta_str(total_residents if total_residents else None, prev_residents)} vs prior quarter</div>
        </div>
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Nurse Staffing (HPRD)</div>
            <div class="value">{fmt(get_val('Total_Nurse_HPRD'))}</div>
            <div class="delta">{delta_str(get_val('Total_Nurse_HPRD'), prev_hprd)} vs prior quarter</div>
        </div>
        <div class="pbj-metric-card" style="background:rgba(15,23,42,0.6); border:1px solid rgba(59,130,246,0.2); border-radius:8px; padding:1rem;">
            <div class="label">Contract Staff %</div>
            <div class="value">{fmt(get_val('Contract_Percentage'))}%</div>
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
    
    # SFF facilities section (collapsible)
    sff_section = ""
    if sff_facilities:
        sff_count = len(sff_facilities)
        facility_word = "facility" if sff_count == 1 else "facilities"
        sff_section = f"""
    <details class="pbj-details">
    <summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Special Focus Facilities (SFF) — {sff_count} {facility_word}</summary>
    <div class="pbj-details-content">
    <p class="pbj-subtitle" style="color: rgba(226,232,240,0.95); margin: 0 0 0.5rem 0;">{state_name} has <strong>{sff_count}</strong> {facility_word} in the Special Focus Facility program:</p>
    <ul class="sff-facilities-list" style="color: rgba(226,232,240,0.95); margin: 0.5rem 0 0 0;">
    """
        for facility in sff_facilities:  # List ALL facilities
            facility_name = facility.get('facility_name', 'Unknown')
            provider_number = facility.get('provider_number', '')
            months_sff = facility.get('months_as_sff', 0)
            city = facility.get('city', '')
            
            # Get provider info
            prov_info = provider_info.get(provider_number, {})
            if not city:
                city = prov_info.get('city', '')
            residents = prov_info.get('avg_residents_per_day', '')
            ownership = format_ownership_type(prov_info.get('ownership_type', ''))
            entity = prov_info.get('entity_name', '')
            
            # Capitalize properly
            facility_name_cap = capitalize_facility_name(facility_name)
            city_cap = capitalize_city_name(city) if city else ''
            # Create link to PBJ Dashboard
            dashboard_link = f'/provider/{provider_number}'
            
            # Build facility line (polished format)
            facility_line = f'<li><a href="{dashboard_link}">{facility_name_cap}</a>'
            if city_cap:
                facility_line += f' ({city_cap})'
            facility_line += f' – {months_sff} months as SFF'
            if residents:
                try:
                    residents_int = int(float(residents))
                    facility_line += f' - {residents_int} residents'
                except:
                    pass
            if ownership:
                facility_line += f', {ownership}'
            if entity:
                facility_line += f': {entity}'
            facility_line += '</li>'
            sff_section += facility_line
        sff_section += "</ul></div></details>"
    
    # Ranking info removed - already shown in overview table
    ranking_info = ""
    
    # Generate chart HTML (with dynamic state name in heading)
    chart_html = generate_state_chart_html(state_name, state_code)
    
    # Generate contact/complaint section (Wikipedia-style, factual)
    contact_section = ""
    if contact_info:
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
    elif macpac_standard is None:
        contact_section = """
    <div class="section-header">Filing Complaints & Contact Information</div>
    <p style="color: rgba(226,232,240,0.95);">To file a complaint about a nursing home, contact your state's health department or the <a href="https://www.medicare.gov/care-compare/" target="_blank" rel="noopener">Medicare Care Compare</a> complaint system.</p>
    """
    
    # CustomReportCTA for state page
    _canonical_slug = get_canonical_slug(state_code)
    _state_page_url = f"https://pbj320.com/{_canonical_slug}"
    _region_str = ''
    if region_info is not None and hasattr(region_info, 'get'):
        _region_str = str(region_info.get('CMS_Region_Number', '') or region_info.get('Region_Number', '') or '')
    cta_section = render_custom_report_cta('state', _state_page_url, state_name=state_name, region=_region_str)
    
    total_hprd_val = fmt(get_val('Total_Nurse_HPRD'))
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
    residents_per_staff = round(8 / cur_hprd, 1) if cur_hprd and cur_hprd > 0 else None
    state_na_hprd = None
    try:
        na = get_val('Nurse_Assistant_HPRD')
        if na != 'N/A':
            state_na_hprd = float(na)
    except (TypeError, ValueError):
        pass
    avg_facility_census = int(round(avg_daily_census_float)) if avg_daily_census_float and avg_daily_census_float > 0 else None
    state_narrative = ''
    if cur_hprd is not None:
        parts = [f"{state_name}'s reported <strong>{total_hprd_val} hours per resident day</strong>"]
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
                parts.append(f" This level is below the national ratio of {fmt(national_hprd)} HPRD")
            elif cur_hprd > national_hprd * 1.03:
                parts.append(f" This level is above the national ratio of {fmt(national_hprd)} HPRD")
            else:
                parts.append(f" This level is near the national ratio of {fmt(national_hprd)} HPRD")
            parts.append(".")
        if rank_total_nurse and total_states:
            parts.append(f" Ranks #{rank_total_nurse} of {total_states} states.")
        state_narrative = '<p style="margin: 0.5rem 0; font-size: 0.95rem; color: rgba(226,232,240,0.95);">' + ''.join(parts) + '</p>'
    else:
        state_narrative = f'<p style="margin: 0.5rem 0; font-size: 0.95rem; color: rgba(226,232,240,0.95);">In {quarter}, {state_name} nursing homes reported an average of <strong>{total_hprd_val} hours per resident day</strong> of total nurse staffing.{" Ranks #" + str(rank_total_nurse) + " of " + str(total_states) + " states." if rank_total_nurse and total_states else ""}</p>'
    state_put_another_way = ''
    if cur_hprd and cur_hprd > 0:
        floor_staff = max(1, int(round(30 * cur_hprd / 8)))
        floor_aides = max(0, int(round(30 * (state_na_hprd or 0) / 8))) if state_na_hprd is not None else 0
        state_put_another_way = f"On a 30-bed floor at a typical {state_name} nursing home you'd see about <strong>{floor_staff}</strong> staff members, including ~{floor_aides} nurse aides."
        if avg_facility_census and avg_facility_census > 0:
            fac_staff = max(1, int(round(avg_facility_census * cur_hprd / 8)))
            fac_aides = max(0, int(round(fac_staff * (state_na_hprd or 0) / cur_hprd))) if state_na_hprd is not None else 0
            state_put_another_way += f" For the entire {avg_facility_census}-resident facility ({state_name} average), that's about {fac_staff} total staff, including ~{fac_aides} nurse aides."
        state_put_another_way = '<p style="margin: 0.5rem 0 0 0; color: #e2e8f0;"><strong>Put another way…</strong> ' + state_put_another_way + '</p>'
    state_note_line = '<p style="margin: 0.5rem 0 0 0; font-size: 0.85rem; color: rgba(226,232,240,0.7);">Note: staffing varies by day and shift, with the lowest levels typically on nights and weekends.</p>'
    state_standard_footer = f'<p style="margin: 0.35rem 0 0 0; font-size: 0.8rem; color: rgba(226,232,240,0.6);">{state_standard_line}</p>' if state_standard_line else ''
    state_takeaway_card = f'''
<div id="pbj-takeaway" class="pbj-content-box" style="margin: 1rem 0; padding: 1rem; border: 1px solid rgba(59,130,246,0.3); border-radius: 8px;">
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
<img src="/phoebe.png" alt="Phoebe J" width="48" height="48" style="border-radius: 50%; object-fit: cover; border: 2px solid rgba(96,165,250,0.4); flex-shrink: 0;">
<div style="font-size: 16px; font-weight: bold; color: #e2e8f0;">PBJ Takeaway: {state_name}</div>
</div>
<p style="margin: 0.5rem 0 0.5rem 0;"><span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #e2e8f0;">{total_hprd_val} HPRD (rank: {rank_total_nurse or '—'})</span><span style="display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; margin-right: 6px; background: rgba(96,165,250,0.15); color: #e2e8f0;">{fmt(get_val('Contract_Percentage'))}% contract</span></p>
{state_narrative}
{state_put_another_way}
{state_note_line}
{state_standard_footer}
<div style="margin-top: 0.35rem; margin-bottom: 0.15rem; display: flex; justify-content: flex-end;"><span style="display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; background: rgba(96,165,250,0.2); color: #93c5fd; border: 1px solid rgba(96,165,250,0.4);">320 Consulting</span></div>
</div>'''
    # State page content: H1, subtitle (context first), Phoebe takeaway, chart, collapsible table, SFF, Explore, CTA, contact
    content = f"""
    <h1>{state_name} Nursing Home Staffing</h1>
    <p class="pbj-subtitle">{facility_count:,} nursing homes, {total_residents_display} residents ({quarter})</p>
    {state_takeaway_card}
    {chart_html}
    <details class="pbj-details">
    <summary><span class="pbj-details-icon" aria-hidden="true">▼</span> Staffing Metrics ({quarter})</summary>
    <div class="pbj-details-content">
    <div class="pbj-table-wrap"><table style="max-width: 600px;">
        <tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">National Rank</th></tr>
        <tr><td>Total Nurse Staffing HPRD</td><td>{fmt(get_val('Total_Nurse_HPRD'))}</td><td>#{rank_total_nurse} of {total_states if total_states else 'N/A'}</td></tr>
        <tr><td>RN HPRD</td><td>{fmt(get_val('RN_HPRD'))}</td><td>#{rank_rn_hprd} of {total_states if total_states else 'N/A'}</td></tr>
        <tr><td>Direct Care Nurse HPRD</td><td>{fmt(get_val('Nurse_Care_HPRD'))}</td><td>#{rank_direct_care} of {total_states if rank_direct_care and total_states else 'N/A'}</td></tr>
        <tr><td>RN Direct Care HPRD</td><td>{fmt(get_val('RN_Care_HPRD'))}</td><td>#{rank_rn_care} of {total_states if rank_rn_care and total_states else 'N/A'}</td></tr>
        <tr><td>Nurse Aide HPRD</td><td>{fmt(get_val('Nurse_Assistant_HPRD'))}</td><td>#{rank_nurse_aide} of {total_states if rank_nurse_aide and total_states else 'N/A'}</td></tr>
        <tr><td>Contract Staff Percentage</td><td>{fmt(get_val('Contract_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Direct Care Percentage</td><td>{fmt(get_val('Direct_Care_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Total RN Percentage</td><td>{fmt(get_val('Total_RN_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Nurse Aide Percentage</td><td>{fmt(get_val('Nurse_Aide_Percentage'))}%</td><td>—</td></tr>
    </table></div>
    </div>
    </details>
    {sff_section}
    <div class="section-header">Explore {state_name} Data</div>
    <p style="color: rgba(226,232,240,0.95);">
        <a href="https://pbjdashboard.com/?state={state_code}" target="_blank" rel="noopener">PBJ Dashboard</a> &middot;
        <a href="https://www.pbj320.com/sff/{state_code.lower()}" target="_blank" rel="noopener">Special Focus</a> &middot;
        <a href="https://www.pbj320.com/wrapped/{state_code.lower()}" target="_blank" rel="noopener">PBJ Wrapped</a>
    </p>
    {render_methodology_block()}
    {cta_section}
    {contact_section}
    """
    
    # Wikipedia-style title (state name with context)
    page_title = f"{state_name} Nursing Home Staffing"
    
    # Build SEO description for OG tags
    total_hprd = fmt(get_val('Total_Nurse_HPRD'))
    seo_description_parts = [
        f"{state_name} nursing homes averaged {total_hprd} hours per resident day (HPRD) of total nurse staffing in {quarter}."
    ]
    if rank_total_nurse and total_states:
        seo_description_parts.append(f"Ranked #{rank_total_nurse} of {total_states} states.")
    if macpac_standard:
        min_staffing = macpac_standard.get('Min_Staffing', '')
        if min_staffing:
            try:
                min_val = float(str(min_staffing).replace(' HPRD', ''))
                seo_description_parts.append(f"State minimum staffing requirement: {min_val:.2f} HPRD.")
            except:
                pass
    seo_description_parts.append("Data from CMS Payroll-Based Journal (PBJ).")
    seo_description = " ".join(seo_description_parts)
    
    # OG title with SEO info
    og_title = f"{state_name} | PBJ320 Nursing Home Staffing Data"
    
    # OG description for social sharing
    og_description = f"{state_name} reports {total_hprd} HPRD"
    if rank_total_nurse and total_states:
        og_description += f" (rank: {rank_total_nurse})"
    og_description += f" staffing at {facility_count:,} nursing homes and {total_residents_display} residents."
    
    # Canonical slug for URL (state page has its own URL, not under /pbjpedia)
    canonical_slug = get_canonical_slug(state_code)
    canonical_url = f"https://pbj320.com/{canonical_slug}"
    
    # Return content and metadata so caller can render state page with its own layout (separate from PBJpedia)
    return (content, page_title, seo_description, canonical_url)

def generate_region_page_html(region_num, region_data, states_in_region, state_data_list, quarter, rank=None, total_regions=None, sff_facilities=None, raw_quarter=None):
    """Generate HTML for CMS region page"""
    def fmt(val, decimals=2):
        try:
            if pd.isna(val) or val is None:
                return "N/A"
            return f"{float(val):.{decimals}f}"
        except:
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
    
    # Get basics
    facility_count = int(float(get_val('facility_count', 0)))
    avg_daily_census_val = get_val('avg_daily_census', 0)
    try:
        avg_daily_census_float = float(avg_daily_census_val) if avg_daily_census_val != 'N/A' else 0
    except:
        avg_daily_census_float = 0
    
    # Calculate total residents: nursing homes × average daily census
    total_residents = int(facility_count * avg_daily_census_float) if avg_daily_census_float > 0 and facility_count > 0 else 0
    total_residents_display = f"{total_residents:,}" if total_residents > 0 else "N/A"
    
    # Basics section
    basics_section = f"""
    <div class="infobox" style="width: 280px; margin-bottom: 1em;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><th colspan="2" scope="colgroup" style="background-color: #eaecf0; padding: 0.3em; text-align: center; border-bottom: 1px solid #a2a9b1;">{region_full} Overview</th></tr>
            <tr><td style="padding: 0.3em; font-weight: bold; border-bottom: 1px solid #a2a9b1;">Nursing Homes</td><td style="padding: 0.3em; border-bottom: 1px solid #a2a9b1;">{facility_count:,}</td></tr>
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
                <td>{fmt(get_state_val('Total_Nurse_HPRD'))}</td>
                <td>{fmt(get_state_val('RN_HPRD'))}</td>
                <td>{fmt(get_state_val('Nurse_Care_HPRD'))}</td>
                <td>{fmt(get_state_val('Contract_Percentage'))}%</td>
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
        <tr><td>Total Nurse Staffing HPRD</td><td>{fmt(get_val('Total_Nurse_HPRD'))}</td><td>{fmt(get_val('Total_Nurse_HPRD_Median'))}</td></tr>
        <tr><td>RN HPRD</td><td>{fmt(get_val('RN_HPRD'))}</td><td>{fmt(get_val('RN_HPRD_Median'))}</td></tr>
        <tr><td>Direct Care Nurse HPRD</td><td>{fmt(get_val('Nurse_Care_HPRD'))}</td><td>{fmt(get_val('Nurse_Care_HPRD_Median'))}</td></tr>
        <tr><td>RN Direct Care HPRD</td><td>{fmt(get_val('RN_Care_HPRD'))}</td><td>{fmt(get_val('RN_Care_HPRD_Median'))}</td></tr>
        <tr><td>Nurse Aide HPRD</td><td>{fmt(get_val('Nurse_Assistant_HPRD'))}</td><td>{fmt(get_val('Nurse_Assistant_HPRD_Median'))}</td></tr>
        <tr><td>Contract Staff Percentage</td><td>{fmt(get_val('Contract_Percentage'))}%</td><td>{fmt(get_val('Contract_Percentage_Median'))}%</td></tr>
        <tr><td>Direct Care Percentage</td><td>{fmt(get_val('Direct_Care_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Total RN Percentage</td><td>{fmt(get_val('Total_RN_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Nurse Aide Percentage</td><td>{fmt(get_val('Nurse_Aide_Percentage'))}%</td><td>—</td></tr>
        <tr><td>Number of Facilities</td><td>{int(float(get_val('facility_count', 0)))}</td><td>—</td></tr>
        <tr><td>Average Daily Census</td><td>{fmt(get_val('avg_daily_census'))}</td><td>—</td></tr>
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
                            <li><a href="mailto:eric@320insight.com">Contact</a></li>
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
                <a href="https://pbjdashboard.com/" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Dashboard</a>
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
            <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(929) 804-4996</a> (text preferred)
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

# PBJpedia routes - serve markdown files as HTML
@app.route('/pbjpedia')
@app.route('/pbjpedia/')
def pbjpedia_index():
    """Redirect to PBJpedia overview page"""
    from flask import redirect
    return redirect('/pbjpedia/overview')


# Provider (facility), state alias, and entity pages - before catch-all <state_slug>
@app.route('/provider/<ccn>')
def provider_page(ccn):
    """Facility (provider) page at /provider/<ccn>. CCN normalized to 6 digits."""
    from flask import abort
    if not HAS_PANDAS:
        return "Pandas not available. Provider pages require pandas.", 503
    prov = normalize_ccn(ccn)
    if not prov:
        abort(404)
    facility_df = load_facility_quarterly_for_provider(prov)
    if facility_df is None or facility_df.empty:
        abort(404)
    provider_info = load_provider_info()
    provider_info_row = provider_info.get(prov, {})
    html = generate_provider_page_html(prov, facility_df, provider_info_row)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/state/<state_slug>')
def state_alias_page(state_slug):
    """Serve state page at /state/<slug> (same content as canonical state page, not PBJpedia)."""
    canonical_slug, state_code = resolve_state_slug(state_slug)
    if not canonical_slug or not state_code:
        from flask import abort
        abort(404)
    return generate_state_page(state_code)

@app.route('/entity/<int:entity_id>')
def entity_page(entity_id):
    """Entity (chain) page at /entity/<id>. Lists facilities and latest-quarter metrics."""
    from flask import abort
    if not HAS_PANDAS:
        return "Pandas not available. Entity pages require pandas.", 503
    entity_name, facilities = load_entity_facilities(entity_id)
    if not facilities:
        abort(404)
    html = generate_entity_page_html(entity_id, entity_name, facilities)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


# Test pages: same content at /test/provider, /test/state, /test/entity
@app.route('/test/provider/<ccn>')
def test_provider_page(ccn):
    """Test facility page at /test/provider/<ccn>."""
    return provider_page(ccn)

@app.route('/test/state/<state_slug>')
def test_state_page(state_slug):
    """Test state page at /test/state/<slug> (e.g. /test/state/ny)."""
    return state_alias_page(state_slug)

@app.route('/test/entity/<int:entity_id>')
def test_entity_page(entity_id):
    """Test entity page at /test/entity/<id>."""
    return entity_page(entity_id)


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
    
    # If requested slug is not canonical, redirect
    if state_slug.lower() != canonical_slug:
        return redirect(f'/{canonical_slug}', code=301)
    
    # Generate the state page
    return generate_state_page(state_code)

@app.route('/pbjpedia/state/<state_identifier>')
def pbjpedia_state_page(state_identifier):
    """Legacy PBJpedia state page route - redirects to canonical"""
    canonical_slug, state_code = resolve_state_slug(state_identifier)
    
    if not canonical_slug or not state_code:
        return f"State '{state_identifier}' not found", 404
    
    # Redirect to canonical URL
    return redirect(f'/{canonical_slug}', code=301)

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
    
    # Get latest quarter data for this state
    state_data = state_df[state_df['STATE'] == state_code]
    if state_data.empty:
        return f"No data found for {state_name}", 404
    
    latest_quarter = get_latest_quarter(state_data)
    latest_data = state_data[state_data['CY_Qtr'] == latest_quarter].iloc[0] if latest_quarter else state_data.iloc[-1]
    formatted_quarter = format_quarter(latest_quarter)
    
    # Load SFF facilities for this state
    sff_facilities = load_sff_facilities()
    state_sff = [f for f in sff_facilities if f.get('state', '').upper() == state_code]
    
    # Calculate rankings for this state
    latest_all_states = state_df[state_df['CY_Qtr'] == latest_quarter] if latest_quarter else state_df
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
        a[href^="http"]:not([href*="pbj320.com"]):not([href*="pbjdashboard.com"]) {{
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
                <a href="https://pbjdashboard.com/" class="nav-link" style="color:rgba(255,255,255,0.8);text-decoration:none;font-weight:500;">Dashboard</a>
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
                <p><strong>Contact:</strong> <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(929) 804-4996</a> (text preferred)</p>
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
            <a href="mailto:eric@320insight.com">eric@320insight.com</a> | <a href="tel:+19298084996">(929) 804-4996</a> (text preferred)
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

# Serve data files from pbj-wrapped/dist/data
# This route MUST come before the catch-all route to work correctly
@app.route('/data', defaults={'path': ''})
@app.route('/data/', defaults={'path': ''})
@app.route('/data/<path:path>')
def data_files(path):
    """Serve data files from pbj-wrapped/dist/data directory"""
    data_dir = os.path.join('pbj-wrapped', 'dist', 'data')
    file_path = os.path.join(data_dir, path)
    
    if os.path.isfile(file_path):
        # Serve with proper MIME types
        if path.endswith('.json'):
            return send_file(file_path, mimetype='application/json')
        elif path.endswith('.csv'):
            return send_file(file_path, mimetype='text/csv')
        else:
            return send_from_directory(data_dir, path)
    else:
        from flask import abort
        abort(404)

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
    # Don't handle routes that are already defined
    if filename in ['insights', 'insights.html', 'about', 'pbj-sample', 'report', 'report.html', 'sitemap.xml', 'pbj-wrapped', 'wrapped', 'sff', 'data', 'pbjpedia', 'owner']:
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
        # Add cache-control headers for favicon to ensure updates are visible
        if filename.endswith('.ico') or 'favicon' in filename.lower():
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response
    # Handle CSS
    elif filename.endswith('.css'):
        return send_from_directory('.', filename, mimetype='text/css')
    # Handle JS
    elif filename.endswith('.js'):
        return send_from_directory('.', filename, mimetype='application/javascript')
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

