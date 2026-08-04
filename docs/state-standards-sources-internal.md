# State staffing standards — internal source dossier

_Generated: 2026-08-04_

Front page (`/state-standards`) stays clean: state name → `/state/{slug}`, estimated HPRD numbers only.
This document holds citations, source URLs, and cross-source discrepancies.

## Authoritative / primary sources

1. **MACPAC** — [State Policies Related to Nursing Facility Staffing](https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/) (March 2022 framing; workbook searched ~2021).
   - Workbook used this run: `State-Policies-Related-to-Nursing-Facility-Staffing.xlsx` (from Downloads / `--xlsx`)
2. **Consumer Voice** — Appendix B State Nursing Home Staffing Standards Chart (November 2021 (PDF cover)).
   - PDF used this run: `CV_StaffingReport_AppB_Chart.pdf` (from Downloads / `--pdf`)
3. **PBJ320 clean table** — `macpac_state_standards_clean.csv` (display / chart estimates; not silently overwritten by this enrichment).

Verified from: MACPAC Summary sheet totals match `macpac_state_standards_clean.csv` for all 51 jurisdictions (no numeric overwrite).

## Pipeline artifacts

- `data/state_standards/macpac_xlsx_extract.json` — per-state MACPAC categories, citations, URLs
- `data/state_standards/cv_appendix_b_extract.json` — CV PDF totals + citation lines
- `data/state_standards/state_standards_enriched.csv` / `.json` — joined view
- `data/state_standards/discrepancies.json` — machine-readable conflict list
- `data/state_standards/cv_appendix_b_extract_raw.txt` — raw PDF text

## Discrepancies (do not auto-resolve)

### `cv_missing_total` (3)

- **AK**: No CV Total Nursing Staff parsed; clean=0.38 HPRD
- **IN**: No CV Total Nursing Staff parsed; clean=0.56 HPRD
- **TX**: No CV Total Nursing Staff parsed; clean=0.46 HPRD

### `cv_vs_clean_value` (4)

- **ME**: CV Total Nursing Staff 2.99 vs clean 3.02 HPRD (min=3.02, max=3.02)
- **MT**: CV Total Nursing Staff 1.92 vs clean 1.90 HPRD (min=1.9, max=1.9)
- **OR**: CV Total Nursing Staff 2.35 vs clean 2.46 HPRD (min=2.46, max=2.46)
- **RI**: CV Total Nursing Staff 3.87 vs clean 3.64 HPRD (min=3.64, max=3.64) (CV year totals: {'2022': 3.64, '2023': 3.87})

## Notable interpretive notes

- MACPAC **federal floor ~0.30 HPRD** states often have **blank CV Total Nursing Staff** (ratio/coverage rules only). Clean CSV correctly flags `Is_Federal_Minimum`.
- **Ranges** in clean CSV (DC, IL, IA, KS, WI, WY) may correspond to facility-size / care-level bands in CV rather than a single total.
- **Phased standards** (e.g. CT, MA, RI) appear as year columns in CV; MACPAC Summary often uses the then-current / upcoming total.
- Source URLs and statute cites below are **as of MACPAC/CV research windows (~2021)** — always re-verify before compliance use.

## Per-state dossier

### Alabama (`AL`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - Alabama State Board of Health, Division of  Licensure and Certification, Administrative Code,  Chapter 420-5-10, § 11 Nursing Facilities, p. 50
  - (A) Alabama administrative code, Chapter 22: Nursing facility reimbursement, Rule No. 560-X-22-.06, Reimbursement methodology, pp. 8—12
  - (B) Alabama state plan amendment, attachment 4.19-D, p. 8
- MACPAC source URLs:
  - https://www.alabamapublichealth.gov/providerstandards/assets/nursingfacilitiesrules_amended_july302016.pdf
  - https://medicaid.alabama.gov/documents/9.0_Resources/9.2_Administrative_Code/9.2_Adm_Code_Chap_22_Nursing_Facility_Reimbursement.pdf
  - https://medicaid.alabama.gov/documents/9.0_Resources/9.8_State_Plan/9.8_A4.19-D_Methods_and_Procedures_for_Determining_Nursing_Facility_Reimbursement.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)AL Administrative Code
  - Ala. Admin. Code r. 420-5-10-.1 1
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Alaska (`AK`)

- Clean / front-page estimate: **0.38 HPRD**
- MACPAC Summary total: 0.38 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=Not found; DON=0.06 HPRD; LNs=0.32 HPRD; CNAs=Not found
- MACPAC citations:
  - (A) Alaska Administrative Code (AAC) tit. 7, § 12.275. Nursing and medical services
  - (B) AAC, tit. 7, § 12.670. Nursing service
  - (A) AAC tit. 7, § 12.275. Nursing and medical services
  - Alaska state plan amendment, attachment 4.19-D, pp. 3—4.
- MACPAC source URLs:
  - http://www.legis.state.ak.us/basis/aac.asp#7.12.275
  - http://www.legis.state.ak.us/basis/aac.asp#7.12.670
  - https://www.medicaid.gov/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/AR/AK-19-0005.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)AK Administrative Code
  - Alaska Admin. Code tit. 7 , § 12.275.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.38 HPRD
  - **RNs, LPNs, and CNAs combined**: Not found
  - **DON**: 0.06 HPRD
  - **LNs**: 0.32 HPRD
  - **CNAs**: Not found

### Arizona (`AZ`)

- Clean / front-page estimate: **0.54 HPRD**
- MACPAC Summary total: 0.54 HPRD
- CV Total Nursing Staff (parsed): 0.54
- MACPAC components: RN/LPN/CNA combined=0.48 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - Arizona Administrative Code (AAC), tit. 9, § R9-10-412. Nursing services, p. 88
  - AAC, tit. 9, § R9-10-412. Nursing services, p. 88
  - State of Arizona Executive Order 2020-17, Continuity of Work
- MACPAC source URLs:
  - https://apps.azsos.gov/public_services/Title_09/9-10.pdf
  - https://azgovernor.gov/sites/default/files/eo_2020-17_0.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)AZ Administrative Code
  - Ariz. Admin. Code § 9-10-412
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.54 HPRD
  - **RNs, LPNs, and CNAs combined**: 0.48 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### Arkansas (`AR`)

- Clean / front-page estimate: **3.42 HPRD**
- MACPAC Summary total: 3.42 HPRD
- CV Total Nursing Staff (parsed): 3.42
- MACPAC components: RN/LPN/CNA combined=3.36 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - Arkansas Code Annotated (ACA) § 20-10-1402. Staffing standards
  - Arkansas Rules and Regulations for Nursing Homes, Office of Long Term Care § 511.1
  - Arkansas Department of Human Services, Manual of cost reimbursement rules for long term care facilities, Payment method, Facility class, Nursing facilities, pp. 2-2—2-2a
  - Arkansas Department of Human Services, Guidance on long-term services and supports direct care payment
- MACPAC source URLs:
  - https://www.arkleg.state.ar.us/Acts/FTPDocument?path=%2FACTS%2F2021R%2FPublic%2F&file=715.pdf&ddBienniumSession=2021%2F2021R
  - https://www.sos.arkansas.gov/uploads/rulesRegs/Arkansas%20Register/2005/nov_2005/016.06.05-094F-8006.pdf
  - https://humanservices.arkansas.gov/divisions-shared-services/medical-services/helpful-information-for-providers/manuals/oltc-prov/
  - https://humanservices.arkansas.gov/wp-content/uploads/Guidance_on_LTSS_Direct_Care_Payments_final_4.16.20_.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)AR Rules for Nursing Homes
  - Arkansas Rules and Regulations
  - Term Care § 51 1.1:-514.
  - AR Statute
  - Act 175
  - Arkansas Code Annotated (ACA) §
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.42 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.36 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### California (`CA`)

- Clean / front-page estimate: **3.56 HPRD**
- MACPAC Summary total: 3.56 HPRD
- CV Total Nursing Staff (parsed): 3.56
- MACPAC components: RN/LPN/CNA combined=3.50 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=2.40 HPRD (of total)
- MACPAC citations:
  - California Code of Regulations (CCR) tit. 22 § 72329.2 Nursing Service—Staff
  - CCR tit. 22 § 72329.2 Nursing Service—Staff
  - California Welfare and Institutions Code (WIC), Division 9. Public Social Services, Part 3. Aid and Medical Assistance, Chapter 7. Basic Health Care, Article 3.8. Medi-Cal Long-Term Care Reimbursement Act § 14126.022
  - California state plan amendment, attachment 4.19-D, Supplement 4, p. 6
  - Assembly Bill No. 81, Chapter 13, Public health funding: health facilities and services
  - California WIC, Division 9. Public Social Services, Part 3. Aid and Medical Assistance, Chapter 7. Basic Health Care, Article 3. Administration, § 14110.6
  - Assembly Bill No. 650, Employer-provided benefits: health care workers: COVID-19: hazard pay retention bonuses, Part 4.6. Health Care Workers Recognition and Retention Act
  - California Executive Order N-39-20
