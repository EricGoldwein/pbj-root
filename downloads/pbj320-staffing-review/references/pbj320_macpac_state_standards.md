# MACPAC-style state staffing reference (PBJ320)

How PBJ320 uses **MACPAC** summaries—and how reviewers should describe them **without overstating**.

## Primary source

- MACPAC publication: **[State Policies Related to Nursing Facility Staffing](https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/)**  
  Publication used in PBJ320 integrations is summarized as **March 2022**; **states update rules**. Always steer serious compliance questions toward **current state statute/regulation**, not dashboard copy alone.

MACPAC summarizes state policy; **PBJ320’s numeric band or minimum is an estimate** derived from a cleaned table (ranges → min/max semantics, federal-minimum states flagged). It is **not** a citation to a specific enacted section unless the dashboard row includes that citation text or link.

## What this is **not**

- Not a CMS enforcement standard for PBJ filings in the MACPAC summary sense (PBJ is separate reporting; state licensing/enforcement differs).  
- **Not PASS/FAIL** from a dashed line alone — use **below / within / above reference band** (or similar neutral language). See also `references/pbj320_premium_exports.md`.  
- **Not** RN-only minimums: MACPAC’s “total estimated staffing requirements” framing is predominantly **total nursing / direct-care** style totals in the cleaned file PBJ320 uses; **RN 8-hour rules and other doctrines** live in statutes/surveys, not automatically in MACPAC totals.

## Cleaned reference table semantics (when reading exports or documentation)

Production pipelines use **`macpac_state_standards_clean.csv`** (conceptually): one row per state/DC.

| Field (typical) | Meaning |
|----------------|---------|
| `State` | Full state name |
| `Min_Staffing` / `Max_Staffing` | Parsed HPRD bounds; ranges use both |
| `Value_Type` | e.g. `single`, `range`, `invalid` |
| `Is_Federal_Minimum` | When **true**, state row reflects **~0.30 HPRD** federal-floor treatment in the cleaned summary (verify column presence in actual export) |
| `Display_Text` | Human-readable label for charts |
| `State_Code_URL` / `State_Code_Citation` / `Legislation_Text` | Optional statute links or narrative |

Apps often plot the **minimum** HPRD (or sensible single value from a range) for a chart line while showing **band language** where `Value_Type` is `range`.

## Reviewer posture

1. Quote what the **page or export literally shows** (value, band, quarter).  
2. Say **MACPAC estimate** / **policy summary** when that is how the UI labels it.  
3. When users need “did they violate state law?” — **cannot conclude from HPRD vs MACPAC alone**; list records and primary legal sources (`pbj320_limitations.md`).

## Companion references

- `references/pbj320_harrington_vs_casemix.md` — do not confuse MACPAC lines with CMS case-mix or Harrington.  
- `references/pbj320_case_mix_cms.md` — CMS acuity benchmarks (Users Guide).  
- Premium / attorney workflow: `references/pbj320_premium_workflows.md`.
