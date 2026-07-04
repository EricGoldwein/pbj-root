# PBJ320 deployment runbook

**Canonical production deploy runbook** for `www.pbj320.com` (Render web service `pbj`).  
Related: `DEPLOY_AND_RUN.md` (local dev only), `RENDER_DEPLOY.md` (memory/cache/provider warming), `docs/DATA_DEPLOY.md` (CSV/index build gates).

---

## Production today

- **`www.pbj320.com` points at the `pbj` Render web service** (Gunicorn + Flask `app.py`). All public traffic hits this single app.
- **Static-looking pages** (insights reports, about, press, root HTML) are served by Flask (`_serve_public_html`, `send_file`, templates) — not a separate CDN.
- **Therefore, copy-only HTML/CSS/image edits still trigger a full Render app build and instance replacement today.** There is no static-only publish path on production.
- The optional **`old-pbj320` Render Static Site** (`pbj-root.onrender.com`) is **not** the production front door unless DNS is explicitly pointed at it. It is not defined in `render.yaml`; production DNS uses `pbj`.

On a single-instance Render web service, deploys can still create brief unavailability or cold-start exposure during instance replacement. True redundancy requires multiple instances or splitting static content away from the dynamic app.

---

## Do not

- **Do not** push copy-only or cosmetic changes directly to the production-watched branch during active outreach, press, demo, or client-review windows. Batch copy edits or wait until the window ends.
- **Do not** use `/warmup` as the Render health check. It loads `search_index.json` and hydrates state aggregates — readiness smoke only.
- **Do not** put CSV validation, index generation, cache warming, ownership builds, or other expensive work in the **runtime start command**. Build-time only (`render.yaml` `buildCommand`). Start must be `python scripts/render_start.py`.
- **Do not** leave unused static services deploying from the repo root (`.`). Suspend auto-deploy or narrow publish directory + build filters.
- **Do not** assume rollback restores in-memory caches. Provider HTML cache, CSV caches, and owner dashboard state are per-process and rebuild on traffic.

---

## Health check and start command

| Setting | Value |
|---------|--------|
| **Health check path** | **`/healthz`** (`render.yaml` `healthCheckPath`; confirm Render Dashboard → **pbj** → Settings) |
| **Alias** | `/health` — same handler, kept for scripts |
| **Start command** | `python scripts/render_start.py` (`Procfile`, `render.yaml`) |

`/healthz` and `/health` return `200` with body `ok`. Verified behavior:

- No pandas import (`_ensure_pandas` skips `_HEALTH_PROBE_PATHS`)
- No CSV, SQLite, ownership data, cache warmers, or external APIs
- Bot throttles and rate limits skip probe paths

**Readiness (post-deploy smoke, not liveness):** `GET /warmup`

```powershell
curl.exe -s -m 10 "https://www.pbj320.com/healthz"
```

**Dashboard audit (do once, re-check after manual edits):**

1. Start Command = `python scripts/render_start.py` only — not `ensure_deploy_csvs && gunicorn …`
2. Health Check Path = `/healthz`
3. `PBJ_SKIP_START_CSV_ENSURE=1` set (in `render.yaml` env)

### Health-check path change rule

Changing the Render Dashboard path **before** production serves the new route causes 404 probes and can mark the instance unhealthy (even when `/` and the old path still work).

When changing the Render health-check path:

1. Add the new health route in app code first.
2. Deploy the code while the **old** health path is still active in the Dashboard.
3. Confirm the new health path returns `200` in production.
4. Only then change the Render Dashboard Health Check Path.
5. Keep the old health route as an alias for at least one deploy cycle.
6. If the new health path fails in production, temporarily switch Render back to the last known-good path.
7. **Example:** Do not change Render from `/health` to `/healthz` until production already returns `200` for `/healthz`.

**Post-incident verification:** After changing health-check routing, confirm Render logs show `/healthz` returning `200` from `Render/1.0`, then run the low/medium smoke checklist. Do not continue deploy/config changes if production is stable.