- MACPAC source URLs:
  - https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1276.65&lawCode=HSC
  - https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=14126.022&lawCode=WIC
  - http://www.dhcs.ca.gov/formsandpubs/laws/Pages/Attachment419.aspx
  - https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=201920200AB81
  - https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?lawCode=WIC&division=9.&title=&part=3.&chapter=7.&article=3
  - https://leginfo.legislature.ca.gov/faces/billCompareClient.xhtml?bill_id=202120220AB650&showamends=false#
  - http://www.californiasimulationalliance.org/wp-content/uploads/2020/04/Governors-Executive-Order.3.4.20.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)CA Code of Regulations
  - Cal. Code Regs. tit. 22, § 72327
  - and § 72329.2.
  - CA Health and Safety Code
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.56 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.50 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: 2.40 HPRD (of total)

### Colorado (`CO`)

- Clean / front-page estimate: **2.06 HPRD**
- MACPAC Summary total: 2.06 HPRD
- CV Total Nursing Staff (parsed): 2.06
- MACPAC components: RN/LPN/CNA combined=2.0 HPRD; DON=0.06 HPRD; LNs=0.24 (of total); CNAs=Not found
- MACPAC citations:
  - (A) 6 Code of Colorado Regulations (CCR) 1011-1 Chapter 5, § 9.3 24-hour nursing coverage, p. 15
  - (B) 6 CCR 1011-1 Chapter 5, § 9.3 24-hour nursing coverage, p. 15
  - (A) 6 CCR 1011-1 Chapter 5, § 9.2 Director of nursing, p. 15
  - Colorado admin. code, tit. 10 CCR 2505-10 § 8.443.7.B, Class I health care state-wide maximum allowable per diem reimbursement rates (limit)
  - 10 CCR 2505-10 § 8.443.12 Pay-for-Performance (P4P) supplemental payment, p. 124
  - Informational memo number HCPF IM 20-019, State cross-agency guidance on flexibility in hiring and training staff for healthcare providers, pp. 3—4
- MACPAC source URLs:
  - https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=8836&fileName=6%20CCR%201011-1%20Chapter%2005
  - https://www.sos.state.co.us/CCR/DisplayRule.do?action=ruleinfo&ruleId=2921&deptID=7&agencyID=69&deptName=Department%20of%20Health%20Care%20Policy%20and%20Financing&agencyName=Medical%20Services%20Board%20(Volume%208;%20Medical%20Assistance,%20Children%27s%20Health%20Plan
  - https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=9540&fileName=10%20CCR%202505-10%208.400
  - https://www.colorado.gov/pacific/sites/default/files/HCPF%20IM%2020-019%20State%20Cross-Agency%20Guidance%20on%20Flexibility%20in%20Hiring%20and%20Training%20Staff%20for%20Healthcare%20Providers.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - Note: Medicaid Regulations : CO Department of Health Care Policy and
  - (DC + DON) or (CNA + LN)Code of CO Regulations
  - Colo. Code Regs. § 101 1-1 Chapter
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.0 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 (of total)
  - **CNAs**: Not found

### Connecticut (`CT`)

- Clean / front-page estimate: **3.06 HPRD**
- MACPAC Summary total: 3.06 HPRD
- CV Total Nursing Staff (parsed): 3.06
- CV year totals: `{"2021": 1.96, "2022": 3.06}`
- MACPAC components: RN/LPN/CNA combined=3.00 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - CT Senate Bill 1030, file 457, LCO No. 9032, Cal. No. 281. Sec. 10.(a) On or before January 1, 2022, the Department of Public Health shall (1) establish minimum staffing level requirements for nursing homes of three hours of direct care per resident per day.
  - Regulations of Connecticut State Agencies, tit. 19, § 19-13-D8t. Chronic and convalescent nursing homes and rest homes with nursing supervision
  - Connecticut general statutes, tit. 17, chapter 319y § 17b-340. Rates of payment to nursing homes, chronic disease hospitals associated with chronic and convalescent homes, rest homes with nursing supervision, residential care homes and residential facilities for persons with intellectual disability
  - (A) Medicaid Nursing Home Reimbursement, Public Health Emergency, March 2020 - 10% Medicaid Rate Increases Effective March 2020
  - (B) Medicaid Nursing Home Reimbursement, Public Health Emergency, February 2021 - COVID-19 Financial Supports Package
  - State of Connecticut Department of Public Health, Order regarding nurse aid training and employment
- MACPAC source URLs:
  - https://www.cga.ct.gov/2021/amd/S/pdf/2021SB-01030-R00SA-AMD.pdf
  - https://eregulations.ct.gov/eRegsPortal/Browse/RCSA/Title_19Subtitle_19-13Section_19-13-d8t/
  - https://www.cga.ct.gov/current/pub/chap_319y.htm#sec_17b-340
  - https://portal.ct.gov/DSS/Health-And-Home-Care/Medicaid-Nursing-Home-Reimbursement/Medicaid-Nursing-Home-Reimbursement/Public-Health-Emergency-Supports
  - https://portal.ct.gov/-/media/Coronavirus/20200904-DPH-order-regarding-nurse-aid-training-and-employment.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - Conn. Agencies Regs. § 19-13-D8t
  - CT Statute
  - Public Act No. 21.85.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### Delaware (`DE`)

- Clean / front-page estimate: **3.34 HPRD**
- MACPAC Summary total: 3.34 HPRD
- CV Total Nursing Staff (parsed): 3.34
- MACPAC components: RN/LPN/CNA combined=3.28 HPRD; DON=0.06 HPRD; LNs=1.20 HPRD (of total); CNAs=1.60 HPRD (of total)
- MACPAC citations:
  - Del. Code § 1162, Nursing Staffing
  - Delaware state plan amendment, attachment 4.19-D, pp. 4—6
  - (A) Joint Order of the Department of Health and Social Services and the Delaware Emergency Management Agency
  - (B) Governor Carney, Twelfth Modification of the Declaration of a State of Emergency for the State of Delaware due to a public health threat
- MACPAC source URLs:
  - http://delcode.delaware.gov/title16/title16.pdf
  - http://dhss.delaware.gov/dhss/dmma/state_plan.html
  - https://governor.delaware.gov/wp-content/uploads/sites/24/2021/08/Joint-Practice-Order-Joint-Order-of-the-Department-of-Health-and-Social-Services-and-the-Delaware-Emergency-Management-Agency-08122021.pdf
  - https://governor.delaware.gov/health-soe/twelfth-state-of-emergency/
- CV citation lines (OCR/text-extract; may need cleanup):
  - Note: 05/01/03 Regulations were not implemented because of funding: 1:15 LN ratio
  - Del. Code Ann. tit. 16, § 1 162
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.34 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.28 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 1.20 HPRD (of total)
  - **CNAs**: 1.60 HPRD (of total)

### District of Columbia (`DC`)

- Clean / front-page estimate: **3.56—4.16 HPRD**
- MACPAC Summary total: 3.56-4.16 HPRD
- CV Total Nursing Staff (parsed): 4.16
- MACPAC components: RN/LPN/CNA combined=3.50-4.10 HPRD; DON=0.06 HPRD; LNs=0.60 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Title 22B District of Columbia Municipal Regulations, Chapter 32. Nursing facilities, § 3211. Nursing personnel and required staffing levels, pp. 12—13
  - Title 22B District of Columbia Municipal Regulations, Chapter 32. Nursing facilities, §§ 3208. Nursing services and 3211. Nursing personnel and required staffing levels, pp. 9, 12
  - (A) District of Columbia state plan amendment, attachment 4.19-D, Part 1, pp. 3, 5—6
  - (B) District of Columbia Department of Health Care Finance, Notice of nursing facility peer group specific factors for the rate period beginning on February 1, 2018
  - Title 29 District of Columbia Municipal Regulations, Chapter 65. Medicaid reimbursement to nursing facilities, § 29-6526. NFQII performance scoring
  - Title 17 District of Columbia Municipal Regulations, Chapter 40. Health occupations: General rules, § 4020. Temporary waiver of licensure requirements for certain healthcare providers.
- MACPAC source URLs:
  - https://doh.dc.gov/sites/default/files/dc/sites/doh/publication/attachments/Nursing_Facility_Regulations_Health_Care_Facilities_Improvement_2012.pdf
  - https://dhcf.dc.gov/node/192472
  - https://dhcf.dc.gov/page/medicaid-reimbursement-nursing-facilities-participating-district-columbia-medicaid-program
  - https://www.dcregs.dc.gov/Common/DCMR/RuleDetail.aspx?RuleId=R0038867
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)DC Municipal Regulations
  - D.C. Mun. Regs. tit. 22, §§ 3208-
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.56—4.16 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.50—4.10 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.60 HPRD (of total)
  - **CNAs**: Not found

### Florida (`FL`)

