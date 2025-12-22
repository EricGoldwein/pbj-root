#!/usr/bin/env python3
"""
Simple Flask app to serve static files with proper headers for Facebook scraper
Now with dynamic date support
"""
from flask import Flask, send_from_directory, send_file, render_template_string, jsonify
import os
import sys

# Import date utilities from local utils package
from utils.date_utils import get_latest_data_periods

app = Flask(__name__)

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

# Serve data files from pbj-wrapped/dist/data
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
    """Serve the wrapped React app index page for SFF routes"""
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
        # For SPA routing, serve index.html for any route
        # This allows React Router to handle client-side routing
        wrapped_index = os.path.join(wrapped_dist, 'index.html')
        if os.path.exists(wrapped_index):
            return send_file(wrapped_index, mimetype='text/html')
        else:
            return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

# Serve wrapped app at /wrapped (for pbj320.com/wrapped/)
@app.route('/wrapped')
@app.route('/wrapped/')
def wrapped_index():
    """Serve the wrapped React app index page"""
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
        # For SPA routing, serve index.html for any route
        # This allows React Router to handle client-side routing
        wrapped_index = os.path.join(wrapped_dist, 'index.html')
        if os.path.exists(wrapped_index):
            return send_file(wrapped_index, mimetype='text/html')
        else:
            return "PBJ Wrapped app not built. Run 'npm run build' in pbj-wrapped directory.", 404

# Legacy route: Serve pbj-wrapped app (for backward compatibility)
@app.route('/pbj-wrapped')
@app.route('/pbj-wrapped/')
def pbj_wrapped_index():
    """Serve the pbj-wrapped React app index page (legacy)"""
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
        # For SPA routing, serve index.html for any route
        # This allows React Router to handle client-side routing
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

