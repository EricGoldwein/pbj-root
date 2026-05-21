# Payroll-Based Journal Nursing Home Staffing Data

The **Payroll-Based Journal (PBJ)** is a federally mandated staffing data reporting system for U.S. nursing homes. It requires Medicare- and Medicaid-certified long-term care facilities to submit daily, employee-level staffing data each quarter using payroll and time-keeping records. Facilities must report hours worked for each staff member (including agency and contract staff) by job category and date, and submissions are considered timely only if they are received within 45 days after the quarter closes. PBJ data are auditable and are used by the [Centers for Medicare & Medicaid Services (CMS)](https://www.cms.gov/) to inform public reporting, enforcement activities, and research.

PBJ replaced earlier staffing surveys that captured only a short window of staffing and were vulnerable to manipulation. The system became mandatory on July 1, 2016, and CMS began posting [public use files](https://data.cms.gov/provider-data/dataset/4pq5-n9py) in 2017. PBJ is the most detailed national dataset on nursing home staffing available, but it must be interpreted carefully because it captures only paid hours and excludes important information such as shift start times, wages, and clinical outcomes.

## Why PBJ Exists

Before PBJ, nursing home staffing information was collected through periodic surveys (e.g., [CMS-671 and CMS-672 forms](https://www.cms.gov/regulations-and-guidance/guidance/transmittals/downloads/r75soma.pdf)). These surveys captured staffing over a two-week period and relied on self-reported counts, leading to concerns that facilities overstated their staffing levels. [Section 6106 of the Affordable Care Act](https://www.congress.gov/bill/111th-congress/house-bill/3590/text) directed CMS to develop an auditable, uniform system for collecting staffing information based on payroll records. PBJ addresses this requirement by requiring facilities to submit verifiable daily staffing data and by publishing public use files that can be analyzed by researchers, regulators, and the public.

## What PBJ Measures

PBJ collects data on who worked, what job they performed, and how many hours they worked on each calendar day. Key elements include:

- **Facility identifier:** Each nursing home's CMS certification number.
- **Worker identifier:** An anonymized employee ID.
- **Job category:** Standardized CMS job codes for nursing (5–12) and non-nursing roles (1–4, 15–40)—see [PBJ Metrics](/pbjpedia/metrics) and [Non-Nursing Staff](/pbjpedia/non-nursing-staff).
- **Work date:** The day on which hours were paid.
- **Hours worked:** Total hours, plus employee and contract hours by category.
- **Resident census:** Daily resident counts derived from [Minimum Data Set (MDS) assessments](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/nhqimds30).

## What PBJ Does Not Measure

PBJ data reflect paid hours only and therefore do not capture unpaid or volunteer work. The data do not include wages, pay rates, shift start or end times, or quality-of-care outcomes. Because PBJ reports staffing inputs rather than outcomes, it cannot alone determine whether a facility complies with clinical requirements such as the [eight-hour RN coverage requirement](/pbjpedia/state-standards). PBJ also lacks resident-level acuity information, so [hours-per-resident-day metrics](/pbjpedia/metrics) must be interpreted alongside other data sources. Analysts should be cautious when interpreting extreme daily values because [inclusion and exclusion criteria](/pbjpedia/methodology) are applied at the quarterly facility level, not for individual days.

## Key Concepts

### Staffing Metrics

PBJ data are commonly converted into **hours per resident day (HPRD)** metrics to enable comparisons across facilities. The default staffing metric is **Total Nurse Staffing HPRD**, which includes all nursing staff hours (administrative and direct care). Other common measures include RN HPRD, LPN/LVN HPRD, CNA HPRD, and Direct-Care Nurse HPRD (which excludes administrative hours). For detailed definitions, job codes, and calculations, see [PBJ Metrics](/pbjpedia/metrics).

### State Variation

Staffing requirements vary by state above the federal baseline (roughly 0.3 HPRD for a typical facility). PBJ320 displays MACPAC-style policy estimates on state and facility pages; see [State Staffing Standards](/pbjpedia/state-standards) for the full reference table from `macpac_state_standards_clean.csv`.

### Non-Nursing Staff

PBJ also collects hours for administrators, physicians, therapists, dietary staff, and other non-nursing roles. See [Non-Nursing Staff](/pbjpedia/non-nursing-staff).

### Data Limitations

PBJ was designed for compliance monitoring, not research. See [Data Limitations](/pbjpedia/data-limitations) for paid-hours-only caveats, census methodology, and exclusion rules.

## PBJpedia Structure

- **[PBJ Methodology](/pbjpedia/methodology)** – Collection, aggregation, PUF structure, inclusion/exclusion rules, MDS census.
- **[PBJ Metrics](/pbjpedia/metrics)** – HPRD definitions and nursing job codes 5–12.
- **[State Staffing Standards](/pbjpedia/state-standards)** – Federal baseline and MACPAC state reference table.
- **[Non-Nursing Staff](/pbjpedia/non-nursing-staff)** – Non-nursing job codes 1–4 and 15–40.
- **[Data Limitations](/pbjpedia/data-limitations)** – Interpretation caveats.

## References

1. CMS. **[Staffing Data Submission Payroll Based Journal (PBJ) webpage](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/staffing-data-submission-payroll-based-journal)**.
2. CMS & Abt Associates. **[Payroll-Based Journal Public Use Files: Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)** (2018).
