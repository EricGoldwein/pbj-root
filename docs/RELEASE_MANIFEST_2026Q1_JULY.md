# Release manifest — PBJ Q1 2026 + July 2026 packages

**Target:** PBJ `2026Q1` · Provider Norm July 2026 · SFF July 2026 · Ownership `2026-07-17` · current UI · audience  
**Date check:** No conflicts (verified 2026-07-29 from local artifacts).  
**Verdict gate:** Not ready until Phase 5–6 pass.

Legend: **Commit** = must be in git for Render; **Render** = generated in `render.yaml` buildCommand; **Local** = gitignored working copy.

---

## 1. PBJ quarterly facility data

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Facility metrics gz | Local full CSV history | `facility_quarterly_metrics.csv.gz` | **Yes** | Decompress → `.csv` + `_latest` | 2026Q1 (37 qtrs) | **M** | Provider, entity, indexes, SPA |
| Raw facility CSV | gz decompress | `facility_quarterly_metrics.csv` | No (gitignore) | Yes | 2026Q1 | Local | Server loaders |
| `_latest` hardlink/copy | ensure_deploy | `facility_quarterly_metrics_latest.csv` | No | Yes | 2026Q1 | Local | Internal only (must not be public) |
| Quarter label | Aggregates / pipeline | `latest_quarter_data.json` | **Yes** | No | 2026Q1 | **M** | Homepage, `/api/dates` |

## 2. National and state aggregates

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| National quarterly | Facility agg | `national_quarterly_metrics.csv` | **Yes** | No* | max 2026Q1 | **M** | State vs national, charts, wrapped preprocess |
| State quarterly | Facility agg | `state_quarterly_metrics.csv` | **Yes** | No* | max 2026Q1 | **M** | `/state/*`, ranks, charts |
| State page aggregates | Script from CSVs | `data/state_page_aggregates.json.gz` | **Yes** (also rebuilt) | **Yes** `build_state_page_aggregates.py` | 2026Q1 | **M** | Fast `/state` hydrate |

\*Ensured present by deploy gates; not regenerated from scratch on Render.

## 3. Historical and regional aggregates

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| National historical JSON | National CSV | `national_historical_data.json` | **Yes** | No | latest 2026Q1 | **M** | Charts / homepage |
| CMS region quarterly | `add_medians_to_state_quarterly.py` | `cms_region_quarterly_metrics.csv` | **Yes** | No | **must include 2026Q1** | **M** (still 2025Q3 only — regenerate) | State region panels, `/report` |
| Region→state map | Static | `cms_region_state_mapping.csv` | Yes (unchanged) | No | n/a | tracked | Region joins |

## 4. Provider search / index data

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Search index | Provider + facilities | `search_index.json` | **Yes** | No | July-aligned | **M** | Site search |
| CHOW index | Pipeline | `chow_index.json` | **Yes** | No | current | **M** | CHOW UI |
| Provider sqlite/pkl | Facility CSV | `data/provider_indexes/*` | No | **Yes** build+validate | 2026Q1 meta | gitignore (stale locally) | `/provider` cold path |
| Sitemap | Routes/data | `data/deploy/sitemap.xml` | **Yes** (also rebuilt) | **Yes** | current | **M** | `/sitemap.xml` |

## 5. Provider Information Norm

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Norm July | PBJapp normalize + copy | `provider_info/ProviderInfoNorm_2026_07.csv` | **Yes** | Backfill+validate | July 2026 | **??** | Provider CMI/urban, `/api/dates` |
| Combined latest | Pipeline | `provider_info_combined_latest.csv` | **Yes** | Soft-warn if missing | July-aligned | **M** | Ownership legal names, report |
| NH Jul (parity) | CMS | `NH_ProviderInfo_Jul2026.csv` | No (gitignore) | Self-check without NH | July | Local only | Local validate only |
| Report Norm pin | Code | `_REPORT_PINNED_PROVIDER_NORM_REL` | Code change → July | n/a | Align to July | Currently June pin | `/report` |

## 6. Compliance

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Summary gz | PBJapp export | `data/compliance/staffing_compliance_summary.csv.gz` | **Yes** | Decompress + index | incl. CY2026Q1 | **M** | Facility takeaway compliance |
| Manifest | Export | `staffing_compliance_manifest.json` | **Yes** | Validate | CY2026Q1 | **M** | Gates |
| Thresholds | Config | `staffing_compliance_thresholds.json` | **Yes** | Copy | current | **M** | Labels |
| Runtime sqlite | Build script | `staffing_compliance_index.sqlite` | No | **Yes** | 2026Q1 | gitignore | Fast lookup |

## 7. SFF

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Current release meta | Extract pipeline | `data_sources/cms/sff/current_release.json` | **Yes** | No | 2026-07 | **M** | `/api/dates` |
| Derived JSON | PDF extract | `data/derived/sff/sff_facilities.json` | **Yes** | No | July 2026 | **M** | High-risk, `/sff` |
| Public JSON | Publish | `pbj-wrapped/public/sff-facilities.json` | **Yes** | No | July | **M** | Wrapped |
| Public PDF | CMS copy | `pbj-wrapped/public/sff-posting-with-candidate-list-july-2026.pdf` | **Yes** | No | July | **??** | `/downloads/sff/...` |
| Raw July PDF+manifest | Archive | `data_sources/cms/sff/raw/2026-07/*` | **Yes** (repro) | No | July | **??** | Provenance |
| Tables CSV (optional) | Extract | `data/derived/sff/tables/*`, `sff_facilities.csv` | Optional | No | July | **??** | Offline / QA |

