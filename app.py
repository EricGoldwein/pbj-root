#!/usr/bin/env python3
"""
Simple Flask app to serve static files with proper headers for Facebook scraper
"""
from flask import Flask, send_from_directory, send_file
import os

app = Flask(__name__)

@app.route('/')
def index():
    return send_file('index.html', mimetype='text/html')

@app.route('/about.html')
def about():
    return send_file('about.html', mimetype='text/html')

@app.route('/<path:filename>')
def static_files(filename):
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
