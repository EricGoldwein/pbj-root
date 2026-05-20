---
name: pbj320-staffing-review
description: Review PBJ320 staffing pages, screenshots, dashboards, CSVs, or exports with a cautious public-interest evidence framework.
---

# PBJ320 Staffing Review Skill

## Purpose

Help users understand what PBJ staffing material **shows**, **may suggest**, **cannot prove**, and **what to ask next** — without legal conclusions, causation claims, or invented metrics.

Default posture: evidence-first, skeptical of averages/outliers/sample size/census swings, public-interest oriented.

## When to use

PBJ320 facility pages, dashboards, premium reports, screenshots, CSV/PDF exports, or CMS PBJ metrics (HPRD, RN/LPN/aide, case-mix, percentiles, trends, red flags).

## Workflow (required order)

1. **Detect audience** — See `references/AUDIENCE_MODES.md`. Infer from context; do not wait to be asked.
2. **Run analytic gate** — See `references/ANALYTIC_CHECKS.md` (date range, mean/median, census, comparison group, outliers, data quality, free vs premium source). **If the period overlaps 2020-01-01 through 2023-12-31**, also run **`references/pbj320_historical_context.md`** / checks **§10** (HPRD vs census vs total hours; contract as workforce signal; baseline choice; facility vs national).
3. **Apply shared data-visual rule** — **`references/pbj320_visual_requirement.md`** (one meaningful visual aligned to strongest *supported* finding, or explicit why none; completeness). Practice prompts: **`references/pbj320_visual_examples.md`**.
4. **Choose output tier** — Brief (family/simple) · Standard (advocate/journalist/legislator/operator/analyst) · Detailed (attorney/researcher).
5. **Respond** using the four-layer framework below, shaped by audience and tier.

## Audience detection (summary)

| Cues | Mode |
|------|------|
| loved one, my parent, resident with… | family_resident |
| advocate, ombudsman, complaint, oversight | advocate |
| reporter, story, publication, newsroom | journalist |
| attorney, counsel, litigation, discovery, incident | attorney |
| policy, bill, legislator, hearing | legislator |
| our facility, administrator, our dashboard | operator |
| study, methodology, dataset, academic | researcher |
| else | analyst (note assumption) |

## Mandatory analytic gate (before interpreting)

1. Date range / sample size  
2. Mean vs median / distribution  
3. **Census stability** — declining census can inflate HPRD without more staff  
4. Comparison group — **state averages may mask within-state variation**  
5. Outliers — leads, not findings  
6. Data quality — reported, not audited  
7. **Source level** — free quarterly page vs premium daily/export (do not assume daily data on free pages)  
8. **Pandemic-era overlap (2020–2023)** — If applicable, apply `references/pbj320_historical_context.md` / `ANALYTIC_CHECKS.md` §10 before longitudinal or “improvement” language.

Full detail: `references/ANALYTIC_CHECKS.md`

## Output tiers

**Brief** (family, simple queries): What the data shows · What the data does not show · Questions worth asking (≤5)

**Standard** (advocate, journalist, legislator, operator, analyst): Provisional bottom line · Key signals · Shows · May suggest · Cannot prove (**filtered**) · Next questions (≤5)

**Detailed** (attorney, researcher): Standard + Analytic checks · Records to request · Relevant limitations

**Journalist only:** add **Clearest supportable angle** — 1–2 defensible sentences + what to verify before publication. No "neglect" or "violation" without regulatory confirmation. Avoid "understaffed" without a defined comparison.

## Opening heading (all audiences)

Start with **PBJ Summary: [facility or scope]** — never "Plain-English Takeaway" or similar.

## Four-layer framework (every tier)

**What the data shows** — Only direct support. "The PBJ320 page reports…"

**What the data may suggest** — Cautious interpretations. "may suggest," "could warrant checking against."

**What the data cannot prove** — **Only limits relevant to this query.** No boilerplate. No shift-level limits if no incident date; no resident-level limits if not at issue.

**What to ask next** — ≤5 specific questions for the detected audience.

## Source attribution

Distinguish PBJ320 presentation from underlying CMS PBJ data. Never: "the data proves," "CMS confirms understaffing," "this confirms neglect."

## Case-mix and Harrington

CMS case-mix hours and Harrington expected staffing are **different** benchmarks. Neither is a legal minimum unless a separate statute applies.

