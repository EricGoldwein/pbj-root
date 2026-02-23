# Data sources and publishability

**Canonical external URLs, contact info, and link structure:** see [SOURCES.md](SOURCES.md).

## What’s in git (publishable)

- **App and static site**: `app.py`, HTML (index, about, press, report, insights, etc.), static assets, `search_index.json`.
- **PBJ Wrapped / dashboard data**: `pbj-wrapped/public/data/json/` (e.g. facility/state JSON by region), `pbj-wrapped/public/sff-facilities.json`, `pbj-wrapped/public/data/json/state_standards.json`, `state_agency_contact.json`, etc.
- **Donor dashboard**: FEC committee master CSVs under `donor/data/fec_committee_master/` (explicitly un-ignored).
- **Provider info (owner dashboard)**: `provider_info/NH_ProviderInfo_Jan2026.csv` (un-ignored). For **quarter-aligned** provider/entity data (e.g. Q3 2025), use `provider_info_combined.csv` and run `extract_latest_quarter.py` to create `provider_info_combined_latest.csv`; the app prefers that file when present. NH_ProviderInfo is a single snapshot (no quarter column) and is used only when combined/_latest are not available.
- **Chain performance (entity pages)**: `2025-11/Chain_Performance_*.csv` (e.g. `Chain_Performance_20251205.csv`). Not gitignored; include in repo or place on server for entity-page chain metrics (facilities, states, SFF, abuse, fines, CMS star ratings, ownership mix).

## What’s gitignored (not in repo – server or local only)

These are listed in `.gitignore` and are **not** published with the repo:

| File / pattern | Purpose | Where it’s used |
|----------------|--------|-----------------|
| `provider_info_combined.csv` | Entity/facility lookup, provider info (multi-quarter) | Entity pages, provider pages, search |
| `provider_info_combined_latest.csv` | Same, one quarter (from `extract_latest_quarter.py`); preferred when present | Same; has explicit quarter (e.g. Q3 2025) |
| `facility_quarterly_metrics.csv` | Facility-level quarterly PBJ metrics | Provider pages, entity facility list, charts |
| `facility_quarterly_metrics_latest.csv` | Fallback (same, latest subset) | Same (fallback in `load_csv_data`) |
| `state_quarterly_metrics.csv` | State-level quarterly metrics | State pages, rankings, charts |
| `national_quarterly_metrics.csv` | National metrics | Charts / comparisons |
| `cms_region_quarterly_metrics.csv` | Region-level metrics | Region / PBJpedia-style pages |
| `macpac_state_standards_clean.csv` | State staffing standards | State standard lines/badges |
| `facility_lite_metrics.csv` | Lite facility metrics | Preprocessing / optional |
| `*_old.csv`, `*_latest.csv`, `*_updated.csv` | Old/duplicate CSVs | — |
| `NH_ProviderInfo_*.csv` (except Jan2026) | Raw CMS provider info | — |
| `donor/FEC data/*.parquet`, `*.zip`, committee CSVs, etc. | FEC bulk / donor data | Donor dashboard (server-only) |

## Where the app looks for data

- **CSVs**: `load_csv_data()` in `app.py` tries, in order:
  - `filename` (current working directory)
  - `APP_ROOT/filename`
  - `pbj-wrapped/public/data/filename`
  - `pbj-wrapped/dist/data/filename`
  - `data/filename`
- **JSON**: State standards, SFF, agency contact, etc. are under `pbj-wrapped/public/data/json/` or `pbj-wrapped/public/` and **are** in git.
- **Search**: `search_index.json` is in git and used for the index search.

## Safe to say?

- **Code and static content**: Yes – everything in the repo is publishable; nothing critical is gitignored except the items above.
- **Data**: The **large CSVs** (facility/state quarterly metrics, provider_info_combined, macpac, etc.) are **intentionally** gitignored. For a deploy:
  - Either place those CSVs on the server (same paths the app checks), or
  - Rely on the JSON in `pbj-wrapped/public/data/` where the app already supports it (e.g. wrapped/dashboard); provider/state/entity dynamic pages currently expect the CSVs to be present on the server.

So: **we know where all the data is** (this file + `.gitignore`); **not all data is in the repo** – the big CSVs are server/local only by design.
