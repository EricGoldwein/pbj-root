# PBJ320 Terms Reference

## PBJ

Payroll Based Journal. CMS staffing data reported by nursing homes (daily nurse staffing and optional Employee Detail).

## HPRD

Hours per resident day. Reported staffing hours ÷ census for the period shown. Does not show shift-level assignment, unit deployment, or worker familiarity with residents.

## RN / LPN / nurse aide staffing

- **RN:** Assessment, supervision, higher-level clinical oversight; includes RN Admin and RN DON in “total RN” on many PBJ320 views.
- **Direct RN:** Excludes RN Admin and RN DON where labeled.
- **LPN:** Licensed practical nurses; distinct scope from RNs.
- **Nurse aides:** CNAs and related aide roles — often central to hands-on care.

## Total nurse staffing

Combined nursing staff hours (RN + LPN + aide categories per the definition on the page).

## Direct care vs total

**Direct care** HPRD excludes administrators and DON from the direct-care subtotal. Check which label the page uses.

## Contract staff

Temporary or agency hours (PBJ `_ctr` fields). Contract **percentage** = contract hours ÷ total hours × 100.

## Case-mix (CMS)

Acuity-adjusted **comparison** from Provider Information / CMS Users Guide — PDPM nursing CMGs and national CMI weighting. **Not a legal staffing minimum.** See `pbj320_case_mix_cms.md`.

## Case-mix index / ratio

Facility nursing CMI and ratio to national reference. Describes acuity context; does not by itself prove adequacy or violation.

## Case-mix hours / % case-mix HPRD

- **Case-mix hours:** CMS-published benchmark HPRD for the quarter.
- **% case-mix:** (Reported HPRD ÷ CMS case-mix HPRD) × 100. Below 100% = reported under CMS acuity benchmark for that quarter.

## Harrington expected

Separate acuity-adjusted model (Harrington et al.). **Not the same label as CMS case-mix hours.** See `pbj320_harrington_vs_casemix.md`. Implemented formula and constants: `pbj320_harrington_formula.md`.

## Percentile / rank

Comparison group must be stated (e.g., within state, nationally). For staffing HPRD, higher often means more reported hours; confirm metric direction.

## Volatility (when shown)

PBJ320 may classify longitudinal staffing stability (e.g., Stable, Drifting, Disrupted, Collapsed). **Collapsed** = high volatility **and** declining staffing — screening label, not a legal finding.

## Red flags / screening

Unusual-day or outlier views are **hypothesis generators** — not proof of neglect, harm, or regulatory violation.

## CCN

Six-digit CMS Certification Number — always verify against Care Compare and pleadings.

## Premium evidence packet

Custom facility deliverable: daily exports, trend tables, definitions, limitations, and context for counsel/advocacy/research. Distinct from the free quarterly facility page.

## State minimum / MACPAC reference

When labeled on PBJ320, a dashed line or sidebar value tied to MACPAC summarizes **state staffing policy estimates** from a **[MACPAC nursing-facility staffing publication](https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/)**. It may be a **range** converted to chart-friendly numbers. Nuance for answers: **`references/pbj320_macpac_state_standards.md`**.
