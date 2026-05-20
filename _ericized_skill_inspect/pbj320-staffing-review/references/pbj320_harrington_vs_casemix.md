# Harrington “expected” vs CMS case-mix hours — do not conflate

AI reviewers must keep these separate. Both adjust for acuity context; they use different methods and labels.

## CMS case-mix hours (Provider Information)

- Published by CMS from PDPM nursing CMGs and national CMI weighting (see `pbj320_case_mix_cms.md`).
- PBJ320 may label this **case-mix**, **case-mix HPRD**, or **% case-mix HPRD** (reported ÷ CMS case-mix benchmark × 100).
- Below 100% means reported staffing is under the CMS-reported acuity benchmark for that quarter — **not** automatic proof of illegal understaffing.
- After April 2019 CMS documentation uses **case-mix hours**, not “expected hours,” for this series.

**Preferred AI language:** “below CMS case-mix hours,” “below the case-mix benchmark on the page,” “lower than the acuity-adjusted comparison point.”

**Avoid:** “failed CMS staffing requirements,” “illegal understaffing,” “proved insufficient staffing,” “violated case-mix standards.”

## Harrington expected staffing (academic adjustment)

- Separate model from Harrington et al., *Journal of the American Geriatrics Society* (case-mix index applied to published formulas).
- PBJ320 Premium may show **Harrington expected HPRD** and **% of Harrington expected** (reported ÷ Harrington expected × 100).
- **Exact curve and constants** as implemented: `references/pbj320_harrington_formula.md` (CMI bounds, intercept/high/exponent table, PBJ column mapping).
- **Direct-care metrics** in PBJ exclude RN Admin/DON per PBJ320 definitions.

**Preferred AI language:** “below Harrington expected staffing (acuity-adjusted model shown on the dashboard),” “reported HPRD as a percent of Harrington expected.”

**Avoid:** Calling Harrington expected “CMS case-mix” or a legal staffing minimum.

## Quick disambiguation for users

| Term on page | Usually means |
|--------------|-------------|
| Case-mix HPRD / case-mix hours | CMS Provider Information benchmark |
| % case-mix / reported vs case-mix | Reported ÷ CMS case-mix benchmark |
| Harrington expected / % of expected | Harrington et al. model, not CMS case-mix label |
| MACPAC reference band (some exports) | State policy illustration — not PASS/FAIL |

When only one benchmark appears in the material, describe that one and note if the other is not shown.
