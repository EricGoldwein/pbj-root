# PBJ Staffing App: Streamlit-to-Flask Migration Audit

**Purpose:** Extract ALL institutional, metric, policy, formatting, and visualization logic in a framework-agnostic way for rebuilding in Flask without losing nuance or institutional definitions.

---

## 1. FILE + ARCHITECTURE INVENTORY

### 1.1 Core Python Files (Streamlit / PBJ Staffing App)

| File | Purpose |
|------|--------|
| **prov_info.py** | Main Streamlit Provider Info Dashboard: facility search, quarter mapping, charts (Reported vs Case-Mix vs Adjusted, Total/RN/CNA longitudinal, Delta, Census, Ratings, Ownership), comprehensive data table, ratings methodology. |
| **facility_report_lib.py** | Framework-agnostic facility report library: rounding (ROUND_HALF_UP), quarter parsing/formatting, facility/city name formatting, load_facility_data, get_facility_info, get_daily_staffing, calculate_quarterly_metrics, calculate_days_under_state_minimum, get_macpac_state_standards, load_provider_info_data, extract_red_flags_history, extract_case_mix_data, Harrington-adjusted HPRD, generate_case_mix_section, generate_red_flags_section, generate_attorney_report (HTML). |
| **internal_report_generator.py** | Internal report orchestration: load_state_metrics (state_lite_metrics.csv), get_state_data_for_quarters, load_provider_info_data (provider_info_normalized/), get_provider_info_for_quarters, generate_report_for_facility; calls dynamic_facility_dashboard and generate_pbj_report. |
| **generate_report.py** | PBJ Brief (Phoebe-style) HTML report generator: generate_pbj_report(facility_name, location, ccn, affiliate_entity, review_period, dates_of_interest, metrics, quarterly_data, state_comparison_data, key_dates_data); MSO-style HTML template, quarterly table, state comparison table, key dates section. |
| **generate_metrics.py** | DuckDB-based metrics pipeline: reads standardized_PBJ/*.csv, outputs facility_quarterly_metrics.csv, state_quarterly_metrics.csv, national_quarterly_metrics.csv; defines Total_Nurse_Hours, RN_Hours, Nurse_Care_Hours, RN_Care_Hours, Nurse_Assistant_Hours, Contract_Hours, HPRD formulas. |
| **lite_report.py** | Lite metrics from quarterly metrics: reads facility/state/national_quarterly_metrics.csv, produces facility_lite_metrics.csv, state_lite_metrics.csv, national_lite_metrics.csv; weighted HPRD by resident_days; Total_RN_HPRD = RN_HPRD, Direct_Care_RN_HPRD = RN_Care_HPRD. |
| **create_facility_csv.py** | Simple facility CSV builder: reads standardized_PBJ/PBJ_dailynursestaffing_*.csv, filters by PROVNUM, writes facility_{provnum}_complete_data.csv and facility_pbj/ copy. |
| **dynamic_facility_dashboard.py** | Flask-oriented dashboard + data prep: create_facility_complete_csv (incremental by quarter), create_facility_provider_info_csv, load_facility_data, load_macpac_standards, generate_pbj_source_link, format_pbj_source_link; uses file_path_utils for deployments/. |
| **file_path_utils.py** | Path resolution: find_facility_file, find_facility_complete_data, find_facility_provider_info, find_facility_flask_app, get_facility_folder, find_donor_file, get_all_facility_folders; checks deployments/pbj320-{provnum}/ then pbj320-{provnum}/ then root. |
| **standardize_pbj_files.py** | PBJ column name normalization: maps lowercase/variant names to canonical (e.g. hrs_rn → Hrs_RN, mdscensus → MDScensus, cy_qtr → CY_Qtr, workdate → WorkDate); outputs to standardized_PBJ/. |
| **standardize_nonnursepbj_files.py** | Non-nurse PBJ standardization (separate pipeline). |
| **normalize_provider_info.py** | Provider Info normalization; outputs to provider_info_normalized/. |
| **fix_provider_info_quarters.py** | Quarter alignment for provider info. |
| **dashboard_generator_app.py** | Alternate dashboard/report UI (Streamlit). |
| **PBJ_Dashboard.py** | Legacy/alternate PBJ dashboard (Streamlit). |
| **Internal_PBJ_Dashboard.py** | Internal PBJ dashboard (Streamlit). |
| **facility_red_flag_report/generate_facility_report.py** | Red-flag facility report generation (Markdown/HTML/PDF). |
| **facility_red_flag_report/detect_red_flags.py** | Red flag detection: structural (40 pts), major operational (20 pts), warnings (8 pts), citation severity (0–40), data quality (0–10); risk score 0–100; High ≥70, Medium 40–69, Elevated 20–39, Low <20. |
| **facility_red_flag_report/collect_facility_data.py** | Collects facility data for red-flag pipeline. |
| **facility_red_flag_report/export_data_for_dashboard.py** | Exports data for red-flag dashboard. |
| **generate_facility_attorney_report.py** | Attorney report entry point (uses facility_report_lib). |
| **generate_facility_attorney_report_enhanced.py** | Enhanced attorney report. |
| **generate_facility_report_attorney.py** | Attorney report generator (uses facility_report_lib). |
| **regenerate_report_from_folder.py** | Regenerate report from existing report folder. |

### 1.2 Data Sources (Exact Paths and Types)

| Source | Path(s) | Type | Notes |
|--------|---------|------|--------|
| Provider Info (combined) | `provider_info_combined.csv` | CSV | Preferred for prov_info + facility_report_lib; ccn, processing_date, quarter, case_mix_*, reported_*, adjusted_*, ratings. |
| Quarter mapping | `quarter_to_provider_mapping_examples.csv` | CSV | processing_date, quarter, lite_total_nurse_hprd; used to map processing_date → quarter in prov_info. |
| PBJ daily staffing | `standardized_PBJ/PBJ_dailynursestaffing_*.csv` | CSV | WorkDate, CY_Qtr, PROVNUM, MDScensus, Hrs_RN, Hrs_RNadmin, Hrs_RNDON, Hrs_LPN, Hrs_LPNadmin, Hrs_CNA, Hrs_NAtrn, Hrs_MedAide, *_ctr (contract). |
| Provider Info (normalized) | `provider_info_normalized/ProviderInfoNorm_*.csv` | CSV | Fallback when provider_info_combined.csv not used; same schema intent. |
| Facility complete data | `deployments/pbj320-{provnum}/facility_{provnum}_complete_data.csv`, `facility_{provnum}_complete_data.csv`, `pbj320-{provnum}/facility_{provnum}_complete_data.csv` | CSV | Per-facility PBJ daily data; WorkDate, CY_Qtr, MDScensus, Hrs_*. |
| Facility provider info | `deployments/pbj320-{provnum}/facility_{provnum}_provider_info_data.csv`, etc. | CSV | Per-facility provider info subset. |
| MACPAC state standards | `macpac_state_standards_clean.csv`, `pbj_lite/macpac_state_standards_clean.csv`, `macpac/macpac_state_standards.csv` | CSV | State, Min_Staffing, Max_Staffing, Value_Type, Is_Federal_Minimum, Display_Text. |
| State lite metrics | `state_lite_metrics.csv` | CSV | STATE, CY_Qtr, Total_Nurse_HPRD, Direct_Care_RN_HPRD (and related); used by internal_report_generator. |
| Facility quarterly metrics | `facility_quarterly_metrics.csv` | CSV | PROVNUM, CY_Qtr, Total_Nurse_HPRD, RN_HPRD, Nurse_Care_HPRD, RN_Care_HPRD, etc. |
| State quarterly metrics | `state_quarterly_metrics.csv` | CSV | STATE, CY_Qtr, facility_count, Total_Nurse_HPRD, etc. |
| National quarterly metrics | `national_quarterly_metrics.csv` | CSV | STATE='NATIONAL', CY_Qtr, etc. |
| Facility lite metrics | `facility_lite_metrics.csv` | CSV | Subset of facility quarterly for “lite” views. |
| National lite metrics | `national_lite_metrics.csv` | CSV | National lite. |
| Red-flag / citations | Facility red flag report pipeline uses Citations/ and facility-specific data. | CSV/varies | Citations: Survey Date, Scope Severity Code, Deficiency Tag Number, Deficiency Category. |

**PBJ canonical column names (after standardize_pbj_files):** `CY_Qtr`, `WorkDate`, `MDScensus`, `PROVNUM`, `Hrs_RNDON`, `Hrs_RNadmin`, `Hrs_RN`, `Hrs_LPNadmin`, `Hrs_LPN`, `Hrs_CNA`, `Hrs_NAtrn`, `Hrs_MedAide`, and `Hrs_*_ctr` for contract; variant names (e.g. hrs_rn, mdscensus) are normalized to these.

### 1.3 Dependencies (requirements.txt)

```
streamlit==1.50.0
pandas==2.2.3
plotly==6.3.0
duckdb==1.3.0
numpy==1.26.4
python-dateutil==2.9.0
pytz==2023.3
reportlab>=4.0
markdown>=3.4
python-docx>=1.1.0
beautifulsoup4>=4.12.0
playwright>=1.40.0
flask>=2.3.0
flask-cors>=4.0.0
requests>=2.31.0
```

### 1.4 Implicit Assumptions About File Structure

- **Quarter format:** Internal canonical is `YYYYQn` (e.g. `2023Q1`). Display format is `Qn YYYY` (e.g. `Q1 2023`). Parsing must accept both and variants with spaces.
- **Processing date vs quarter:** Quarter is NOT derived from processing_date by a fixed offset; it is resolved from `quarter_to_provider_mapping_examples.csv` (processing_date + optional HPRD key). Filtering is `quarter >= "2017Q4"`.
- **CCN/PROVNUM:** Always 6-digit string (zfill(6)); comparison as string.
- **Facility file lookup order:** `deployments/pbj320-{provnum}/` → `pbj320-{provnum}/` → project root.
- **Provider info lookup:** Prefer `provider_info_combined.csv` filtered by ccn; else per-facility CSVs in deployments or root.
- **MACPAC lookup:** State matched by full name (e.g. "New Jersey"); abbreviation mapped via state_names dict to full name; CSV columns State, Min_Staffing, Max_Staffing, Display_Text, Value_Type, Is_Federal_Minimum.

---

## 2. DATA TRANSFORMATION LAYER

### 2.1 Metrics and Required Datasets/Columns

| Metric | Required dataset | Required columns | Transformations | Time level | Precision (calc / display) |
|--------|------------------|------------------|-----------------|------------|----------------------------|
| Total Nurse HPRD | PBJ daily (standardized) | MDScensus, Hrs_RNDON, Hrs_RNadmin, Hrs_RN, Hrs_LPNadmin, Hrs_LPN, Hrs_CNA, Hrs_NAtrn, Hrs_MedAide | Sum hours per quarter, sum resident_days; HPRD = total_hours / total_resident_days | Quarterly | Calc: full float; Display: 2 decimals (report), 3 in tables (prov_info) |
| RN HPRD (Total RN) | Same | Hrs_RNDON, Hrs_RNadmin, Hrs_RN | Same | Quarterly | 2 / 2 or 3 |
| Direct Care RN HPRD | Same | Hrs_RN, MDScensus | direct_care_rn_hours = Hrs_RN; / resident_days | Quarterly | 2 / 2 |
| Nurse Care HPRD (Direct care total) | Same | Hrs_RN, Hrs_LPN, Hrs_CNA, Hrs_NAtrn, Hrs_MedAide | Sum, divide by resident_days | Quarterly | 2 / 2 |
| RN Care HPRD | Same | Hrs_RN | Sum Hrs_RN / resident_days | Quarterly | 2 / 2 |
| Nurse Assistant HPRD | Same | Hrs_CNA, Hrs_NAtrn, Hrs_MedAide | Sum / resident_days | Quarterly | 2 / 2 |
| Contract % | Same | Hrs_*_ctr, Hrs_* (same roles) | contract_hours / total_nurse_hours * 100 | Quarterly | 1 / 1 |
| Case-mix expected HPRD | Provider Info | case_mix_total_nurse_hrs_per_resident_per_day, case_mix_rn_hrs_per_resident_per_day, case_mix_na_hrs_per_resident_per_day, case_mix_lpn_hrs_per_resident_per_day | None (use as-is per quarter) | Quarterly | 2 / 2 |
| Reported HPRD (Provider Info) | Provider Info | reported_*_hrs_per_resident_per_day | None | Quarterly (by processing_date→quarter) | 3 / 3 |
| Adjusted HPRD | Provider Info | adjusted_*_hrs_per_resident_per_day | None | Quarterly | 3 / 3 |
| Delta (Reported − Case-mix) | Both | reported_total_nurse_*, case_mix_total_nurse_* | reported − case_mix | Quarterly | 3 / 3 |
| Percent delta | Same | Same | (reported / case_mix − 1) * 100 | Quarterly | 1 / 1 |
| Days under state minimum | PBJ daily + state min | WorkDate, MDScensus, all hour columns, state_minimum | Daily Total_HPRD and Direct_Care_HPRD; count days < state_minimum | Daily → period | Integer days, 1 decimal % |
| Avg census | PBJ daily | MDScensus | mean per quarter or period | Quarterly | 1 / 1 |

### 2.2 Conceptual Pure-Python Functions (No Streamlit)

```python
# ----- Quarter mapping (conceptual) -----
def get_quarter_from_processing_month(proc_month: str, date_to_quarter: dict) -> str | None:
    """Resolve quarter from processing month using mapping table (date, rounded_hprd) -> quarter."""
    # In prov_info, date_to_quarter is built from quarter_to_provider_mapping_examples.csv.
    # Key is (processing_date, round(hprd, 3)); conflict 2023Q2 vs 2023Q3 for 2024-01..06 -> prefer 2023Q3.
    ...

def get_processing_months_for_quarter(quarter: str) -> list[str]:
    """Return list of YYYY-MM for a given quarter (e.g. 2021Q1 -> ['2021-04','2021-05','2021-06'])."""
    # Logic in prov_info: parse "Q1 2018" or "2018Q1", then return 3 months per q_num.
    ...

# ----- HPRD from daily PBJ (conceptual) -----
def total_nurse_hours_row(row: pd.Series) -> float:
    return (
        row.get("Hrs_RNDON", 0) or 0 + row.get("Hrs_RNadmin", 0) or 0 + row.get("Hrs_RN", 0) or 0
        + row.get("Hrs_LPNadmin", 0) or 0 + row.get("Hrs_LPN", 0) or 0
        + row.get("Hrs_CNA", 0) or 0 + row.get("Hrs_NAtrn", 0) or 0 + row.get("Hrs_MedAide", 0) or 0
    )

def direct_care_hours_row(row: pd.Series) -> float:
    return (
        row.get("Hrs_RN", 0) or 0 + row.get("Hrs_LPN", 0) or 0 + row.get("Hrs_CNA", 0) or 0
        + row.get("Hrs_NAtrn", 0) or 0 + row.get("Hrs_MedAide", 0) or 0
    )

def total_rn_hours_row(row: pd.Series) -> float:
    return (row.get("Hrs_RNDON", 0) or 0) + (row.get("Hrs_RNadmin", 0) or 0) + (row.get("Hrs_RN", 0) or 0)

def quarterly_hprd(df: pd.DataFrame, quarter: str, hours_fn) -> float:
    q = df[df["CY_Qtr"] == quarter]
    resident_days = q["MDScensus"].sum()
    if resident_days == 0:
        return 0.0
    total_hours = q.apply(hours_fn, axis=1).sum()
    return total_hours / resident_days
```

---

## 3. STAFFING DEFINITIONS (CRITICAL)

### 3.1 Total Nurse Staff

- **Definition:** All nursing staff hours (RN + LPN + Nurse Aide) including administrative and DON.
- **PBJ columns included:**  
  `Hrs_RNDON` + `Hrs_RNadmin` + `Hrs_RN` + `Hrs_LPNadmin` + `Hrs_LPN` + `Hrs_CNA` + `Hrs_NAtrn` + `Hrs_MedAide`
- **Inclusion:** Employee + contract (same role columns; contract in `*_ctr`).
- **Rationale:** CMS PBJ “total nurse” concept; used in generate_metrics (DuckDB), facility_report_lib (quarterly/daily), and prov_info via Provider Info reported_total_nurse_hrs_per_resident_per_day.

### 3.2 Total Nurse Care Staff (Direct Care)

- **Definition:** Direct care only; excludes DON and admin.
- **PBJ columns:**  
  `Hrs_RN` + `Hrs_LPN` + `Hrs_CNA` + `Hrs_NAtrn` + `Hrs_MedAide`
- **Rationale:** “Nurse care hours” / “direct care” in generate_metrics (Nurse_Care_Hours), facility_report_lib (direct_care_hours, direct_care_hprd), state/national lite metrics.

### 3.3 Total RN

- **Definition:** All RN hours including admin and DON.
- **PBJ columns:**  
  `Hrs_RNDON` + `Hrs_RNadmin` + `Hrs_RN`
- **Rationale:** CMS total RN; used for RN_HPRD in generate_metrics, facility_report_lib (rn_hprd, total_rn_hours), and Provider Info reported_rn_hrs_per_resident_per_day.

### 3.4 RN Care (Direct Care RN Only)

- **Definition:** Direct care RN only; excludes RN admin and DON.
- **PBJ columns:**  
  `Hrs_RN` only.
- **Rationale:** “RN Care” / “Direct Care RN” in generate_metrics (RN_Care_Hours, RN_Care_HPRD), facility_report_lib (direct_care_rn_hprd, direct_care_rn_hours), state Direct_Care_RN_HPRD.

### 3.5 Administrative RN (If Separated)

- **Definition:** DON + RN Admin.
- **PBJ columns:**  
  `Hrs_RNDON` + `Hrs_RNadmin`
- **Inclusion:** Included in “Total RN” but excluded from “RN Care” / “Direct Care RN.” Not shown as its own metric in prov_info; used implicitly in Total RN and in report narrative (e.g. “includes administrative and DON hours”).

### 3.6 Total Nurse Aide

- **Definition:** CNA + NA in training + Med Aide.
- **PBJ columns:**  
  `Hrs_CNA` + `Hrs_NAtrn` + `Hrs_MedAide`
- **Rationale:** Nurse_Assistant_Hours in generate_metrics; “total nurse aide hours” / “CNA” HPRD in facility_report_lib and reports; prov_info uses reported_na_hrs_per_resident_per_day (Provider Info NA = nurse aide).

### 3.7 Contract vs Employee

- **Contract hours:** Columns `Hrs_RNDON_ctr`, `Hrs_RNadmin_ctr`, `Hrs_RN_ctr`, `Hrs_LPNadmin_ctr`, `Hrs_LPN_ctr`, `Hrs_CNA_ctr`, `Hrs_NAtrn_ctr`, `Hrs_MedAide_ctr` (and _emp for employee where present).
- **Total contract:** Sum of all _ctr for the same roles as total nurse.
- **Contract %:** (Total_contract_hours / Total_nurse_hours) * 100. Display: 1 decimal.

### 3.8 Composite Categories Summary

| Label in app/reports | PBJ columns | Notes |
|----------------------|------------|--------|
| Total Nurse / Total HPRD | RNDON+RNadmin+RN+LPNadmin+LPN+CNA+NAtrn+MedAide | Includes admin/DON |
| Direct Care / Nurse Care HPRD | RN+LPN+CNA+NAtrn+MedAide | Excludes admin/DON |
| Total RN / RN HPRD | RNDON+RNadmin+RN | Includes admin/DON |
| Direct Care RN / RN Care HPRD | RN only | Excludes admin/DON |
| Nurse Aide / CNA HPRD | CNA+NAtrn+MedAide | |
| LPN (displayed “direct”) | LPN only (excl. LPNadmin) | facility_report_lib uses direct_lpn_hours for display; total_lpn includes admin for internal HPRD. |

---

## 4. MACPAC + FEDERAL / STATE THRESHOLD LOGIC

### 4.1 MACPAC RN Threshold

- **Harrington RN Expected (formula):** Used in case-mix section and risk context; see Section 5. The **federal minimum RN** referenced in narrative is **0.55 HPRD** (Harrington base). MACPAC state standards file does not define a separate “RN-only” minimum; state Min_Staffing is total nursing HPRD.

### 4.2 MACPAC Total Nurse Threshold

- **Source:** `macpac_state_standards_clean.csv` columns `Min_Staffing`, `Max_Staffing`, `Display_Text`, `Value_Type`, `Is_Federal_Minimum`.
- **Lookup:** By state full name (e.g. "New Jersey"); state abbreviation mapped to full name in code.
- **Federal minimum:** Where `Is_Federal_Minimum` is True or Min_Staffing == 0.3 → **0.30 HPRD** (total).
- **State-specific:** Per-row Min_Staffing (and Max_Staffing for range states). Examples: NJ 2.5 (estimated/display text), NY 3.56–4.16 (range), CA 3.56.

### 4.3 Federal Minimum Logic

- **0.30 HPRD:** Used as fallback in internal_report_generator when state_comparison_data has no state data for a quarter (`state_direct_care_hppd` / `state_direct_rn_hppd` set to `'0.300'`).
- **0.55 HPRD:** Base for Harrington RN Expected formula (not a compliance threshold in code; formula constant).

### 4.4 State Minimum Standards

- **Usage:** facility_report_lib `get_macpac_state_standards(state)` returns `min_staffing`, `max_staffing`, `display_text`, `value_type`, `is_federal_minimum`.
- **Days under minimum:** `calculate_days_under_state_minimum(df, start_date, end_date, state_minimum)` counts days where Total_HPRD < state_minimum and Direct_Care_HPRD < state_minimum (separate counts). State minimum is **raw HPRD** (not case-mix adjusted).
- **Compliance:** Binary per day (above/below min). No graded compliance in this function; report narrative and “below state average” styling are separate.

### 4.5 Raw vs Case-Mix Adjusted

- **MACPAC state thresholds:** Applied to **raw** (reported) HPRD in “days under state minimum” and in narrative.
- **Case-mix expected:** Used for comparison (reported vs expected) and proportion (reported/case_mix * 100); not used as legal minimum in code.

### 4.6 Where Constants Are Defined

- **prov_info.py:** No MACPAC constants; uses Provider Info columns only.
- **facility_report_lib.py:** `get_macpac_state_standards()` reads CSV; no hardcoded numeric thresholds. Harrington constants in `calculate_harrington_adjusted_hprd`: base_cmi=0.62, max_cmi=3.84, and formula coefficients (0.55, 2.39, 3.48, 7.68, 2.45, 3.6; exponents 0.715…, 0.974…, 0.236…).
- **internal_report_generator.py:** Federal fallback `'0.300'` for state HPRD when quarter has no state data.
- **facility_red_flag_report/detect_red_flags.py:** 0.70 (severe RN/total ratio), 0.90/3.2 (low total), 0.60–0.80 RN ratio, 0.40–0.60 RN HPRD, 2.0 CNA, 35% contract, 0.85 state ratio, etc. (see Section 6).

### 4.7 Explicit Threshold Constants List

| Constant | Value | Use |
|----------|--------|-----|
| Federal minimum (total) | 0.30 HPRD | Fallback state comparison; MACPAC Is_Federal_Minimum |
| Harrington RN base | 0.55 HPRD | Harrington formula |
| Harrington total base | 3.48 HPRD | Harrington formula |
| Harrington CNA base | 2.45 HPRD | Harrington formula |
| Severe RN ratio | 0.70 | Structural red flag (RN_ratio or RN HPRD) |
| Severe total ratio | 0.70 | Structural red flag (Total_ratio) |
| Low total ratio | 0.90 | Major operational |
| Low total HPRD | 3.2 | Major operational |
| Low CNA HPRD | 2.0 | Major operational |
| Moderate RN ratio | 0.60–0.80 | Major operational |
| Moderate RN HPRD | 0.40–0.60 | Major operational |
| Below state ratio | 0.85 | Major operational |
| High contract % | 35% | Major operational |
| Borderline total ratio | 0.90–1.0 | Warning |
| Borderline total HPRD | 3.2–3.5 | Warning |
| Borderline RN ratio | 0.80–0.95 | Warning |
| Borderline RN HPRD | 0.60–0.75 | Warning |
| Borderline CNA HPRD | 2.0–2.5 | Warning |
| Moderate contract % | 25–35% | Warning |
| Case-mix ratio below 80% | 0.80 | Red-flag narrative (facility_red_flag_report) |

---

## 5. CASE-MIX INDEX (CMI) HANDLING

### 5.1 Source of CMI

- **Provider Info:** Columns sought: `nursing_case_mix_index`, `nursing_case_mix_index_ratio`, `case_mix_index`, `CMI`, `Case Mix Index`, `case_mix`, `Case-Mix Index`, `Case Mix Index (CMI)` (facility_report_lib).
- **Level:** Per record (processing_date/quarter); facility-level, quarterly in practice.

### 5.2 Formula for Expected Staffing (Harrington)

- **Total Expected HPRD:**  
  `3.48 + ((CMI - 0.62) / (3.84 - 0.62))^0.715361977219995 * (7.68 - 3.48)`
- **RN Expected HPRD:**  
  `0.55 + ((CMI - 0.62) / (3.84 - 0.62))^0.973947642000645 * (2.39 - 0.55)`
- **CNA Expected HPRD:**  
  `2.45 + ((CMI - 0.62) / (3.84 - 0.62))^0.236050267902121 * (3.6 - 2.45)`
- **Constants:** base_cmi=0.62, max_cmi=3.84; ratio clamped by denominator (3.84−0.62). If CMI ≤ 0 or None, returns None.

### 5.3 Normalization / Ratio Logic

- **Proportion (reported vs expected):** (reported / case_mix_or_harrington) * 100. Displayed as “X%” (e.g. “95.2% of case-mix expected”).
- **Case-mix direct:** case_mix_direct = case_mix_rn + case_mix_lpn + case_mix_na when all three present (facility_report_lib).

### 5.4 Use in Risk Scoring

- **total_ratio:** Total_HPRD / Expected_Total_HPRD (case-mix); < 0.70 → structural red flag; < 0.90 → major operational; 0.90–1.0 → warning.
- **rn_ratio:** RN_HPRD / Expected_RN_HPRD (when available); < 0.70 → structural; 0.60–0.80 → major; 0.80–0.95 → warning.
- Harrington-adjusted expected is used in case-mix section and narrative, not as separate risk input in detect_red_flags (risk uses provider_info case_mix when available).

### 5.5 Display vs Internal

- CMI and case-mix expected HPRD are shown in attorney report case-mix section and in narrative (e.g. “X% of case-mix expected”). Harrington formula is documented in report HTML and used for Harrington Expected column/summary.

---

## 6. HIGH-RISK FACILITY CLASSIFICATION

### 6.1 Risk Score (0–100)

- **Structural red flags:** 40 points each (SFF, SFF Candidate, Abuse icon, 1-Star Overall, Severe RN failure RN_ratio < 0.70 or RN HPRD < 0.70, Severe total ratio < 0.70, Collapsed staffing volatility).
- **Major operational failures:** 20 points each (Low total ratio/HPRD, Low CNA < 2.0, Moderate RN weakness, Below state ratio < 0.85, Contract > 35%, Sustained 2-quarter decline ≥10%).
- **Warning indicators:** 8 points each (Borderline total/RN/CNA, contract 25–35%, single-quarter drop ≥12%).
- **Citation severity:** 0–40 (high-severity G+ in 24 months, F600 series, pattern-and-practice).
- **Data quality modifiers:** 0–10 (missing quarters, census < 10, missing fields). Total capped at 100.

### 6.2 Overrides

- **≥3 structural red flags → score = 100.**
- **SFF + Abuse icon → minimum 80 before data modifiers.**
- **Census < 20 → cap score at 85.**

### 6.3 Risk Levels (Tiers)

- **High Risk:** score ≥ 70  
- **Medium Risk:** 40 ≤ score < 70  
- **Elevated:** 20 ≤ score < 40  
- **Low Risk:** score < 20  

### 6.4 Rule Expressions (Precise)

- **Structural – Severe RN:** `(rn_ratio is not None and rn_ratio < 0.70) or (rn_hprd is not None and rn_hprd < 0.70)`  
- **Structural – Severe total:** `total_ratio is not None and total_ratio < 0.70`  
- **Structural – Collapsed:** `volatility_category == 'Collapsed'`  
- **Major – Low total:** `(total_ratio is not None and total_ratio < 0.90) or (total_hprd is not None and total_hprd < 3.2)`  
- **Major – Low CNA:** `cna_hprd is not None and cna_hprd < 2.0`  
- **Major – Moderate RN:** `(0.60 <= rn_ratio < 0.80) or (0.40 <= rn_hprd < 0.60)`  
- **Major – Below state:** `state_ratio is not None and state_ratio < 0.85`  
- **Major – Contract:** `contract_pct is not None and contract_pct > 35`  
- **Major – Sustained decline:** Last 2 consecutive quarters, (latest_hprd - two_q_ago_hprd) / two_q_ago_hprd * 100 <= -10  
- **Warning – Borderline total:** `(0.90 <= total_ratio < 1.0) or (3.2 <= total_hprd < 3.5)`  
- **Warning – Borderline RN:** `(0.80 <= rn_ratio < 0.95) or (0.60 <= rn_hprd < 0.75)`  
- **Warning – Single-quarter drop:** `hprd_change_pct is not None and hprd_change_pct <= -12`  

---

## 7. PHOEBE BRIEF REPORT PIPELINE

### 7.1 Inputs

- Facility ID (CCN), resident stay start/end dates, key dates (list of dates).
- Data: facility complete CSV (PBJ daily), state_lite_metrics.csv, provider_info (normalized or combined) filtered by facility and quarter.

### 7.2 Calculations

- **Quarterly aggregation:** By (Year, Quarter) from WorkDate; mean census, mean Total_Nurse_HPRD, Total_Staff_HPRD, RN_HPRD, Total_RN_HPRD (column names from dynamic_facility_dashboard / internal_report_generator).
- **State comparison:** get_state_data_for_quarters(state_data, quarters) → total_nurse_hprd, direct_care_rn_hprd per quarter; **exact quarter match only**, no fallback except federal 0.300 when state has no data for that quarter.
- **Provider Info per quarter:** get_provider_info_for_quarters(provider_df, quarters) → case_mix_total_hprd, case_mix_rn_hprd, staffing_rating, overall_rating, health_inspection_rating, turnover; **exact quarter match**; missing quarter → '-'.

### 7.3 Comparisons

- Facility direct care HPRD vs state direct care HPRD; facility direct RN HPRD vs state direct RN HPRD (state_comparison_data).
- Key dates: daily census, direct_care_hppd, total_hppd, rn_hppd, total_rn_hppd from facility daily data.

### 7.4 Percentile Logic

- Phoebe brief (generate_report.py) does not compute percentiles; it shows facility vs state and key dates. Percentiles appear in red-flag / lite ranking contexts elsewhere, not in this pipeline.

### 7.5 Rounding Logic

- **generate_report.py:** Uses values from quarterly_data/state_comparison_data/key_dates_data as preformatted strings (e.g. ".3f", ".1f").
- **facility_report_lib:** round_half_up(value, decimals) (Decimal ROUND_HALF_UP); 2 decimals for HPRD/hours, 1 for contract % and percentages.

### 7.6 Risk Flags in Phoebe Brief

- The simple PBJ Brief (generate_report.py) does not include red-flag or risk score; it includes staffing metrics, state comparison, ratings, turnover. Attorney report (facility_report_lib generate_attorney_report) includes red_flags_history and case-mix/Harrington.

### 7.7 Export Format and Templating

- **Format:** HTML (MSO/Word-style markup in generate_report.py; attorney styling in facility_report_lib).
- **Templating:** String formatting and f-strings; no Jinja in generate_report.py. facility_report_lib uses f-strings and conditional HTML sections (e.g. state-specific MACPAC text for NJ/NY).

### 7.8 Narrative Text Injection

- generate_report.py: Fixed structure with facility_name, location, ccn, review_period, dates of interest, quarterly rows, state comparison rows, key dates bullets.
- facility_report_lib: MACPAC display_text, “Estimated New Jersey Staffing Requirements”, “New York State Staffing Requirements”, Harrington formula text, case-mix proportion narrative, “below state average” CSS class, days under minimum paragraph.

### 7.9 Framework-Independent Report Module (Conceptual)

- **Inputs:** facility_id, start_date, end_date, key_dates, options (include_total_staffing, watermark).
- **Steps:** (1) Load facility PBJ (via load_facility_data), (2) Load state metrics and provider info, (3) Compute quarterly_data and state_comparison_data with exact quarter match, (4) get_macpac_state_standards(state), (5) calculate_quarterly_metrics / calculate_period_metrics / calculate_days_under_state_minimum, (6) extract_red_flags_history, extract_case_mix_data, (7) round_half_up and format_quarter_display, (8) generate_attorney_report(...) or generate_pbj_report(...) to HTML string, (9) return string or write to file. No st.* or Flask in this pipeline.
- **Phoebe Brief entry point:** `generate_report.generate_pbj_report(...)` produces the simpler HTML brief; `facility_report_lib.generate_attorney_report(...)` produces the full attorney report with MACPAC, case-mix, Harrington, and red flags. Both can be called from a single framework-agnostic report module.

---

## 8. DIRECT RN VS TOTAL RN LOGIC

### 8.1 Column Composition

- **Total RN:** Hrs_RNDON + Hrs_RNadmin + Hrs_RN.  
- **Direct RN (RN Care):** Hrs_RN only.

### 8.2 Where Each Is Used

- **Dashboard (prov_info):** Uses Provider Info columns: reported_rn_hrs_per_resident_per_day, case_mix_rn_hrs_per_resident_per_day, adjusted_rn_hrs_per_resident_per_day. Provider Info “reported_rn” is typically **total RN** (CMS definition). Charts label “Reported RN” / “Case-Mix RN” / “Adjusted RN” — no explicit “Direct RN” series in prov_info.
- **Reports (facility_report_lib, internal_report_generator):** Differentiate explicitly: direct_care_rn_hprd (Hrs_RN) vs rn_hprd (total RN). State comparison uses Direct_Care_RN_HPRD from state_lite_metrics; internal_report_generator uses RN_HPRD and Total_RN_HPRD from facility columns (Total_Nurse_HPRD, Total_Staff_HPRD, RN_HPRD, Total_RN_HPRD) — naming in that file: “Direct Care HPRD” = Total_Nurse_HPRD, “RN HPRD” = direct RN, “Total RN HPRD” = reported total RN.

### 8.3 Charts Using Direct RN Only

- prov_info does not plot “Direct RN” as a separate series; it plots “Reported RN” (Provider Info), which is total RN. Attorney report and state comparison tables show both “RN HPRD (Total)” and “RN HPRD” (Direct) columns.

### 8.4 Potential Inconsistencies

- **Provider Info column names:** reported_rn_hrs_per_resident_per_day is CMS total RN. Any label saying “Direct RN” in UI must come from PBJ-derived direct_care_rn_hprd (Hrs_RN) computed in facility_report_lib or generate_metrics (RN_Care_HPRD), not from Provider Info reported_rn.
- **State lite:** Direct_Care_RN_HPRD = RN_Care_HPRD (direct); Total_RN_HPRD = RN_HPRD (total). Internal_report_generator state_quarterly_data uses Total_Nurse_HPRD and Direct_Care_RN_HPRD — so state comparison is direct-care vs direct-care and total vs total when both are present.

---

## 9. VISUALIZATION LAYER

### 9.1 Library

- **Plotly** (plotly.express.px and plotly.graph_objects.go) only in prov_info.

### 9.2 Charts in prov_info.py

| Chart | Type | Input dataset | Transformations | Color | Tooltip | Axis |
|-------|------|----------------|------------------|-------|---------|------|
| Reported vs Case-Mix (bar) | go.Bar, group | One row (selected quarter): reported_* vs case_mix_* for Total, RN, CNA | None | Blue Reported, Red Case-Mix | %{x}, %{y:.2f} HPRD | y: Hours per Resident Day |
| Delta annotations | Annotation | Same row | delta = rep − cm, pct = (rep/cm − 1)*100 | Blue if delta ≥ 0, red if < 0 | — | — |
| Total Staffing (line) | go.Scatter lines+markers | fac by quarter, last processing_date per quarter | groupby(quarter).last() | Blue Reported, Red Case-Mix, Green Adjusted (dash) | Quarter, HPRD .3f, File YYYY-MM | y: Hours per Resident Day |
| RN Staffing (line) | Same | reported_rn, case_mix_rn, adjusted_rn | Same | Same | Same | Same |
| Nurse Aide (line) | Same | reported_na, case_mix_na, adjusted_na | Same | Same | Same | Same |
| MDS Census (line) | px.line | quarter, avg_residents_per_day | groupby(quarter).last() | Default | Census, Residents .1f, File | y: Average Residents per Day |
| Delta over time (line) | px.line | delta = reported_total − case_mix_total | groupby(quarter).last(), sort by quarter | Default | Delta .3f, File | y: Hours per resident per day; hline at 0 |
| Percent delta (line) | px.line | (reported/case_mix − 1)*100 | Same, exclude case_mix==0 | Default | Percent .1f%, File | y: Percent; hline at 0 |
| Adjusted staffing (line) | px.line, melt | adjusted_na, adjusted_lpn, adjusted_rn, adjusted_total | groupby(quarter).last(), melt | Discrete color by metric | fullData.name, Value .3f, File | — |
| Ratings (line) | px.line | overall, staffing, health_inspection | Same | Overall #1f77b4, Staffing #2ca02c, Health #ff7f0e | Rating, File | y: Rating (1–5) |

### 9.3 Conditional Coloring

- Bar delta annotation: `rgba(33, 150, 243, 0.9)` if delta ≥ 0 else `rgba(244, 67, 54, 0.9)`.
- Ratings: color_discrete_map for series names.

### 9.4 Axis Formatting

- x: quarter_label = "Q{n} {YYYY}"; tickangle=45; nticks = len(unique quarter_label).
- y: title set per chart; no explicit y range or zero-forcing in layout (zero baseline added only for delta and percent delta via add_hline(y=0)).
- Height: 280 (bar), 400 (line charts).

### 9.5 Legend

- Horizontal, yanchor=bottom, y=1.02, xanchor=right, x=1; template=plotly_white.

---

## 10. DYNAMIC AXIS LOGIC

### 10.1 Y-Axis Min/Max

- **prov_info:** Plotly default autorange; no explicit yaxis_range or yaxis.min/max. No shared axis across facilities.

### 10.2 Zero Enforced

- Only for “Delta (Reported − Case-Mix)” and “Percent Delta” charts: `fig_delta.add_hline(y=0, ...)` and `fig_pct.add_hline(y=0, ...)`.

### 10.3 Padding

- No explicit padding; Plotly’s default margin. Bar annotation y = ymax + 0.4 for delta text above bars.

### 10.4 Pseudocode for Axis (If Implementing Explicit Logic)

```text
For line charts (HPRD, Census, Delta, Percent):
  y_min = min(data[y_column].min(), 0) if allow_negative else max(0, data[y_column].min())
  y_max = data[y_column].max()
  Option: add padding fraction (e.g. 0.05 * (y_max - y_min))
  Set yaxis_range = [y_min, y_max] or leave autorange

For bar chart (Reported vs Case-Mix):
  y_max = max(reported_values + case_mix_values) + 0.4 for annotation space
  y_min = 0
```

---

## 11. FORMATTING + DISPLAY STANDARDS

### 11.1 HPRD Decimal Precision

- **Calculation:** Full float in pandas; round_half_up(_, 2) for report outputs in facility_report_lib.
- **Display:** 3 decimals in prov_info comprehensive table and metric table (format_metric_table_value: f"{f:.3f}"); 2 decimals in attorney report and state comparison; 2 in Harrington/case-mix section. Delta annotation: .2f HPRD, .1f%.

### 11.2 Percentage Precision

- **Contract %:** 1 decimal (round_half_up(_, 1)).
- **Delta %:** .1f% in prov_info; report proportions (reported/case_mix*100): .1f%.

### 11.3 Case-Mix Precision

- 2 decimals in facility_report_lib for case_mix_* and Harrington; 3 in prov_info table for case_mix_* columns.

### 11.4 Region Sorting

- **State list:** Sorted string (sorted(latest["state"].dropna().astype(str).unique().tolist())).
- **Quarters:** Sorted by (year, quarter) key e.g. (int(x[:4]), int(x[5])) for "YYYYQn".

### 11.5 Label Naming Conventions

- **Reported:** “Reported Total”, “Reported RN”, “Reported Nurse Aide”, “Reported CNA HPRD” (table).
- **Case-Mix:** “Case-Mix (Expected)”, “Case-Mix Total”, “Case-Mix RN”, “Case-Mix CNA HPRD”.
- **Adjusted:** “Adjusted Total”, “Adjusted RN”, “Adjusted Nurse Aide”.
- **Quarter display:** “Q1 2023” not “2023Q1” in axis and tables (quarter_label).

### 11.6 Rounding: Calculation vs Display

- **Calculation:** round_half_up for report and risk (2 for HPRD/hours, 1 for %).
- **Display:** Same 2/3 decimals as above; prov_info table uses .3f for HPRD columns; report HTML uses .2f or .1f as specified per section.

---

## 12. STREAMLIT-SPECIFIC DEPENDENCIES

### 12.1 @st.cache_data

- **prov_info.load_data:** `@st.cache_data(show_spinner=False)` on load_data(). Reads provider_info_combined.csv and quarter_to_provider_mapping_examples.csv, builds date_to_quarter, adds quarter column, filters quarter >= "2017Q4", cleans text and numeric columns. **Flask replacement:** In-memory cache (e.g. flask_caching or lru_cache) or load once at app init; invalidate on file change or TTL.

### 12.2 Session State

- **prov_info:** No st.session_state used; selection is via selectbox return values (selected_ccn, sel_quarter) in the same run. **Flask:** Use request args or session for selected_ccn/quarter and pass to template or JSON.

### 12.3 Sidebar

- **prov_info:** No sidebar; main area has columns [1, 2] for state + facility selectors. **Flask:** Render as form or dropdowns in layout; no replacement for “sidebar” per se.

### 12.4 Dynamic Rerun Assumptions

- Script runs top-to-bottom on each interaction; load_data() is cached, so only first run reads CSV. **Flask:** Each request can call the same load_data equivalent (with server-side cache); no automatic rerun — route handlers must return full response.

### 12.5 Container Layout

- st.columns([1, 2]), st.columns([1, 0.001]), st.columns(3) for metrics; left/right for main vs empty. **Flask:** Replace with HTML/CSS grid or Bootstrap columns; render charts as HTML (plotly.to_html(fig, include_plotlyjs=...)) or return JSON for front-end Plotly.

### 12.6 CSS / Theme

- prov_info uses default Streamlit theme; no custom CSS injection. **Flask:** Use link to stylesheet or inline style in base template.

### 12.7 Replacements Summary

| Streamlit | Flask replacement |
|-----------|-------------------|
| st.cache_data(load_data) | Cached loader (Flask-Caching or lru_cache) or load at startup |
| st.selectbox / st.columns | HTML form + dropdowns + grid layout |
| st.plotly_chart(fig, use_container_width=True) | plotly.io.to_html(fig) or fig.to_json() for JS |
| st.dataframe | HTML <table> or return JSON for DataTables |
| st.metric | HTML cards or <span> with same labels/values |
| st.error / st.warning / st.stop | Flash messages + return 4xx or redirect |
| st.expander | Collapsible <details> or Bootstrap collapse |
| st.caption / st.markdown | HTML <p> / safe Markdown render |

---

## 13. PROPOSED FRAMEWORK-AGNOSTIC MODULE STRUCTURE

All modules below must contain **zero** Streamlit (or Flask) code; they are pure data/formatting/report logic.

```
metrics/
    __init__.py
    staffing_definitions.py   # Constants: PBJ column lists for Total Nurse, RN, Direct Care, Nurse Aide, Contract; helper functions total_nurse_hours_row(), direct_care_hours_row(), total_rn_hours_row().
    thresholds.py             # MACPAC lookup (get_macpac_state_standards), federal minimum constant, days_under_state_minimum logic; list of threshold constants (0.30, 0.55, 0.70, 3.2, etc.).
    case_mix.py               # CMI column name list, Harrington formula (calculate_harrington_adjusted_hprd), case_mix_direct = rn+lpn+na, proportion (reported/expected)*100.
    risk_flags.py             # From facility_red_flag_report.detect_red_flags: structural/major/warning/citation/data_quality detection, calculate_risk_score, risk level tiers; no UI.
    report_generator.py       # From facility_report_lib: round_half_up, format_quarter_display, _parse_quarter, _format_quarter_range, format_facility_name, format_city_name; load_facility_data, get_facility_info, get_daily_staffing, calculate_quarterly_metrics, calculate_period_metrics, calculate_days_under_state_minimum; get_macpac_state_standards, load_provider_info_data, extract_red_flags_history, normalize_quarter_format, extract_case_mix_data; calculate_quarterly_direct_care_hprd, calculate_harrington_adjusted_hprd; generate_case_mix_section, generate_red_flags_section, generate_attorney_report (return HTML string). Optional: thin wrapper that calls generate_pbj_report from generate_report.py (move that function into report_generator or keep as one dependency).
    formatting.py             # round_half_up (if not in report_generator), format_metric_table_value (3 decimals), HPRD 2 vs 3 decimal rules, percentage 1 decimal, quarter_label "Qn YYYY", column label map (reported_* -> "Reported ...").
    axis_logic.py             # Optional: compute_y_range(y_series, allow_negative=False, padding_frac=0.05), enforce_zero_min(series) for charts; used by Flask view layer when building Plotly figures.
```

### Data Loading (Remain in Top-Level or data/)

- **file_path_utils.py** — keep; used by report and dashboard to resolve facility/MACPAC paths.
- **load_provider_info** / **load_facility_data** — can live in report_generator or a small `data/loaders.py` that uses file_path_utils and returns DataFrames; no st.* or Flask.

### Flask App Layer (Outside metrics/)

- Routes call metrics.staffing_definitions, metrics.thresholds, metrics.case_mix, metrics.risk_flags, metrics.report_generator, metrics.formatting; build Plotly figures in views or a separate `charts/` module that uses axis_logic and returns go.Figure or dict for JSON.
- Templates render HTML; include Plotly via to_html or JS.

This structure preserves all institutional definitions, MACPAC and Harrington logic, red-flag rules, and report generation so that a Flask production environment can reproduce behavior without Streamlit.