- Clean / front-page estimate: **3.66 HPRD**
- MACPAC Summary total: 3.66 HPRD
- CV Total Nursing Staff (parsed): 3.66
- MACPAC components: RN/LPN/CNA combined=3.60 HPRD; DON=0.06 HPRD; LNs=1.00 HPRD (of total); CNAs=2.5 HPRD (of total)
- MACPAC citations:
  - Florida (FL)., Title XXIX Chapter 400 PART II Nursing Homes (ss. 400.011-400.334), 400.23 Rules; evaluation and deficiencies; licensure status (2020)
  - (A) FL., Title XXIX Chapter 400 PART II Nursing Homes (ss. 400.011-400.334), 400.23 Rules; evaluation and deficiencies; licensure status (2020)
  - (B) 59A-4.108 Nursing Services (2015)
  - FL., Title XXIX Chapter 400 PART II NURSING HOMES (ss. 400.011-400.334), 400.23 Rules; evaluation and deficiencies; licensure status (2020)
  - Title XXIX Chapter 400 PART II NURSING HOMES (ss. 400.011-400.334), 400.23 Rules; evaluation and deficiencies; licensure status
  - (A) Florida admin. code tit. XXX § 409.908 (2)(2018)
  - (B)  Florida state plan amendment, attachment 4.19-D, Part 1, III. Allowable costs, p. 22 (2017)
  - FLORIDA TITLE XIX LONG-TERM CARE REIMBURSEMENT PLAN, pp. 17—18 (2020)
  - State of Florida, Department of Health, Emergency Order #20-012, p. 1—4 (2020)
- MACPAC source URLs:
  - http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0400-0499/0400/Sections/0400.23.html
  - https://www.flrules.org/gateway/ruleNo.asp?id=59A-4.108
  - http://www.fdhc.state.fl.us/medicaid/Finance/finance/nh_rates/nhpprm.shtml
  - http://ahca.myflorida.com/medicaid/stateplan_attach.shtml
  - https://ahca.myflorida.com/medicaid/stateplanpdf/attachment_4-19-D.pdf
  - https://www.flhealthsource.gov/pdf/DOH-EO-20-012.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)FL Administrative Code
  - Fla. Admin. Code Ann. r.59A-
  - FL Statutes
  - Fla. Stat. § 400.23 (2021).
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.66 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.60 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 1.00 HPRD (of total)
  - **CNAs**: 2.5 HPRD (of total)

### Georgia (`GA`)

- Clean / front-page estimate: **2.06 HPRD**
- MACPAC Summary total: 2.06 HPRD
- CV Total Nursing Staff (parsed): 2.06
- MACPAC components: RN/LPN/CNA combined=2.00 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Georgia (GA). Comp. R. & Regs. R. 111-8-56-.04, Nursing Service
  - GA. Comp. R. & Regs. R. 111-8-56-.04, Nursing Service
  - GA. Division of Medicaid, Part II: Policies and procedures for nursing facility services, Section 1002.2 Total allowed per diem billing rate for facilities for which a cost report is used to set a billing rate, pp. X-7, X-9 (2019)
  - Policies and Procedures for Nursing Facility Services, 1002.4 Other Rate Adjustments (2007)
  - Georgia Health Care Association, COVID-19 Temporary nurse aide training program
- MACPAC source URLs:
  - http://rules.sos.state.ga.us/gac/111-8-56
  - https://www.mmis.georgia.gov/portal/Portals/0/StaticContent/Public/ALL/HANDBOOKS/Nursing%20Facility%20Services%20Policy%20Manual%20January%202022%2020211222132943.pdf
  - https://www.ghca.info/tna-program
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)GA Rules & Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Hawaii (`HI`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - Hawaii (HI)Administrative Rules, Chapter 94, Skilled Nursing/Intermediate Care Facilities § 321-9, 321-11
  - HI Administrative Rules, Chapter 94, Skilled Nursing/Intermediate Care Facilities § 321-9, 321-11
- MACPAC source URLs:
  - https://health.hawaii.gov/opppd/files/2015/06/11-94.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)HI Administrative Rules
  - Haw. Code R. § 1 1-94.1-39.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Idaho (`ID`)

- Clean / front-page estimate: **2.46 HPRD**
- MACPAC Summary total: 2.46 HPRD
- CV Total Nursing Staff (parsed): 2.46
- MACPAC components: RN/LPN/CNA combined=2.40 HPRD; DON=0.06 HPRD; LNs=0.24 (of total); CNAs=Not found
- MACPAC citations:
  - Idaho (ID) admin. code (2007), 16.03.02, § 200.02. Nursing services: Minimum staffing requirements, p. 27
  - ID admin. code (2007), 16.03.02, § 200.02. Nursing services: Minimum staffing requirements, p. 28
  - (A) ID admin. code (2021), 16.03.10 § 257, Nursing facility: Development of the rate, p. 50
  - (B) ID state plan amendment (2012), attachment 4.19-D, pp. 3—4
  - Idaho Division of Human Resources (2021), Statewide COVID-19 hazard pay policy, pp. 1—2
- MACPAC source URLs:
  - https://adminrules.idaho.gov/rules/current/16/160302.pdf
  - https://adminrules.idaho.gov/rules/current/index.html
  - https://www.medicaid.gov/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/ID/ID-12-011.pdf
  - https://dhr.idaho.gov/wp-content/uploads/2020/COVID-19/StatewideHazardPayPolicy1.29.2021-final.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)ID Administrative Rules
  - Idaho Admin. Code r.16.03.02.200.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.46 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.40 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 (of total)
  - **CNAs**: Not found

### Illinois (`IL`)

- Clean / front-page estimate: **2.56—3.86 HPRD**
- MACPAC Summary total: 2.56-3.86 HPRD
- CV Total Nursing Staff (parsed): 3.83
- MACPAC components: RN/LPN/CNA combined=2.50-3.80 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Illinois Compiled Statutes (ILCS), chp. 210, Act 45, § 3-202.05. Staffing ratios effective July 1, 2010 and thereafter
  - (A) ILCS, chp. 210, Act 45, § 3-202.05. Staffing ratios effective July 1, 2010 and thereafter
  - (B) Joint Committee on Administrative Rules,  Administrative Code, tit. 77, chp. Ic., § 300.1240. Additional requirements
  - IL Joint Committee on Administrative Rules,  Administrative Code, tit. 77, chp. Ic., § 300.1240. Additional requirements
  - ILCS, chp. 210, Act 45, § 3-202.05. Staffing ratios effective July 1, 2010 and thereafter
  - Illinois nursing home rate calculation handbook, p. 3
  - IL Joint Committee on Administrative Rules,  Administrative Code, tit. 89, chp. Id., § 147.345. Quality incentives
- MACPAC source URLs:
  - https://www.ilga.gov/legislation/ilcs/ilcs4.asp?DocName=021000450HArt%2E+III&ActID=1225&ChapterID=21&SeqStart=8500000&SeqEnd=25200000
  - https://www.ilga.gov/commission/jcar/admincode/077/077003000F12400R.html
  - https://www.illinois.gov/hfs/MedicalProviders/MedicaidReimbursement/Pages/LTC.aspx
  - https://www.ilga.gov/commission/jcar/admincode/089/089001470003450R.html
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)IL Administrative Code
  - Ill. Admin. Code tit. 77 , §§
  - IL Statute
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.56—3.86 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.50—3.80 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Indiana (`IN`)

- Clean / front-page estimate: **0.56 HPRD**
- MACPAC Summary total: 0.56 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=Not found; DON=0.06 HPRD; LNs=0.50 HPRD; CNAs=Not found
- MACPAC citations:
  - Indiana Administrative Code (IAC), tit. 410, art. 16.2, § 3.1-17. Nursing services
  - IAC, tit. 410, art. 16.2, § 3.1-17. Nursing services
  - Indiana state plan amendment, attachment 4.19D, p. 29
  - Indiana state plan amendment, attachment 4.19D, p. 25
  - (A) Indiana Department of Health, Emergency Order authorizing temporary personal care attendant positions and training for nursing homes
  - (B) Indiana Department of Health, Third Emergency Order concerning temporary  personal care attendants for nursing homes
  - (C) State of Indiana, Nineteenth renewal of the public health emergency declaration for the COVID-19 outbreak
- MACPAC source URLs:
  - http://iac.iga.in.gov/iac/iac_title?iact=410
  - http://provider.indianamedicaid.com/ihcp/StatePlan/state_plan.asp
  - https://www.coronavirus.in.gov/files/B%20-%20CCF%20PCA%20Order%20Full%20Signed.pdf
  - https://www.coronavirus.in.gov/files/X%20-%20CCF%20PCA%20Order%20AMENDMENT%20%232%20-%20Final%20Signed.pdf
  - https://www.in.gov/gov/files/Executive-Order-21-26-Nineteenth-Renewal-of-Emergency-Declaration.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)IN Administrative Code
  - Title 410, Art. 16.2, Sec. 3.1-17.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.56 HPRD
  - **RNs, LPNs, and CNAs combined**: Not found
  - **DON**: 0.06 HPRD
  - **LNs**: 0.50 HPRD
  - **CNAs**: Not found

### Iowa (`IA`)

- Clean / front-page estimate: **1.76—2.06 HPRD**
- MACPAC Summary total: 1.76-2.06 HPRD
- CV Total Nursing Staff (parsed): 2.06
- MACPAC components: RN/LPN/CNA combined=1.70-2.00 HPRD; DON=0.06 HPRD; LNs=0.34-0.40 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - (A) Iowa admin code (IAC), tit. 441, § 81.13(11). Nursing services, pp.14—15
  - (B) IAC,  tit. 481, § 58.11(2). Nursing supervision and staffing, p. 2
  - (A) IAC, tit. 441, § 81.13(11). Nursing services, pp.14—15
  - (B) IAC (2021),  tit. 481, § 58.11(2). Nursing supervision and staffing, p. 2
  - Iowa Department of Human Services (2014), Nursing facility—provider manual, Chapter III. § I.1, Basis of payment, Rate determination, pp. 71, 75
  - 441—81.6 (249A) Financial and statistical report and determination of payment rate, Ch. 81, p. 1
  - IAC (2019),  tit. 481, § 36.7(1). Determination and payment of assessment, p. 1
