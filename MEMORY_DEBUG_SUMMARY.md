# Memory debug summary (Flask 2GB OOM on Render)

## 1. Memory-risky locations (files + lines)

### app.py
| Location | Line(s) | Risk |
|----------|--------|------|
| `_LOAD_CSV_CACHE` | 987 | Caches full DataFrames (facility_quarterly_metrics, provider_info_combined, state_quarterly_metrics, etc.) with 5 min TTL. Multiple large CSVs can sit in memory at once. |
| `load_csv_data()` | 990–1034 | `pd.read_csv(path, low_memory=False)` loads entire file; no chunking. Called for facility_quarterly_metrics.csv, provider_info_combined.csv, state_quarterly_metrics.csv. |
| `get_canonical_latest_quarter()` | 1047–1068 | Calls `load_csv_data('state_quarterly_metrics.csv')` and `load_csv_data('facility_quarterly_metrics.csv')` → both get cached in _LOAD_CSV_CACHE. |
| `load_facility_quarterly_for_provider()` | 1903–1921 | Calls `load_csv_data('facility_quarterly_metrics.csv')` → full CSV load/cache; then `.copy()` and filter for one provider. |
| `load_provider_info()` | 1184–1302 | Streams CSV in chunks but builds full `provider_dict` (and `provider_dict_by_quarter`) in memory; cached in _LOAD_PROVIDER_INFO_CACHE. |
| `load_entity_facilities()` | 2655–2780 | `pd.read_csv(path, low_memory=False)` for full provider file → cached in _PROVIDER_INFO_ENTITY_CACHE; then `load_csv_data('facility_quarterly_metrics.csv')` at 2768. |
| `load_chain_performance()` | 2798–2846 | `pd.read_csv(path, low_memory=False)` full file; builds dict; cached in _CHAIN_PERF_CACHE. |
| `generate_state_page()` | 5312–5443 | Calls `load_csv_data('state_quarterly_metrics.csv')`, `load_csv_data('cms_region_state_mapping.csv')`, `get_canonical_latest_quarter()` (→ facility_quarterly), `load_sff_facilities()`. |
| `_PROVIDER_PAGE_CACHE` | 5175–5198 | Caches HTML per CCN (120s TTL). Can grow with many unique provider page requests. |
| `_PROVIDER_INFO_ENTITY_CACHE` | 2651, 2682–2696 | Caches full provider DataFrame for entity pages. |
| `get_owner_app()` | 667–684 | Imports `owner_donor_dashboard` on first /owners request → triggers donor module load; first request then runs `ensure_load_data()` → `load_data()`. |

### donor/owner_donor_dashboard.py
| Location | Line(s) | Risk |
|----------|--------|------|
| Module-level data paths | 54–89 | OWNERS_DB, PROVIDER_INFO, OWNERSHIP_RAW (250k CSV), PROVIDER_INFO (provider_info_combined), NH_ProviderInfo_*.csv, etc. |
| `load_data()` | 888–1132 | Loads in one shot (or parallel): owners_df, donations_df, ownership_df (parquet/csv), provider_info_df (full provider_info_combined with usecols), provider_info_latest_df (full NH_ProviderInfo CSV), facility_name_mapping_df, entity_lookup_df, facility_metrics_df; committee_master. On Render, ownership_raw_df is skipped but provider + provider_info_latest are still full CSVs. |
| `ensure_load_data()` + `@app.before_request` | 148–162, 1226–1230 | Every request to donor app runs `ensure_load_data()`; first request runs `load_data()` and loads all DataFrames into module globals. |
| FEC cache read/write | 3438–3443, 3601–3618 | `FEC_CACHE_PATH.read_text()` + `json.loads()`; full cache loaded per request when checking; `json.dumps(cache_data)` on write. |
| `_read_csv` / `_read_csv_or_parquet` inside load_data | 904–927, 935–951 | Full `pd.read_csv` or `pd.read_parquet` for owners, donations, ownership; then provider_info (1089–1103), provider_info_latest (1129–1134), facility_name_mapping (1161), entity_lookup (1177–1182), facility_metrics (1198–1203). |

