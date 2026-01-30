# Data Limitations

This page outlines important limitations and caveats when using Payroll-Based Journal (PBJ) data. For an overview of what PBJ is and what it measures, see [PBJ Overview](/pbjpedia/overview).

PBJ data are a valuable resource for understanding staffing patterns in nursing homes, but they were designed for compliance monitoring rather than research. Users of PBJ data should be aware of several important limitations and caveats. PBJ captures only hours for which staff are paid. Unpaid overtime or volunteer work is not reported. Salaried workers may work additional hours that are unpaid and therefore unreported, which means PBJ may underestimate the time spent caring for residents. The data do not include wages, pay rates, shift start or end times, or quality-of-care outcomes.

PBJ data are best used comparatively and contextually. Higher HPRD values generally indicate more staffing time per resident, but they do not necessarily reflect staffing adequacy or quality of care. Analysts should consider staffing mix (ratio of RNs to CNAs), weekend versus weekday staffing, contract versus employee hours and facility characteristics. PBJ data do not indicate compliance with specific regulations such as the eight-hour RN coverage requirement. For policy analysis, PBJ should be combined with other sources such as MDS quality measures, survey deficiencies and financial data.

Inclusion and exclusion criteria are applied at the facility-quarter level, not for individual days. This means that extreme daily values (very high or very low staffing on a given day) may remain in the data even if a facility is included. Analysts may need to apply additional edits to address implausible patterns. PBJ PUFs include only data received by the reporting deadline. Facilities that submit incomplete or erroneous data are excluded entirely. As a result, coverage may vary across quarters.

## PBJpedia Navigation

- [PBJ Overview](/pbjpedia/overview)
- [PBJ Methodology](/pbjpedia/methodology)
- [PBJ Metrics](/pbjpedia/metrics)
- [State Staffing Standards](/pbjpedia/state-standards)
- [Non-Nursing Staff](/pbjpedia/non-nursing-staff)
- [Data Limitations](/pbjpedia/data-limitations) (this page)
- [History of PBJ](/pbjpedia/history)

## Key Limitations

- **Paid hours only.** PBJ captures only hours for which staff are paid. Unpaid overtime or volunteer work is not reported. Salaried workers may work additional hours that are unpaid and therefore unreported, which means PBJ may underestimate the time spent caring for residents.

- **No wages or shift times.** PBJ does not include wage information or the start and end times of shifts. Analysts cannot determine whether staffing hours are concentrated during certain parts of the day.

- **Limited acuity information.** Resident census counts are derived from MDS assessments, but PBJ data do not provide resident-level acuity or case mix. HPRD metrics should therefore be interpreted in context; facilities with higher-acuity residents may require more staff.

- **Administrative vs. direct care.** PBJ combines administrative and direct-care hours for some job categories. CMS publishes both total and direct-care versions of some staffing measures, but distinguishing administrative duties may still require additional assumptions. Administrative hours are included per CMS rules but are conceptually distinct from direct-care hours.

- **Quarterly exclusion rules.** Inclusion and exclusion criteria are applied at the facility-quarter level. This means that extreme daily values (very high or very low staffing on a given day) may remain in the data even if a facility is included. Analysts may need to apply additional edits to address implausible patterns.

- **Incomplete submissions and missing data.** PBJ PUFs include only data received by the reporting deadline. Facilities that submit incomplete or erroneous data are excluded entirely. As a result, coverage may vary across quarters.

- **Differences from prior surveys.** Job categories and definitions in PBJ differ from those used in earlier staffing surveys (CMS-671). For example, PBJ separates licensed practical/vocational nurses with administrative duties from those providing direct care. Comparisons across data sources should take these definitional differences into account.

- **Low physician/practitioner hours.** Hours reported for physicians and non-physician practitioners (e.g., nurse practitioners, physician assistants and clinical nurse specialists) are often low because these services are typically billed to Medicare or other insurers rather than paid by the facility.

- **Excel limitations.** PBJ PUFs can contain more than one million rows. Desktop spreadsheet programs like Microsoft Excel cannot load all rows; users should use statistical software (e.g., SAS, Stata, R) or filter data by state or facility before opening.

## Interpreting PBJ Data

PBJ data are best used comparatively and contextually. Higher HPRD values generally indicate more staffing time per resident, but they do not necessarily reflect staffing adequacy or quality of care. Analysts should consider staffing mix (ratio of RNs to CNAs), weekend versus weekday staffing, contract versus employee hours and facility characteristics. PBJ data do not indicate compliance with specific regulations such as the eight-hour RN coverage requirement. For policy analysis, PBJ should be combined with other sources such as MDS quality measures, survey deficiencies and financial data.

## Related PBJpedia Pages

- [PBJ Overview](/pbjpedia/overview) – Describes what PBJ measures and what it does not measure.
- [PBJ Methodology](/pbjpedia/methodology) – Details how PBJ data are collected, aggregated and published.## References1. CMS & Abt Associates. **Payroll-Based Journal Public Use Files: Technical Specifications** (2018). Provides details on inclusion/exclusion criteria, MDS-based census and data limitations.**Last updated:** January 2026