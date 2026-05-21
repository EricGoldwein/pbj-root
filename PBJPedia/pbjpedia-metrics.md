# PBJ Metrics

This page defines common metrics derived from [Payroll-Based Journal (PBJ)](/pbjpedia/overview) data and explains how they are calculated.

The Payroll-Based Journal reports staffing inputs in terms of paid hours. To make meaningful comparisons across facilities, researchers and regulators convert these hours into hours per resident day (HPRD) and related metrics. HPRD represents the average number of staff hours available per resident in a given period. The general formula is: **HPRD = Total paid hours ÷ Resident days**, where resident days are calculated from [MDS assessments](/pbjpedia/methodology). HPRD can be computed for a single day, a quarter, or any time window by summing hours and resident days over that period. [PBJ public use files](https://data.cms.gov/provider-data/dataset/4pq5-n9py) provide the data needed to compute HPRD at the facility-day and facility-quarter level.

PBJ distinguishes between several categories of nursing staff, allowing multiple HPRD measures. The default staffing metric is **Total Nurse Staffing HPRD**, which includes hours for the director of nursing, RNs with administrative duties, RNs, LPNs with administrative duties, LPNs, certified nurse aides, medication aides/technicians, and nurse aides in training. Other common measures include RN HPRD, LPN/LVN HPRD, CNA HPRD, and Direct-Care Nurse HPRD (which excludes administrative hours). Administrative hours are included in total nurse staffing per CMS rules but are conceptually distinct from direct-care hours.

HPRD is a measure of staffing input, not quality of care. Higher HPRD values generally indicate more staff time per resident, but they do not guarantee better outcomes. Staffing mix (e.g., ratio of RNs to CNAs), weekend versus weekday staffing, and contract versus employee hours are all important contextual factors. PBJ data are best used in combination with quality measures, resident acuity, and facility characteristics. For more information, see [Data Limitations](/pbjpedia/data-limitations).

## Hours Per Resident Day (HPRD)

**HPRD = Total paid hours ÷ Resident days**

Resident days come from the [MDS-based census](/pbjpedia/methodology) in PBJ public use files.

### Nurse Staffing HPRD

| Measure | What it includes |
|---------|------------------|
| **Total Nurse Staffing HPRD** | All nursing codes below (admin + direct care) |
| **RN HPRD** | Codes 5–7 (DON, RN admin, RN) |
| **Direct RN HPRD** | Code 7 only |
| **LPN/LVN HPRD** | Codes 8–9 (LPN admin + LPN) |
| **CNA / nurse aide HPRD** | Codes 10–12 (CNA, aide in training, medication aide) |
| **Direct-Care Nurse HPRD** | Codes 7, 9, 10–12 (excludes DON and admin RN/LPN) |

### Nursing Job Codes (CMS Table 1)

| Job Code | Role | In typical HPRD metrics |
|----------|------|-------------------------|
| 5 | **RN Director of Nursing (DON)** | Total nurse; excluded from direct-care HPRD |
| 6 | **RN with administrative duties** | Total nurse and RN HPRD; excluded from direct-care |
| 7 | **Registered Nurse (RN)** | Total, RN, and direct-care RN |
| 8 | **LPN/LVN with administrative duties** | Total and LPN HPRD; excluded from direct-care |
| 9 | **Licensed Practical/Vocational Nurse** | Total, LPN, and direct-care |
| 10 | **Certified Nurse Aide (CNA)** | Total nurse and CNA/nurse aide HPRD |
| 11 | **Nurse Aide in Training** | Total nurse and CNA/nurse aide HPRD |
| 12 | **Medication Aide/Technician** | Total nurse and CNA/nurse aide HPRD |

Codes **13–14** (nurse practitioner, clinical nurse specialist) appear in CMS Table 1; reporting may appear in nursing or non-nursing files depending on role. [Non-nursing staff](/pbjpedia/non-nursing-staff) use codes 1–4 and 15–40.

Analysts often compare calculated HPRD values to benchmarks. CMS's 2001 staffing study recommended 0.75 HPRD of RN staffing and 4.1 HPRD of total direct-care staffing. A 2024 CMS final rule proposed 3.48 HPRD of total direct nursing care (0.55 RN, 2.45 nurse aide); those numeric federal minimums were rescinded and are not in effect—see [State Staffing Standards](/pbjpedia/state-standards).

### Non-Nursing HPRD

HPRD can also be calculated for [non-nursing roles](/pbjpedia/non-nursing-staff) by dividing paid hours in a job category by resident days (e.g., administrator HPRD, therapist HPRD). There are no universal federal benchmarks for these roles; they help describe operational mix and contract reliance.

## Interpreting HPRD Metrics

Use HPRD comparatively and with context: staffing mix, weekends vs. weekdays, contract share, acuity, and survey or quality data. PBJ alone does not show compliance with RN coverage rules or state statutes—see [State Staffing Standards](/pbjpedia/state-standards) and [Data Limitations](/pbjpedia/data-limitations).

## Related PBJpedia Pages

- [PBJ Overview](/pbjpedia/overview)
- [PBJ Methodology](/pbjpedia/methodology)
- [Non-Nursing Staff](/pbjpedia/non-nursing-staff)
- [State Staffing Standards](/pbjpedia/state-standards)

## References

1. CMS & Abt Associates. **[Payroll-Based Journal Public Use Files: Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)** (2018).
2. CMS. **[PBJ Policy Manual v2.4](https://www.cms.gov/medicare/quality-initiatives-patient-assessment-instruments/nursinghomequalityinits/downloads/pbj-policy-manual-final-v24.pdf)**. Table 1 job codes.
3. MACPAC. **[State Policy Levers to Address Nursing Facility Staffing Issues](https://www.macpac.gov/publication/state-policy-levers-to-address-nursing-facility-staffing-issues/)** (2022).
