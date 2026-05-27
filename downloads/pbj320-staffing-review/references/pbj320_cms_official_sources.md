# CMS official sources cheat sheet (PBJ320-facing)

Anchors reviewers and counsel to **primary CMS** URLs. PDFs update; verify the edition date on downloads.

## Payroll-Based Journal (PBJ)

- **CMS PBJ landing** (datasets, specs, FAQs): https://www.cms.gov/medicare/quality/nursing-home-improvement/staffing-data-submission  
- **Daily staffing** dataset (catalog entry; API paths change): https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing  

Use for: what PBJ collects, exclusions, linkage to census/quarters, methodological caveats CMS publishes alongside the data.

## Provider Information · case-mix · Care Compare staffing fields

- **Nursing Home Provider Information** dataset: https://data.cms.gov/provider-data/dataset/4pq5-n9py  
- **Five-Star / Care Compare Technical Users’ Guide (PDF)** — case-mix hours, staffing fields, QM ties (same bundle PBJ320 cites for “expected” vs “case-mix” terminology evolution):  
  https://www.cms.gov/medicare/provider-enrollment-and-certification/certificationandcomplianc/downloads/usersguide.pdf  
- **Nursing Home Quality Initiatives** hub: https://www.cms.gov/medicare/quality-initiatives-patient-assessment-instruments/nursinghomequalityinits  

Use for: **reported vs case-mix vs adjusted staffing**, `% case-mix` style definitions, staffing star methodology context.

## Payment model context (why CMGs / CMI exist)

- **SNF PDPM**: https://www.cms.gov/Medicare/Medicare-Fee-for-Service-Payment/SNFPPS/PDPM  
- Example rule cross-reference for PDPM nursing weights tied to published CMI: **FY 2024 SNF PPS Final Rule** (Federal Register):  
  https://www.federalregister.gov/documents/2023/08/07/2023-16249/medicare-program-prospective-payment-system-and-consolidated-billing-for-skilled-nursing-facilities  

## State policy summary (non-CMS but common on PBJ320 charts)

- **MACPAC**: https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/  
  Detailed skill guidance: `references/pbj320_macpac_state_standards.md`.

## Depth already in this skill bundle

| Topic | File |
|--------|------|
| Case-mix hours & CMI formula outline | `references/pbj320_case_mix_cms.md` |
| Harrington vs CMS case-mix | `references/pbj320_harrington_vs_casemix.md` |
| Harrington formula (constants) | `references/pbj320_harrington_formula.md` |
| Interpretation traps | `references/pbj320_interpretation_rules.md` |

*Do not reproduce long excerpts from CMS PDFs inside model answers when a link + short paraphrase suffices; cite the controlling document for filings.*
