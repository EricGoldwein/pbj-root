# Data Accuracy Audit — Entity, State, Provider, SFF Pages

This document is the **master checklist** for ensuring every datapoint on provider, state, entity, and SFF pages is accurate: no rounding errors, no bad fallbacks, no mislabeled columns.

---

## 0. Canonical quarter and fallback policy

- **Single source of truth for “current” quarter**: `get_canonical_latest_quarter()` returns the latest quarter from `state_quarterly_metrics.csv` (else `facility_quarterly_metrics.csv` / `_latest`). State, provider, and entity pages all use this so they show the same quarter (e.g. Q3 2025).
- **No prior-quarter-as-current**: We never label an older quarter as the “latest” quarter. If a state or facility has no row for the canonical quarter, we show that state’s or facility’s actual latest row and still label it with that row’s quarter (not the canonical one).
- **No synthetic data**: Fallbacks use only real CSV/JSON data (e.g. facility count from state_quarterly for the same quarter, or facility aggregate for charts). No placeholder numbers, no made-up HPRD/census.

---

## 1. Data sources and column contracts

### 1.1 Facility (provider) page

| Source | File(s) | Required columns | Aliases / notes |
|--------|--------|-------------------|-----------------|
| Facility quarterly metrics | `facility_quarterly_metrics.csv` (fallback: `facility_quarterly_metrics_latest.csv`) | `PROVNUM`, `CY_Qtr`, `STATE`, `Total_Nurse_HPRD` | Optional: `RN_HPRD`, `Nurse_Assistant_HPRD`, `Nurse_Care_HPRD`, `Contract_Percentage`, `avg_daily_census` or `Avg_Daily_Census` |
| Provider info | `provider_info_combined.csv` → `pbj-wrapped/public/data/provider_info_combined.csv` | CCN key: `ccn` or `PROVNUM` or `CCN` or `Provnum`; entity: `chain_id` or `affiliated_entity_id`; name: `provider_name` or `PROVNAME`; state: `state` or `STATE`; city: `CITY` or `city` | `Chain ID`, `Chain_ID`, `AFFILIATED_ENTITY_ID`; entity name: `entity_name`, `affiliated_entity`, `Entity Name`, `chain_name`, `affiliated_entity_name`, `Chain Name` |

- **CCN normalization**: All CCNs must be 6-digit zero-padded (`str(c).strip().zfill(6)`). Used in provider lookup, entity facility list, SFF match.
- **Provider page metrics**: Values come from the row for **canonical latest quarter** (see §0) when the facility has it; otherwise the facility’s most recent row. Fallback for reported HPRD/census: `provider_info` fields like `reported_total_nurse_hrs_per_resident_per_day`, `avg_residents_per_day`.
- **Rounding**: All displayed HPRD/percentages use `pbj_format.format_metric_value()` (ROUND_HALF_UP; HPRD 2 decimals, Contract % 1 decimal, census integer).

**Audit checklist — Provider**

- [ ] Facility CSV has `PROVNUM`, `CY_Qtr`, `STATE`, `Total_Nurse_HPRD` (no typos).
- [ ] Provider info CSV has at least one of the CCN column names and entity ID column; names match `_row_val` usage in `load_provider_info()`.
- [ ] No facility row uses a different state in facility_quarterly_metrics vs provider_info for same CCN (optional cross-check).
- [ ] State HPRD on provider page (e.g. "above/below state average") uses same quarter and state as facility; source is `state_quarterly_metrics.csv` with `STATE` + `CY_Qtr` match.
- [ ] Percentile phrase uses `get_facility_state_percentile()` from facility_quarterly_metrics (within-state, same state/quarter); value is 0–100, rounded with round_half_up to int; state_name full name (2-letter code is normalized to full name in phrase).
- [ ] SFF badge: `load_sff_facilities()` provider_number normalized to 6-digit and compared to page CCN; no case/space mismatch.

---

### 1.2 State page

