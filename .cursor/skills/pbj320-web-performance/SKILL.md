---
name: pbj320-web-performance
description: >-
  PBJ320 production performance, Lighthouse vs server slowness, Render/Gunicorn,
  Git LFS deploy pitfalls, and safe front-end patterns for pbj320.com.
---

# PBJ320 web performance and production

## Git LFS (critical for deploys)

- **10 GB/month bandwidth** is consumed almost entirely by **Render[bot]** cloning and smudging LFS files (~3 GB per full fetch).
- LFS paths: `facility_quarterly_metrics.csv` (~190 MB), `provider_info_combined_latest.csv` (see `.gitattributes`).
- **Do not** commit LFS CSVs on small code-only PRs; each push can trigger Render clone → bandwidth.
- Perf/UI commits (`app.py`, `report.html`) do **not** use LFS but still trigger deploys.
- If LFS budget exceeded: deploy fails with smudge error; pause auto-deploy; see `docs/LFS_BANDWIDTH.md`.
- **Safe Render deploy without LFS bandwidth:** `GIT_LFS_SKIP_SMUDGE=1` + `python scripts/ensure_deploy_csvs.py` in `buildCommand` (copies `facility_quarterly_metrics_latest.csv` over LFS pointer). Provider data from `provider_info/ProviderInfoNorm_*.csv` (normal git).
- Skip-smudge **alone** is unsafe (pointer files look like CSV paths). Never deploy without `ensure_deploy_csvs.py`.

## Two kinds of “slow”

| Symptom | Layer | Fixes |
|--------|-------|--------|
| `MEM_ROUTE` 6–14s `/provider/*` | Server cold HTML | Provider cache (900s on Render), GPT rate limit, workers |
| Lighthouse bad, HTML fast | Browser | WebP avatars, dedupe report CSV fetches, defer D3 |

## Render defaults (no dashboard needed)

- `PBJ_PROVIDER_PAGE_CACHE_TTL=900`, `PBJ_PROVIDER_PAGE_CACHE_MAX=400`
- `PBJ_AI_CRAWLER_RATE_LIMIT=12` / `WINDOW=60` — GPTBot on `/provider/*`, `/entity/*` only
- `PBJ_MEM_LOG_RSS_MB` — logging only, not performance

## Static assets

- 48×48 Phoebe: `/phoebe-avatar-72.webp`, not `/phoebe.png` (~1.6 MB)
- CSS: serve from `APP_ROOT`; catch-all `*.css` must not use `'.'` cwd
- `report.html`: inline contact-popup CSS; avoid external stylesheet for report

## Report `/report`

~18 MB first load still: `embed/pi`, `facility_quarterly_metrics_latest.csv`, state CSV. Dedupe `fetchStateQuarterlyMetricsCsvText()`; defer D3 at end of body.

## Provider pages

- **Deploy indexes:** `build_facility_provider_indexes.py` + `validate_provider_index_schema.py` in Render `buildCommand`. Schema contract: skill **`pbj320-provider-indexes`**.
- CT ownership: `pbj-details-ownership`; cache bust if missing
- SQLite: per-thread connections in `owner_profile.py` (not `@lru_cache` on connections)

## Facility footer UX

- Sources: `PBJ through {quarter}` · `CMS Provider Info` (no About data button on facility)
- Download label: **PBJ320 CSV**
- Related links: footer below sources (`pbj-cross-links-footer`)

## Post-deploy

`python scripts/check_deploy_53c6698.py` — only after LFS quota allows Render clone.
