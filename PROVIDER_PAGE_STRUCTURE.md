# Provider (Facility) Page Structure

This document describes the structure of the **provider (facility) page** served at `/provider/<ccn>`, as generated in `app.py` by `generate_provider_page_html()`.

---

## Route and data loading

- **URL:** `/provider/<ccn>` (CCN normalized to 6 digits via `normalize_ccn()`).
- **Handler:** `provider_page(ccn)` → loads data, then calls `generate_provider_page_html(ccn, facility_df, provider_info_row)`.
- **Data sources:**
  - **`facility_df`** — from `load_facility_quarterly_for_provider(prov)`: facility-level quarterly metrics (e.g. `facility_quarterly_metrics.csv` or equivalent). Columns include `CY_Qtr`, `Total_Nurse_HPRD`, `RN_HPRD`, `Nurse_Assistant_HPRD`, `Nurse_Care_HPRD`, `RN_Care_HPRD`, `Contract_Percentage`, `avg_daily_census` / `Avg_Daily_Census`, `COUNTY_NAME`, `STATE`, `PROVNAME`.
  - **`provider_info_row`** — from `load_provider_info()[prov]`: one row per CCN from `provider_info_combined.csv` (or fallbacks). Fields: `provider_name`, `state`, `city`, `ownership_type`, `entity_name`, `entity_id`, `avg_residents_per_day`, `reported_*`, `case_mix_*` HPRD values.
- **404:** If `facility_df` is missing or empty, the route returns 404.

---

## Page assembly (top to bottom)

The page is built as:

```text
layout['head'] + layout['nav'] + layout['content_open'] + inner + layout['content_close']
```

- **Layout** comes from `get_pbj_site_layout(page_title, seo_desc, canonical_url)` and supplies:
  - **head:** `<html>`, `<head>` (meta, title, canonical, favicon, inline CSS for `.pbj-content`, `.section-header`, charts, CTA, navbar, footer).
  - **nav:** Sticky navbar (brand link to `/`, optional nav links).
  - **content_open:** `<main class="pbj-content">` (or equivalent wrapper).
  - **content_close:** `</main>` and optional footer.
- **inner** is the facility-specific content described below.

---

## Inner content structure (order)

### 1. Page header

- **H1:** Facility name (from `provider_info_row` or `facility_df`, then `capitalize_facility_name()`; fallback `"Facility {ccn}"`).
- **Subtitle (one line):** `{city}, {state_link} • {ownership_short}` and, when present, ` • Operator: {entity_link}`.  
  - City from provider info; state is a link to `/{canonical_slug}`; ownership abbreviated to "For Profit" / "Non Profit" / "Government"; entity links to `/entity/{entity_id}`.

### 2. Section: Key metrics (quarter)

- **Section header:** `Key metrics ({quarter_display})` (e.g. "Q3 2025"; from latest `CY_Qtr` in `facility_df` via `format_quarter_display()`).

### 3. PBJ Takeaway card (`#pbj-takeaway`)

A single bordered card containing:

- **Header row:** Phoebe avatar image + title `PBJ Takeaway: {facility_name}`.
- **Badge row:** Inline pills (all optional when empty):
  - **Risk badge:** If high-risk from `get_facility_risk_from_search_index(prov)` or SFF from `load_sff_facilities()`: red pill with label (e.g. "SFF", "Abuse", "1 star", or "High risk").
  - **HPRD:** Facility total nurse HPRD (formatted).
  - **State HPRD:** `{state_code}: {state_hprd}` for same quarter (from `state_quarterly_metrics.csv` when available).
  - **Residents:** `{census_int} Residents` (or "— Residents").
  - **Contract %:** Facility contract staff percentage.
  - **Entity:** Link to `/entity/{entity_id}` when entity is present.
- **Narrative paragraph:** One or two sentences: facility name, reported HPRD, “residents per total staff” ratio, quarter, and comparison to case-mix (expected) HPRD when available; otherwise note that CMS did not report case-mix.
- **“Put another way” paragraph:** 30-bed floor equivalent staff and nurse aides; facility-wide total staff and nurse aides (FTE-style: `(census × total HPRD) / 8`), with comma-formatted thousands.
- **Footer:** Small “320 Consulting” badge (right-aligned).

Values used in the takeaway (HPRD, case-mix, census, state HPRD) are resolved from `facility_df` latest row and `provider_info_row` with fallbacks and `format_metric_value()` / `pbj_format` when available.

### 4. Section: Reported vs. Case-Mix (Expected)