---

## Deploy risk levels

Classify every change before pushing to the branch Render watches (typically `main`).

### Low risk

- Copy-only HTML changes
- CSS-only fixes
- Image or OG image updates
- Static insight/report page edits (e.g. `insights-ny-minimum-staffing.html`)

*Still triggers full app deploy today — plan timing even when risk to logic is low.*

### Medium risk

- Shared templates (`insights_hub.html`, owner templates, report shells)
- JavaScript UI behavior (`pbj-site-universal.js`, `state-page-charts.js`, owner JS)
- Navigation, filters, accordions, charts, or dashboard display logic
- Sitemap or search-index **presentation** changes (not data pipeline)

### High risk

- `app.py` routing changes
- Provider / state / entity dashboard logic
- Ownership database or ownership index logic
- Data/index build scripts (`scripts/build_*.py`, `ensure_deploy_csvs.py`)
- `requirements.txt`
- `render.yaml`
- Startup command changes
- Environment-variable-dependent behavior

---

## Smoke tests by risk level

Use `https://www.pbj320.com` (or preview URL). Replace example paths with the page you changed.

### Low-risk deploy smoke

```powershell
curl.exe -s -m 10 "https://www.pbj320.com/healthz"
curl.exe -s -m 30 -o NUL -w "%{http_code}" "https://www.pbj320.com/insights/ny-minimum-staffing"
curl.exe -s -m 60 -o NUL -w "%{http_code}" "https://www.pbj320.com/provider/075325"
```

- [ ] `/healthz` → `200`
- [ ] One **edited** public/static page → `200` (or expected redirect)
- [ ] One representative dashboard URL (e.g. `/provider/075325`) → `200`

### Medium-risk deploy smoke

```powershell
curl.exe -s -m 10 "https://www.pbj320.com/healthz"
curl.exe -s -m 30 "https://www.pbj320.com/warmup"
curl.exe -s -m 60 -o NUL -w "%{http_code}" "https://www.pbj320.com/provider/075325"
curl.exe -s -m 60 -o NUL -w "%{http_code}" "https://www.pbj320.com/state/ny"
curl.exe -s -m 60 -o NUL -w "%{http_code}" "https://www.pbj320.com/owners"
```

- [ ] `/healthz` → `200`
- [ ] `/warmup` → JSON with `"ok": true`
- [ ] One provider page → `200`
- [ ] One state page → `200`
- [ ] `/owners` if owners/UI/navigation touched → `200`
- [ ] One edited public/static page → `200`
- [ ] Basic mobile-width check in browser if UI changed

### High-risk deploy smoke

All medium-risk items, plus:

```powershell
curl.exe -s -m 30 "https://www.pbj320.com/api/dates"
curl.exe -s -m 60 -o NUL -w "%{http_code}" "https://www.pbj320.com/report"
```

- [ ] Relevant API endpoint (e.g. `/api/dates`, `/owners/api/stats` if ownership changed)
- [ ] Relevant report/insight page
- [ ] Render **build** logs: no failed steps in `buildCommand`
- [ ] Render **runtime** logs: `[gunicorn] Listening`, no import errors; no repeated `cold_render_started` / OOM (137) spikes right after deploy

Optional after provider/index changes: `python scripts/warm_provider_cache.py --base-url https://www.pbj320.com --limit 20`

---

## Production deploy flow

1. Classify change (low / medium / high) and check **Do not** guardrails.
2. Push to production-watched branch.
3. Render **build** (`render.yaml` `buildCommand`) — runs on every deploy, including copy-only HTML:
   - `ensure_deploy_csvs.py --quick`
   - State aggregates, provider indexes, staffing compliance, SNF owners indexes, owners DB, sitemap
   - `pbj-wrapped` `npm install && npm run build`