- MACPAC source URLs:
  - https://www.legis.iowa.gov/docs/iac/rule/07-28-2021.441.81.13.pdf
  - https://www.legis.iowa.gov/docs/iac/rule/06-16-2021.481.58.11.pdf
  - https://dhs.iowa.gov/policy-manuals/medicaid-provider
  - https://www.legis.iowa.gov/docs/iac/rule/01-07-2015.441.81.6.pdf
  - https://www.legis.iowa.gov/docs/iac/rule/11-30-2011.441.36.7.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)IA Administrative Code
  - Iowa Admin. Code r. 481-58.1 1.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 1.76—2.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 1.70—2.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.34—0.40 HPRD (of total)
  - **CNAs**: Not found

### Kansas (`KS`)

- Clean / front-page estimate: **1.91—2.06 HPRD**
- MACPAC Summary total: 1.91-2.06 HPRD
- CV Total Nursing Staff (parsed): 2.06
- MACPAC components: RN/LPN/CNA combined=1.85-2.00 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Kansas Department for Aging and Disability Services (KDADS), Statutes and Regulations for the Licensure and Operation of Nursing Facilities, § 29-39-154. Nursing Services
  - KDADS, Statutes and Regulations for the Licensure and Operation of Nursing Facilities, § 29-39-154. Nursing Services
  - (A) Kansas state plan amendment, attachment 4.19-D, Part 1, Subpart C, Exhibit C-1, pp. 9—10 of 19
  - (B) Kansas admin. regulation § 129-10-18, Per diem rates of reimbursement
  - Kansas Office of Revisor of Statutes, Chapter 39, § 971
  - Kansas Legislature, Session of 2021, Senate Bill 289, Committee on Ways and Means
  - Kansas Executive Order 20-56, Amended Licensure, Certification, and Registration for persons and Licensure of "Adult Care Homes" during state of disaster emergency
- MACPAC source URLs:
  - https://kdads.ks.gov/docs/librariesprovider17/general-provider-pages/provider-statutes-and-regulations/ksa-and-kar-for-adult-care-homes/nursing-facilities-2015.pdf?sfvrsn=cd9a3dee_2
  - https://www.medicaid.gov/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/KS/KS-16-014.pdf
  - https://www.kssos.org/pubs/pubs_kar.aspx
  - https://www.ksrevisor.org/statutes/chapters/ch39/039_009_0071.html
  - http://www.kslegislature.org/li/b2021_22/measures/documents/sb289_00_0000.pdf
  - https://governor.kansas.gov/wp-content/uploads/2020/07/EO-20-56-Executed.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)KS Administrative Regulations
  - Kan. Admin. Regs. § 28-39-154.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 1.91—2.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 1.85—2.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Kentucky (`KY`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - Kentucky admin rules (KAR) 20:048, § 902 . Operation and services; nursing homes
- MACPAC source URLs:
  - https://apps.legislature.ky.gov/law/kar/902/020/048.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)KY Administrative Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Louisiana (`LA`)

- Clean / front-page estimate: **2.41 HPRD**
- MACPAC Summary total: 2.41 HPRD
- CV Total Nursing Staff (parsed): 2.41
- MACPAC components: RN/LPN/CNA combined=2.35 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Louisiana Administrative Code (LAC), Title 48, Part 1, Chapter 97. Nursing Facilities. Subchapter A. General Provisions, §9823. Nursing Service Personnel
  - LAC, Title 48, Part 1, Chapter 97. Nursing Facilities. Subchapter A. General Provisions, §9823. Nursing Service Personnel
  - Louisiana Revised Statutes - Title 46, Section 2691, Chapter 54, §2691. Medicaid Trust Fund for the Elderly
- MACPAC source URLs:
  - https://ldh.la.gov/assets/medicaid/hss/docs/NH/Standards_for_Payment_NF_LAC50_052020.pdf
  - http://legis.la.gov/legis/Law.aspx?d=100787
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)LA Administrative Code
  - La. Admin. Code Title 48, §§ 9821,
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.41 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.35 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Maine (`ME`)

- Clean / front-page estimate: **3.02 HPRD**
- MACPAC Summary total: 3.02 HPRD
- CV Total Nursing Staff (parsed): 2.99
- MACPAC components: RN/LPN/CNA combined=2.96 HPRD; DON=0.06 HPRD; LNs=0.32 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Maine, Dept. of the Secretary of State, 10-144 Department of Health and Human Services Chapter 110, Chapter 9, Resident Care Staffing
  - (A) State of Maine, H.P. 1170, Legislative Document 1573, 130th Maine Legislature, First Special Session
  - (B) H.P. 156 - L.D. 221, An Act Making Unified Appropriations and Allocations for the Expenditures of State Government, General Fund and Other Funds and Changing Certain Provisions of the Law Necessary to the Proper Operations of State Government for the Fiscal Years Ending June 30, 2021, June 30, 2022 and June 30, 2023;
  - Maine Department of Health and Human Services, MaineCare benefits manual, Chapter III—Section 67: Principles of reimbursement for nursing facilities, Section 22.3.3, Base year direct cost component
  - Maine Department of Health and Human Services, MaineCare benefits manual, Chapter III—Section 67: Principles of reimbursement for nursing facilities, Section 43, Special wage allowance
  - (A) Maine Dept of Health and Human Services, Admin Bulletin, Temporary Rate Increase Guidance for MaineCare Providers
  - (B) Maine Dept of Economic and Community Development, Maine Health Care Financial Relief Grant Program
  - (C) 130th Maine Legislature, First regular session-2021, H.P. 156, An Act Making Unified Appropriations and Allocations for the Expenditures of State Government, General Fund and Other Funds and Changing Certain Provisions of the Law Necessary to the Proper Operations of State Government for the Fiscal Years Ending June 30, 2021, June 30, 2022 and June 30, 2023
  - Maine, Dept. of the Secretary of State, 10-144 Department of Health and Human Services Chapter 110, Chapter 8, Personnel
- MACPAC source URLs:
  - https://www.maine.gov/sos/cec/rules/10/ch110.htm
  - http://legislature.maine.gov/legis/bills/getPDF.asp?paper=HP1170&item=1&snum=130
  - http://www.mainelegislature.org/legis/bills/getPDF.asp?paper=HP0156&item=7&snum=130
  - http://www.maine.gov/sos/cec/rules/10/ch101.htm
  - https://content.govdelivery.com/accounts/MEHHS/bulletins/28970d8
  - https://www.maine.gov/decd/sites/maine.gov.decd/files/inline-files/Maine%20Health%20Care%20Financial%20Relief%20Grant%20FAQs%20v3.pdf
  - http://www.mainelegislature.org/legis/bills/getPDF.asp?paper=HP0156&item=1&snum=130
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)Code of ME Rules
  - 10-144-1 10 Me. Code R. § 9.A
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.02 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.96 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.32 HPRD (of total)
  - **CNAs**: Not found

### Maryland (`MD`)

- Clean / front-page estimate: **3.06 HPRD**
- MACPAC Summary total: 3.06 HPRD
- CV Total Nursing Staff (parsed): 3.06
- MACPAC components: RN/LPN/CNA combined=3.00 HRPD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Maryland (MD)10.07.02.19 Nursing Services — Staffing. (2019)
  - MD 10.07.02 Comprehensive Care Facilities and Extended Care Facilities] Nursing Homes (2019)
  - MD 10.07.02.19 Nursing Services — Staffing. (2019)
  - 10.09.10.15 Pay-for-Performance — Quality Measures. (2021)
- MACPAC source URLs:
  - http://www.dsd.state.md.us/comar/comarhtml/10/10.07.02.19.htm
  - https://health.maryland.gov/regs/Pages/10-07-02-Nursing-Homes-(Office-of-Health-Care-Quality
  - http://www.dsd.state.md.us/comar/comarhtml/10/10.09.10.15.htm
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)Code of MD Regulations
  - Code of MD Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.00 HRPD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Massachusetts (`MA`)

- Clean / front-page estimate: **3.64 HPRD**
- MACPAC Summary total: 3.64 HPRD
- CV Total Nursing Staff (parsed): 3.64
- MACPAC components: RN/LPN/CNA combined=3.58 HPRD; DON=0.06 HPRD; LNs=0.51 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Massachusetts (MA) 101 CMR §105.07, Nursing services, p. 22
  - MA 101 CMR §105.07, Nursing services, p. 22
  - MA 101 CMR §206.06, Adjustments to standard nursing facility rates, p. 408
  - (A) MA 101 CMR §411.03, Rate provisions, p. 8
  - (B) Massachusetts, Bill H.4000, 191st House (2019-2020)
  - Commonwealth of MA, Executive Office of Health and Human Services, Assistant Secretary for Administration and Finance , Resident Care Facility Bulletin 34, COVID-19 Signing Bonuses for Resident Care Facility Staff