- **Section header:** `Reported vs. Case-Mix (Expected)`.
- **Methodology line:** Short italic blurb: case-mix HPRD is the expected staffing for acuity; positive/negative delta meaning.

### 5. Chart section (Chart.js)

Rendered by `_provider_charts_html(chart_data)` where `chart_data = _provider_charts_chartjs_data(facility_df, state_code, reported_*, case_mix_*)`. Order:

1. **Reported vs Case-Mix** — Bar chart: Total, RN, Nurse aide (reported vs case-mix when available).
2. **Total staffing over time** — Line chart: Total HPRD, Direct care HPRD; optional state standard line when MACPAC exists for the state.
3. **RN staffing over time** — Line chart: RN HPRD, Direct care RN HPRD.
4. **Census over time** — Line chart: Average daily census by quarter.
5. **Contract staff % over time** — Line chart: Facility contract % (state median series is no longer shown on the facility page).

Charts use a dark theme (e.g. `textColor`, `gridColor`), dynamic y-axis where appropriate (`beginAtZero: false` for line charts), and x-axis labels that show year on Q1 to reduce clutter.

### 6. Custom Report CTA

- **HTML:** From `render_custom_report_cta('facility', facility_page_url, facility_name=..., ccn=..., state_name=..., entity_name=...)`.
- **Content:** “Need deeper staffing context?”; one line on independent analysis from CMS PBJ data for legal, media, and policy use; links Request – Attorney · Request – Media · Request – Advocate; Email · Text (929) 804-4996 (with mailto and SMS when facility context).
- **Styling:** Dark, compact box (`.custom-report-cta`), single placement per page.

### 7. Footer links and attribution

- **Nav line:** `Home` · `{state_name} staffing` (link to `/{canonical_slug}`) · optional `{entity_name}` (link to `/entity/{entity_id}`).
- **Attribution line:** “Staffing from CMS payroll-based journal (PBJ) data.” Optional link: “View on Medicare Care Compare” → `https://www.medicare.gov/care-compare/details/nursing-home/{ccn}/view-all/?state={state_code}` when `state_code` is present.

---

## Key functions and helpers

| Function / data | Purpose |
|----------------|--------|
| `generate_provider_page_html(ccn, facility_df, provider_info_row)` | Builds full facility page HTML (layout + inner). |
| `get_pbj_site_layout(page_title, meta_description, canonical_url)` | Returns head, nav, content_open, content_close and shared CSS. |
| `_provider_charts_chartjs_data(...)` | Builds JSON-serializable chart data (reportedCaseMix, totalHprd, rnHprd, census, contract) and optional state/MACPAC series. |
| `_provider_charts_html(chart_data)` | Renders Chart.js script + canvas elements and inline script that draws the five charts. |
| `get_facility_risk_from_search_index(ccn)` | Reads `search_index.json`, returns `(risk_flag, reason_str)` for facility CCN (high-risk badge). |
| `load_sff_facilities()` | Loads SFF list; used as fallback for “SFF” badge when facility not in search index. |
| `load_provider_info()` | Returns dict CCN → provider info row (name, state, city, entity, ownership, HPRD/census/case-mix fields). |
| `load_facility_quarterly_for_provider(ccn)` | Returns DataFrame of quarterly metrics for the facility. |
| `get_macpac_hprd_for_state(state_code)` | State standard HPRD for “Total staffing over time” state line. |

---

## Data flow summary

1. Route normalizes CCN and loads `facility_df` and `provider_info_row`.
2. Latest quarter and all displayed metrics (HPRD, census, case-mix, state HPRD) are derived from `facility_df` and `provider_info_row`.
3. Risk badge comes from `search_index.json` (and SFF list as fallback).
4. Chart data is built from `facility_df` plus state/MACPAC data where applicable.
5. Layout wraps the inner content with site-wide head, nav, and main container; inner is a linear sequence of header, Key metrics, takeaway card, Reported vs. Case-Mix section, charts, CTA, and footer/attribution.

---

## Styling and UX notes

- **Theme:** Dark (e.g. `#0f172a` background, `#e2e8f0` text, blue accents).
- **Sections:** `.section-header` for section titles; `.pbj-subtitle` for short supporting text.
- **Takeaway:** Single content box with badges, narrative, and “Put another way” with comma-formatted numbers.
- **Charts:** Contained in `.pbj-chart-container`; Chart.js loaded from CDN; responsive and accessible labels/colors.
- **Care Compare:** Link only when state is known; subtle, small font in footer.

This structure aligns with the intended “header block, key metrics, longitudinal chart, basic info” flow referenced in the docstring and pbj-page-guide.
