# CMS nursing case-mix hours and nursing case-mix index (CMI)

Synthesized for PBJ320 AI review from CMS public documentation. For filings or testimony, cite CMS primary sources directly.

## Primary sources

- CMS Provider Information / PBJ Users Guide (case-mix hours, CMI, alignment with reported staffing):  
  https://www.cms.gov/medicare/provider-enrollment-and-certification/certificationandcomplianc/downloads/usersguide.pdf
- PDPM overview: https://www.cms.gov/Medicare/Medicare-Fee-for-Service-Payment/SNFPPS/PDPM
- FY 2024 SNF PPS Final Rule (CMI tied to PDPM nursing weights):  
  https://www.federalregister.gov/documents/2023/08/07/2023-16249/medicare-program-prospective-payment-system-and-consolidated-billing-for-skilled-nursing-facilities

## What “case-mix hours” means (CMS framing)

CMS does **not** present case-mix staffing as a separate clinical judgment label. In the Users Guide, **case-mix nurse staffing hours per resident day** are derived from:

1. Resident classification by **PDPM nursing component minute group (CMG)** from MDS data for days aligned with the PBJ reporting period.
2. **Daily CMG census** — counts in each of 25 PDPM nursing CMGs per facility per day.
3. **Facility nursing CMI** for the quarter (weighted by resident-days in each CMG).
4. **National weighted-average nursing CMI** for the same period.
5. **Relative nursing CMI ratio** = facility CMI ÷ national CMI.
6. **Case-mix HPRD** = facility nursing CMI ratio × national mean of reported hours per resident day (computed separately for RN, total nursing, weekends, etc., per Users Guide).

## Important CMS caveats

- **Terminology:** CMS states **“case-mix hours” replaced “expected hours”** in documentation after April 2019. Older literature may say “expected” where current CMS text says **case-mix hours**.
- **Historical exclusion:** For periods **before January 2022**, facilities with **total nurse staffing below 1.5 HPRD** were excluded from certain published calculations (per CMS documentation).
- **Not a legal minimum:** Case-mix hours are an acuity-adjusted **comparison benchmark**, not a state or federal staffing requirement unless a separate statute or regulation applies.

## How PBJ320 labels map to CMS

- **Reported** = facility-reported nursing HPRD from Provider Information for the matched quarter.
- **Case-mix** = CMS-published **case-mix nurse staffing hours per resident day** for that quarter (Users Guide terminology).
- **Adjusted** = CMS **adjusted** staffing where published on the same Provider Information row.
- **Nursing case-mix index (CMI)** = facility-level nursing CMI from Provider Information when present.

Quarter alignment between PBJ work quarters and Provider Information processing dates follows PBJ320’s data-matching methodology on the site.
