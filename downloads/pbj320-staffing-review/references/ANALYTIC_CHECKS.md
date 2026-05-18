# PBJ320 analytic checks (mandatory gate)

Run these checks **before** interpreting any pattern. If the material lacks information for a check, say what is missing.

## 1. Date range and sample size

- How many days, weeks, or quarters are included?
- Is the window long enough for the claim being made?
- For peer comparisons: how many facilities are in the comparison group?

## 2. Mean vs distribution / median

- Is the conclusion driven by a mean that may hide outlier days?
- Would median, distribution, or count of low-staffing days tell a clearer story?
- Do not treat one average as the whole story.

## 3. Census stability (census swing)

- Did average daily census or occupancy change materially during the period?
- **If census declined, HPRD can appear higher without any actual staffing increase.** Flag this before praising HPRD improvement.
- Language: "If census declined during this period, HPRD may appear higher without any actual staffing increase. Check whether census was stable."

## 4. Comparison group

- State, national, peer group, portfolio, or self-comparison over time?
- State each comparison separately.
- **State-average masking:** A facility near the state average may still rank poorly among similar-acuity or local peers. State averages compress wide within-state variation.

## 5. Outliers

- Are extreme days driving the pattern? Outliers are leads, not findings.
- Check holidays, weekends, reporting artifacts, missing days, ownership transitions.

## 6. Data quality

- Impossible values, missing days, internal inconsistencies?
- PBJ is facility-reported to CMS. Treat as evidence to verify, not gospel.

## 7. Source level (free vs premium)

| Source | Usually available | Usually not on this source alone |
|--------|-------------------|----------------------------------|
| **Free PBJ320 facility page** | Quarterly staffing context, visible facility-level metrics, case-mix context, percentiles, narrative summary | Daily staffing, 90-day aide/CNA day counts, mean/median/outlier tables, incident-window drill-down, employee roster |
| **Premium PBJ320 dashboard / export** | Daily PBJ, 90-day aide/CNA patterns, trends, mean/median/outlier views, incident-window context, exports, evidence-packet materials | Assignment-level care, resident-specific outcomes, audited payroll |

Do not assume daily data exists on a free quarterly page. Do not claim weekend/weekday patterns without daily data.

## 8. State reference / MACPAC-style line

When charts or narratives show a **state minimum**, **reference band**, or **MACPAC** dashed series:

- Is the value a **single HPRD**, a **range**, or a federal-floor fallback? Say which.  
- Is the metric **direct care**, **total nursing**, or another subtotal matching the labeled series? Mixed denominators inflate or deflate comparisons.  
- **Do not** upgrade to PASS/FAIL, “violated state law,” or “substandard” absent statute text, survey/deficiency linkage, or other primary documentation (see `references/pbj320_macpac_state_standards.md`).  
- Prefer: **below / within / above reference band**, **estimate**, **verify against current rule**.

## Role mix (when RN, LPN, aide are present)

- What share of total nurse hours is RN vs LPN vs aide?
- Prefer: **"staffing role distribution that may warrant review"** — not "weak staffing mix."
- RN HPRD very low relative to benchmarks is a hypothesis trigger, not a legal standard.

## Weekend / holiday (daily data only)

If daily data is available: compare weekday vs weekend RN and aide HPRD. Do not assume this is visible on free quarterly pages.

## Contract staff continuity

High contract share is not only volume. Agency workers may be less familiar with residents, units, and care plans. When contract share is elevated, note continuity questions — not findings.

## Trend label (3+ quarters)

When enough quarters exist, cautiously classify as one of:

- **Structurally low** — consistently below benchmarks, limited variation
- **Worsening** — decline without reversal
- **Recovering** — improvement after prior decline
- **Volatile** — high variation without clear direction

Only use when the data support the label.

## Filtered limitations

In "What the data cannot prove," list **only limits relevant to this query** — not a boilerplate list of every possible limit.

## 9. Data visual completeness

Before finalizing:

- Follow **`references/pbj320_visual_requirement.md`**: **one meaningful visual** for the strongest *supported* finding **or** a concise statement that none is possible (**and why** — missing columns, single quarter only when trend was needed, timing question without daily rows, etc.).
- Do **not** draw a chart only because quarterly numbers exist; prose may be clearer.
- When no rendered figure is feasible, use **chart-ready** Markdown/table (title, chart type, values, one-line takeaway, limitation).

## 10. Pandemic-era / COVID longitudinal context (2020–2023)

When the reviewed period **overlaps 2020-01-01 through 2023-12-31** or trends are anchored to quarters in that window, **`references/pbj320_historical_context.md`** applies **before** trend or “improvement” language:

- **Period overlap:** Explicitly check whether the window includes **2020–2023**; if yes, use the historical-context rules (not optional).
- **Census:** Require census / resident-day stability or explain denominator movement. **Do not** use “staffing improved” / “better staffed” from **HPRD alone**.
- **Total hours:** Where possible, interpret **total nurse hours** (or category hours) **with** HPRD — national PBJ-based work documents **HPRD can rise while total hours fall** when census drops (ASPE/RTI issue briefs, cited in that reference).
- **Contract / agency:** Frame as **workforce supply and continuity** — **not** a proxy for poor care and **not** causal for outcomes without other evidence.
- **Baselines:** **Do not** treat peak disruption quarters (especially **2020**, often **early–mid 2021**) as neutral “pre-trend” baselines unless the user defines that choice and its limits.
- **Scale:** Separate **facility** findings from **national or state aggregate** narratives; do not assume a national contract or HPRD story matches a single facility.
- **Source level:** Free quarterly pages may lack daily contract series or full census history — **say what is missing** instead of inferring (`section 7`).
