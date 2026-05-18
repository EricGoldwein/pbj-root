---
slug: use-pbj-data-with-ai
title: "How to Use PBJ Data with Claude, ChatGPT, or Whatever Robot You Currently Trust"
description: "Nine habits for public PBJ data + AI—attach files, cite HPRD, verify against CMS."
published: false
hideFromHub: true
date: 2026-05-16
author: Eric Goldwein
previewImage: /insights-use-pbj-ai-cover.png
coverCaption: "Good Bot vs. Bad Bot."
coverAlt: "Cartoon at PBJ Obedience School—a sandwich instructor rewards a robot with a chart while another bot scribbles nonsense on a flipchart."
readTime: 8 min read
category: pbj
tags: PBJ, AI, CMS, nursing home staffing, public data, Care Compare
---

You probably already use AI. You may have fed this page to ChatGPT before reading it. You may have asked Claude whether PBJ320 is a legitimate site. It is. That's fine—you're busy, and you'd probably rather doom scroll IG vids, watch the Knicks, take out the trash, or do basically anything else than read another "how to use AI" guide from a Brooklyn millennial with a Substack.

So I'll keep this useful.

The narrower point here: how to use **Payroll-Based Journal (PBJ)** staffing data with Claude, ChatGPT, Gemini, or whatever model you trust this week—without turning limited public data into a polished story that sounds smarter than it is.

<aside class="insight-fast-callout" role="note">
<strong>Fast version:</strong> attach real data, ask specific questions, make the model cite numbers, and treat the output as a draft—not a verdict.
</aside>