| Source | File(s) | Required columns | Notes |
|--------|--------|-------------------|--------|
| State quarterly metrics | `state_quarterly_metrics.csv` | `STATE`, `CY_Qtr`, `Total_Nurse_HPRD` | Optional: `Nurse_Care_HPRD`, `RN_HPRD`, `RN_Care_HPRD`, `avg_daily_census` or `Avg_Daily_Census`, `Contract_Percentage` |
| Facility quarterly (fallback) | `facility_quarterly_metrics.csv` or `facility_quarterly_metrics_latest.csv` | `STATE`, `CY_Qtr`, same HPRD columns | Used when state_quarterly missing; aggregate by mean per quarter. |
| State standards | `pbj-wrapped/public/data/json/state_standards.json` (or similar) | — | For minimum HPRD reference line. |
| State agency contact | `pbj-wrapped/public/data/json/state_agency_contact.json` (or `state_contact.json`) | `state_code` | Keyed by 2-letter state code. |

- **State code**: Always 2-letter uppercase; slugs from `STATE_ALIAS_TO_SLUG` (e.g. `tn` → `tennessee`, `new-york` → `new-york`).
- **State page quarter**: Uses **canonical latest quarter** (§0). If the state has no row for that quarter, we use that state’s latest available quarter (still labeled correctly).
- **Chart data**: `get_state_historical_data()`: primary = state_quarterly rows for state; fallback = aggregate facility_quarterly by STATE and CY_Qtr. Round to 3 decimals for JSON. No synthetic data.
- **Facility count**: From `get_state_facility_count_from_facility_quarterly(state_code, raw_quarter)` for the **same** quarter; fallback to state_quarterly `facility_count` column (same quarter). Never show 0 when both sources missing.

**Audit checklist — State**

- [ ] State CSV has `STATE`, `CY_Qtr`, `Total_Nurse_HPRD`; STATE is 2-letter (no trailing space).
- [ ] If using facility fallback, aggregate uses same column names and mean; census column alias `avg_daily_census` or `Avg_Daily_Census` consistent.
- [ ] State slug resolution: every state code in STATE_CODE_TO_NAME has a canonical slug; no 404 for valid codes.
- [ ] State standards / agency contact JSON: state_code keys match STATE in CSVs (2-letter upper).

---

### 1.3 Entity (chain) page

| Source | File(s) | Required columns | Notes |
|--------|--------|-------------------|--------|
| Provider info (entity list) | Same as 1.1 | `chain_id` or `affiliated_entity_id`; entity name column; CCN column | One row per CCN; latest by processing_date or CY_Qtr. |
| Facility quarterly (metrics) | Same as 1.1 | `PROVNUM`, `CY_Qtr`, `Total_Nurse_HPRD`, `RN_HPRD`, `Contract_Percentage`, census column | Latest quarter only; joined by CCN. |
| Chain performance (CMS) | `2025-11/Chain_Performance_*.csv` or `chain_performance.csv` | **Chain ID** (entity_id); column names exact as in CSV (strip-spaced) | Used for chain-level metrics; entity_id = int(Chain ID). |

**Chain performance column names (exact)** — used by `_chain_val(chain_row, ...)`:

- `Number of facilities`, `Number of states and territories with operations`
- `Average overall 5-star rating`, `Average staffing rating`, `Average health inspection rating`, `Average quality rating`
- `Total amount of fines in dollars`, `Total number of fines`, `Total number of payment denials`
- `Number of Special Focus Facilities (SFF)`, `Number of SFF candidates`
- `Number of facilities with an abuse icon`, `Percentage of facilities with an abuse icon`
- `Percent of facilities classified as for-profit` (etc. non-profit, government-owned)
- `Average total nurse hours per resident day`, `Average total Registered Nurse hours per resident day`
- `Average total nursing staff turnover percentage`

**Audit checklist — Entity**

- [ ] Entity list: entity_id from provider_info matches integer Chain ID in Chain_Performance (when chain file present).
- [ ] Facility table: each row CCN is 6-digit; state 2-letter; Total_Nurse_HPRD, RN_HPRD, Contract_Percentage, census from facility_quarterly for **canonical latest quarter** (§0) only.
- [ ] Chain metrics: every `_chain_val` key exists in Chain CSV or is optional (display "—"); no mis-spelled column names.
- [ ] For-profit %: displayed as int(round(for_profit)); no confusion with non_profit/govt (they can sum to 100).
- [ ] High-risk count: from search_index risk flags (SFF, 1-star, abuse, etc.), not from chain CSV alone; SFF count on page can come from chain CSV.