- MACPAC source URLs:
  - https://www.mass.gov/doc/105-cmr-150-standards-for-long-term-care-facilities/download
  - https://www.mass.gov/doc/101-cmr-206-standard-payments-to-nursing-facilities/download
  - https://www.mass.gov/doc/101-cmr-411-rates-for-certain-placement-support-and-shared-living-services/download
  - https://malegislature.gov/Bills/191/H4000
  - https://www.mass.gov/doc/resident-care-facility-bulletin-34-covid-19-signing-bonuses-for-resident-care-facility-staff/download
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)Code of MA Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.64 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.58 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.51 HPRD (of total)
  - **CNAs**: Not found

### Michigan (`MI`)

- Clean / front-page estimate: **2.31 HPRD**
- MACPAC Summary total: 2.31 HPRD
- CV Total Nursing Staff (parsed): 2.31
- MACPAC components: RN/LPN/CNA combined=2.25 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Michigan (MI) Public Health Code (EXCERPT) § 333.217a. Director of nursing; nursing personnel; effective date of subsection (1); natural disaster or other emergency
  - MI Public Health Code (EXCERPT) § 333.217a. Director of nursing; nursing personnel; effective date of subsection (1); natural disaster or other emergency.
  - MI Department of Health and Human Services Medicaid provider manual, Nursing Facility, Cost reporting & reimbursement Appendix
  - MI state plan amendment, attachment 4.19-D, Section IV, pp. 28—29
  - 2017-18 MI Health and Human Services Budget
  - MI, Supplemental to Public Act 123 of 2020. S.B. 2019-SFA-0690, Sec. 401
- MACPAC source URLs:
  - http://www.legislature.mi.gov/(S(fccuprm15ezvk2tuhmcwdcnb
  - https://www.mdch.state.mi.us/dch-medicaid/manuals/MedicaidProviderManual.pdf
  - https://www.mdch.state.mi.us/dch-medicaid/manuals/MichiganStatePlan/MichiganStatePlan.pdf
  - https://www.legislature.mi.gov/documents/2017-2018/billanalysis/Senate/pdf/2017-SFA-4238-R.pdf
  - https://www.legislature.mi.gov/documents/2019-2020/billanalysis/Senate/pdf/2019-SFA-0690-N.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - Mich. Comp. Laws § 333.21720a.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.31 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.25 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Minnesota (`MN`)

- Clean / front-page estimate: **2.06 HPRD**
- MACPAC Summary total: 2.06 HPRD
- CV Total Nursing Staff (parsed): 2.06
- MACPAC components: RN/LPN/CNA combined=2.00 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - Minnesota Admin Code (MAC), §4658.0510 Nursing Personnel
  - MAC, §4658.0500 Director of Nursing Services
  - MN (2020) §144A.04, Qualifications for license
  - Minnesota state plan amendment, attachment 4.19-D, pp. 176, 183—184
  - MN Nursing Facility Payment Reform
- MACPAC source URLs:
  - https://www.revisor.mn.gov/rules/4658.0510/
  - https://www.revisor.mn.gov/rules/4658.0500/
  - https://www.revisor.mn.gov/statutes/cite/144A.04
  - https://mn.gov/dhs/assets/17-16-spa_tcm1053-322728.pdf
  - https://mn.gov/dhs/assets/2017-03-nursing-facility-payment-reform_tcm1053-286209.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)MN Administrative Rules
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### Mississippi (`MS`)

- Clean / front-page estimate: **2.86 HPRD**
- MACPAC Summary total: 2.86 HPRD
- CV Total Nursing Staff (parsed): 2.86
- MACPAC components: RN/LPN/CNA combined=2.80 HPRD; DON=0.06 HPRD; LNs=0.40 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Miss. Code Ann. §43-11-13, p. 10 (2019)
  - Mississippi state plan amendment, attachment 4.19-D, § 3-4 Computation of Standard Per Diem Rate for Nursing Facilities, pp. 99, 101 (2018)
- MACPAC source URLs:
  - http://www.msdh.state.ms.us/msdhsite/_static/resources/119.pdf
  - https://medicaid.ms.gov/wp-content/uploads/2020/09/Attachment_4.19-D-Searchable-09.01.20.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)MS Administrative Code
  - MS Admin Code, Title 15, Part 16,
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.86 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.80 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.40 HPRD (of total)
  - **CNAs**: Not found

### Missouri (`MO`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - 19 CSR 30-85.042 Administration and Resident Care Requirements for New and Existing Intermediate Care and Skilled Nursing Facilities, p. 18 (2004)
  - Missouri admin. code, tit. 13 § 70-10.015, Prospective reimbursement plan for nursing facility services, p. 45 (2016)
- MACPAC source URLs:
  - https://s1.sos.mo.gov/cmsimages/adrules/csr/current/19csr/19c30-85.pdf
  - https://www.sos.mo.gov/CMSImages/AdRules/csr/current/13csr/13c70-10a.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)MO Code of State Regulations
  - Mo. Code of State Regulations. 19
  - CSR 30-85.042.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Montana (`MT`)

- Clean / front-page estimate: **1.90 HPRD**
- MACPAC Summary total: 1.90 HPRD
- CV Total Nursing Staff (parsed): 1.92
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.64 HPRD; CNAs=1.20 HPRD
- MACPAC citations:
  - Administrative Rules of Montana (MT), Public Health and Human Services, Senior and long term services, Rule 37.40.315  Staffing and reporting requirements
  - Administrative Rules of MT, Public Health and Human Services, health Care Facilities, Rule 37.106.605, Minimum Standards for a Skilled Nursing Care Facility for each 24 Hour Period: Staffing
  - MT Code Annotated 2019, Title 15. Taxation, Chapter 60. Nursing Facility Utilization Fee, Part 2. Collection of Fee. Section 15-60-211. State Special Revenue Account
  - Madison County Board of Commissioners, Resolution 8-2021, A Resolution to Continue Hazard Pay to Nursing Home Employees Due to the COVID-19 Pandemic.
- MACPAC source URLs:
  - https://rules.mt.gov/gateway/ruleno.asp?RN=37%2E106%2E605
  - https://leg.mt.gov/bills/mca/title_0150/chapter_0600/part_0020/section_0110/0150-0600-0020-0110.html
  - https://www.madisoncountymt.gov/ArchiveCenter/ViewFile/Item/1753
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)Administrative Rules of MT
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 1.90 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.64 HPRD
  - **CNAs**: 1.20 HPRD

### Nebraska (`NE`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - Nebraska Health and Human Services, Regulation and Licensure, Title 175, Chapter 12, § 12-006.04C Nursing Staff Resources and Responsibilities
  - Nebraska state plan, attachment 4.19-D, Methods and standards for establishing payment rates - skilled nursing and intermediate care facility services, pp. 11–14
