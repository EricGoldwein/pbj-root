# PBJ320 Premium exports and roster PDFs

How to describe exports when users paste Premium screenshots or PDFs into AI tools.

## Roster / Employee Detail PDF (single work date)

- **Source:** CMS PBJ daily staffing + **Employee Detail** for the selected **work date**.
- **Purpose:** Neutral dated snapshot: who appears with paid hours that day, by CMS job code, plus summary counts.
- **Not:** A clinical staffing determination, regulatory compliance decision, or proof any resident received care.

### Roster breakdown lines (typical)

| Line | Meaning |
|------|--------|
| Unique employees (paid hours this date) | Distinct people with any reported hours (admin + nursing codes 5–12 as loaded). |
| RN (5–7) | Employees whose job code that day is in CMS RN groups (DON, RN admin, direct RN). |
| LPN/LVN (8–9) | LPN with administrative duties or direct LPN/LVN. |
| Nurse aides / trainee / med aide (10–12) | CNA, aide in training, medication aide. |
| Administrator (code 1) | Facility administrator in CMS dictionary. |
| Any contract hours reported | Any contract/agency hours that day (not necessarily 100% contract). |

**Census (PBJ day):** Resident count from the PBJ daily row when available.

### Total HPRD vs reference band

- Day total HPRD from the same single-day analysis as the on-screen report.
- **MACPAC-style** state reference band when shown: language is **below / within / above reference band** — **not PASS/FAIL**.
- Verify against current statute, regulation, and survey context.

### Employee lines table

One row per employee × job code with hours. “Staff” vs “Contract” indicates whether **any** contract hours were reported for that row.

## Staff categories (Premium Methods)

- **Total Staff:** RN, LPN, CNAs, RN/LPN administrators, DON.
- **Direct Staff:** Direct patient care (excludes administrators and DON).
- **Total RN:** RNs + RN administrators + RN DON.
- **Direct RN:** Excludes RN Admin and RN DON.
- **LPN:** Direct LPNs + LPN administrators.
- **Nurse Aides:** CNAs, trainee aides, medication aides.
- **Contract Staff:** Agency/temp (PBJ fields with `_ctr` suffix).

## Provenance rule for AI

Do not invent decimals, employee counts, or job-code breakdowns not shown in the export. If a table is cropped or missing, say what is missing and what full export would clarify.
