# Data quality & fallback patterns (internal audit index)

Last reviewed: 2026-05-28 (staffing bundle DQ audit). Companion: `docs/staffing_minimums_methodology.md`, `docs/ownership_methodology_audit.md`.

**Staffing thresholds:** NY operational **3.56** total nursing HPRD; CT operational **3.06** (not 3.56). Statutory direct-care figures (e.g. NY ~3.50, CT ~3.0) are separate from MACPAC total estimated staffing requirements used in the daily screen.

Hard rule: **missing or invalid data must not silently become compliant, noncompliant, or a precise average** without documentation.

---

## Edge-case handling matrix

| Case | Staffing compliance (PBJ daily) | Provider quarterly HPRD | Owner portfolio metrics | Ownership CCN match |
|------|--------------------------------|-------------------------|-------------------------|---------------------|
| Missing PBJ day | Day absent from quarter CSV → not in denominator | Quarter aggregate from facility CSV | N/A | N/A |
| Missing census | **Excluded** (`MDScensus > 0`) | Varies by column | Excluded from weighted means if no beds/census | N/A |
| Zero census | **Excluded** | Often excluded or null | N/A | N/A |
| Missing hour columns | **COALESCE → 0** in build SQL (latent risk; see § Staffing compliance bundle QA) | Usually NaN / N/A display | Omitted from means | N/A |
| Negative hours | **Not filtered** in compliance SQL | Depends on upstream CSV | Not specially filtered in compliance | N/A |
| Implausible HPRD (>12, <1.5) | **Not filtered** in compliance | Portfolio means exclude 1.5–12 | N/A | N/A |
| Duplicate facility/day | **Not deduped** in compliance SQL (latent risk; none in NY/CT 2025 audit) | Depends on facility_quarterly build | Name-dedup vs CCN-dedup mismatch on profiles | Multiple SNF rows possible |
| No provider info | N/A | Missing star/HPRD → N/A | Facility still listed; no PBJ columns | legal_exact fails → fuzzy/name |
| CCN leading zeros | `LPAD(provnum,6)` in build | Normalized in app | Normalized `_norm_ccn_key` | zfill(6) |
| Facility rename | N/A | Historical names in CSV | Crosswalk by name | Org name index |
| Partial quarter | All days in file counted | Quarter label from data | Snapshot point-in-time | N/A |
| Facility opens/closes mid-quarter | All reported days in file | CMS quarterly rollups | N/A | N/A |
| CHOW without PAC | N/A | N/A | N/A | `chow_only` profile |
| Fuzzy owner name | N/A | N/A | N/A | `~` badge; excluded from portfolio means |

---

## Fallback / default patterns (site-wide)

| Pattern | Location | Public? | Risk | Class |
|---------|----------|---------|------|-------|
| `COALESCE(hours,0)` | PBJapp compliance SQL | Indirect (counts) | Latent: missing hours → zero RN / low HPRD; **no impact on NY/CT 2025 bundle** (audited) | **B** (latent) |
| `load_csv_data` fallback | `app.py` provider index | Yes | Local dev masks missing sqlite | **C** |
| `_api_dates_fallback_quarters()` | `app.py` | API | Stale quarter list if JSON missing | **B** |
| `format_metric_value` → N/A | `pbj_format.py` | Yes | Missing metrics show N/A not 0 | **A** (safe) |
| Portfolio weight fallback | `owner_portfolio_metrics` | Yes | No weight=1.0 fallback anymore | **A** |
| FEC name match | `owner_fec_section` | Yes | Similar names | **B** (disclaimed) |
| `get_macpac_hprd_for_state` | Charts / SEO | Yes | MACPAC estimate, not law | **B** |
| Provider `or 0` on ratings | `app.py` risk flags | Yes | Only for star==1 checks | **B** |
| Premium demo HTML | `premium/samples/*` | Sample only | Softened OUT/IN compliance labels (2026-05-28) | **C** |
| `about.html` 3.50 HPRD | Marketing | Yes | Clarified vs 3.56 operational screen; 3.50 retained | **B** |
| Provider warning copy | `app._provider_staffing_compliance_warning` | Yes | "PBJ days below … threshold"; modal disclaims legal findings | **B** |

Run `python scripts/audit_no_fake_numbers.py` for a fresh grep report.

---

## Staffing compliance bundle QA (NY/CT 2025)

**Audited:** `PBJapp/standardized_PBJ` daily files for **CY2025Q1–CY2025Q4**, states NY + CT (same scope as deployed `staffing_compliance_summary.csv.gz`).  
**Script:** `python scripts/audit_pbj_compliance_data_quality.py`  
**Production logic:** unchanged (read-only audit artifact).

### Conclusions (preserve)

| Finding | Result |
|---------|--------|
| **COALESCE(hours, 0)** | **Latent risk** in build SQL, but **does not affect current NY/CT 2025 bundle counts** — zero null/blank hour fields in standardized files (286,352 census>0 facility-days audited). |
| **Duplicate (CCN, WorkDate)** | **Not present** in current NY/CT 2025 inputs (0 extra rows across four quarters). Build `len(group)` would double-count if dupes appeared. |
| **Extreme HPRD (>12)** | **141** facility-days (mostly **very low census**, e.g. census=1). **Not inflating** below-threshold counts (0 high-HPRD days also below threshold). |
| **Negative hours / negative census** | **0** in audited scope. |
| **Public bundle vs source** | **Match** — e.g. CY2025Q4: 71,821 days, 53 RN-0 days, 29,752 below-threshold days, 781 facilities (source aggregation = bundle sums). |

**Not implemented (by design):** low-census exclusion, HPRD caps, COALESCE/dedupe production changes, new public UI fields.

### Pre-export guardrail

Before publishing a **new compliance bundle** or **adding states**, rerun:

```powershell
python scripts/audit_pbj_compliance_data_quality.py
python scripts/audit_staffing_thresholds.py --quarter CY2025Q4
```

Flag any:

- null or blank PBJ hour fields (COALESCE impact on 0 RN / below-threshold / RN<8),
- duplicate CCN + WorkDate rows,
- negative hours or census,
- extreme total nursing or RN HPRD values,
- whether any of the above **change** below-threshold, 0 RN, or RN&lt;8 day counts vs current bundle.

---

## Ownership count scope (see ownership doc)

- State index: in-state distinct CCNs (owner PAC).
- Profile header: national facility-name count (or snapshot `n_facilities`).
- Tooltips document scope (2026-05-28); numbers may differ for multistate owners.

---

## Tests / scripts

| Script | Purpose |
|--------|---------|
| `scripts/audit_pbj_compliance_data_quality.py` | Pre-export DQ: COALESCE impact, dupes, extreme HPRD, source vs bundle |
| `scripts/audit_staffing_thresholds.py` | Bundle vs expectations; sample CCNs |
| `scripts/audit_no_fake_numbers.py` | Grep risky patterns + threshold literals |
| `scripts/audit_ownership_data.py` | Owner index vs profile counts |
| `scripts/validate_ownership_linkage.py` | Deploy guard for ownership crosswalk |
