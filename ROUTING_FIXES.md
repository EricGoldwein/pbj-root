# Flask Routing Fixes - JSON and Image Files

## Problem Summary

The `@app.route('/<state_slug>')` route was intercepting requests for static files (JSON and images) before they could be served by the catch-all route, causing 404 errors.

## Root Cause

Flask matches routes in the order they are defined. The route `@app.route('/<state_slug>')` at line ~2004 was defined **before** the catch-all route `@app.route('/<path:filename>')` at line ~3577. This meant:

1. A request to `/national_historical_data.json` would match the `/<state_slug>` route first
2. Flask would treat `"national_historical_data.json"` as a state slug
3. The function would try to resolve it as a state, fail, and return: `"State 'national_historical_data.json' not found"`
4. The catch-all route never got a chance to serve the file

## Solutions Implemented

### 1. JSON File Handling

**Location:** `app.py` lines ~1994-2002

**Fix:** Added JSON file detection at the start of `canonical_state_page()` function:

```python
@app.route('/<state_slug>')
def canonical_state_page(state_slug):
    """Canonical state page route (e.g., /tn, /new-york)"""
    # Handle JSON files first - serve them directly
    if state_slug.endswith('.json'):
        json_path = os.path.join('.', state_slug)
        if os.path.isfile(json_path):
            return send_file(json_path, mimetype='application/json')
        from flask import abort
        abort(404)
    
    # ... rest of function
```

**Why this works:** By checking for JSON files first, we intercept them before they're processed as state slugs.

### 2. Image File Handling

**Location:** `app.py` lines ~2004-2013

**Fix:** Added image file detection right after JSON handling:

```python
    # Handle image files - serve them directly
    if state_slug.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.svg')):
        image_path = os.path.join('.', state_slug)
        if os.path.isfile(image_path):
            mimetype = 'image/png' if state_slug.endswith('.png') else 'image/jpeg' if state_slug.endswith(('.jpg', '.jpeg')) else 'image/gif' if state_slug.endswith('.gif') else 'image/webp' if state_slug.endswith('.webp') else 'image/svg+xml' if state_slug.endswith('.svg') else 'image/x-icon'
            return send_file(image_path, mimetype=mimetype)
        from flask import abort
        abort(404)
```

**Why this works:** Same principle - intercept image files before state slug processing.

### 3. CSV File Handling

**Location:** `app.py` lines ~2013-2020

**Fix:** Added CSV file detection after image handling:

```python
    # Handle CSV files - serve them directly
    if state_slug.endswith('.csv'):
        csv_path = os.path.join('.', state_slug)
        if os.path.isfile(csv_path):
            return send_file(csv_path, mimetype='text/csv')
        from flask import abort
        abort(404)
```

**Why this works:** Prevents CSV files from being processed as state slugs.

### 4. Catch-All Route File Handling

**Location:** `app.py` lines ~3605-3620

**Fix:** Added explicit JSON and CSV handling in the catch-all route as a backup:

```python
    # Handle JSON files
    elif filename.endswith('.json'):
        json_path = os.path.join('.', filename)
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
```

## Files Affected

- **JSON files:** `latest_quarter_data.json`, `states_list.json`, `state_historical_data.json`, `quarters_list.json`, `national_historical_data.json`
- **Image files:** `seagate_staffing_pbj.png`, `phoebe.png`, `pbj_favicon.png`, and any other images in root directory
- **CSV files:** `national_quarterly_metrics.csv`, `state_quarterly_metrics.csv`, `provider_info_combined_latest.csv`, `cms_region_state_mapping.csv`, `facility_quarterly_metrics_latest.csv`, `cms_region_quarterly_metrics.csv`

## Best Practices to Prevent This Issue

### 1. Route Order Matters

**Rule:** More specific routes should come before catch-all routes.

