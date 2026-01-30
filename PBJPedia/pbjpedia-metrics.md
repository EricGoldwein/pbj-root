# PBJ Metrics

This page defines common metrics derived from [Payroll-Based Journal (PBJ)](/pbjpedia/overview) data and explains how they are calculated.

The Payroll-Based Journal reports staffing inputs in terms of paid hours. To make meaningful comparisons across facilities, researchers and regulators convert these hours into hours per resident day (HPRD) and related metrics. HPRD represents the average number of staff hours available per resident in a given period. The general formula is: **HPRD = Total paid hours ÷ Resident days**, where resident days are calculated from [MDS assessments](/pbjpedia/methodology). HPRD can be computed for a single day, a quarter or any time window by summing hours and resident days over that period. [PBJ public use files](https://data.cms.gov/provider-data/dataset/4pq5-n9py) provide the data needed to compute HPRD at the facility-day and facility-quarter level.

PBJ distinguishes between several categories of nursing staff, allowing multiple HPRD measures. The default staffing metric is **Total Nurse Staffing HPRD**, which includes hours for the director of nursing, RNs with administrative duties, RNs, LPNs with administrative duties, LPNs, certified nurse aides, medication aides/technicians and nurse aides in training. Other common measures include RN HPRD, LPN/LVN HPRD, CNA HPRD, and Direct-Care Nurse HPRD (which excludes administrative hours). Administrative hours are included in total nurse staffing per CMS rules but are conceptually distinct from direct-care hours.

HPRD is a measure of staffing input, not quality of care. Higher HPRD values generally indicate more staff time per resident, but they do not guarantee better outcomes. Staffing mix (e.g., ratio of RNs to CNAs), weekend versus weekday staffing and contract versus employee hours are all important contextual factors. PBJ data are best used in combination with quality measures, resident acuity and facility characteristics. For more information, see [Data Limitations](/pbjpedia/data-limitations).

## PBJpedia Navigation

- [PBJ Overview](/pbjpedia/overview)
- [PBJ Methodology](/pbjpedia/methodology)
- [PBJ Metrics](/pbjpedia/metrics) (this page)
- [State Staffing Standards](/pbjpedia/state-standards)
- [Non-Nursing Staff](/pbjpedia/non-nursing-staff)
- [Data Limitations](/pbjpedia/data-limitations)
- [History of PBJ](/pbjpedia/history)

## Hours Per Resident Day (HPRD)

HPRD represents the average number of staff hours available per resident in a given period. The general formula is:

**HPRD = Total paid hours ÷ Resident days**

where resident days are calculated from [MDS assessments](/pbjpedia/methodology). HPRD can be computed for a single day, a quarter or any time window by summing hours and resident days over that period. [PBJ public use files](https://data.cms.gov/provider-data/dataset/4pq5-n9py) provide the data needed to compute HPRD at the facility-day and facility-quarter level.

### Nurse Staffing HPRD

PBJ distinguishes between several categories of nursing staff, allowing multiple HPRD measures:

- **Total Nurse Staffing HPRD** – The default staffing metric. Includes hours for the director of nursing, RNs with administrative duties, RNs, LPNs with administrative duties, LPNs, certified nurse aides, medication aides/technicians and nurse aides in training.
- **RN HPRD** – Uses hours for RNs (administrative and direct care).
- **LPN/LVN HPRD** – Uses hours for LPNs (administrative and direct care).
- **CNA HPRD** – Uses hours for certified nurse aides.
- **Direct-Care Nurse HPRD** – Excludes administrative hours; counts only hours spent delivering hands-on care to residents. CMS publishes both total and direct-care versions of nurse staffing HPRD.

Administrative hours are included in total nurse staffing per CMS rules, but are conceptually distinct from direct-care hours. Analysts often compare calculated HPRD values to benchmarks. CMS's 2001 staffing study recommended 0.75 HPRD of RN staffing and 4.1 HPRD of total direct-care staffing. In 2024 CMS finalized a national minimum staffing standard of 3.48 HPRD of total direct nursing care, comprising at least 0.55 HPRD of RN care and 2.45 HPRD of nurse aide care (see [History of PBJ](/pbjpedia/history) for details on the rescission of this rule).

### Non-Nursing HPRD

While public reporting focuses on nursing hours, HPRD can also be calculated for [non-nursing roles](/pbjpedia/non-nursing-staff). To compute a non-nursing HPRD for a given category, divide total paid hours for that job by the resident days. Examples include administrator HPRD, therapist HPRD and dietary HPRD. Because non-nursing roles differ widely in their functions, there are no established benchmarks; however, tracking these metrics can reveal reliance on contract staff and highlight operational differences across facilities.

## Interpreting HPRD Metrics

HPRD is a measure of staffing input, not quality of care. Higher HPRD values generally indicate more staff time per resident, but they do not guarantee better outcomes. Staffing mix (e.g., ratio of RNs to CNAs), weekend versus weekday staffing and contract versus employee hours are all important contextual factors. PBJ data are best used in combination with quality measures, resident acuity and facility characteristics. For more information, see [Data Limitations](/pbjpedia/data-limitations).

## Related PBJpedia Pages

- [PBJ Overview](/pbjpedia/overview) – Describes the core data elements and what PBJ does not measure
- [PBJ Methodology](/pbjpedia/methodology) – Details how resident days are calculated and how data are aggregated
- [Non-Nursing Staff](/pbjpedia/non-nursing-staff) – Provides definitions of non-nursing job categories
- [State Staffing Standards](/pbjpedia/state-standards) – Summarizes federal and state minimum staffing requirements

## References

1. CMS & Abt Associates. **[Payroll-Based Journal Public Use Files: Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)** (2018). Describes job categories included in total nurse staffing.
2. MACPAC. **[State Policy Levers to Address Nursing Facility Staffing Issues](https://www.macpac.gov/publication/state-policy-levers-to-address-nursing-facility-staffing-issues/)** (2022). Provides recommended staffing benchmarks of 0.75 RN HPRD and 4.1 total direct-care HPRD.
3. CMS. **[Minimum Staffing Standards for Long-Term Care Facilities Final Rule](https://www.cms.gov/newsroom/fact-sheets/medicare-and-medicaid-programs-minimum-staffing-standards-long-term-care-facilities-and-medicaid-0)** (2024, rescinded). See [History of PBJ](/pbjpedia/history) for details.