### Other
| File | Line(s) | Risk |
|------|--------|------|
| app.py | 268, 277–298 | `/search_index.json` serves file; `get_facility_risk_from_search_index()` loads full `search_index.json` into _SEARCH_INDEX_CACHE (5 min TTL). |
| app.py | 946–984 | `load_state_agency_contact()` loads JSON and caches in _STATE_AGENCY_CONTACT_CACHE. |

---

## 2. Where memory likely multiplies (workers / requests)

- **Multiple Gunicorn workers**: Each worker has its own process and its own caches. So _LOAD_CSV_CACHE, _LOAD_PROVIDER_INFO_CACHE, _PROVIDER_PAGE_CACHE, _PROVIDER_INFO_ENTITY_CACHE, _CHAIN_PERF_CACHE, _CANONICAL_QUARTER_CACHE, etc. are duplicated per worker. With 2–4 workers, expect 2–4× baseline DataFrame/CSV memory.
- **Donor sub-app**: First request to `/owner`, `/owners`, or `/owners/api/*` calls `get_owner_app()` → import of `owner_donor_dashboard` → then that app’s `before_request` runs `ensure_load_data()` → `load_data()` loads all donor DataFrames once per process. So each worker that ever serves an owner route holds a full copy of owners_df, donations_df, ownership_df, provider_info_df, provider_info_latest_df, facility_name_mapping_df, entity_lookup_df, facility_metrics_df.
- **Per-request growth**: _PROVIDER_PAGE_CACHE and _LOAD_CSV_CACHE grow with distinct provider pages and distinct CSV filenames requested; TTLs (120s, 300s) delay release. Many unique provider/state/entity pages in a short window increase peak RSS.

---

## 3. Exact places where memory logging was added

### app.py
- **Startup**: After all route/after_request registration, before `if __name__ == '__main__'`: `_log_mem("app_startup")`.
- **Helper**: Near top (after `import gzip`): `import psutil`, `_psutil_process = psutil.Process()`, and `def _log_mem(label)` that prints `[MEM] {label}: {rss_mb:.1f} MB RSS`.
- **Provider page**: Start of `_provider_page_impl(ccn)`: `_log_mem("route_provider_before")`. Before return of successful HTML: `_log_mem("route_provider_after")`.
- **State page**: Start of `_state_page_impl(state_slug)`: `_log_mem("route_state_before")`. After `generate_state_page(state_code)`, before return: `_log_mem("route_state_after")`.
- **generate_state_page**: Start of `generate_state_page(state_code)`: `_log_mem("generate_state_page_start")`. Before successful return (before `return html_content, 200, {...}`): `_log_mem("generate_state_page_end")`.
- **Entity page**: Start of `_entity_page_impl(entity_id)`: `_log_mem("route_entity_before")`. Before return of HTML: `_log_mem("route_entity_after")`.
- **Owner API proxy**: Start of `owner_api_proxy(api_path)`: `_log_mem("route_owner_api_before")`. After building `resp` and before `return resp`: `_log_mem("route_owner_api_after")`.

### donor/owner_donor_dashboard.py
- **Helper**: After `import requests`: `import psutil`, `_donor_psutil_process = psutil.Process()`, and `def _log_mem_donor(label)` printing `[MEM] donor {label}: {rss_mb:.1f} MB RSS`.
- **load_data()**: Immediately after the `global ...` line: `_log_mem_donor("load_data_start")`. Right before starting the committee autocomplete thread: `_log_mem_donor("load_data_end")`.
- **before_request**: Start of `_before_request_ensure_data()`: `_log_mem_donor("before_request_ensure_data")`.

---

## 4. Quick reference: labels you’ll see in logs

| Label | When |
|-------|------|
| `app_startup` | Once per worker when app module is loaded. |
| `route_provider_before` / `route_provider_after` | Each request to `/provider/<ccn>`. |
| `route_state_before` / `route_state_after` | Each request to `/state/<state_slug>`. |
| `generate_state_page_start` / `generate_state_page_end` | Inside state page generation. |
| `route_entity_before` / `route_entity_after` | Each request to `/entity/<id>`. |
| `route_owner_api_before` / `route_owner_api_after` | Each request to `/owners/api/*` (or /owner/api/*, /ownership/api/*). |
| `donor before_request_ensure_data` | Every request to the donor app (before ensure_load_data). |
| `donor load_data_start` / `donor load_data_end` | First request to donor app (or first after restart) when load_data() runs. |

Install `psutil` if needed: `pip install psutil`.