---

### 1.4 SFF (Special Focus Facilities)

| Source | File(s) | Structure | Notes |
|--------|--------|-----------|--------|
| SFF facilities (app) | `pbj-wrapped/public/sff-facilities.json` (or dist) | `{"facilities": [{"provider_number": "...", ...}]}` | Used for SFF badge on provider page; provider_number normalized to 6-digit. |
| SFF tables (wrapped) | `sff_table_a.csv` (current SFF), `sff_table_b.csv` (graduated), `sff_table_c.csv` (no longer participating), `sff_table_d.csv` (candidates) | Table A: Provider Number, Facility Name, ... Months as an SFF. Table D: Provider Number, ... Months as an SFF Candidate | Column names must match React/dataLoader (e.g. Provider Number → provider_number). |

**Audit checklist — SFF**

- [ ] `sff-facilities.json`: every facility has `provider_number`; string normalized to 6-digit when comparing to CCN in app.py.
- [ ] Provider page SFF badge: only True when normalized CCN is in normalized SFF list; no case/whitespace bug.
- [ ] SFF table CSVs: column headers match what sff-page / dataLoader expect (e.g. "Provider Number", "Months as an SFF", "Months as an SFF Candidate").
- [ ] No facility appears in more than one SFF table with conflicting status (optional cross-check between table_a/b/c/d).

---

## 2. Rounding and display rules (single source of truth)

- **pbj_format.py**: `round_half_up()` uses `Decimal` ROUND_HALF_UP. Used by `format_metric_value()` and `fmt()`.
- **HPRD**: 2 decimal places.
- **Contract %**: 1 decimal place.
- **Census / integers**: 0 decimal places (int).
- **Percentile (state)**: 0–100 integer; `format_percentile_phrase()` uses round_half_up then int. Percentile must be within-state for the given state_name; state_name should be full state name (e.g. 'New York'); 2-letter code is normalized to full name in output.
- **Stars**: 1–5 integer; `_star_display()` uses int(round(float(val))).
- **Entity for-profit %**: int(round(for_profit)) for display.
- **State chart JSON**: HPRD rounded to 3 decimals for API; display still uses format_metric_value where applicable.

**Audit checklist — Rounding**

- [ ] No raw `round()` in app.py for user-facing metrics; use `pbj_format.round_half_up` or `format_metric_value`.
- [ ] Exception: internal calculations (e.g. residents_per_staff = 24/HPRD) can use round() for display clarity but narrative numbers should still go through formatter where defined.

---

## 3. Fallbacks (order matters)

- **load_csv_data(filename)**: Tries APP_ROOT, cwd, pbj-wrapped/public/data, pbj-wrapped/dist/data, data/. **No** automatic _latest.csv substitute; callers must request that filename explicitly.
- **State historical**: 1) state_quarterly_metrics by STATE + CY_Qtr; 2) aggregate facility_quarterly_metrics by state/quarter (mean). Do not reorder without updating docs and tests.
- **Provider info**: 1) provider_info_combined.csv; 2) pbj-wrapped/public/data/provider_info_combined.csv.
- **Entity facilities**: Same provider_info path order; then facility_quarterly for latest quarter metrics.
- **SFF**: 1) pbj-wrapped/public/sff-facilities.json; 2) pbj-wrapped/dist/sff-facilities.json; 3) sff-facilities.json.

**Audit checklist — Fallbacks**

- [ ] When primary CSV is missing, fallback does not introduce wrong state/entity (e.g. wrong file in a path).
- [ ] State chart: if state_quarterly exists but has a typo in STATE, facility fallback still filters by same state_code.
- [ ] No fallback uses a different quarter or different metric definition (e.g. Total_Nurse_HPRD vs another column).

---

## 4. Mislabeled columns

