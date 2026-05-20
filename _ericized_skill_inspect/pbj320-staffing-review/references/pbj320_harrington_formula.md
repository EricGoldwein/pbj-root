# Harrington expected HPRD — formula PBJ320 uses

This is the **acuity-adjusted staffing model** from Harrington et al., not CMS case-mix hours. For conceptual contrast, see `pbj320_harrington_vs_casemix.md`.

## Primary source

- Harrington, C. et al. **Nursing Home Guide to Adjusting Nurse Staffing for Resident Case-Mix.** *Journal of the American Geriatrics Society* (2023). DOI: https://doi.org/10.1111/jgs.19501  

PBJ320 implements the published curve with numeric constants kept in application config (same values as `pbj-contract/definitions.yaml` → `harrington_case_mix` in the PBJapp codebase). If code and this file disagree, **trust the shipped constants** and refresh this reference.

## Inputs

- **Nursing case-mix index (CMI)** — facility-level nursing CMI from CMS Provider Information for the quarter (when present). If CMI is missing or non-positive, Harrington expected is **not** computed for that quarter.

## CMI scaling (common to all three series)

Let `base_cmi = 0.62` and `max_cmi = 3.84`. If `max_cmi - base_cmi` is not positive, skip.

**Normalized CMI ratio:**

`r = (CMI - base_cmi) / (max_cmi - base_cmi)`

(Ratios below 0 or above 1 should follow application clamping if any; PBJ320 uses the ratio as computed when CMI is valid.)

## Expected HPRD by series

For each series, constants are **intercept**, **high** (upper anchor HPRD at the top of the normalized CMI range), and **exponent**:

**Harrington HPRD** = intercept + pow(r, exponent) × (high − intercept)

(Same expression in Python: `intercept + (ratio ** exponent) * (high - intercept)`.)

| Series (`hprd_type`) | intercept | high | exponent |
|----------------------|-----------|------|----------|
| **total** (total nursing) | 3.48 | 7.68 | 0.715361977219995 |
| **rn** | 0.55 | 2.39 | 0.973947642000645 |
| **cna** (nurse aide / NA) | 2.45 | 3.6 | 0.236050267902121 |

## How PBJ320 compares “reported” to Harrington

- **Total** Harrington vs **direct care** total HPRD from PBJ (admin/DON excluded from direct care, per product definitions).  
- **RN** Harrington vs **direct RN** HPRD.  
- **CNA** Harrington vs **reported nurse aide** HPRD (NA aggregate as implemented on the dashboard).  

**\% of Harrington expected** = (reported HPRD ÷ Harrington HPRD) × 100 when both are defined.

## Reviewer reminders

- Still **not** a legal staffing floor.  
- Different from **CMS case-mix hours** (PDPM CMG pathway) — see `pbj320_case_mix_cms.md`.  
- Do not hand-recompute decimals for filings unless you verify CMI and rounding match the export; cite the dashboard or recreate from the primary paper + Provider Information.