- MACPAC source URLs:
  - https://www.nebraska.gov/rules-and-regs/regsearch/Rules/Health_and_Human_Services_System/Title-175/Chapter-12.pdf
  - https://dhhs.ne.gov/Pages/Medicaid-State-Plan.aspx#SectionLink7
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NE Agency Rules for Health and
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Nevada (`NV`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - Nevada Admin. Code (NAC), Chapter 449 - Medical Facilities and Other Related Entities, §§ 74517 and 74519
  - NAC, Chapter 449 - Medical Facilities and Other Related Entities, §§ 74517 and 74519
- MACPAC source URLs:
  - https://www.leg.state.nv.us/NAC/NAC-449.html#NAC449Sec74517
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NV Administrative Code
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### New Hampshire (`NH`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - New Hampshire Code of Administrative Rules, Chapter He-P 800, Part HeP 803, New Hampshire Nursing Home Rules
  - New Hampshire admin. rules, tit. He-E § 806.31
  - State of New Hampshire, Office of the Governor, Emergency Order #45, Modification of Emergency Order #31 (Establishment of the COVID-19 Long Term Care Stabilization Program)
  - (A)State of New Hampshire, Office of the Governor, Emergency Order #42, Authorizing Temporary Health Partners to Assist in Responding to the COVID-19 in Long Term Care Facilities
  - (B)State of New Hampshire, Office of the Governor, Emergency Order #75, An Order Authorizing Certain Nursing Students to Obtain Temporary Licensure
  - (C)State of New Hampshire, Office of the Governor, Emergency Order #78, An Order Authorizing Certain Military Service Members and Emergency Medical Technicians to Obtain Temporary Licensure as a Licensed Nursing Assistant
- MACPAC source URLs:
  - https://www.dhhs.nh.gov/oos/bhfa/documents/he-p803.pdf
  - http://www.gencourt.state.nh.us/rules/about_rules/listagencies.aspx
  - https://www.governor.nh.gov/sites/g/files/ehbemt336/files/documents/emergency-order-45.pdf
  - https://sos.nh.gov/media/xd0lxftr/sununu-2020-04-42.pdf
  - https://sos.nh.gov/media/vval2gci/sununu-2020-75.pdf
  - https://sos.nh.gov/media/cplhdld0/sununu-2020-04-78.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NH Code of Administrative Rules
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### New Jersey (`NJ`)

- Clean / front-page estimate: **2.56 HPRD**
- MACPAC Summary total: 2.56 HPRD
- CV Total Nursing Staff (parsed): 2.56
- MACPAC components: RN/LPN/CNA combined=2.50 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=1.04 HPRD (of total)
- MACPAC citations:
  - (A) State of New Jersey, Senate Budget and Appropriations Committee. Senate, No. 4482
  - (B) New Jersey Administrative Code (N.J.A.C.) Standards for Licensure of Long-term Care Facilities, tit. 8, ch. 8, § 8:39-25.1 and 8:39-25.2 Mandatory policies and procedures for nurse staffing and Mandatory nurse staffing amounts and availability
  - N.J.A.C Standards for Licensure of Long-term Care Facilities, tit. 8, ch. 8, § 8:39-25.1 Mandatory policies and procedures for nurse staffing
  - State of New Jersey, Senate Budget and Appropriations Committee. Senate, No. 2712
  - State of New Jersey, Assembly, No. 4482, 219th Legislature
  - New Jersey state plan amendment, attachment 4.19-D, pp. 7, 11
  - New Jersey state plan amendment, attachment 4.19-D, p. 191.14
  - (A) Title 26. Chapter 2H. V - Nursing Home Quality of Care Improvement Fund. §§1-10 - C.26:2H-92 to 26:2H-101 §11 - Note
  - ftp://www.njleg.state.nj.us/20022003/AL03/105_.PDF
  - (B) State of New Jersey, Assembly, No. 4482, 219th Legislature
  - Executive Directive NO: 20-004, Authorization for Long-Term Care Facilities to Hire Out-of-State Certified Nurse Aides
- MACPAC source URLs:
  - https://www.njleg.state.nj.us/2020/Bills/S3000/2712_S2.PDF
  - https://www.pharmacareinc.com/files/201711_NJAC_8_39_Long-Term_Care_Facilities.pdf
  - https://www.njleg.state.nj.us/2020/Bills/A4500/4482_R2.PDF
  - https://www.medicaid.gov/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/CT/CT-17-0025.pdf
  - https://www.medicaid.gov/sites/default/files/State-resource-center/Medicaid-State-Plan-Amendments/Downloads/NJ/NJ-09-08-Att.pdf
  - https://www.nj.gov/health/legal/covid19/4-14-2020_NurseAideTempCert_Waiver.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NJ Administrative Code
  - NJ Adm Code Title 8, Ch. 39,
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.56 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.50 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: 1.04 HPRD (of total)

### New Mexico (`NM`)

- Clean / front-page estimate: **2.56 HPRD**
- MACPAC Summary total: 2.56 HPRD
- CV Total Nursing Staff (parsed): 2.56
- MACPAC components: RN/LPN/CNA combined=2.50 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - New Mexico Administrative Code (NMAC), tit. 7, Chapter 9, Part 2, Requirements for Long Term Care Facilities §7.9.2.50 & 7.9.51 Nursing Services
  - NMAC. code, tit. 7, Chapter 9, Part 2, Requirements for Long Term Care Facilities §7.9.2.50 & 7.9.51 Nursing Services
  - NMAC code, tit. 7, Chapter 9, Part 2, Requirements for Long Term Care Facilities §7.9.2.50 & 7.9.51 Nursing Services
  - (A) NMAC, tit. 8 § 312.3.11, p. 4
  - (B) NMAC, tit. 8 § 312.3.13, p. 7
- MACPAC source URLs:
  - https://www.srca.nm.gov/parts/title07/07.009.0002.html
  - https://www.srca.nm.gov/parts/title08/08.312.0003.html
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NM Administrative Code
  - NM Adm Code Title 7 , Chapter 9,
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.56 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.50 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### New York (`NY`)

- Clean / front-page estimate: **3.56 HPRD**
- MACPAC Summary total: 3.56 HPRD
- CV Total Nursing Staff (parsed): 3.56
- CV year totals: `{"2022": 3.56, "2023": 3.56}`
- MACPAC components: RN/LPN/CNA combined=3.50 HPRD; DON=0.06 HPRD; LNs=1.1 HPRD (of total); CNAs=2.20 HPRD (of total)
- MACPAC citations:
  - New York (NY) Public Health Law, Article 28d, § 2895-b.  Nursing home staffing levels
  - (A) NY Codes, Rules and Regulations, Tit. 10, Chapter 5, Article 3, §415.13 - Nursing services
  - (B) NY Public Health Law, Article 28d, § 2895-b.  Nursing  home  staffing levels
  - NY Public Health Law, Article 28d, § 2895-b.  Nursing  home  staffing levels
  - (A) State of NY: Executive Order (EO) No. 202.18
  - (B) State of NY, EO No. 210
- MACPAC source URLs:
  - https://nyassembly.gov/leg/?default_fld=&leg_video=&bn=S06346&term=2021&Summary=Y&Actions=Y&Committee%26nbspVotes=Y&Floor%26nbspVotes=Y&Memo=Y&Text=Y
  - https://regs.health.ny.gov/content/section-41513-nursing-services
  - https://www.governor.ny.gov/sites/default/files/atoms/files/EO_202.18.pdf
  - https://www.governor.ny.gov/news/no-210-expiration-executive-orders-202-and-205
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NY Code Revised Regulations
  - Title 10 Health, Sec. 415.13.
  - Statute A07119
  - Article 28d, § 2895-b. Nursing
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.56 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.50 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 1.1 HPRD (of total)
  - **CNAs**: 2.20 HPRD (of total)

### North Carolina (`NC`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=No HPRD described
- MACPAC citations:
  - North Carolina Administrative Code (NCAC), tit. 10A, Chapter 13D, §.2303. Nurse Staffing Requirements
  - NCAC, tit. 10A, Chapter 13D, §.2303. Nurse Staffing Requirements
  - NCAC, tit. 10A, Chapter 13D, §.2304. Nurse Aides
  - NC State Plan Amendment, attachment 4.19-D, pp. 2–3
- MACPAC source URLs:
  - http://reports.oah.state.nc.us/ncac.asp?folderName=\Title%2010A%20-%20Health%20and%20Human%20Services\Chapter%2013%20-%20NC%20Medical%20Care%20Commission
  - https://medicaid.ncdhhs.gov/get-involved/nc-health-choice-state-plan
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)NC Administrative Code
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: No HPRD described

### North Dakota (`ND`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - North Dakota (ND), Chapter 33-07-03.2
  - Nursing facilities, 33-07-03.2-14. Nursing services, p. 10
  - ND Chapter 33-07-03.2
  - ND, Chapter 33-07-03.2
  - ND Department of Human Services, Nursing facility rate manual, pp. 14, 38
- MACPAC source URLs:
  - https://www.legis.nd.gov/information/acdata/pdf/33-07-03.2.pdf
  - https://www.nd.gov/dhs/services/medicalserv/medicaid/provider-all.html
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)ND Administrative Code
  - ND Admin. Code 33-07-03.2-14.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Ohio (`OH`)

- Clean / front-page estimate: **2.56 HPRD**
- MACPAC Summary total: 2.56 HPRD
- CV Total Nursing Staff (parsed): 2.56
- MACPAC components: RN/LPN/CNA combined=2.50 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - Ohio Revised Code (OHRC), tit. 37, § 3721. Adoption and publication of uniform rules governing operation of homes
  - OHRC, tit. 37, Rule 3701-17-08. Personnel requirements
  - OHRC, tit. 51, § 5165.26. Nursing facility's per Medicaid day quality incentive payment rate
- MACPAC source URLs:
  - https://codes.ohio.gov/ohio-revised-code/section-3721.04
  - https://codes.ohio.gov/ohio-administrative-code/rule-3701-17-08
  - https://codes.ohio.gov/ohio-revised-code/section-5165.26/6-19-2020
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)OH Administrative Code
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.56 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.50 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### Oklahoma (`OK`)

- Clean / front-page estimate: **2.92 HPRD**
- MACPAC Summary total: 2.92 HPRD
- CV Total Nursing Staff (parsed): 2.92
- MACPAC components: RN/LPN/CNA combined=2.86 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - Oklahoma (OK) Nursing Home Care Act, 63 O.S. § 1-1925.2, pp. 54—55
  - Title 310,  OK State Department of Health, Chp. 675 Nursing and Specialized Facilities, Sub-chp. 13. Staff requirements, § 5. Nursing service, p. 75
  - OK Nursing Home Care Act, 63 O.S. § 1-1914.1, p. 20 (2017)
  - (A) OK state plan amendment, attachment 4.19-D, pp. 3—4 (2018)
  - (B) OK Health Care Authority, Long term care facility rate setting methodology summary, p. 1 (2015)
- MACPAC source URLs:
  - https://oklahoma.gov/content/dam/ok/en/health/health2/documents/675-nhca.pdf
  - https://oklahoma.gov/content/dam/ok/en/health/health2/documents/675.pdf
  - http://www.okhca.org/about.aspx?id=19741
  - https://oklahoma.gov/content/dam/ok/en/okhca/documents/a0401/24891.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)OK Administrative Code
  - Okla. Admin. Code § 310:675-13-5.
  - OK Statute
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.92 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.86 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### Oregon (`OR`)