- **Provider page**: Table or narrative that says "Total Nurse HPRD" must pull from `Total_Nurse_HPRD` (or provider_info reported_total_nurse_hrs_per_resident_per_day fallback). Not RN-only, not direct care only.
- **Entity page**: "Average total nurse hours per resident day" in chain_row = chain CSV column `Average total nurse hours per resident day`; do not swap with RN-only.
- **State page**: Labels "Total Nurse HPRD" etc. must match METRIC_LABELS in pbj_format.py (or contract definitions); axis labels in charts must match data series (e.g. 'Reported' vs 'Case-Mix').
- **SFF**: "Months as an SFF" vs "Months as an SFF Candidate" — table A vs table D; column names in CSV must match what the frontend expects.

**Audit checklist — Labels**

- [ ] Every user-visible metric label (table header, axis, card title) is defined in METRIC_LABELS or contract and matches the key used to fetch the value.
- [ ] Entity chain CSV column names are spelled exactly as in _chain_val() calls (including spaces and punctuation).

---

## 5. How to run the automated audit script

From repo root:

```bash
python audit_data_accuracy.py
```

The script validates:

- **Schema**: Required columns present in facility, state, provider_info, and (if present) chain performance CSVs; SFF JSON structure.
- **IDs**: CCN 6-digit format; state 2-letter; entity_id integer; SFF provider_number normalized.
- **Rounding**: Imports pbj_format and checks format_metric_value/round_half_up behavior on sample values.
- **Column name list**: Prints expected column names for chain performance so you can diff against actual CSV headers.

It does **not** substitute for:

- Spot-checking a few provider/state/entity pages in the browser.
- Verifying that Chain_Performance CSV column headers exactly match CMS export (no extra/missing columns).
- Checking that SFF table CSV column names match the React app (e.g. dataLoader and sff-page.tsx).

---

## 6. Pre-publish manual checklist (summary)

1. Run `python audit_data_accuracy.py` and fix any reported errors.
2. Confirm DATA_SOURCES.md and this file list the same CSVs and paths.
3. Confirm pbj_format.py is the single place for rounding rules; no ad-hoc round() for displayed metrics.
4. Spot-check: one provider page (with SFF badge), one without; one state page; one entity with chain_row; one entity without chain data.
5. Confirm SFF table CSVs (a/b/c/d) have correct column names for the SFF React app.
6. Confirm state slug resolution for all 50 states + DC (or your intended set) returns correct canonical slug and code.

After the audit, keep this file and the script in the repo and re-run the script when adding new data sources or columns.

---

## 7. Other concerns (non-exhaustive)

- **search_index.json**: Home-page search and risk badges (provider/entity) use this file. Rebuild it from the same quarter and CSVs you use for provider/state/entity pages when you refresh data; otherwise autocomplete can point to facilities that 404 or show different data.
- **Cache TTL (5 min)**: CSV, provider info, chain perf, SFF, search index, canonical quarter, and state agency contact are cached 5 min. After updating CSVs on the server, wait 2 min or restart the app so pages don’t serve stale data.
- **SFF sources**: Provider SFF badge uses `sff-facilities.json`; the SFF React app may use `sff_table_*.csv`. If the JSON and tables are from different CMS posting dates, counts/lists can differ. Keep them in sync when you refresh SFF data.
- **national_quarterly_metrics.csv**: State and entity pages compare to “national” HPRD for the same quarter via `get_national_hprd_for_quarter(raw_quarter)`. Ensure this file includes the canonical quarter (e.g. 2025Q3) so the comparison is valid.
- **Zero vs missing**: We use "—" / "N/A" for missing data and avoid showing 0 when we mean “no data” (e.g. facility_count_display is "—" when both sources missing; total_residents_display is "N/A" when 0). No change needed; just be aware when adding new metrics.

---

## 8. Deep dive (recent fixes)

- **Entity page quarter filter**: `load_entity_facilities()` now filters facility_quarterly by `fq['CY_Qtr'].astype(str) == str(latest_q)` so string/int quarter values from different sources do not mismatch and drop rows.
- **State page rounding**: `generate_state_page_html()` now uses `format_metric_value()` from pbj_format for all displayed HPRD, Contract %, and census so state page uses the same ROUND_HALF_UP rules as provider and entity. The local `fmt()` was updated to use `round_half_up()` for any remaining generic decimals.
- **Region page**: `generate_region_page_html()` now imports `format_metric_value` and uses it for the states table and Region-Wide Staffing Metrics table; `fmt()` there also uses `round_half_up()` for consistency.
