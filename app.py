#!/usr/bin/env python3
"""
Simple Flask app to serve static files with proper headers for Facebook scraper
Now with dynamic date support
"""
from flask import Flask, send_from_directory, send_file, render_template_string, render_template, jsonify, request
import os
import sys
import re

# Import date utilities from local utils package
from utils.date_utils import get_latest_data_periods
from utils.seo_utils import get_seo_metadata

app = Flask(__name__)

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
    """API endpoint to get dynamic date information"""
    return jsonify(get_dynamic_dates())

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

@app.route('/sitemap.xml')
def sitemap():
    return send_file('sitemap.xml', mimetype='application/xml')

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
    if filename in ['insights', 'insights.html', 'about', 'pbj-sample', 'report', 'report.html', 'sitemap.xml', 'pbj-wrapped', 'wrapped', 'sff', 'data']:
        from flask import abort
        abort(404)
    
    # Exclude directories that shouldn't be served (prevents connection failures)
    excluded_prefixes = ['node_modules/', '.git/', 'pbj-wrapped/node_modules/', 'pbj-wrapped/.git/', 'data/']
    if any(filename.startswith(prefix) for prefix in excluded_prefixes):
        from flask import abort
        abort(404)
    
    # Handle images with proper headers
    if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        return send_from_directory('.', filename, mimetype='image/png')
    # Handle CSS
    elif filename.endswith('.css'):
        return send_from_directory('.', filename, mimetype='text/css')
    # Handle JS
    elif filename.endswith('.js'):
        return send_from_directory('.', filename, mimetype='application/javascript')
    # Handle other static files
    else:
        return send_from_directory('.', filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

