# PBJ320 performance work — real-world gains (May 2026)

Commits: `354befc` (SQLite threads), `53c6698` (perf + bots), `2f3ac7d` (report UX/CSS).

## Human-visible

| Area | Before | After |
|------|--------|--------|
| Provider repeat visit (same CCN, &lt;15 min) | Often 10+ s | Usually **&lt;100 ms** (in-memory HTML cache) |
| Provider first visit during GPT crawl | Could queue 10+ s behind bots | Less queueing; bots throttled after **12/min/IP** |
| Provider/entity/state takeaway avatar | **1.6 MB** PNG download on mobile | **~2 KB** WebP |
| Report mobile | 2× state CSV (~1.2 MB extra); blocking D3 in head | **1×** state CSV; deferred D3/report JS |
| Report console | `contact-popup-shared.css` MIME error (HTML 404) | Inlined styles on report; CSS route fixed |
| CT provider ownership | Missing / errors (SQLite threads) | Block present; cache bust if stale |
| Facility footer | 3 items + About data; Related mid-page | **PBJ through Qx · CMS Provider Info**; Related under sources; **PBJ320 CSV** |

## Lighthouse (lab, not CrUX)

Illustrative targets from May 2026 runs:

| URL | Mobile score (before → expected) | Main lever |
|-----|----------------------------------|------------|
| `/provider/335513` | ~62 → **~75–85** | Phoebe WebP |
| `/report` | ~51 → **~55–70** | Dedupe CSV + defer JS (still ~18 MB data) |

Server **cold** provider render (~10 s) is unchanged by front-end fixes.

## Capacity / ops

- **GPTBot:** Not blocked; slowed. Humans unaffected.
- **RAM:** No new always-on services. Provider cache capped (400 entries).
- **Risk:** Low — HTML/CSS/footer only except bot middleware and SQLite thread fix.

## Still heavy (future work)

- `/report` first load: ~12 MB `embed/pi` + ~4 MB facility CSV in browser
- Provider **first** hit per worker: full cold build
- `insights.html` / `about.html` still use `phoebe.png` in some places

## Verify after deploy

```bash
python scripts/check_deploy_53c6698.py
# optional modest warm (not a substitute for CPU / code tuning):
python scripts/warm_provider_cache.py --base-url https://www.pbj320.com --limit 20 --passes 3
```

Hard-refresh `/report` and one provider page in browser; confirm no contact-popup MIME error and footer copy. Second visit to same provider should show `X-PBJ-Provider-Cache: HIT` in Network headers. Grep Render logs for `[PBJ_PROVIDER]` JSON (see `docs/PROVIDER_PAGE_PERFORMANCE.md`).
