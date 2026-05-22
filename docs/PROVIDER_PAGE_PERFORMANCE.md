# Provider page performance — diagnosis and tuning

Plain-language summary of why `/provider/{ccn}` is sometimes slow, what we changed, and how to test.

## Diagnosis (plain English)

**The real problem is not “three unwarmed smoke-test pages.”**  
Cold provider rendering is **CPU-heavy** (~5–15s per facility on cache MISS). Render metrics showing **CPU pinned at 100%** on a **1 CPU** instance mean the server is often **compute-bound**, not “missing a magic warm list.”

**What happens on each request**

1. **Cache HIT** — HTML already built in this worker’s memory → usually **fast** (&lt;100 ms).
2. **Cache MISS** — Stream rows from `facility_quarterly_metrics.csv`, load CMS fields from provider-info CSV, run `generate_provider_page_html()` (charts, ownership blocks, case-mix, etc.) → **slow**.
3. **Queue** — Only **2 cold renders at a time per worker** (`PBJ_PROVIDER_COLD_SLOTS`). More requests wait or get **503 Server busy**.

**After deploy**

- Memory drops (restart), then climbs as caches fill — normal.
- Every Gunicorn **worker** has its **own** cache (default **2 workers**). A page warmed on worker A is still cold on worker B.
- **Do not** add workers blindly: more workers = **more RAM** (duplicate pandas/caches) and **more cold-cache fragmentation**.

**Bots**

- **AI crawlers** (GPTBot, Claude, Perplexity, etc.) used to be only rate-limited; they could still trigger **cold renders** on cache MISS and steal CPU.
- On Render, **`PBJ_AI_PROVIDER_CACHE_ONLY=1`** (default): AI bots get **429 on provider cache MISS** — no cold render. **`/entity/{id}`** has no HTML cache; AI bots get **429** before heavy load. Google/Bing still allowed to cold-render for SEO.
- **Aggressive SEO scrapers** still get **429** on `/provider` and `/entity`.

**Smoke-test CCNs (075325, 335513, 075263)**

- Used only in **deploy checks** — not popular facilities.
- Warming them only proves routing/HTML for those URLs; it does **not** fix national slowness.

## Cold-render bottleneck (code path)

Per cache MISS, in order:

| Step | What |
|------|------|
| 1 | `load_facility_quarterly_for_provider(ccn)` — chunked scan of `facility_quarterly_metrics.csv` (sorted by PROVNUM; stops at matching CCN) |
| 2 | `_provider_info_row_for_ccn` — national provider-info cache or `load_provider_info(ccn_only=…)` chunked scan |
| 3 | `generate_provider_page_html()` — large HTML string: charts, takeaway, ownership/CHOW (CT), case-mix, provider-info fields, layout |
| 4 | Store in `_PROVIDER_PAGE_CACHE` (per worker, max 400 entries, TTL 900s on Render) |

**Not loaded on every request:** full national provider-info index (unless cache cold), full facility CSV into memory (streaming per CCN).

**Future ROI (not implemented here)**

- Precomputed static fragments per CCN at deploy (heavy build step).
- Shared Redis/HTML cache across workers (ops + invalidation).
- Startup preload of provider-info index when RAM allows.
- More CPU on Render before more workers.

## Instrumentation

Every `/provider/{ccn}` request logs one JSON line when `PBJ_PROVIDER_PERF_LOG=1` (default on Render):

```text
[PBJ_PROVIDER] {"cache":"MISS","ccn":"335513","cold_render_ms":8420.1,"outcome":"cold_render","pid":123,"queue_wait_ms":120.5,"status":200,"stale":false,"total_ms":8541.2,"ua":"human"}
```

| Field | Meaning |
|-------|---------|
| `cache` | `HIT` or `MISS` |
| `total_ms` | End-to-end request time |
| `cold_render_ms` | Time in pandas + HTML generation (0 on HIT) |
| `queue_wait_ms` | Time waiting for cold-render semaphore |
| `pid` | Gunicorn worker process id |
| `ua` | `human`, `googlebot`, `bingbot`, `ai_crawler`, `aggressive_bot`, `other_bot` |
| `stale` | Served from cache while another request was queued (contention) |
| `outcome` | `cache_hit`, `cold_render`, `queue_rejected`, `ai_cache_only`, etc. |

## Env vars (Render defaults in `app.py`)

| Variable | Render default | Purpose |
|----------|----------------|---------|
| `PBJ_PROVIDER_PERF_LOG` | `1` | Structured `[PBJ_PROVIDER]` logs |
| `PBJ_AI_PROVIDER_CACHE_ONLY` | `1` | AI crawlers: no cold render on MISS |
| `PBJ_AI_CRAWLER_RATE_LIMIT` | `6` | AI requests per IP per minute on /provider, /entity |
| `PBJ_PROVIDER_BROWSER_CACHE` | `1` | `private, max-age=300, must-revalidate` |
| `PBJ_PROVIDER_PAGE_CACHE_TTL` | `900` | In-memory HTML cache (15 min) |
| `PBJ_PROVIDER_COLD_SLOTS` | `2` | Concurrent cold renders per worker |
| `PBJ_GUNICORN_WORKERS` | `2` | **Not auto-increased** — check RAM first |

## Deploy warming (modest, optional)

```bash
python scripts/warm_provider_cache.py --base-url https://www.pbj320.com --limit 20 --passes 3
```

- Helps **only** URLs that are fetched.
- **Costs CPU** during the run — avoid aggressive warming on a **1 CPU** instance right after deploy.
- `check_deploy_53c6698.py` runs the same modest warm before smoke tests.

## Is upgrading Render the right short-term move?

**Yes, if CPU is repeatedly at 100%.** Code tuning (bots, cache, browser `max-age`) reduces **waste** but does not add compute. A **higher CPU** plan (or more CPU per instance) likely helps **cold MISS latency** and **503 rate** more than going from 2→3 workers on the same 1 CPU / tight RAM box.

**Order of operations**

1. Deploy this change; watch `[PBJ_PROVIDER]` logs and Render CPU.
2. If humans still see slow **first** visits and CPU is pinned → **upgrade CPU** (or plan tier).
3. Only then consider `PBJ_GUNICORN_WORKERS` if RSS headroom exists (see `/debug/mem` with `PBJ_MEM_DEBUG=1`).

## Before/after test plan

### 1. Same provider × 3 (human UA)

```bash
curl -sI -A "Mozilla/5.0" https://www.pbj320.com/provider/335513 | grep -i x-pbj-provider-cache
```

Expect: first `MISS` (slow), second/third `HIT` (fast) on same worker (repeat quickly).

### 2. Five random CCNs (cold_render_ms)

Pick 5 CCNs from search index; one request each with human UA; grep Render logs:

```text
[PBJ_PROVIDER] ... "outcome":"cold_render" ... "cold_render_ms":...
```

Record `cold_render_ms` and `queue_wait_ms`.

### 3. Bot UA

```bash
curl -sI -A "Mozilla/5.0 (compatible; GPTBot/1.0)" https://www.pbj320.com/provider/335513
```

Expect on MISS: **429** and no long cold render (check logs for `ai_cache_only`).

```bash
curl -sI -A "Mozilla/5.0 (compatible; Googlebot/2.1)" https://www.pbj320.com/provider/335513
```

Expect: **200** or **404**; may cold-render (SEO preserved).

### 4. Render metrics

During tests: CPU %, memory %, correlate with deploy time and warming script.

### 5. Browser cache

After deploy, repeat visit to same provider within 5 minutes; back navigation should feel snappier (`Cache-Control: private, max-age=300` on Render).