- Clean / front-page estimate: **2.46 HPRD**
- MACPAC Summary total: 2.46 HPRD
- CV Total Nursing Staff (parsed): 2.35
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=2.16 HPRD
- MACPAC citations:
  - Oregon Department of Human Services (ODHS), Chapter 411, Division 86, §0100: Nursing Services: Staffing
  - ODHS, Chapter 411, Division 86, §0200: Director of Nursing Services (DNS)
  - ODHS, Chapter 411, Division 86, §0100: Nursing Services: Staffing
  - ODHS, Announcement of Coved incentive payments
- MACPAC source URLs:
  - https://secure.sos.state.or.us/oard/viewSingleRule.action?ruleVrsnRsn=280568
  - https://secure.sos.state.or.us/oard/displayDivisionRules.action;JSESSIONID_OARD=-vYGWxl3CuRsOEIiltTkYPIXctUx90fqYzDEPk9woEQrC_Z9JcaM!-888754201?selectedDivision=1790
  - https://www.oregon.gov/DHS/PROVIDERS-PARTNERS/LICENSING/AdminAlerts/NF-20-83%20-%20NF%20Announcement%20of%20Incentive%20Payments%2005182020.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)OR Administrative Rules
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.46 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: 2.16 HPRD

### Pennsylvania (`PA`)

- Clean / front-page estimate: **2.76 HPRD**
- MACPAC Summary total: 2.76 HPRD
- CV Total Nursing Staff (parsed): 2.76
- MACPAC components: RN/LPN/CNA combined=2.70 HRPD; DON=0.06 HPRD; LNs=0.24 (of total); CNAs=Not found
- MACPAC citations:
  - Pennsylvania Code (Pa. Code) § 211.12. Nursing services. (1999)
  - Pa. Code § 211.12. Nursing services. (1999)
  - Pa. Code, § 1187.51 (2010)
  - (A) PA General Assembly, 2020 Act 2A, COVID-19 Emergency Supplement T0 The General Appropriation Act OF 2019 - Enactment. (2020)
  - (B) PA Dept of Community and Economic Development, OCVID-19 PA Hazard Pay Grant, Program Guidelines (2020)
- MACPAC source URLs:
  - http://www.pacodeandbulletin.gov/Display/pacode?file=/secure/pacode/data/028/chapter211/s211.12.html&d=reduce
  - http://www.pacodeandbulletin.gov/Display/pacode?file=/secure/pacode/data/055/chapter1187/chap1187toc.html&d=
  - https://www.legis.state.pa.us/cfdocs/legis/li/uconsCheck.cfm?yr=2020&sessInd=0&act=2A
  - https://dced.pa.gov/download/covid-19-pa-hazard-pay-grant-guidelines-2020/?wpdmdl=95560
- CV citation lines (OCR/text-extract; may need cleanup):
  - New Proposed Staffing Regulations Announced
  - (DC + DON) or (CNA + LN)PA Administrative Code
  - Title 28, Sec. 21 1.12.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.76 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.70 HRPD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 (of total)
  - **CNAs**: Not found

### Rhode Island (`RI`)

- Clean / front-page estimate: **3.64 HPRD**
- MACPAC Summary total: 3.64 HPRD
- CV Total Nursing Staff (parsed): 3.87
- CV year totals: `{"2022": 3.64, "2023": 3.87}`
- MACPAC components: RN/LPN/CNA combined=3.58 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=2.44 HPRD (of total)
- MACPAC citations:
  - Rhode Island (RI) Chp. 23,  An Act relating to health and safety--Nursing Home Staffing and Quality Care Act, § 23-17.5-32. Minimum staffing levels
  - RI Chp. 23,  An Act relating to health and safety--Nursing Home Staffing and Quality Care Act, § 23-17.5-32. Minimum staffing levels
  - Licensing of nursing facilities (216-RICR-40-10-1)
- MACPAC source URLs:
  - http://webserver.rilin.state.ri.us/PublicLaws/Law21/law21023.htm
  - https://rules.sos.ri.gov/regulations/part/216-40-10-1
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)RI Code of Regulations
  - Title 216, Chapter 40, Subchapter
  - RI Statute
  - R.I. Gen. Laws § 23-17.5-32.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.64 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.58 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: 2.44 HPRD (of total)

### South Carolina (`SC`)

- Clean / front-page estimate: **2.01 HPRD**
- MACPAC Summary total: 2.01 HPRD
- CV Total Nursing Staff (parsed): 2.01
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.32 HPRD; CNAs=1.63 HPRD
- MACPAC citations:
  - South Carolina (SC) § 600—Staff and training, 603. Direct care staff
  - SC § 600—Staff and training, 605. Staff
  - SC Temporary Modification of Nursing Home Staffing Standards for the Current Fiscal Year
- MACPAC source URLs:
  - https://www.scstatehouse.gov/coderegs/Chapter%2061-1%20through%2061-17.pdf
  - https://scdhec.gov/sites/default/files/media/document/Nursing_Home_Staffing_Ratios_Memo.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - psychosocial health and safety needs of each resident.
  - (DC + DON) or (CNA + LN)SC Code of State Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.01 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.32 HPRD
  - **CNAs**: 1.63 HPRD

### South Dakota (`SD`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - South Dakota (SD),  44:73:06:07  Nursing service staffing
  - SD, 44:73:06:03. Director of nursing service
  - SD, 44:73:06:07  Nursing service staffing
- MACPAC source URLs:
  - https://sdlegislature.gov/Rules/Administrative/35250
  - https://sdlegislature.gov/Rules/Administrative/35246
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)SD Administrative Rules
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Tennessee (`TN`)

- Clean / front-page estimate: **2.06 HPRD**
- MACPAC Summary total: 2.06 HPRD
- CV Total Nursing Staff (parsed): 2.06
- MACPAC components: RN/LPN/CNA combined=2.00 HPRD; DON=0.06 HPRD; LNs=0.40 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Tennessee admin code (TAC). § 1200-08-06-.06, Nursing Services, pp 23—26
  - TAC. §1200-08-06-.06, Nursing Services, pp 23—26
  - TAC. § 1200-13-02-.06, Reimbursement methodology for nursing facilities, pp. 15–16
  - TAC. § 1200-13-02-.11, Quality-based component of the reimbursement methodology for nursing facilities, pp 32—41
- MACPAC source URLs:
  - https://publications.tnsosfiles.com/rules/1200/1200-08/1200-08-06.20210818.pdf
  - https://publications.tnsosfiles.com/rules/1200/1200-13/1200-13.htm
  - https://publications.tnsosfiles.com/rules/1200/1200-13/1200-13-02.20210428.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)TN Rules and Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.40 HPRD (of total)
  - **CNAs**: Not found

### Texas (`TX`)

- Clean / front-page estimate: **0.46 HPRD**
- MACPAC Summary total: 0.46 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=No HPRD described; DON=0.06 HPRD; LNs=0.40 HPRD; CNAs=Not found
- MACPAC citations:
  - Texas Administrative Code (TAC). Title 26, Part 1, Chapter 554, Subchapter K, Additional Nursing Services Staffing Requirements
  - TAC. Title 26, Part 1, Chapter 554, Subchapter K, Additional Nursing Services Staffing Requirements
  - Final Quality Metrics for Quality Incentive Payment Program (QIPP) FY2022 Nursing Facilities
  - (A)Texas, 2022 Rate Enhancement Attendant Compensation Information
  - (B) TAC Tit.1, Part 15, Ch. 355, Subchapter C, § 355.308, Direct care Staff Rate Component
  - Texas Health and Human Services, Tit. 26, Ch. 556
- MACPAC source URLs:
  - https://texreg.sos.state.tx.us/public/readtac$ext.TacPage?sl=R&app=9&p_dir=&p_rloc=&p_tloc=&p_ploc=&pg=1&p_tac=&ti=26&pt=1&ch=554&rl=1002
  - https://www.hhs.texas.gov/sites/default/files/documents/services/health/medicaid-chip/programs/qipp/final-quality-metrics-qipp-nf-fy20221.pdf
  - https://pfd.hhs.texas.gov/long-term-services-supports/2022-rate-enhancement-attendant-compensation-information
  - https://texreg.sos.state.tx.us/public/readtac$ext.TacPage?sl=R&app=9&p_dir=&p_rloc=&p_tloc=&p_ploc=&pg=1&p_tac=&ti=1&pt=15&ch=355&rl=308
  - https://www.hhs.texas.gov/news/2021/12/nurse-aide-transition-temporary-status-permanent-rule-effective-dec-26
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)TX Administrative Code
  - Title 26, Rule 554.1001.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.46 HPRD
  - **RNs, LPNs, and CNAs combined**: No HPRD described
  - **DON**: 0.06 HPRD
  - **LNs**: 0.40 HPRD
  - **CNAs**: Not found

### Utah (`UT`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=Not found; DON=0.06 HPRD; LNs=0.24 HPRD; CNAs=Not found
- MACPAC citations:
  - Utah Administrative Code (UAC), Health, Title R432, § 150-5. Nursing Care Facility
  - UAC, Health, Title R432, § 150-5. Nursing Care Facility
- MACPAC source URLs:
  - https://rules.utah.gov/publicat/bulletin/2017/20170815/41966.htm
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)UT Administrative Code
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: Not found
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD
  - **CNAs**: Not found

### Vermont (`VT`)

