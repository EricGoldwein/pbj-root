# PBJ Methodology

This page explains how the [Payroll-Based Journal (PBJ)](/pbjpedia/overview) data collection system works, including how CMS collects, aggregates and publishes PBJ data.

PBJ data are collected through a federally administered reporting system that requires nursing homes to submit auditable, day-by-day staffing information. CMS developed the Payroll-Based Journal to gather staffing information on a regular and more frequent basis than previous surveys. Facilities submit data electronically through the PBJ system, which accepts payroll and time-and-attendance files covering each day in the quarter. The system is auditable to ensure accuracy and is available to all long-term care facilities at no cost. Submissions are due within 45 days after the end of each quarter.

CMS publishes two quarterly [public use files (PUFs)](https://data.cms.gov/provider-data/dataset/4pq5-n9py) to support analysis: the Nursing Staff PUF and the Non-Nursing Staff PUF. Both PUFs have been available since the first calendar quarter of 2017 and are updated each quarter. They report staffing hours for each day in the quarter along with resident census information derived from [MDS assessments](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/nhqimds30). Only data received by the reporting deadline (45 days after quarter end) are included; facilities that submit incomplete or erroneous data are excluded from the PUFs.

## PBJpedia Navigation

- [PBJ Overview](/pbjpedia/overview)
- [PBJ Methodology](/pbjpedia/methodology) (this page)
- [PBJ Metrics](/pbjpedia/metrics)
- [State Staffing Standards](/pbjpedia/state-standards)
- [Non-Nursing Staff](/pbjpedia/non-nursing-staff)
- [Data Limitations](/pbjpedia/data-limitations)
- [History of PBJ](/pbjpedia/history)

## CMS PBJ System Overview

CMS developed the Payroll-Based Journal to gather staffing information on a regular and more frequent basis than previous surveys (see [History of PBJ](/pbjpedia/history)). Facilities submit data electronically through the [PBJ system](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/staffing-data-submission-payroll-based-journal), which accepts payroll and time-and-attendance files covering each day in the quarter. The system is auditable to ensure accuracy and is available to all long-term care facilities at no cost. Submissions are due within 45 days after the end of each quarter.

PBJ distinguishes between [nursing staff](/pbjpedia/metrics) (e.g., directors of nursing, registered nurses, licensed practical/vocational nurses and certified nurse aides) and [non-nursing staff](/pbjpedia/non-nursing-staff) (e.g., administrators, physicians, therapists and support staff). The system also identifies whether hours were worked by facility employees or contract staff. Facilities report the number of hours each staff member is paid to deliver services for each day worked.

## Public Use Files (PUFs)

CMS publishes two quarterly [public use files](https://data.cms.gov/provider-data/dataset/4pq5-n9py) to support analysis:

1. **Nursing Staff PUF** – Contains daily hours and MDS census for registered nurses (RNs), licensed practical/vocational nurses (LPN/LVNs), nurse aides and related categories.
2. **Non-Nursing Staff PUF** – Contains daily hours and MDS census for all other mandatory staffing categories (e.g., administrators, medical directors, therapists).

Both PUFs have been available since the first calendar quarter of 2017 and are updated each quarter. They report staffing hours for each day in the quarter along with resident census information derived from [MDS records](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/nhqimds30). Only data received by the reporting deadline (45 days after quarter end) are included; facilities that submit incomplete or erroneous data are excluded from the PUFs.

### Aggregation Rules

The staffing data in the PUFs are aggregated to the facility-day level. Each included facility has one record per calendar day in the quarter, so the total number of records equals the number of facilities multiplied by the number of days in the quarter (90–92). The files include separate columns for total hours, employee hours and contract hours for each job category.

### Inclusion and Exclusion Criteria

CMS applies facility-level inclusion and exclusion rules before publishing PBJ data. Key criteria include:

- **Facility inclusion:** The facility must have been active on the last day of the quarterly submission period.
- **Missing staffing:** Facilities with multiple days where the MDS census is non-zero but no nurse staffing is reported are excluded.
- **Aberrant staffing:** Facilities are excluded if aggregate nurse staffing for the quarter is less than 1.5 or greater than 12 hours per resident day, or if nurse aide staffing exceeds 5.25 hours per resident day.

These exclusions are applied using quarterly aggregates, not daily values. As a result, extreme daily staffing values may still appear in the data. CMS notes that analysts may wish to apply additional edits when interpreting PBJ data. For more information, see [Data Limitations](/pbjpedia/data-limitations).

## MDS-Based Resident Census

PBJ uses the [Minimum Data Set (MDS)](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/nhqimds30) to estimate the resident census for each day. The methodology involves several steps:

1. Identify the reporting quarter (e.g., January 1 – March 31).
2. Extract MDS assessment data for all residents of the facility beginning one year prior to the quarter to identify all possible residents.
3. Determine whether a resident has been discharged either via a recorded discharge assessment or through a gap of 150 days without any assessment.
4. Count all residents who have not been discharged according to step 3 as residing in the facility on each date; this count becomes the daily census.

The MDS-based census allows PBJ to calculate [hours per resident day (HPRD)](/pbjpedia/metrics) by dividing total staffing hours by resident days.

## Known CMS Caveats

CMS emphasizes that PBJ data are designed for compliance monitoring, not for measuring care quality. Facilities report only paid hours; unpaid or volunteer work is not captured. The PBJ system cannot indicate noncompliance with other long-term care requirements (e.g., the [requirement for registered nurse coverage at least eight hours per day](/pbjpedia/state-standards)). The data also may contain extreme values because inclusion and exclusion rules are applied at the quarterly facility level. CMS notes that some job categories differ from those used in earlier surveys (e.g., CMS-671), so staffing values may not be directly comparable across data sources. Physician and non-physician practitioner hours are often underreported because those services are typically billed separately and not paid by facilities.

For additional caveats, see [Data Limitations](/pbjpedia/data-limitations).

## Related PBJpedia Pages

- [PBJ Overview](/pbjpedia/overview) – Summarizes what PBJ measures, why it exists and what it does not measure
- [PBJ Metrics](/pbjpedia/metrics) – Defines hours-per-resident-day and related calculations
- [Data Limitations](/pbjpedia/data-limitations) – Provides additional caveats when using PBJ data

## References

1. CMS. **[Staffing Data Submission Payroll Based Journal (PBJ) webpage](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/staffing-data-submission-payroll-based-journal)**. Explains the purpose of the PBJ system and reporting deadlines.
2. CMS & Abt Associates. **[Payroll-Based Journal Public Use Files: Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)** (2018). Details the structure of PBJ public use files, aggregation rules and inclusion/exclusion criteria.
3. CMS & Abt Associates. **[PBJ Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)**. Describes the MDS-based census methodology and limitations of PBJ data.