4. Render **start**: `python scripts/render_start.py` → Gunicorn `0.0.0.0:10000`
5. Health probe **`/healthz`** until `200`
6. Old instance SIGTERM (`graceful_timeout=60` in `gunicorn_config.py`)
7. Run smoke checklist for your risk level

---

## Staging and preview

- **Render PR previews** (if enabled): same heavy `buildCommand`; useful for review, not faster copy deploys.
- **Local:** `python app.py` or Gunicorn via `gunicorn_config.py`
- **NY staffing preview:** token path `/preview/ny-staffing-compliance-2025/<token>` on the same app

No separate static-only preview channel exists today.

---

## Rollback

1. **Fastest:** Render Dashboard → **pbj** → **Deploys** → last green deploy → **Rollback**
2. **Git:** Revert on `main` and push (full rebuild)
3. Smoke: `/healthz` + dashboard URL for the area that broke

Rollback does **not** restore in-memory caches.

---

## `old-pbj320` static site

**Status:** Not in `render.yaml`. Not production DNS for `www.pbj320.com`. Legacy `index-render.html` still references `pbj-root.onrender.com` for OG tags — production site uses the Flask app.

| If… | Action |
|-----|--------|
| **Unused** (no DNS, no links) | **Suspend** the service or **disable auto-deploy**. Recommended if you only use `pbj320.com`. |
| **Still used** (OG previews, legacy URL) | Do **not** publish directory `.` (whole repo). Use a minimal folder (e.g. `og/`), add build filters, point OG URLs at `https://www.pbj320.com/…` when retiring the static host. |

Do not change DNS or production routing in routine deploys without an explicit migration plan.

---

## Target route ownership (future static split — not implemented)

When a CDN/static front door is added, **do not implement in this pass**. Target division:

### Static host (future)

| Routes / assets |
|-----------------|
| `/` |
| `/premium` |
| `/attorneys` |
| `/about` |
| `/press` |
| `/data-sources` |
| `/insights/*` |
| Public HTML reports (`insights-*.html`, press variants) |
| Public CSS (`insights-theme.css`, `public-trust.css`, `chow.css`, etc.) |
| Public images, OG/social images |

### Render app (keep)

| Routes / assets |
|-----------------|
| `/provider/*` |
| `/entity/*` |
| `/state/*` |
| State slug dashboard routes (`/<state_slug>`) |
| `/owners/*` |
| `/ownership/*` |
| `/api/*` |
| `/report*` |
| `/rankings*` |
| `/pbjpedia/*` |
| `/wrapped*` |
| `/sff*` |
| `/subscribe` |
| `/contact` |
| `/admin/*` |
| `/sitemap.xml` |
| `/search_index.json` |

Migration requires reverse-proxy rules and build-time HTML injection — deferred.

---

## Build vs runtime (reference)

**Build only** (`render.yaml` `buildCommand`): CSV materialization, indexes, ownership DB, sitemap, `pbj-wrapped` build.

**Runtime start** (`render_start.py`): optional local CSV guard (skipped on Render), brief meta resync, Gunicorn exec. **No** index generation or cache warming.

**Lazy on first traffic:** pandas, owner dashboard, facility CSV scans, cold provider renders.

---

## Repo file reference

| File | Role |
|------|------|
| `render.yaml` | `buildCommand`, `startCommand`, `healthCheckPath: /healthz` |
| `Procfile` | `web: python scripts/render_start.py` |
| `scripts/render_start.py` | Fast Gunicorn start |
| `gunicorn_config.py` | 1 worker, 4 threads, `graceful_timeout=60` |
| `app.py` | `/healthz`, `/health`, `/warmup` |

---

## Intentionally deferred (this pass)

- Static-front-door migration (Vercel / Render Static + proxy to `pbj`)
- Conditional `buildCommand` to skip index rebuilds on HTML-only diffs
- DNS or routing changes for `old-pbj320`
- `app.py` startup refactor
- Retiring or reconfiguring `old-pbj320` in Render Dashboard (documented only; ops action)
