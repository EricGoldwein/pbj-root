---
slug: cost-reports-pbj-staffing-context
title: "PBJ Shows Staffing. Cost Reports Show the Bigger Picture."
description: "PBJ shows reported staffing hours; cost reports add occupancy, payer mix, and operating context so staffing numbers can be read next to the census and revenue pressures behind them."
published: false
hideFromHub: true
date: 2026-05-07
previewImage: /insights-native-preview.svg
readTime: 9 min read
tags: PBJ Trends, CMS, Cost Reports
---

If **PBJ** shows you **reported staffing hours**, cost reports show you the **operating context** those hours sat inside.

If you only read PBJ, you miss context that often changes the next question: **Was the building already light on occupancy? Was payer mix Medicaid-heavy? Was the facility off-pattern for peers?**

Cost reports are annual financial and operating filings. They are **not** bedside quality audits and they do **not** replace staffing investigation. They **do** add baseline context that helps explain why one PBJ signal should trigger deeper follow-up while another might call for a different line of inquiry.

PBJ320 is adding cost reports for exactly that reason: to support better triage, **not** to prove causation. Two facilities can show similar PBJ deterioration while having very different occupancy and payer baselines in the latest available cost-report year.

**Timing matters:** the current cost-report slice runs through **2023**, so this is **not** a live 2026 readout. The intended workflow is to pair older cost-report context with newer PBJ staffing trends, then test what you see against ownership, inspections, complaints, and enforcement records.

<aside class="insight-phoebe-callout">
  <img src="/phoebe.png" alt="Phoebe J" width="48" height="48" loading="lazy" decoding="async" />
  <div>
    <p class="insight-phoebe-callout__label">Phoebe J's takeaway</p>
    <p>Read cost reports as the <strong>wider shot</strong> and PBJ as the <strong>close-up</strong>. Cost reports will not tell you who worked a specific shift, but they do show whether a facility was already running light on occupancy, Medicaid-heavy, or otherwise off-pattern before newer PBJ staffing changes.</p>
  </div>
</aside>

## What a cost report can tell you

PBJ reflects payroll-based staffing hours reported under CMS rules.

Cost reports can support questions like:

- **How full did the home look on paper?** PBJ320 uses an **occupancy proxy**: **resident days divided by available bed-days** in the filing. Think “**estimated fullness** from the report,” not a minute-by-minute headcount.
- **How many resident days** did it report?
- **Payer mix:** **what share of resident days** were tied to **Medicare**, **Medicaid**, or **other payers**—by **days**, not dollars. “Other payer” is **not** a clean synonym for private pay.
- What broader operating picture those numbers suggest.

What cost reports **cannot** do:

- They **do not** tell you the building was **safely staffed** on a specific night.
- They **do not** tell you **why** staffing moved.
- They **do not** score “good care.”

When we say **“rows that passed basic checks,”** we mean rows where simple arithmetic and core fields align well enough to chart reliably (internally: **dashboard-ready**).

## The occupancy drop still matters

These are national medians of the occupancy proxy on dashboard-ready rows, by year in the CMS file (2011-2023):

| Year | Median occupancy proxy |
|------|-------------------------|
| 2011 | 0.866 |
| 2015 | 0.855 |
| 2019 | 0.837 |
| 2020 | 0.749 |
| 2021 | 0.717 |
| 2022 | 0.757 |
| 2023 | 0.797 |

The trend is clear: gradual decline into 2019, a sharp break in 2020-2021, then partial recovery by 2023. But the median remains below 2019 (0.797 vs. 0.837 on a 0-1 scale). The 25th and 75th percentiles show the same pattern (2019: 0.714 / 0.911; 2021: 0.599 / 0.820; 2023: 0.661 / 0.890), indicating this was not just an outlier effect.

Why this matters for legal, advocacy, and reporting work: when someone points to 2024-2025 PBJ deterioration, a fair follow-up is what occupancy and payer environment existed immediately before that period. Low occupancy does not cause low staffing, but it is a baseline signal worth comparing against later PBJ performance.

<figure class="insight-chart">
<img src="/insights-cost-report-national-occupancy.svg" alt="Line chart: national median occupancy proxy with shaded band for the middle fifty percent of facilities, 2011 through 2023." width="820" height="420" loading="lazy" decoding="async" />
<figcaption><strong>Chart 1.</strong> National occupancy proxy: median (blue) and middle 50% (shaded). Dashboard-ready cost report rows.</figcaption>
</figure>

## Rural and urban homes did not follow the exact same pattern

Same occupancy proxy, split by rural vs. urban label in the file:

| Year | Rural | Urban |
|------|-------|-------|
| 2019 | 0.791 | 0.851 |
| 2020 | 0.723 | 0.757 |
| 2021 | 0.672 | 0.733 |
| 2022 | 0.697 | 0.775 |
| 2023 | 0.734 | 0.816 |

Both lines fall in 2020-2021. Urban medians remain higher in every year shown. The gap between urban and rural medians is about 0.060 in 2019 and about 0.082 in 2023, wider at the end of the window than at the start.

Rural status is not a causal claim in this chart. It is a reminder not to collapse U.S. nursing homes into one line. The same staffing signal can require different follow-up depending on where and how a facility operates.

