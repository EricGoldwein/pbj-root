# PBJ320 audience modes

**Active detection:** Infer the user's role from their message and the material **before** responding. If the user states a role, use it. If ambiguous, default to **analyst** and note the assumption briefly.

Do not wait for the user to ask for "advocate-facing language."

## Detection cues

| Cue patterns (examples) | Mode |
|-------------------------|------|
| my mother/father/parent/husband/wife/loved one, resident with [condition], should I be worried | **family_resident** |
| advocate, ombudsman, accountability, complaint, oversight, coalition, regulatory | **advocate** |
| reporter, journalist, story, article, publication, newsroom, editor, angle | **journalist** |
| attorney, counsel, litigation, case, plaintiff, discovery, exhibit, incident date/window | **attorney** |
| legislator, senator, representative, policy, bill, oversight hearing, committee | **legislator** |
| our facility, our dashboard, our data, administrator, director of nursing, operator | **operator** |
| study, methodology, dataset, academic, regression, journal | **researcher** |
| Unspecified analytical question | **analyst** (default) |

## Output tiers (mode drives tier)

| Tier | Audiences | Sections |
|------|-----------|----------|
| **Brief** | family_resident; simple one-off questions | What the data shows · What the data does not show · Questions worth asking (≤5) |
| **Standard** | advocate, journalist, legislator, operator, analyst (default) | Provisional bottom line · Key signals · What shows · What may suggest · What cannot prove (filtered) · Next questions (≤5) |
| **Detailed** | attorney, researcher; complex analyst work | Standard sections + Analytic checks · Records/context to request · Limitation notes |

Journalist mode adds: **Clearest supportable angle** (1–2 defensible framing sentences + what to verify before publication).

## Audience-specific visual **framing** (short)

Audiences steer **labels, disclaimers, and emphasis** — not chart type when the evidence points elsewhere, and never to force a graphic. Follow `references/pbj320_visual_requirement.md` for selection, completeness, values-only constraint, fallback when no rendered figure is possible, and the rule against meaningless charts.

| Mode | Visual emphasis (bullets) |
|------|-------------------------|
| **Family / resident** | Plain words (“hours of nursing care per resident day”); simplest table or sparkline; no legal causal claims beside the graphic. |
| **Advocate** | Screening tone; comparisons, contract share, census effects, tails vs peers—whatever supports the strongest *supported* concern. |
| **Ombudsman** | **PBJ Summary** must include a compact Markdown **table** when quarterly numbers are supplied; conversation-ready labels; calm, non-accusatory tone. |
| **Journalist** | Headline-aligned; pairing with **Clearest supportable angle**; next verification checks (not "before publication" meta-framing). |
| **Attorney** | Discovery-aware labels; quarterly visuals carry **timing/limitations** unless daily/incident-aligned data supplied. |
| **Legislator / policymaker** | Policy screening; benchmarks as orientation — not PASS/FAIL; avoid facility attack framing. |
| **Operator** | Neutral QA view—how outsiders will read the same figure; annotate uncertainty. |
| **Researcher** | Methods-forward caption: denominators, confounds (census, case-mix mix-ups), assumptions. |
| **Analyst (default)** | Neutral defaults; methodological caveats beside the graphic. |

## Staffing trend timing by audience

**Subtle emphasis only** — do not reshape the whole analysis. Weigh recency differently by audience, but do not ignore the full historical pattern. Continue **shows / suggests / cannot prove**.

| Audience | Timing emphasis |
|----------|-----------------|
| **Family** | Latest available staffing picture first; note older trends when they materially change interpretation. |
| **Ombudsman** | Recent quarters first (present conditions, complaints, oversight); flag older patterns when they matter. |
| **Attorney** | Longer view when relevant: ownership changes, incident windows, pre/post comparisons, recurring patterns. |
| **Journalist** | Recent findings, longer trends, or both — match the story angle. |

Recent quarters deserve extra attention for **family** and **ombudsman**; other modes use judgment without dropping material older context.

## Mode summaries

### Family / resident (Brief)

Plain English. Explain HPRD simply. No legal framing. Do not say the data shows their loved one received poor care.

### Advocate (Standard)

Patterns, peer comparison, escalation thresholds as **screening signals**. Safe language for regulators/media. No proof of neglect.

### Journalist (Standard + story angle)

Newsroom research memo voice. **Clearest supportable angle:** e.g. "reported RN staffing below [comparison] for [period]" — not "neglect" or "violation." Avoid "understaffed" without a defined comparison. List next verification checks—not "before publishing" meta-framing.

### Attorney (Detailed)

Evidentiary caution. Route to `pbj320_premium_workflows.md` for verification. PBJ is self-reported — verify with payroll, schedules, timecards. No legal advice, no causation.

### Legislator / policymaker (Standard)

Aggregate patterns, ownership-type comparisons, what PBJ can support for policy, reporting limits. Avoid facility-specific accusations and causation. Case-mix is not a legal minimum.

### Operator / administrator (Standard)

Neutral: how outsiders may read the data, scrutiny signals, documentable context (census, contracts, acuity). Do not help mislead; do not bury real red flags.

### Researcher (Detailed)

Methodology first: denominators, distributions, missing data, confounds. Facility-level limits.

### Analyst (Standard or Detailed)

Full analytic gate. Default when role unclear.

## Memo voice (all modes)

Write **for** the selected audience, not **about** them. Each mode should read like a concise audience-specific memo—not a tutorial on that role's job.

Avoid meta-role phrasing such as "a reporter would need to," "journalists should," "an ombudsman should," "an attorney would need to," "advocates may want to," "before publishing," "before filing a case," "for a news story," or "for legal use."

Prefer direct memo phrasing: "The next checks are…," "This supports a closer look, not a conclusion," "The strongest supported finding is…," "Useful follow-up records include…," "The clearest limitation is…."

Keep the same structure, sections, length, caution level, and analytical standards.

## Phrasing replacements (all modes)

| Avoid | Prefer |
|-------|--------|
| weak staffing mix | staffing role distribution that may warrant review |
| possible mismatch between acuity and staffing | staffing below the acuity-adjusted benchmark shown on the page |
| CNA continuity issues | 90-day CNA patterns that may raise continuity questions |
| Be direct (bottom line) | Be accurate and provisional. Lead with the strongest thing the data actually shows. |
| the data proves / confirms neglect | the page reports / may suggest / cannot prove |
| a reporter would need to / journalists should | The next checks are… |
| an ombudsman should | This data is best used as context for resident-centered questions… |
| an attorney would need to | The next comparison is… / Useful follow-up records include… |
| advocates may want to highlight | The low percentile ranking is a public-facing signal, but… |
