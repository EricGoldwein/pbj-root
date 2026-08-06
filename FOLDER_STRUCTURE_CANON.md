# Folder Structure Canon

Use this as the canonical map for where files belong.  
Companion: `AGENTS.md` · `docs/AUTHORITY_LADDER.md`

Every 320 / PBJ / Dog environment uses the same **four layers**. Names differ; roles do not.

## 1. Runtime (served by app)

Live routes and assets required for production.

- `app.py` and `templates/`
- root runtime data artifacts consumed by routes:
  - `facility_quarterly_metrics.csv` (often from `.gz` at deploy)
  - `state_quarterly_metrics.csv`
  - `national_quarterly_metrics.csv`
  - `provider_info_combined_latest.csv`
  - `search_index.json`, `*_historical_data.json`, etc.
- `static/`, `public/`, premium HTML under `premium/` when served
- `pbj-wrapped/public/` — **still live** for SFF JSON/PDFs, some `data/json` (e.g. state standards), and `/downloads/sff/*` even though the Wrapped slideshow product is parked
- `PBJPedia/` markdown served as public reference pages
- `insights_posts/` published insight bodies

## 2. Upstream / Raw Inputs

Immutable or slow-changing source inputs. Do not treat as derived.

- `provider_info/` for ProviderInfoNorm / NH snapshots
- `ownership/` for ownership/chain source CSVs (live-serving names stay here until a `_sources` layout is adopted)
- `data/geo/` for geo/state helper inputs
- `data_sources/` documentation of external sources
- `donor/data/` FEC committee master and related inputs
- source PDFs/zips should stay outside runtime paths until processed

## 3. Derived / Generated

Built from upstream; rebuildable; may be gitignored or deploy-built.

- generated JSONs and merged CSVs used by app
- `data/provider_indexes/` (sqlite/pkl — deploy-built)
- `data/compliance/` materialized CSV/sqlite from committed gzip
- SFF derived outputs:
  - `pbj-wrapped/public/sff-facilities.json`
  - `pbj-wrapped/public/sff-candidate-months.json`
- `pbj-wrapped/dist/` Vite build (if present)

## 4. Local / Scratch (not for release)

Ignored by `.gitignore`. **Never required for Render.**

Preferred home for agent QA:

- `_scratch/` — default for smoke HTML, patch probes, WIP backups
- `artifacts/`, `audit_artifacts/` — larger local dumps
- `donor/output/` — donor pipeline local output
- root patterns already ignored: `_smoke_*`, `_patch_*`, `_tmp_*`, `_audit_*`, `_parse_*`, `_verify_*`, `_wt_*/`, `_wip_aside/`

**Rule:** New agent probes go under `_scratch/`, not the repo root. Legacy root `_smoke_*` files may remain gitignored until an explicit cleanup pass.

## Product surfaces inside this repo (still one git root)

| Surface | Primary folders |
|---------|-----------------|
| Public site | `app.py`, `templates/`, root HTML |
| Insights | `insights_posts/`, `insights.html` |
| Owners / FEC | `donor/`, `/owners` routes |
| SFF + legacy Wrapped host | `pbj-wrapped/` (product parked; `public/` still runtime) |
| Premium samples | `premium/` |
| Audience prompts | `audience/` |
| Metric contract | `pbj-contract/` |

## Rule of Thumb

If a file is required for live routes, it must have **one** canonical location and be referenced from **exactly one** loader path in code.