<figure class="insight-chart">
<img src="/insights-cost-report-rural-urban-occupancy.svg" alt="Two-line chart comparing rural and urban median occupancy proxy from 2019 through 2023." width="720" height="380" loading="lazy" decoding="async" />
<figcaption><strong>Chart 2.</strong> Rural (green) vs. urban (violet) median occupancy proxy. Both dropped in 2020–21; medians had not converged by 2023.</figcaption>
</figure>

## Payer mix is not a side detail

Payer mix here means who paid for resident days (Medicare, Medicaid, or other payers), measured as shares of days, not dollars.

**2023 state snapshots** (each row is a state; **n** is facilities in that state’s slice):

- **West Virginia** — **103** facilities: **median** occupancy proxy **0.936**, **weighted** Medicaid day share **0.810**, Medicare **0.067**.
- **Texas** — **1,163** facilities: **median** occupancy **0.627**, **weighted** Medicaid **0.602**, Medicare **0.090**.
- **Ohio** — **918** facilities: **weighted** other-payer resident-day share **0.521**; **median** Medicare share **0.057**, **median** Medicaid **0.406**.
- **California** — **1,035** facilities: **weighted** Medicare day share **0.161**, Medicaid **0.463**, **median** occupancy **0.881**.

These are not rankings or moral scores. High Medicaid share does not imply poor care, and high occupancy does not imply good management. The point is narrower: national staffing comparisons are often too blunt without local operating context.

For public audiences, a **U.S. map** shaded by weighted Medicaid day share (with Overall / Rural / Urban views) is the clearest format.

<figure class="insight-chart">
<img src="/insights-cost-report-state-medicaid-tilemap-2023.svg" alt="U.S. state tile map shaded by weighted Medicaid day share of resident days in 2023. Darker blue indicates higher Medicaid share." width="860" height="520" loading="lazy" decoding="async" />
<figcaption><strong>Chart 3.</strong> U.S. state map (tile choropleth), shaded by weighted Medicaid day share (2023). Darker blue means a higher Medicaid day share.</figcaption>
</figure>

## How this helps PBJ320 ask better questions

<aside class="insight-workflow" aria-label="Review workflow">
<p class="insight-workflow__title">The workflow</p>
<ol class="insight-workflow__steps">
<li>Cost report signal</li>
<li>PBJ staffing check</li>
<li>Ownership / inspection / complaint / enforcement pass</li>
<li>Facility-specific question</li>
</ol>
</aside>

<p class="insight-workflow-example"><em>Illustrative (not causal):</em> a facility with low 2023 occupancy, heavy Medicaid day share, and worsening 2024–2025 PBJ staffing deserves closer review than a facility where only one signal appears.</p>

<aside class="insight-pbj320-fit" aria-label="Language for public-facing work">
<div class="insight-pbj320-fit__grid">
<div class="insight-pbj320-fit__col insight-pbj320-fit__col--is">
<p class="insight-pbj320-fit__label">Good verbs</p>
<p class="insight-pbj320-fit__text">Paired with, compared with, looked at alongside, helps flag questions.</p>
</div>
<div class="insight-pbj320-fit__col insight-pbj320-fit__col--ai">
<p class="insight-pbj320-fit__label">Bad verbs</p>
<p class="insight-pbj320-fit__text">Proves, explains away, caused.</p>
</div>
</div>
</aside>

<aside class="insight-fast-callout" role="note">
<strong>Data caveat:</strong> a “facility-year” sounds cleaner than the underlying data can be. In the CMS files PBJ320 uses, one provider-year bucket can include more than one fiscal reporting row.
</aside>

<p>In duplicate checks for 2023, about <strong>5.55%</strong> of provider-year groups had more than one row. Where duplicates materially diverged, the pattern was usually different fiscal windows and large swings in total resident days—for example, <strong>93.7%</strong> of material duplicate groups showed total-day spreads above 25% of the primary row, and <strong>100%</strong> had multiple fiscal date pairs.</p>

<p>That is why long, naive payer-mix trend lines require extra scrutiny, and why snapshots plus benchmarks often do more reliable public-facing work.</p>

<aside class="insight-source-directory" aria-label="What PBJ320 is doing next">
<p class="insight-source-directory__title">What PBJ320 is doing next</p>
<ul class="insight-source-directory__links insight-next-list">
<li><span class="insight-next-list__item"><strong>Pair</strong> 2023 cost-report occupancy and payer mix with newer PBJ staffing trends for the same facilities.</span></li>
<li><span class="insight-next-list__item"><strong>Build</strong> facility-level review queues instead of pretending one national average tells a story.</span></li>
<li><span class="insight-next-list__item"><strong>Compare</strong> rural and urban patterns inside states, not only at the national level.</span></li>
<li><span class="insight-next-list__item"><strong>Layer in</strong> ownership, inspections, complaints, and enforcement where the records support it.</span></li>
<li><span class="insight-next-list__item">Treat cost reports as <strong>context</strong>, not verdicts.</span></li>
</ul>
</aside>

<aside class="insight-sendoff" aria-label="Closing">
<p class="insight-sendoff__text">PBJ320 is adding cost reports because staffing data becomes more useful when read alongside occupancy, payer mix, ownership, inspections, and enforcement. No single file tells the full story.</p>
<p class="insight-sendoff__text">If you are building a case file, a newsroom investigation, or an advocacy brief, PBJ320 can connect cost-report patterns with PBJ staffing, ownership, inspection, and facility-level trend data.</p>
</aside>
