# Payroll-Based Journal Nursing Home Staffing Data

The **Payroll-Based Journal (PBJ)** is a federally mandated staffing data reporting system for U.S. nursing homes. It requires Medicare- and Medicaid-certified long-term care facilities to submit daily, employee-level staffing data each quarter using payroll and time-keeping records. Facilities must report hours worked for each staff member (including agency and contract staff) by job category and date, and submissions are considered timely only if they are received within 45 days after the quarter ends. PBJ data are auditable and are used by the [Centers for Medicare & Medicaid Services (CMS)](https://www.cms.gov/) to inform public reporting, enforcement activities and research.

PBJ replaced earlier staffing surveys that captured only a short window of staffing and were vulnerable to manipulation. The system became mandatory on July 1, 2016, and CMS began posting [public use files](https://data.cms.gov/provider-data/dataset/4pq5-n9py) in 2017. PBJ is the most detailed national dataset on nursing home staffing available, but it must be interpreted carefully because it captures only paid hours and excludes important information such as shift start times, wages and clinical outcomes.

## Why PBJ Exists

Before PBJ, nursing home staffing information was collected through periodic surveys (e.g., [CMS-671 and CMS-672 forms](https://www.cms.gov/regulations-and-guidance/guidance/transmittals/downloads/r75soma.pdf)). These surveys captured staffing over a two-week period and relied on self-reported counts, leading to concerns that facilities overstated their staffing levels. [Section 6106 of the Affordable Care Act](https://www.congress.gov/bill/111th-congress/house-bill/3590/text) directed CMS to develop an auditable, uniform system for collecting staffing information based on payroll records. PBJ addresses this requirement by requiring facilities to submit verifiable daily staffing data and by publishing public use files that can be analyzed by researchers, regulators and the public.

## What PBJ Measures

PBJ collects data on who worked, what job they performed and how many hours they worked on each calendar day. Key elements include:

- **Facility identifier:** Each nursing home's CMS certification number.
- **Worker identifier:** An anonymized employee ID.
- **Job category:** Standardized codes for nurses (e.g., director of nursing, RN, LPN, CNA) and non-nursing roles (e.g., administrator, physician, therapist).
- **Work date:** The day on which hours were paid.
- **Hours worked:** Total hours, as well as hours paid to facility employees and hours paid to contract staff.
- **Contract vs. employee status:** Identifies whether hours were worked by facility employees or by agency/contract staff.
- **Resident census:** Daily resident counts derived from [Minimum Data Set (MDS) assessments](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/nhqimds30).

## What PBJ Does Not Measure

PBJ data reflect paid hours only and therefore do not capture unpaid or volunteer work. The data do not include wages, pay rates, shift start or end times, or quality-of-care outcomes. Because PBJ reports staffing inputs rather than outcomes, it cannot alone determine whether a facility complies with clinical requirements such as the [eight-hour RN coverage requirement](/pbjpedia/state-standards). PBJ also lacks resident-level acuity information, so [hours-per-resident-day metrics](/pbjpedia/metrics) must be interpreted alongside other data sources. Analysts should be cautious when interpreting extreme daily values because [inclusion and exclusion criteria](/pbjpedia/methodology) are applied at the quarterly facility level, not for individual days.

## Key Concepts

### Staffing Metrics

PBJ data are commonly converted into **hours per resident day (HPRD)** metrics to enable comparisons across facilities. The default staffing metric is **Total Nurse Staffing HPRD**, which includes all nursing staff hours (administrative and direct care). Other common measures include RN HPRD, LPN/LVN HPRD, CNA HPRD, and Direct-Care Nurse HPRD (which excludes administrative hours). Administrative hours are included in total nurse staffing per CMS rules but are conceptually distinct from direct-care hours. For detailed definitions and calculations, see [PBJ Metrics](/pbjpedia/metrics).

### State Variation

Staffing requirements for nursing homes vary widely across the United States. While the federal baseline requires minimal staffing (roughly 0.3 HPRD for a typical facility), states can and do impose additional minimum staffing standards. Analysis conducted for [MACPAC in 2021](https://www.macpac.gov/publication/state-policy-levers-to-address-nursing-facility-staffing-issues/) found that thirty-eight states and the District of Columbia have minimum staffing standards exceeding the federal requirement. Standards range from less than 2.0 HPRD to more than 4.0 HPRD. In April 2024, CMS issued a final rule establishing a national minimum staffing standard of 3.48 HPRD of total direct nursing care (see [History of PBJ](/pbjpedia/history) for details on the rescission). For more information, see [State Staffing Standards](/pbjpedia/state-standards).

### Non-Nursing Staff

Although PBJ is often discussed in the context of nurse staffing, the system also collects detailed information on non-nursing roles that are essential to nursing home operations, including administrators, medical directors, physicians, therapists and support staff. PBJ distinguishes between employees and contract staff and reports hours worked for each job category on each day. For detailed information on non-nursing job categories, see [Non-Nursing Staff](/pbjpedia/non-nursing-staff).

### Data Limitations

PBJ data are a valuable resource for understanding staffing patterns, but they were designed for compliance monitoring rather than research. Users should be aware that PBJ captures only paid hours, excludes unpaid work, does not include wages or shift times, lacks resident-level acuity information, and may contain extreme daily values because exclusion criteria are applied at the quarterly facility level. For a comprehensive discussion of limitations and caveats, see [Data Limitations](/pbjpedia/data-limitations).

## PBJpedia Structure

PBJpedia is organized into the following reference pages:

- **[PBJ Methodology](/pbjpedia/methodology)** – Explains how CMS collects, aggregates and publishes PBJ data, including public use file structure, aggregation rules, inclusion/exclusion criteria, and MDS-based resident census methodology.

- **[PBJ Metrics](/pbjpedia/metrics)** – Defines hours-per-resident-day (HPRD) and other derived measures, including Total Nurse Staffing HPRD, RN HPRD, LPN/LVN HPRD, CNA HPRD, and Direct-Care Nurse HPRD.

- **[State Staffing Standards](/pbjpedia/state-standards)** – Summarizes minimum staffing requirements in federal and state policy, including the federal baseline, state variation, policy mechanisms, and the 2024 federal minimum staffing rule.

- **[Non-Nursing Staff](/pbjpedia/non-nursing-staff)** – Describes non-nursing job categories in PBJ, including administrators, medical directors, physicians, therapists and support staff.

- **[Data Limitations](/pbjpedia/data-limitations)** – Outlines important caveats when using PBJ data, including limitations related to paid hours only, missing information, exclusion rules, and interpretation challenges.

- **[History of PBJ](/pbjpedia/history)** – Provides a timeline of policy milestones, from pre-PBJ surveys through mandatory reporting (2016), public data release (2017), methodological updates, and the 2024 national minimum staffing standard.

## PBJpedia Navigation

- [PBJ Overview](/pbjpedia/overview) (this page)
- [PBJ Methodology](/pbjpedia/methodology)
- [PBJ Metrics](/pbjpedia/metrics)
- [State Staffing Standards](/pbjpedia/state-standards)
- [Non-Nursing Staff](/pbjpedia/non-nursing-staff)
- [Data Limitations](/pbjpedia/data-limitations)
- [History of PBJ](/pbjpedia/history)

## References

1. CMS. **[Staffing Data Submission Payroll Based Journal (PBJ) webpage](https://www.cms.gov/medicare/quality/initiatives/patient-assessment-instruments/nursinghomequalityinits/staffing-data-submission-payroll-based-journal)**. Provides general information about the PBJ system, mandatory reporting dates and categories of nursing staff.
2. CMS & Abt Associates. **[Payroll-Based Journal Public Use Files: Technical Specifications](https://www.cms.gov/data-research/statistics-trends-and-reports/payroll-based-journal)** (2018). Explains the structure of PBJ public use files, aggregation rules, inclusion/exclusion criteria, data contents and limitations.