**Good order:**
```python
# 1. Specific routes first
@app.route('/about')
@app.route('/insights')

# 2. Routes with specific patterns (like /images/, /data/)
@app.route('/images/<path:filename>')
@app.route('/data/<path:path>')

# 3. Routes that need to check file extensions (like state_slug)
@app.route('/<state_slug>')  # Checks for .json, .png, etc. first

# 4. Catch-all route last
@app.route('/<path:filename>')
```

### 2. Always Check File Extensions in Parameter Routes

**Rule:** If you have a route with a parameter that could match files, check for file extensions first.

**Pattern to follow:**
```python
@app.route('/<param>')
def handler(param):
    # Check for static files FIRST
    if param.endswith(('.json', '.png', '.jpg', '.csv', '.css', '.js')):
        file_path = os.path.join('.', param)
        if os.path.isfile(file_path):
            # Serve the file with proper MIME type
            mimetype = 'application/json' if param.endswith('.json') else \
                      'text/csv' if param.endswith('.csv') else \
                      'image/png' if param.endswith('.png') else '...'
            return send_file(file_path, mimetype=mimetype)
        abort(404)
    
    # Then handle your actual logic
    # ...
```

### 3. Use Specific Routes for Known File Types

**Better approach:** Create specific routes for file types before parameter routes:

```python
# Serve JSON files explicitly (before state_slug route)
@app.route('/<filename>.json')  # Note: This pattern doesn't work in Flask
# Instead, check in state_slug route as we did
```

**Alternative:** Use a converter or check in the parameter route (as implemented).

### 4. Test Static File Serving

**When adding new routes:**
1. Test that static files (JSON, images, CSS, JS) still load
2. Check browser console for 404 errors
3. Verify MIME types are correct

### 5. Document Route Order

**In code comments:**
```python
# IMPORTANT: This route must come before /<state_slug> to handle JSON files
# Route order: specific routes -> file type checks -> parameter routes -> catch-all
```

## Testing Checklist

After adding or modifying routes, verify:

- [ ] JSON files load correctly (check browser Network tab)
- [ ] Image files load correctly
- [ ] CSV files load correctly
- [ ] CSS files load correctly
- [ ] JS files load correctly
- [ ] State pages still work (e.g., `/tn`, `/new-york`)
- [ ] No 404 errors in browser console
- [ ] MIME types are correct (check Response Headers)

## Related Files

- `app.py` - Main Flask application with routing
- `index.html` - Uses JSON files for dynamic data
- `about.html` - Uses image files
- `generate_dynamic_data_json.py` - Generates JSON files

## Future Considerations

If you add more file types or routes:

1. **Add file extension checks** in `canonical_state_page()` for new file types
2. **Update the catch-all route** to handle new file types
3. **Consider creating a helper function** to serve static files:

```python
def serve_static_file(filename, base_dir='.'):
    """Helper to serve static files with proper MIME types"""
    file_path = os.path.join(base_dir, filename)
    if not os.path.isfile(file_path):
        abort(404)
    
    # Determine MIME type
    if filename.endswith('.json'):
        mimetype = 'application/json'
    elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        mimetype = 'image/png' if filename.endswith('.png') else 'image/jpeg'
    # ... etc
    
    return send_file(file_path, mimetype=mimetype)
```

Then use it in both `canonical_state_page()` and the catch-all route.

## Summary

**Key Takeaway:** When you have a route with a catch-all parameter like `/<state_slug>`, always check for static file extensions (`.json`, `.png`, `.csv`, `.css`, `.js`, etc.) at the **beginning** of the handler function, before processing the parameter as your intended data type.

This prevents static files from being incorrectly processed and ensures they're served with the correct MIME types.

## Additional Fixes

### Meta Tag Deprecation

**Fixed in:** `insights.html` and `report.html`

**Issue:** `apple-mobile-web-app-capable` meta tag is deprecated.

**Fix:** Added the new standard tag while keeping the Apple-specific one for backward compatibility:

```html
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
```
