# Routing Breakdown for PBJ Wrapped App

## Current Routing Architecture

### Flask Server Routes (app.py)

1. **Root Routes** (`/`, `/about`, `/insights`, etc.)
   - Serve static HTML files directly
   - No React involvement

2. **SFF Routes** (`/sff`, `/sff/<path:path>`)
   - `/sff` and `/sff/` → Serve `pbj-wrapped/dist/index.html`
   - `/sff/<path:path>` → 
     - If `path` is a file in `dist/` (has extension like `.js`, `.css`), serve that file
     - Otherwise, serve `index.html` for SPA routing
   - **Purpose**: Allow `/sff/usa` to work at root level (not under `/wrapped`)

3. **Wrapped Routes** (`/wrapped`, `/wrapped/<path:path>`)
   - `/wrapped` and `/wrapped/` → Serve `pbj-wrapped/dist/index.html`
   - `/wrapped/<path:path>` → 
     - If `path` is a file in `dist/` (has extension), serve that file
     - Otherwise, serve `index.html` for SPA routing
   - **Purpose**: Main entry point for wrapped pages

4. **Legacy Routes** (`/pbj-wrapped`, `/pbj-wrapped/<path:path>`)
   - Same as wrapped routes, kept for backward compatibility
   - **Purpose**: Support old URLs like `/pbj-wrapped/sff/usa`

5. **Catch-all Route** (`/<path:filename>`)
   - Serves static files from root directory
   - Excludes routes already handled above

### React Router Configuration

**Basename**: `/` (empty - routes work at root level)

**Routes in App.tsx**:
- `/` → Index page (map landing page)
- `/wrapped` → Index page (same as `/`)
- `/wrapped/usa` → Wrapped component (USA data)
- `/wrapped/:identifier` → Wrapped component (state/region data)
- `/sff` → SFFHomePage (redirects to `/sff/usa`)
- `/sff/usa` → SFFPage (SFF data for USA)
- `/sff/:scope` → SFFPage (SFF data for state/region)

### Asset Loading

**Vite Build Configuration**:
- `base: '/wrapped/'` in `vite.config.ts`
- Assets are built with paths like `/wrapped/assets/index-xxx.js`

**How Assets Load**:
1. When page is served at `/wrapped/usa`:
   - HTML references `/wrapped/assets/index-xxx.js`
   - Flask `/wrapped/<path:path>` route serves the asset file
   - ✅ Works correctly

2. When page is served at `/sff/usa`:
   - HTML still references `/wrapped/assets/index-xxx.js` (because Vite base is `/wrapped/`)
   - Browser requests `/wrapped/assets/index-xxx.js`
   - Flask `/wrapped/<path:path>` route serves the asset file
   - ✅ Works correctly (assets are accessible from any route)

### Redirects and Navigation

**SFF Redirect Flow**:
1. User visits `/sff`
2. Flask serves `index.html` (via `/sff/` route)
3. React Router matches `/sff` route → renders `SFFHomePage`
4. `SFFHomePage` uses `navigate('/sff/usa', { replace: true })`
5. React Router updates URL to `/sff/usa` (client-side)
6. React Router matches `/sff/usa` route → renders `SFFPage`
7. ✅ No page reload, smooth transition

**State Navigation Flow**:
1. User clicks state on map at `/wrapped`
2. `USMap` component calls `navigate('/wrapped/ny')`
3. React Router updates URL to `/wrapped/ny` (client-side)
4. React Router matches `/wrapped/:identifier` route → renders `Wrapped` component
5. `Wrapped` component loads data and processes it
6. ✅ Works correctly

### Potential Issues and Solutions

**Issue**: Redirects might cause problems if:
- Using `window.location.href` instead of React Router `navigate` → Causes full page reload
- **Solution**: Always use React Router's `navigate` for internal navigation

**Issue**: Assets might not load if:
- Vite base path doesn't match Flask route structure
- **Solution**: Keep Vite base as `/wrapped/` and ensure Flask serves assets from `/wrapped/<path:path>`

**Issue**: Routes might not match if:
- React Router basename doesn't match Flask route structure
- **Solution**: Use basename `/` (empty) so routes work at root level, and handle path prefixes in Flask

### Current Status

✅ **Working**:
- `/wrapped` → Index page
- `/wrapped/usa` → USA wrapped page
- `/wrapped/ny` → State wrapped page (after implementing processStateData)
- `/sff` → Redirects to `/sff/usa`
- `/sff/usa` → SFF page
- `/pbj-wrapped/sff/usa` → Legacy route still works

✅ **Assets**: All assets load correctly from `/wrapped/assets/...` regardless of which route serves the page