PBJ is **reported staffing hours** that nursing homes submit to CMS. It is public. You do not need PBJ320 to get it; [CMS publishes the files](https://data.cms.gov/provider-data/dataset/4pq5-n9py). PBJ320 just tries to make some of that easier to read. The source still matters more than any dashboard, including mine. Do not trust a clean UI because it looks clean. Do not trust an AI summary because it sounds confident. Check the source.

The models are not the hard part. The hard part is knowing what to attach, what to ask, and what not to believe. Below are nine habits that help—whether you are a reporter, advocate, family member, or counsel who would rather get to the point.

<div class="insight-tips-section">
<h2 class="insight-tips-heading">9 tips for using PBJ data with AI</h2>
<ol class="insight-tips-list">
<li><strong>Start with public sources, not a vibe.</strong> Before you ask a model anything, know where the data lives: Care Compare, CMS PBJ files, ProPublica, state inspection sites, and—when you need operating context—cost reports and ownership records. A clean UI is not a source. Neither is a confident paragraph.</li>
<li><strong>Give the model something concrete.</strong> Attach a CSV, a facility-page export, a screenshot, or a copied table. "Is this nursing home understaffed?" is too vague. "Using the attached PBJ data, explain what it shows, what it might suggest, what it cannot prove, and what I should verify next" is closer to useful.</li>
<li><strong>Make it cite numbers.</strong> If the output says staffing is "low" or "concerning," ask which HPRD values support that and compared to what—state median, the facility's own history, a state minimum, CMS case-mix reference, or nothing at all. Models love adjectives. Make them earn them.</li>
<li><strong>Always pair HPRD with census.</strong> Hours per resident day moves when staffing moves <em>and</em> when census moves. A facility can look better because it added nurses or because it had fewer residents. That distinction mattered during COVID and still matters when you compare quarters, owners, or peers.</li>
<li><strong>Look at trends, not one quarter.</strong> A single bad quarter can be important, but it is not the whole facility. Ask whether RN and aide staffing diverged, whether the pattern repeats, whether quarters are missing, and whether the facility usually runs hotter or colder than peers.</li>
<li><strong>Treat PBJ as context, not proof.</strong> PBJ can support reporting, advocacy, oversight, or discovery. It does not, by itself, prove neglect, harm on a specific shift, or causation. "The data raises questions about staffing during this period" is defensible. "The data proves the facility caused harm" is not.</li>
<li><strong>Ask what the data cannot show.</strong> Good analysis separates what the data shows, what it suggests, and what it cannot prove. Staffing files do not tell you what happened on Tuesday night, whether call bells went unanswered, or whether care met any one resident's needs.</li>
<li><strong>Use the AI you already use.</strong> Model theology matters less than clean inputs and a clear prompt.</li>
<li><strong>Edit the output like a skeptical human.</strong> Use AI to organize, summarize, and draft. Then read it the way a reporter, counsel, or daughter with a specific question would—and cut the beige ("robust," "crucial," "it is important to note"). People can feel lazy AI writing even when they cannot name it.</li>
</ol>
</div>

<aside class="insight-phoebe-callout">
  <img src="/phoebe.png" alt="Phoebe J" width="48" height="48" loading="lazy" decoding="async" />
  <div>
    <p class="insight-phoebe-callout__label">Phoebe J's takeaway</p>
    <p>Think of PBJ as the <strong>close-up</strong> and everything else—Care Compare, inspections, cost reports, interviews—as the <strong>wider shot</strong>. AI is good at summarizing the close-up. It is not good at inventing what happened on a Tuesday night shift. Give it real numbers, then make it show its work.</p>
  </div>
</aside>

<aside class="insight-source-directory" aria-label="Public data sources">
<p class="insight-source-directory__title">Start here (public data)</p>
<div class="insight-source-directory__grid">
<div class="insight-source-directory__col">
<h3 class="insight-source-directory__heading">Federal &amp; public sources</h3>
<ul class="insight-source-directory__links">
<li><a href="https://www.medicare.gov/care-compare/" target="_blank" rel="noopener noreferrer">CMS Care Compare</a><span class="insight-source-directory__desc">Consumer nursing home lookup</span></li>
<li><a href="https://data.cms.gov/provider-data/dataset/4pq5-n9py" target="_blank" rel="noopener noreferrer">CMS PBJ public files</a><span class="insight-source-directory__desc">Raw staffing &amp; census data</span></li>
<li><a href="https://projects.propublica.org/nursing-homes/" target="_blank" rel="noopener noreferrer">ProPublica Nursing Home Inspect</a><span class="insight-source-directory__desc">Inspections &amp; penalties</span></li>
<li><a href="https://data.cms.gov/provider-data/topics/nursing-homes" target="_blank" rel="noopener noreferrer">CMS nursing home datasets</a><span class="insight-source-directory__desc">Provider info &amp; related files</span></li>
</ul>
</div>
<div class="insight-source-directory__col">
<h3 class="insight-source-directory__heading">On PBJ320</h3>
<ul class="insight-source-directory__links">
<li><a href="/">Facility lookup</a><span class="insight-source-directory__desc">Provider pages, charts, exports</span></li>
<li><a href="/ai/prompts">Copyable AI prompts</a><span class="insight-source-directory__desc">Starter text by audience</span></li>
<li><a href="/pbj-ai-support">AI support guide</a><span class="insight-source-directory__desc">Workflows and review modes</span></li>
</ul>
</div>
</div>
</aside>

## What PBJ can and cannot tell you

The number people argue about most is **HPRD**—hours per resident day: reported staff time by role, relative to resident census. That can surface low RN staffing, heavy aide reliance, weekend patterns, odd quarters, operator changes, and facilities that look off compared with peers.

It does **not** automatically tell you whether neglect occurred, whether a specific resident was harmed, whether the home broke the law, or what happened on one shift. PBJ is evidence you still have to pair with inspections, complaints, interviews, schedules, and facility response.

<figure class="insight-chart">
<img src="/seagate_staffing_pbj.png" alt="Example PBJ320 facility staffing chart: reported nurse hours per resident day over time compared with a state minimum reference line." width="820" height="auto" loading="lazy" decoding="async" />
<figcaption>At <a href="/provider/335513">Seagate Rehabilitation and Nursing Center</a> (NY), reported nurse HPRD runs mostly below the state minimum reference line across the quarters shown here.</figcaption>
</figure>

<h3 class="insight-section-heading">What about Claude Skills, GPTs, and plugins?</h3>

<p>Skills, custom GPTs, and plugins only help when you give them structured prompts and real attachments—not vibes. PBJ320 keeps a <a href="/ai/prompts">library of copyable prompts</a>, an <a href="/pbj-ai-support">AI support guide</a>, and a <a href="/downloads/pbj320-staffing-review.zip">downloadable Claude Skill package</a> for staffing review. Use them as draft instructions; CMS filings and your own judgment still decide what holds up.</p>

<aside class="insight-sendoff" aria-label="Closing">
<p class="insight-sendoff__text">Start with the public data. If AI or PBJ320 help you ask a sharper question, use them—then check what you get against CMS, state records, the building, and the people who live there. Neither a dashboard nor a chat transcript is the answer.</p>
<p class="insight-sendoff__text">Stuck on a facility, a chain, or a pattern in the filings?</p>
<p class="insight-sendoff__actions"><a class="insight-sendoff__btn" href="/about?open=contact">Book a free 30-minute PBJ consult with Eric</a></p>
</aside>

<aside class="insight-colophon" aria-label="Assisted by Phoebe J.">
<img class="insight-colophon__avatar" src="/phoebe.png" alt="Phoebe J" width="44" height="44" loading="lazy" decoding="async" />
<div class="insight-colophon__content">
<p class="insight-colophon__label">Assisted by Phoebe <span class="insight-colophon__sublabel">(PBJ320's AI assistant)</span></p>
<p class="insight-colophon__body">This piece took shape after I read about <a href="https://free.law/2026/05/12/courtlistener-is-now-available-inside-claude/" target="_blank" rel="noopener noreferrer">how CourtListener landed inside Claude</a>—not because "AI is the future," but because Free Law Project is wiring real legal data into models instead of letting them invent citations. PBJ has the same problem in miniature: public, technically accessible, and still a pain to use well. I used AI to think through an outline, wrote a draft, hated how AI it sounded, and revised it. The trick is not letting that last step disappear.</p>
</div>
</aside>