## 8. Ownership

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| SNF All Owners July | CMS | `ownership/SNF_All_Owners_2026.07.17.csv` | **Yes** | Index build | 2026-07-17 | **??** | Owners profiles |
| Policy | Hand-edited | `ownership/ownership_release_policy.json` | **Yes** | Resolve active | 2026-07-17 | **M** | Active release |
| Handoff module | Code | `ownership/ownership_active_release_handoff.py` (+ parse if needed) | **Yes** | Import | n/a | **??** | Policy checksum |
| Handoff staged | Stage script | `ownership/_handoff/*` | **Yes** | Validate | 2026-07-17 | **??** | Provenance |
| CCN bridge | Derived | `ownership/_derived/**` | **Yes** | Lookup | 2026-07-17 | **??** | CCN join |
| snf_owners indexes/sqlite | Build scripts | `snf_owners_*.json.gz`, `*.sqlite` | Prefer commit current; **Render rebuilds** | **Yes** | July | **M** | `/provider` ownership, `/owners` |
| Chain performance Jun | CMS | `Nursing_Home_Chain_Performance_Measures_Jun_2026.csv` | **Yes** (staged A) | No | June 2026 | **A** | Entity chain metrics |
| Policy/profile py changes | Code | `ownership_release_policy.py`, etc. | **Yes** | No | n/a | **M** | Runtime |

## 9. Wrapped / static application data

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Quarterly JSON (~255) | `npm run preprocess` | `pbj-wrapped/public/data/json/quarterly/**` | **Yes** (or regen on Render from CSVs) | **Yes** preprocess | q2=2026Q1 | **M** | Wrapped SPA |
| Legacy `national_q2.json` (root) | Old path | `pbj-wrapped/public/data/json/national_q2.json` | Quarantine/delete or ignore | Prefer unused | Must not be 2025Q2 live | stale | Risk if mounted |
| Vite dist | `npm run build` | `pbj-wrapped/dist/**` | Usually not required | **Yes** | current | build | `/wrapped` |
| UI templates | Editors | `app.py`, `index.html`, `about.html`, `make_dynamic.py`, … | **Yes** | No | n/a | **M** | Site |

## 10. Audience code and assets

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| Package | New feature | `audience/*.py` | **Yes** | No | n/a | **??** | Signup, inject, admin |
| JS/CSS | New feature | `pbj-audience.js`, `pbj-audience.css` | **Yes** | No | n/a | **??** | Pages |
| App wiring | Code | `app.py` imports/routes | **Yes** with package | No | n/a | **M** | Mount |
| Optional DB | Env | audience sqlite/postgres | Env docs; soft-fail | Runtime | n/a | local | Persistence |

## 11. Methodology / source files

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| State standards JSON | MACPAC pipeline | `pbj-wrapped/public/data/json/state_standards.json` | Yes | No | current | tracked | State min badges |
| MACPAC CSV | Pipeline | `macpac_state_standards_clean.csv` | No (gitignore) | Prefer JSON | n/a | Local | Methodology table fallback |
| About/methodology pages | HTML | `about.html` etc. | **Yes** | No | n/a | **M** | `/about` |

## 12. Deployment configuration

| Item | Source | Output | Commit | Render | Expected | Git status | Consumer |
|------|--------|--------|--------|--------|----------|------------|----------|
| `render.yaml` | Ops | build/start/env | Yes if changed | Executes | current | tracked | Deploy |
| `scripts/ensure_deploy_csvs.py` | Ops | CSV materialize | Yes if changed | First build step | — | tracked | Gates |
| Env: `SECRET_KEY`, audience DB | Dashboard | secrets | Dashboard | Runtime | set in prod | not in git | Flask/session |

---

## Intentionally excluded / gitignored

- Raw `facility_quarterly_metrics.csv` / `_latest` (built from gz)
- `NH_ProviderInfo_*` except whitelist (Norm self-check on Render)
- `data/provider_indexes/*` (Render build)
- `pre_*` backup CSVs
- `audience` DB files if any; `__pycache__`
- `data/preview_catalog/poc/*` (optional; not required for this release unless routes enabled)
- `data/geo_intelligence/*` — include only if `/geo` is in-scope for this release (default: **include CT bundle** if route live)

## Date alignment decision

| Surface | Decision |
|---------|----------|
| PBJ | **2026Q1** everywhere |
| Norm (site + `/api/dates`) | **July 2026** |
| Report pin | **Align to July** (`ProviderInfoNorm_2026_07.csv`) — was June |
| SFF | **July 2026** |
| Ownership | **2026-07-17** |
| Chain performance CSV | **June 2026** (latest CMS chain file; OK lag vs owners) |
| Region CSV | Regenerate to **2026Q1** (was 2025Q3 — blocking) |
