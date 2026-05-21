# PBJ Methodology

This page explains how the [Payroll-Based Journal (PBJ)](/pbjpedia/overview) data collection system works, including how CMS collects, aggregates, and publishes PBJ data.

PBJ data are collected through a federally administered reporting system that requires nursing homes to submit auditable, day-by-day staffing information. CMS developed the Payroll-Based Journal to gather staffing information on a regular and more frequent basis than previous surveys. Facilities submit data electronically through the [PBJ system](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/staffing-data-submission-payroll-based-journal), which accepts payroll and time-and-attendance files covering each day in the quarter. Submissions are due within 45 days after the end of each quarter.

CMS publishes two quarterly [public use files (PUFs)](https://data.cms.gov/provider-data/dataset/4pq5-n9py): the Nursing Staff PUF and the Non-Nursing Staff PUF. Both have been available since 2017 Q1. They report daily hours by job category and MDS-derived resident census. Only data received by the reporting deadline are included; facilities with incomplete or erroneous submissions may be excluded.

## CMS PBJ System Overview

Facilities report hours each staff member is paid to work, by [job code](/pbjpedia/metrics), and whether hours are employee or contract. Nursing categories (codes 5–12) and [non-nursing categories](/pbjpedia/non-nursing-staff) (codes 1–4 and 15–40) are submitted separately in the two PUFs.

## Public Use Files (PUFs)

1. **Nursing Staff PUF** – Daily hours and census for RNs, LPNs/LVNs, nurse aides, and related nursing categories.
2. **Non-Nursing Staff PUF** – Daily hours and census for administrators, physicians, therapists, dietary, environmental, and other mandatory non-nursing categories.

### Aggregation Rules

Staffing data are aggregated to the facility-day level: one record per facility per calendar day in the quarter (90–92 days). Columns include total, employee, and contract hours for each job category.

### Inclusion and Exclusion Criteria

CMS applies facility-level rules before publishing PBJ data, including:

- **Facility inclusion:** Active on the last day of the quarterly submission period.
- **Missing staffing:** Exclusion when MDS census is non-zero but no nurse staffing is reported on multiple days.
- **Aberrant staffing:** Exclusion when quarterly aggregate nurse staffing is below 1.5 or above 12 HPRD, or nurse aide staffing exceeds 5.25 HPRD.

These exclusions use quarterly aggregates, not daily values—extreme single-day hours may still appear. See [Data Limitations](/pbjpedia/data-limitations).

## MDS-Based Resident Census

PBJ uses the [Minimum Data Set (MDS)](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/nhqimds30) to estimate daily resident census:

1. Define the reporting quarter.
2. Pull MDS assessments from one year before the quarter through quarter end.
3. Treat residents as discharged after a discharge assessment or 150 days without an assessment.
4. Count remaining residents per day as the daily census.

That census is the denominator for [HPRD](/pbjpedia/metrics).

## Known CMS Caveats

PBJ reflects **paid hours only**—not volunteer time, wages, or shift times. It does not prove compliance with RN coverage or state staffing statutes. Physician and practitioner hours are often underreported when billed outside facility payroll. Job codes differ from legacy CMS-671 categories, so long-term trends across systems require care.

## Related PBJpedia Pages

- [PBJ Overview](/pbjpedia/overview)
- [PBJ Metrics](/pbjpedia/metrics)
- [Data Limitations](/pbjpedia/data-limitations)
- [State Staffing Standards](/pbjpedia/state-standards)

## References

1. CMS. **[Staffing Data Submission Payroll Based Journal (PBJ) webpage](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/staffing-data-submission-payroll-based-journal)**.
2. CMS & Abt Associates. **[Payroll-Based Journal Public Use Files: Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)** (2018).