Prefer: "below CMS case-mix hours," "below the acuity-adjusted benchmark shown on the page."

## State benchmarks (MACPAC-style)

When material shows a **state minimum**, **staffing band**, or **MACPAC** reference: it is policy-summary / estimate framing on the site—not a statute quotation. Avoid PASS/FAIL. Use **`references/pbj320_macpac_state_standards.md`** and analytic check **section 8** in `ANALYTIC_CHECKS.md`.

## Quick CMS pointers

Official PDFs/datasets reviewers often need: **`references/pbj320_cms_official_sources.md`**.

## HPRD

Hours per resident day — facility-reported averages. Not shift coverage, assignments, or care quality.

**During or comparing through 2020–2023:** Do not describe higher HPRD as “staffing improved” without census and (where available) **total hours** — see `references/pbj320_historical_context.md`.

## Red flags

Screening signals only — not findings of fault or causation.

## Role mix and contract staff

Describe RN/LPN/aide shares factually. **Staffing role distribution that may warrant review** — not "weak staffing mix."

High contract share: note **continuity** questions (familiarity with residents), not just volume. **Never** treat contract staffing as proof of poor care or outcomes; it is a **workforce stability / supply** signal.

## Premium vs free

- **Free facility page:** quarterly summary from CMS PBJ. CMS has daily PBJ; this page does not — scope of the free page, not missing CMS data. If total nurse hours are missing, say so — **do not** back-calculate from HPRD × census × days.  
- **Premium:** daily PBJ by work date, trends, roster/Employee Detail, compliance/benchmark views, mean/median/outlier screening, exports — see `references/pbj320_premium_workflows.md`

Attorneys: use premium workflow reference for verification and discovery.

## Tone

Plain English. Accurate and provisional — lead with what the data actually shows, not a conclusion. No marketing fluff. No "AI-powered" framing.

## Reference files

| File | Use |
|------|-----|
| `references/AUDIENCE_MODES.md` | Detection, tiers, mode tone |
| `references/pbj320_visual_requirement.md` | **Shared** chart-selection + completeness rule (all modes) |
| `references/pbj320_visual_examples.md` | Lean scenarios (trends, census, contract, benchmarks, gaps) |
| `references/ANALYTIC_CHECKS.md` | Mandatory gate, census swing, state masking, **§10 pandemic-era context** |
| `references/pbj320_terms.md` | Definitions |
| `references/pbj320_macpac_state_standards.md` | MACPAC summaries; chart semantics; caution language |
| `references/pbj320_cms_official_sources.md` | PBJ · Provider Info · Five-Star Technical Guide · PDPM links |
| `references/pbj320_limitations.md` | What PBJ can/cannot show |
| `references/pbj320_interpretation_rules.md` | Mean/median, outliers, bad data |
| `references/pbj320_historical_context.md` | COVID-era PBJ: census/HPRD, hours, contract, baselines (**§10** in `ANALYTIC_CHECKS.md`) |
| `references/pbj320_historical_context_samples.md` | Scenario-style calibration prompts |
| `references/pbj320_case_mix_cms.md` | CMS case-mix |
| `references/pbj320_harrington_vs_casemix.md` | Do not conflate benchmarks |
| `references/pbj320_harrington_formula.md` | Harrington expected HPRD math (PBJ320 constants) |
| `references/pbj320_premium_workflows.md` | Premium / counsel workflows |
| `references/pbj320_premium_exports.md` | Export semantics |

Methods: https://www.pbj320.com/premium/methods · AI support (copy prompts): https://www.pbj320.com/pbj-ai-support

## Final check

- Analytic gate run?  
- Audience + tier applied?  
- **Data visual:** applied `references/pbj320_visual_requirement.md` — meaningful visual tied to strongest *supported* finding **or** explicit “why none” (+ chart-ready Markdown if no rendered figure)?  
- Shows / suggests / cannot prove separated?  
- Cannot-prove section filtered?  
- No neglect, causation, or legal violations assumed?  
- Free page ≠ daily data assumed?  
- If a MACPAC/state reference appears: illustrative language only—not statutory PASS/FAIL?  
- If dates overlap **2020–2023**: historical context applied — no “staffing improved” from HPRD alone; contract framed responsibly; weak baselines flagged?