- Clean / front-page estimate: **3.06 HPRD**
- MACPAC Summary total: 3.06 HPRD
- CV Total Nursing Staff (parsed): 3.06
- MACPAC components: RN/LPN/CNA combined=3.00 HPRD; DON=0.06 HPRD; LNs=0.08 HPRD (of total); CNAs=2.00 HPRD (of total)
- MACPAC citations:
  - Code of Vermont (VT) Rules, Chapter 005: Licensing and Operating Rules for Nursing Homes, §7.13 Nursing Services
  - Code of VT Rules, Chapter 005: Licensing and Operating Rules for Nursing Homes, §7.13 Nursing Services
  - VT state plan, addendum A to attachment 4.19-D, pp. 23—24, 27
- MACPAC source URLs:
  - https://dail.vermont.gov/sites/dail/files/documents/Nursing_Home_Regulations_2018.pdf
  - https://humanservices.vermont.gov/sites/ahsnew/files/documents/MedicaidPolicy/MedicaidStatePlan/4attachment-4.19-d-addendum-a.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)Code of VT Rules
  - CVR 13-110-005-7.13.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.06 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.00 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.08 HPRD (of total)
  - **CNAs**: 2.00 HPRD (of total)

### Virginia (`VA`)

- Clean / front-page estimate: **0.30 HPRD** · federal floor flag
- MACPAC Summary total: 0.30 HPRD
- CV Total Nursing Staff (parsed): — / blank
- MACPAC components: RN/LPN/CNA combined=0.24 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - Virginia Administrative Code (VAC) Chapter 371. Regulations for Licensure of Nursing Facilities. Part III Resident Services, § 210 Nurse staffing. Subsection B.
  - VAC Chapter 371. Regulations for Licensure of Nursing Facilities. Part III Resident Services, § 200 Director of nursing. Subsection A
  - (A) Commonwealth of Virginia (VA), Waiver of 12VAC5-371-210(G): Certified Nurse Aide Registration
  - (B) Commonwealth of VA, Executive Order 57, Licensing of healthcare professional in response to novel Coronavirus (COVID-19)
- MACPAC source URLs:
  - https://law.lis.virginia.gov/admincode/title12/agency5/chapter371/section210/
  - https://law.lis.virginia.gov/admincode/title12/agency5/chapter371/section200/
  - https://www.vdh.virginia.gov/content/uploads/sites/96/2020/04/EO51-Waiver-for-12VAC5-371-210G.pdf
  - http://digitool1.lva.lib.va.us:8881/R/BX5UIU31TFKQ3RLFPRFFHA5HS7XTT4B17NXJ9QGIFMQDXGS4KP-02877?func=collections&collection_id=1512&pds_handle=GUEST
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)VA Administrative Code
  - 12 VAC5-371-200, 210, 220.
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 0.30 HPRD
  - **RNs, LPNs, and CNAs combined**: 0.24 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

### Washington (`WA`)

- Clean / front-page estimate: **3.46 HPRD**
- MACPAC Summary total: 3.46 HPRD
- CV Total Nursing Staff (parsed): 3.46
- MACPAC components: RN/LPN/CNA combined=3.40 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Washington Administrative Code (WAC), Adequate staff—Minimum staffing standards—Exceptions—Definition. Rev. Code Wash. (RCW) § 74.42.360
  - WAC (A) Nursing Services.  388-97-1090
  - (B) Engrossed Substitute House Bill 1564. Chapter 301, Laws of 2019, 66th Legislature; Nursing Facility Medicaid Payment Rate Methodology
  - WAC, Nursing Services. 388-97-1090
  - Rev. Code Wash. (ARCW) § 74.42.360
  - Engrossed Substitute House Bill 1120. Chapter 203, Laws of 2021, 67th Legislature; Long-term Services and Supports - State of Emergency
  - Washington state plan, attachment 4.19-D, Part 1, pp. 4, 6
- MACPAC source URLs:
  - https://app.leg.wa.gov/rcw/default.aspx?cite=74.42&full=true#74.42.360
  - https://app.leg.wa.gov/wac/default.aspx?cite=388-97-1080
  - http://lawfilesext.leg.wa.gov/biennium/2019-20/Pdf/Bills/Session%20Laws/House/1564.SL.pdf?q=20210816084758
  - http://lawfilesext.leg.wa.gov/biennium/2021-22/Pdf/Bills/Session%20Laws/House/1120-S.SL.pdf
  - https://www.hca.wa.gov/about-hca/apple-health-medicaid/medicaid-title-xix-state-plan
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)WA Administrative Code
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 3.46 HPRD
  - **RNs, LPNs, and CNAs combined**: 3.40 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### West Virginia (`WV`)

- Clean / front-page estimate: **2.31 HPRD**
- MACPAC Summary total: 2.31 HPRD
- CV Total Nursing Staff (parsed): 2.31
- MACPAC components: RN/LPN/CNA combined=2.25 HPRD; DON=0.06 HPRD; LNs=0.24 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - West Virginia Code (WVC)  Title 64, §8.14 Nursing Services Staffing.
  - (A) WVC, Title 64, §8.14.4 Registered Nurse.
  - (B) WVC Title 64, §8.14.6 Director of Nursing.
  - (A) WVC, Title 64, §8.14.2  Licensed nurses
  - (B) W. Va. Code Title 64, §8.14.3 Charge Nurse.
  - West Virginia (WV) HB 2142 §16-5C-25. Enforcement; civil penalties.
  - WV Department of Health and Human Services, Covered services, limitations, and exclusions for nursing facility services, pp. 57, 66
- MACPAC source URLs:
  - http://apps.sos.wv.gov/adlaw/csr/rule.aspx?rule=64-13
  - http://www.wvlegislature.gov/bill_Status/bills_text.cfm?billdoc=HB2142%20intr.htm&yr=2012&sesstype=RS&i=2142
  - http://dhhr.wv.gov/bms/Provider/Documents/Manuals/bms-manuals-chapter_514_NursingFacility.pdf
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)WV Code of State Rules
  - 64 CSR 13 – 8. And see below 64
  - CSR 13 -17 for Table 64-13A for
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.31 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.25 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.24 HPRD (of total)
  - **CNAs**: Not found

### Wisconsin (`WI`)

- Clean / front-page estimate: **2.06—3.31 HPRD**
- MACPAC Summary total: 2.06-3.31 HPRD
- CV Total Nursing Staff (parsed): 2.56
- MACPAC components: RN/LPN/CNA combined=2.00-3.25 HPRD; DON=0.06 HPRD; LNs=0.40-0.65 HPRD (of total); CNAs=Not found
- MACPAC citations:
  - Wisconsin (WI), Chapter 50. Uniform Licensure. Special provision applying to licensing and regulations of nursing homes § 50.04(2)(d)
  - WI Chapter DHS Nursing Homes, § 132.62. Nursing services
  - (A) WI, Chapter 50. Uniform Licensure. Special provision applying to licensing and regulations of nursing homes § 50.04(2)(d)
  - (B) WI, Chapter DHS Nursing Homes, § 132.62. Nursing services
  - WI, Chapter 50. Uniform Licensure. Special provision applying to licensing and regulations of nursing homes 50.04(2)(c)1.
- MACPAC source URLs:
  - https://docs.legis.wisconsin.gov/statutes/statutes/50/i/04/2t/b/3
  - https://docs.legis.wisconsin.gov/code/admin_code/dhs/110/132/vi/62
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)WI Administrative Code
  - WI Statute
  - § 50.04(2)(d).
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 2.06—3.31 HPRD
  - **RNs, LPNs, and CNAs combined**: 2.00—3.25 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: 0.40—0.65 HPRD (of total)
  - **CNAs**: Not found

### Wyoming (`WY`)

- Clean / front-page estimate: **1.56—2.31 HPRD**
- MACPAC Summary total: 1.56-2.31 HPRD
- CV Total Nursing Staff (parsed): 2.31
- MACPAC components: RN/LPN/CNA combined=1.50-2.25 HPRD; DON=0.06 HPRD; LNs=Not found; CNAs=Not found
- MACPAC citations:
  - State of Wyoming Administrative Code (WAC), Agency 048, Chapter 11, § 11-9: Nursing Services
  - WAC, Agency 048, Chapter 11, § 11-9: Nursing Services
  - WAC, Agency 048, Chapter 7, § 7-9: Cost and Rate Categories
- MACPAC source URLs:
  - https://casetext.com/regulation/wyoming-administrative-code/agency-048-health-department-of/subagency-0003-aging-division/chapter-11-program-administration-of-nursing-care-facilities/section-11-9-nursing-services
  - https://casetext.com/regulation/wyoming-administrative-code/agency-048-health-department-of/subagency-0037-medicaid/chapter-7-wyoming-nursing-home-reimbursement-system/section-7-9-cost-and-rate-categories
- CV citation lines (OCR/text-extract; may need cleanup):
  - (DC + DON) or (CNA + LN)WY Rules and Regulations
- MACPAC staffing category notes:
  - **Total estimated staffing requirements**: 1.56—2.31 HPRD
  - **RNs, LPNs, and CNAs combined**: 1.50—2.25 HPRD
  - **DON**: 0.06 HPRD
  - **LNs**: Not found
  - **CNAs**: Not found

