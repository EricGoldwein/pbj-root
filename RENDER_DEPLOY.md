# Render memory, cache, and provider warming

**Production deploy runbook** (deploy flow, `/healthz`, smoke tests, rollback, risk levels): **`DEPLOYMENT.md`**.  
**Local dev:** `DEPLOY_AND_RUN.md`. **CSV/index build gates:** `docs/DATA_DEPLOY.md`.

This file covers Render-specific **memory tuning**, **provider cache warming**, and the optional **`old-pbj320`** static site — not the canonical production deploy procedure.

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
| `PBJ_PROVIDER_PAGE_CACHE_TTL` | **900 on Render** (15 min) | Set automatically in `app.py` on Render (`setdefault`); optional override in dashboard. |
| `PBJ_PROVIDER_PAGE_CACHE_MAX` | **150 on Render** | Max in-memory provider HTML entries per worker; override via env if needed. |
| `PBJ_PROVIDER_PAGE_HTML_BUDGET_MB` | **50** | Per-worker cap on total cached provider HTML bytes; oldest entries evicted when exceeded. |
| `PBJ_FACILITY_QUARTERLY_LRU` | **64 on Render** (128 local) | Max per-facility quarterly DataFrames retained per worker; try **32** if `/debug/mem` shows large LRU footprint. |
| `PBJ_AI_CRAWLER_RATE_LIMIT` | `12` on Render | Max `/provider/*` and `/entity/*` requests per IP per window for User-Agents matching `gptbot` / `oai-searchbot`. Set `0` to disable. |
| `PBJ_AI_CRAWLER_RATE_WINDOW` | `60` | Seconds for the limit above. Over limit → `429` + `Retry-After` (crawler can retry later). |
| `PBJ_AI_CRAWLER_MARKERS` | `gptbot,oai-searchbot` | Comma-separated UA substrings; does not block `ChatGPT-User` (human link clicks). |
| `PBJ_MEM_DEBUG` | off | Set to `1` temporarily; logs `[MEM]` RSS and enables `GET /debug/mem` (404 when off). |
| `PBJ_MEM_ROUTE_LOG` | off (on when `PBJ_MEM_DEBUG=1`) | `[MEM_ROUTE]` lines: RSS, path, elapsed ms, status for heavy routes (`/provider/*`, `/entity/*`, `/premium/*`, `/report*`, `/warmup*`, compliance API, owner API). |
| `PBJ_MEM_LOG_RSS_MB` | `700` | **Unrelated to page cache.** Logs any route when process RSS ≥ 700 MB (needs `psutil`). |

### Memory profiling (2GB Render)

While profiling, set **`PBJ_GUNICORN_WORKERS=1`** on the 2GB service. Two pandas-heavy workers duplicate indexes and caches and can make the 2GB limit look like creep when it is really **2× baseline RSS**.

Enable temporarily:

```bash
PBJ_MEM_DEBUG=1
PBJ_GUNICORN_WORKERS=1
```

**Pass 1 — cold fill** (note `rss_mb`, `provider_page_html.total_bytes`, `facility_quarterly_lru.total_bytes` after each step):

1. `GET /healthz`
2. `GET /debug/mem`
3. Cold `GET /provider/075325` (wait for 200)
4. `GET /debug/mem`
5. Cold `GET /provider/335513` (wait for 200)
6. `GET /debug/mem`
7. `GET /entity/<large_chain_id>` (pick a chain with many facilities from production)
8. `GET /debug/mem`
9. `GET /state/ny` or `GET /report` (major aggregate page)
10. `GET /debug/mem`

**Pass 2 — repeat the same sequence.** Compare snapshots:

| Pattern | Meaning |
|---------|---------|
| RSS and cache byte totals **flat on pass 2** | Healthy first-pass cache fill (A) |
| RSS or `provider_page_html.total_bytes` / `facility_quarterly_lru.total_bytes` **grow every pass** | True leak or unbounded cache (B) — lower `PBJ_PROVIDER_PAGE_CACHE_MAX`, `PBJ_FACILITY_QUARTERLY_LRU`, or investigate partial provider-info merges |

If `provider_page_html.total_bytes` routinely exceeds **50MB** under normal warm traffic, the app evicts oldest HTML automatically; consider lowering `PBJ_PROVIDER_PAGE_CACHE_MAX` (e.g. 75) or `PBJ_PROVIDER_PAGE_HTML_BUDGET_MB`.

Access `/debug/mem` via `PBJ_MEM_DEBUG=1`, header `X-PBJ-Warmup-Key: $PBJ_WARMUP_SECRET`, or `?key=$ADMIN_VIEW_KEY`.

**Quick profiling:** After deploy with `PBJ_MEM_DEBUG=1`, hit `/healthz`, one `/provider/…`, one `/entity/…`, then `GET /debug/mem` to see cache sizes.

## Provider cache warming (optional, modest)

Cold `/provider/{ccn}` is **CPU-heavy** (~5–15s). Warming only helps URLs you fetch; it does **not** fix national slowness. Anchor CCNs (075325, 335513, 075263) are **deploy smoke fixtures**, not important facilities.

```bash
# Recommended after deploy (costs CPU — avoid huge limits on 1-CPU instances)
python scripts/warm_provider_cache.py --base-url https://www.pbj320.com --limit 20 --passes 3

# Smoke only (3 anchor CCNs)
python scripts/warm_provider_cache.py --anchors-only
```

Env overrides: `PBJ_WARM_BASE_URL`, `PBJ_WARM_PROVIDER_LIMIT`, `PBJ_WARM_PROVIDER_PASSES`, `PBJ_WARM_PROVIDER_TIMEOUT`, `PBJ_WARM_PROVIDER_DELAY`.

`python scripts/check_deploy_53c6698.py` runs the modest warm (`--limit 20 --passes 3`) before smoke checks.

See `docs/PROVIDER_PAGE_PERFORMANCE.md` for diagnosis, `[PBJ_PROVIDER]` logs, and Render CPU guidance.

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

## Health check and start command

Canonical settings: **`DEPLOYMENT.md`** (`/healthz` liveness, `/warmup` readiness smoke only, `python scripts/render_start.py`, full `render.yaml` build pipeline).

### Startup log markers (troubleshooting)

After deploy, grep logs for:

| Marker | Meaning |
|--------|---------|
| `[render_start] start command begins` | Instance start |
| `[render_start] ensure_deploy_csvs skipped` | Expected when `PBJ_SKIP_START_CSV_ENSURE=1` and build artifacts exist |
| `[render_start] gunicorn launch` | About to exec Gunicorn |
| `[gunicorn] Listening on 0.0.0.0:10000 at …` | Port open — health checks can succeed |
| `ensure_deploy_csvs: begin` in **build** logs only | CSV materialization at deploy build |

If you see `ensure_deploy_csvs` for **20+ seconds at instance start** (not in build logs) before `[gunicorn] Listening`, the Dashboard Start Command is wrong — see **`DEPLOYMENT.md`** (must be `python scripts/render_start.py` only).
