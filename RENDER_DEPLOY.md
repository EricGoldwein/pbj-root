# Render deployment (pbj web + old-pbj320 static)

## Two services — only one uses Python memory

| Service | Type | URL (example) | RAM/CPU |
|---------|------|---------------|---------|
| **pbj** | Web (Gunicorn + Flask) | pbj320.com (production) | **This is what OOM affects** |
| **old-pbj320** | Static Site | pbj-root.onrender.com | **No Python** — CDN only; does not share RAM with `pbj` |

The static site does **not** make the Flask service slower or use more memory. It is a separate deploy that publishes files from the repo. It can still cause **bandwidth cost**, **duplicate deploy churn**, and **accidental exposure** of repo files if misconfigured (see below).

## Web service (`pbj`) — safe memory tuning

Defaults are unchanged unless you set env vars in the Render dashboard (**Environment**).

| Variable | Default | Safe use |
|----------|---------|----------|
| `PBJ_GUNICORN_WORKERS` | `2` | Set to `1` on 512MB plans to cut RAM (~half). Slightly less parallel request capacity. |
| `PBJ_GUNICORN_THREADS` | `4` | Usually leave at 4 with 1 worker. |
| `PBJ_PROVIDER_PAGE_CACHE_MAX` | `150` | Caps in-memory provider HTML cache entries. |
| `PBJ_PROVIDER_PAGE_CACHE_TTL` | `120` | Seconds (when cache enabled in prod). |
| `PBJ_MEM_DEBUG` | off | Set to `1` temporarily; logs `[MEM]` RSS and enables `GET /debug/mem` (404 when off). |
| `PBJ_MEM_ROUTE_LOG` | off (on when `PBJ_MEM_DEBUG=1`) | `[MEM_ROUTE]` lines: RSS, path, elapsed ms, status for `/`, `/sitemap.xml`, `/provider/*`, `/entity/*`, `/search_index.json`, `/api/entity-summary/*`. |
| `PBJ_MEM_LOG_RSS_MB` | `700` | Also log any route when process RSS ≥ this (even if route logging is off). Requires `psutil`. |

**Profiling:** After deploy with `PBJ_MEM_DEBUG=1`, hit `/health`, one `/provider/…`, one `/entity/…`, then `GET /debug/mem` to see cache sizes.

**Code behavior (safe):**

- Entity/chain pages load provider info only for CCNs on that page (not the full national index).
- Entity/state/sitemap paths **stream** `facility_quarterly_metrics.csv` (no full-file `_LOAD_CSV_CACHE` for that CSV).
- `/sitemap.xml` reuses the in-memory `search_index.json` cache (5 min TTL).
- Single-facility paths use `ccn_only` scans.
- `/debug/mem` is disabled unless `PBJ_MEM_DEBUG=1`.

## Static site (`old-pbj320`) — recommendations

Current settings (publish directory `.`, empty build command) publish the **entire repo root** as static files. That can:

- Expose large CSVs, scripts, and source if URLs are guessed (security/bandwidth).
- Trigger a **second deploy on every commit** (extra build noise, not Flask RAM).

**If production traffic is pbj320.com → Web service `pbj`:**

1. **Best:** Suspend or delete **old-pbj320** if you no longer need `pbj-root.onrender.com`.
2. **If you keep it for OG/social previews only:** Change **Publish Directory** to a minimal folder (e.g. `og/` or a small `static-public/`) and add a redirect `index.html` — not `.`.
3. Point Open Graph URLs in `index-render.html` at `https://pbj320.com/…` if the static site is retired.
4. **Build filters:** Ignore `app.py`, `ownership/`, `data/`, `*.csv` so commits do not redeploy the static site unless static assets change.

**If `pbj-root.onrender.com` is still linked anywhere:** Prefer linking to `https://pbj320.com` (dynamic app) instead.

## Health check

- Web service: **Health Check Path** = `/health`
- Start command: `gunicorn app:app -c gunicorn_config.py --bind 0.0.0.0:10000` (see `render.yaml` / `Procfile`)

## "No open HTTP ports"

- **render.yaml** binds `0.0.0.0:$PORT` (10000).
- Dashboard → **Health Check** → Path `/health` → Redeploy.
