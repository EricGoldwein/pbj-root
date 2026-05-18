"""PBJ320 Staffing Review Framework — shared core + audience/geography modifiers.

Default mode: analyst (existing shows / suggests / cannot prove flow).
Infrastructure for future one-click mode toggles; no duplicate full prompts per audience.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

DEFAULT_AUDIENCE = 'analyst'
DEFAULT_GEOGRAPHY_LEVEL: Optional[str] = None

PBJ_REVIEW_CONTEXT_LEVELS: dict[str, str] = {
    'national': 'National',
    'state': 'State',
    'region': 'Region',
    'county': 'County',
    'city': 'City',
    'facility': 'Facility',
    'ownership_group': 'Ownership Group',
}

VALID_AUDIENCES = frozenset({
    'analyst',
    'journalist',
    'advocate',
    'ombudsman',
    'family_resident',
    'attorney',
    'legislator',
    'operator',
    'researcher',
})

OUTPUT_TIER_BRIEF = 'brief'
OUTPUT_TIER_STANDARD = 'standard'
OUTPUT_TIER_DETAILED = 'detailed'

OUTPUT_TIER_BY_AUDIENCE: dict[str, str] = {
    'family_resident': OUTPUT_TIER_BRIEF,
    'advocate': OUTPUT_TIER_STANDARD,
    'ombudsman': OUTPUT_TIER_BRIEF,
    'journalist': OUTPUT_TIER_STANDARD,
    'legislator': OUTPUT_TIER_STANDARD,
    'operator': OUTPUT_TIER_STANDARD,
    'analyst': OUTPUT_TIER_STANDARD,
    'attorney': OUTPUT_TIER_DETAILED,
    'researcher': OUTPUT_TIER_DETAILED,
}

# (regex fragment, audience) — first strong match wins; order matters
AUDIENCE_DETECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r'\b(my|our)\s+(mother|father|parent|husband|wife|loved\s+one)\b', 'family_resident'),
    (r'\bfamily\s+member\b|\bresident\s+with\b', 'family_resident'),
    (r'\bombuds(man|person|people|program)?\b', 'ombudsman'),
    (r'\b(advocate|advocacy|coalition|accountability)\b', 'advocate'),
    (r'\b(complaint|oversight)\b.*\b(facilit|staff)', 'advocate'),
    (r'\b(reporter|journalist|newsroom|publication|story\s+angle|article)\b', 'journalist'),
    (r'\b(attorney|counsel|litigation|plaintiff|discovery|exhibit)\b', 'attorney'),
    (r'\bincident\s+(date|window)\b', 'attorney'),
    (r'\b(legislator|senator|representative|policymaker)\b', 'legislator'),
    (r'\b(policy|bill|oversight\s+hearing|committee)\b', 'legislator'),
    (r'\b(our\s+facility|our\s+dashboard|administrator|director\s+of\s+nursing)\b', 'operator'),
    (r'\b(study|methodology|dataset|academic|regression|coefficient)\b', 'researcher'),
)

PBJ_SOURCE_LEVEL_COPY: dict[str, str] = {
    'free_facility': (
        'PBJ320 provider page / quarterly CSV. This supports quarterly facility-level review only. '
        'Do not assume daily staffing, weekend patterns, agency reliance, mean/median tables, incident-window analysis, '
        'employee-level staffing, or 90-day aide/CNA day counts unless shown.'
    ),
    'free_state': (
        'PBJ320 state page. This page provides state-level quarterly staffing context, visible aggregate metrics, '
        'and facility comparison context where shown. Do not assume daily staffing, incident-window detail, '
        'employee-level data, or facility-specific conclusions unless those data are explicitly provided.'
    ),
    'free': (
        'PBJ320 page: quarterly staffing context and visible metrics on the page. '
        'Do not assume daily staffing or premium-only fields unless shown.'
    ),
    'premium': (
        'Premium PBJ320 dashboard/export: may include daily staffing, 90-day aide/CNA patterns, '
        'trend tables, mean/median/outlier checks, incident-window context, and evidence-packet materials.'
    ),
}

OUTPUT_TIER_SECTIONS: dict[str, list[tuple[str, str]]] = {
    OUTPUT_TIER_BRIEF: [
        (
            'What the data shows',
            '1–3 sentences. Plain English where helpful. Embed the required data-visual outcome from the DATA '
            'VISUAL rule (meaningful compact graphic/table, chart-ready Markdown, or a brief explicit '
            '"why none"—see Presentation block).',
        ),
        ('What the data does not show', 'Only relevant limits for this query.'),
        ('Questions worth asking', 'Up to 5 specific questions.'),
    ],
    OUTPUT_TIER_STANDARD: [
        (
            'Provisional bottom line',
            '2–3 sentences. Be accurate and provisional. Lead with the strongest thing the data actually shows, not a conclusion.',
        ),
        (
            'Key staffing signals',
            'Signals grounded in the material. Apply DATA VISUAL rule + audience framing under Presentation — '
            'one clarifying exhibit at most when it strengthens that headline; chart-ready Markdown or explicit omission '
            'reason otherwise.',
        ),
        ('What the data shows', 'Directly supported conclusions.'),
        ('What the data may suggest', 'Cautious interpretations worth further review.'),
        ('What the data cannot prove', 'Filtered limits — only what applies to this query.'),
        ('Questions to ask next', 'Up to 5 audience-specific questions.'),
    ],
    OUTPUT_TIER_DETAILED: [
        (
            'Issue / context',
            'Brief framing of what was reviewed and the review scope.',
        ),
        (
            'Key staffing signals',
            'Evidence-bound signals tied to analytic gate. DATA VISUAL rule + audience framing (Presentation): '
            'one meaningful exhibit when warranted; sophisticated charts only when they serve the headline evidence.',
        ),
        ('Analytic checks', 'Report gate results: date range, mean/median, census, comparison group, outliers, data quality, source level.'),
        ('What the data shows', 'Directly supported conclusions.'),
        ('What the data may suggest', 'Cautious interpretations worth further review.'),
        ('What the data cannot prove', 'Filtered limits — only what applies to this query.'),
        ('Records or context to request', 'Specific records that would verify or deepen the review.'),
        ('Questions to ask next', 'Up to 5 audience-specific questions.'),
    ],
}

VALID_GEOGRAPHY_LEVELS = frozenset(PBJ_REVIEW_CONTEXT_LEVELS.keys())

# --- Shared core (all modes) ---

PBJ_REVIEW_CORE_LIMITATIONS = (
    'PBJ data can show reported staffing hours, role mix, facility-level patterns, and changes over '
    'time. It cannot prove what happened on a specific shift, whether a specific resident received '
    'care, whether staffing caused an injury, whether reported staffing data is complete or accurate '
    'without further records, or whether a facility violated a legal standard.'
)

PBJ_REVIEW_CORE_CHECKS = [
    'Run the analytic gate before interpreting: date range/sample size, mean vs median, census stability, comparison group, outliers, data quality, free vs premium source level.',
    'Fulfill DATA VISUAL rule (Presentation block): strongest-supported finding clarified by one concise exhibit—or chart-ready Markdown—or explicit omission with reason.',
    'If census declined during the period, HPRD may appear higher without any actual staffing increase.',
    'If the period overlaps 2020-01-01 through 2023-12-31, apply pandemic-era longitudinal rules: do not conclude “staffing improved” from HPRD alone; pair HPRD with census and total hours where available; treat contract/agency mix as workforce continuity, not care quality; avoid peak-disruption quarters as silent “normal” baselines; separate facility facts from national or state aggregate narratives (see Pandemic-era block in the prompt).',
    'State averages may mask wide within-state variation — note peer-group limits when relevant.',
    'If daily aide or CNA data is available, assess whether low aide staffing is isolated or repeated across the quarter.',
    'Treat red flags as screening signals, not findings.',
]

PBJ_REVIEW_CORE_RULES = """Use cautious, evidence-based language. Do not assume neglect, misconduct, negligence, causation, or legal violations. Do not invent facts not shown in the material. If something is unclear, say what additional information would be needed.

When referring to the source, describe it as "the PBJ320 facility page," "the PBJ320 dashboard," "the PBJ320 report," or "the PBJ320 export," and distinguish PBJ320's presentation from the underlying CMS Payroll Based Journal data.

When the material lists canonical URLs, keep them verbatim for readers (e.g. `https://pbj320.com/provider/<CCN>`, `https://pbj320.com/state/<slug>`, `https://pbj320.com/entity/<id>`, `https://pbj320.com/report`, `https://pbj320.com/sff`, or CMS Care Compare nursing-home deep links such as `https://www.medicare.gov/care-compare/details/nursing-home/<CCN>/view-all?state=XX`). Use both: **CMS** as the origin of submitted PBJ and Care Compare star/survey context, and **PBJ320 / 320 Consulting** as the site that organizes, charts, or narrates that public data—do not collapse the two."""

PBJ_REVIEW_HANDOFF_PLACEHOLDER = '[PASTE PBJ320 PAGE TEXT, SCREENSHOT, CSV, OR EXPORT HERE]'

PBJ_QUICK_PROMPT_TEXT = """Use the PBJ320 Staffing Review Framework to review this PBJ320 page, screenshot, dashboard, CSV, or export.

First identify:
1. the likely audience or use case: family, advocate, ombudsman, journalist, attorney, policymaker, operator, researcher, or general analyst;
2. whether this appears to be a quarterly PBJ320 provider or state page, or a premium daily/export view.

Then explain:
- what the material shows,
- what it may suggest,
- what it cannot prove,
- and what questions to ask next.

Check for sample size, mean vs median, outliers, census/denominator effects, comparison group, bad or incomplete data, and whether the available source is deep enough for the question.

If the material covers or compares across **2020 through 2023**, apply **pandemic-era PBJ context**: do not describe higher HPRD as “staffing improved” without census and total hours; treat contract staffing as a workforce/continuity signal, not proof of poor care; flag weak trend baselines in peak-COVID quarters; do not substitute national narratives for facility-specific evidence; on quarterly pages, do not infer daily contract or weekend patterns without those fields.

If reviewing a PBJ320 facility page, focus on quarterly staffing context and visible facility-level metrics. Do not assume daily staffing, weekend patterns, 90-day aide/CNA day counts, agency reliance, mean/median tables, or incident-window detail unless shown.

If reviewing a PBJ320 state page, focus on state-level quarterly patterns, visible comparison metrics, distribution/percentile context, and what facility-level or premium data would be needed to support more specific claims. Do not infer individual facility conditions unless facility-level data is provided.

If reviewing a premium PBJ320 dashboard or export, use the daily staffing, trend, mean/median, outlier, 90-day aide/CNA, incident-window, or export fields only if they are explicitly shown or provided.

If reviewing a live page or screenshot, identify what is visible, what is missing, what is cut off, and what cannot be assessed.

If copied page text includes CSS, navigation labels, widget controls, repeated buttons, or unrelated UI artifacts, ignore them and focus only on PBJ320 staffing metrics, definitions, and explanatory text.

Apply the DATA VISUAL rule (see Presentation block): one meaningful audience-appropriate visual tied to the strongest supported finding—or chart-ready Markdown with exact supplied values—or a concise explanation of why neither is possible. Do not graph irrelevant patterns just because quarterly numbers exist.

Use cautious, evidence-based language. Do not assume neglect, misconduct, causation, or legal violations. In the 'cannot prove' section, list only limitations relevant to the material and question."""

PBJ_REVIEW_RESPONSE_STRUCTURE = """Structure your response:
- What the material shows (include DATA VISUAL outcome: graphic/table, chart-ready spec, or explicit omission—see Presentation in full framework)
- What it may suggest
- What it cannot prove
- Questions to ask next

Check sample size, mean vs median, outliers, census/denominator effects, comparison group, and data quality. If the period overlaps **2020–2023**, also apply the pandemic-era HPRD/census/contract baseline rules in the prompt (see Pandemic-era longitudinal context)."""

# --- Layered prompt architecture (stable framework + injected context) ---

PBJ_LAYERED_TASK = (
    'Explain what this PBJ320 page or export shows, what it may suggest, what it cannot prove, '
    'and what questions to ask next.'
)

PBJ_LAYERED_TONE = (
    'Use cautious, plain-English, evidence-based language. Do not allege neglect, misconduct, '
    'causation, or legal violations.'
)

# When material date range overlaps 2020–2023 or compares across that window.
PBJ_REVIEW_HISTORICAL_CONTEXT_BLOCK = (
    'Pandemic-era / longitudinal context — apply when any reviewed period overlaps **2020-01-01 through '
    '2023-12-31**, or compares to quarters in that window:\n'
    '- **HPRD vs staffing level:** Rising HPRD can reflect **census / resident-day denominator** drops, '
    'not increased staffing. Use **average daily census** and HPRD together when both appear in the context '
    'or embedded quarterly CSV; check **total nurse hours** (or category hours) **before** any '
    '“improvement,” “better staffed,” or “staffing rose” narrative.\n'
    '- **Contract / agency share:** Treat as **workforce supply, turnover, and continuity** signal — **not** '
    'proof of poor care and **not** causal for harm or quality without non-PBJ evidence.\n'
    '- **Baselines:** Peak disruption / sharp census-movement quarters (especially **2020**, often **early–mid '
    '2021**) are **weak neutral baselines** for long-run trends; say so or use alternative reference periods '
    'when possible.\n'
    '- **Scale:** National or state aggregate patterns **do not** determine what happened at a **specific '
    'facility** — keep them separate.\n'
    '- **Source depth:** Free quarterly PBJ320 packets include quarterly HPRD, CMS case-mix reference values, '
    'and average daily census by quarter when CMS reported them. They do not include daily staffing, weekend '
    'patterns, 90-day aide patterns, or employee-level rows — state what is missing rather than inferring.'
)

PBJ_AUDIENCE_TIMING_EMPHASIS_BLOCK = (
    'Audience-specific timing emphasis (subtle — do not reshape the whole analysis):\n'
    'When interpreting staffing trends, weigh recency differently depending on the audience, but do not '
    'ignore the full historical pattern.\n'
    '- **Family:** Usually most concerned with the **latest available** staffing picture; still note older '
    'trends when they materially affect interpretation.\n'
    '- **Ombudsman:** Tends to prioritize **recent quarters** (present resident conditions, complaints, oversight '
    'priorities); still flag older patterns when they matter.\n'
    '- **Attorney:** Often needs a **longer historical view** (ownership changes, incident windows, pre/post '
    'comparisons, recurring staffing patterns).\n'
    '- **Journalist:** May need recent findings, longer-term trends, or **both** — match the story angle.\n'
    'Continue to report what the data shows, what it may suggest, and what it cannot prove. Recent quarters '
    'deserve extra attention for family and ombudsman audiences; note older trends when they materially affect '
    'interpretation.'
)

# Compact instructions for ChatGPT URL prefill (?q=); {audience_label} filled client-side.
PBJ_CHATGPT_REVIEW_STUB_TEMPLATE = (
    'PBJ320 staffing review. Audience: {audience_label}. '
    'Use the message text below, the pasted full review packet, and/or an uploaded PBJ320 snapshot .txt as your evidence (paste + snapshot together is strongest). '
    'Quarterly PBJ is a screening layer for oversight priorities — not proof of noncompliance, neglect, causation, or care quality. '
    'CMS case-mix nursing HPRD on the page is an acuity-adjusted comparison/reference value — not a legal minimum and not a staffing-sufficiency determination. '
    'MACPAC (https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/) is a credible state-policy compendium; any MACPAC-derived HPRD line is an estimated policy reference for orientation — verify current statute, regulations, waivers, and calculation rules before any compliance claim. '
    'If dates overlap 2020–2023 or N-1 trends span that window: do not equate higher HPRD alone with staffing improvement — check census and total hours; treat contract staffing as workforce continuity, not care quality; avoid peak-COVID baselines for “normal” longitudinal claims (national CMS/PBJ sources include ASPE issue briefs on PBJ during COVID). '
    'Report only what the material shows. If the attachment is thin, say what is missing. '
    'Include one value-grounded data visual (or chart-ready Markdown / explicit why none) tied to the strongest supported finding in the material.'
)

PBJ_VISUAL_SELECTION_RULE = (
    'Include one audience-appropriate data visual **only when** it clarifies the **strongest finding the supplied '
    'material supports** (do not chart for decoration). Choose from data shape and likely reader question: '
    '**trend**; **comparison** (peer/state/reference); **role mix**; **contract reliance**; **census/denominator effect** '
    'alongside HPRD; **incident window** (only with daily/incident-aligned rows—never implied from quarterly alone); '
    '**reference gap** (CMS case-mix, policy/MACPAC-style lines—label correctly); **outlier / low-tail** when percentiles '
    'support it. **Use only supplied values.** Skip the visual when prose alone is clearer. If no meaningful visual is '
    'possible, state succinctly what data are missing.'
)

PBJ_VISUAL_COMPLETENESS_FALLBACK_ATTRIBUTION = (
    '**Completeness:** A review is incomplete until this is satisfied — **either** one such meaningful visual (compact '
    'Markdown table, simple ASCII trend, or one small Mermaid figure, at most **one**) **or** chart-ready Markdown with '
    'title, chart type, exact values copied, one-sentence takeaway, and limitation **or**, if neither applies, **an '
    'explicit statement** why no meaningful visual can be produced. '
    'Audience informs framing/language/disclaimers — **never** overriding evidence nor forcing an irrelevant graphic. '
    'If the visual could be screenshots alone, include one concise attribution line for PBJ320/CMS-sourced staffing and '
    'keep any Care Compare or `pbj320.com` links already in context.'
)

PBJ_VISUAL_OUTPUT_HINT = (
    'DATA VISUAL (required — self-contained; no external skill file needed for beta):\n'
    + PBJ_VISUAL_SELECTION_RULE
    + '\n\n'
    + PBJ_VISUAL_COMPLETENESS_FALLBACK_ATTRIBUTION
)

PBJ_AUDIENCE_VISUAL_FRAMING: dict[str, str] = {
    'family_resident': (
        'Plain labels (spell out hours-per-resident-day); simplest table or sparkline only; pair with caregiver questions.'
    ),
    'advocate': (
        'Screening tone beside the figure; elevate comparisons, contract share, census effects, tails vs peers — only if '
        'they carry the headline finding.'
    ),
    'ombudsman': (
        'Conversation-ready labels; resident-experience-oriented caption; neutral, non-accusatory qualifiers.'
    ),
    'journalist': (
        'Align with strongest defensible story line; annotate what remains unverified before publication.'
    ),
    'attorney': (
        'Evidentiary labels; quarterly visuals explicitly carry timing/discipline caveats absent daily/incident-aligned data.'
    ),
    'legislator': (
        'Briefing-ready; benchmarks as screening/orientation—not PASS/FAIL or facility attack.'
    ),
    'operator': (
        'How regulators, media, or families may read the same pattern; annotate uncertainty crisply.'
    ),
    'researcher': (
        'Methods-forward caption beside the figure — denominators, census/case-mix confounds as relevant.'
    ),
    'analyst': ('Neutral captions; methodological caveats where they change interpretation.'),
}


def audience_visual_framing_block(audience: str) -> str:
    aud = normalize_audience(audience)
    bullet = PBJ_AUDIENCE_VISUAL_FRAMING.get(aud) or PBJ_AUDIENCE_VISUAL_FRAMING['analyst']
    return (
        'Audience visual framing (**labels/disclaimers only** — defer to DATA VISUAL rule above for whether to '
        f'chart and which pattern matters):\n- {bullet}'
    )

PBJ_LAYERED_OUTPUT_QUICK = """1. What the data shows
2. What it may suggest
3. What it cannot prove
4. Questions to ask next
5. Bottom line (1–2 sentences)
6. Data-visual completeness (per Presentation: meaningful exhibit, chart-ready Markdown, or explicit why none—audience informs framing only)"""

PBJ_LAYERED_OUTPUT_STANDARD = """1. Audience / use case (brief)
2. Source type and limits
3. What the data shows
4. What it may suggest
5. What it cannot prove
6. Questions to ask next
7. Bottom line
8. Data-visual completeness (per Presentation — same criterion as layered quick format)"""

PBJ_LAYERED_OUTPUT_DETAILED = PBJ_LAYERED_OUTPUT_STANDARD

PBJ_AUDIENCE_MODE_DISPLAY: dict[str, str] = {
    'general': 'GENERAL ANALYST',
    'family': 'FAMILY',
    'advocate': 'ADVOCATE',
    'ombudsman': 'OMBUDSMAN',
    'journalist': 'JOURNALIST',
    'attorney': 'ATTORNEY',
    'policymaker': 'LEGISLATOR / POLICYMAKER',
    'operator': 'OPERATOR',
    'researcher': 'RESEARCHER',
}

PBJ_PROVIDER_CSV_SOURCE_DEPTH_NOTE = '''Source-depth check — attached spreadsheets:
- If a CSV or spreadsheet appears to be **only one row** for a single quarterly period, treat it as the same summarized provider-page staffing context structured as CSV. Say explicitly that **it does not add** daily staffing, multi-quarter longitudinal rows, incident-window staffing, employee-level staffing, agency mix, comparisons across facilities, premium-only analyses, state statutory staffing calculations, or resident-level conclusions.
- If the attached file **clearly contains** multiple quarterly rows, daily rows, additional facilities/CCNs, or columns labeled as state staffing standards/regulatory fields, Five-Star histories, inspections, MACPAC-derived fields, enforcement actions, survey findings, incident dates, staffing star ratings versus time, census by day—**use only columns and rows that are visibly present.** Do **not invent** missing fields from industry practice.
Language rule: Prefer 'check,' 'compare against,' 'would need to verify,' and 'relevant follow-up source.' Avoid 'violated,' 'failed to meet,' 'illegal,' 'noncompliant,' and 'understaffed under state law' unless **both** an explicit legal standard **and** the calculation inputs needed to apply it are provided in the material.'''

PBJ_PROVIDER_STATE_SUPPLEMENT_INTRO = (
    'State-specific context:\n'
    'This facility is in **{state}**. Before making any **state-law, compliance, or policy claim**, '
    'identify what **state-specific** staffing rule text, citation, enforcement interpretation, '
    'inspection or complaint record set, Medicaid payment policy memo, CMS Care Compare staffing history, '
    'or MACPAC/state-standard benchmark note would **need to be checked** alongside PBJ totals. '
    '**CMS Payroll-Based Journal (PBJ)** metrics and CMS **case-mix nursing HPRD** benchmarks are '
    'different things from—and not interchangeable with—**state staffing laws or staffing standards** '
    '(which may combine nurse categories differently or use different denominators).\n'
    'Treat statutory or regulatory staffing comparisons only as **follow-up factsets** unless the '
    'relevant citations, numerator/denominator rules, exclusions, exemptions, staffing definitions, '
    'and contemporaneous staffing inputs are explicitly provided.'
)

_PROVIDER_STATE_BODY_BY_LENS: dict[str, str] = {
    'general': (
        'General mode — jurisdiction awareness:\n'
        '- Explain **why state context matters**: licensing, complaint processes, staffing rule sets, oversight.\n'
        '- Direct readers to plausible follow-up domains (Care Compare staffing history table, CMS survey scope, MACPAC summaries, Medicaid rate memos).\n'
        '- Do **not** claim compliance/noncompliance with state staffing law without citation + denominator rules + inputs.'
    ),
    'journalist': (
        '## State-specific reporting context ({state})\n'
        '{ny_examples}\n'
        '- Outline **what state standard/policy context deserves checking** versus what PBJ totals alone demonstrate.\n'
        '- Identify **specific record types**: state survey/complaint portals, citation databases, staffing star history, staffing-related enforcement letters, archived inspection PDFs.\n'
        '- Separate language that is safe now (visible comparison over time, explicit definitions) versus **not publishable yet** (legal/regulatory accusations without corroborating records).\n'
        '- Suggested questions for **facility PIO/admin**, **state DOH/unit**, **CMS media office or subject-matter analysts**, **ombuds**, **Medicare/Medicaid plan counsel**, residents/families (care conferences).\n'
        'Do **not only** summarize staffing numbers — explain **what would make findings publishable for {state}**, which **state-administered datasets** merit requests, interview angles, FOIL/FOIA path where applicable.\n'
        'Audience reminder: Explain what should be checked **before** publishing compliance or negligence-adjacent language for {state}.\n'
        'Audience line: Explain what would help make reporting **publishable in {state}**, keeping claims proportionate until verified.'
    ),
    'advocate': (
        '## State advocacy context ({state})\n'
        '{ny_examples}\n'
        '- Outline **resident complaint portals** maintained by **{state}** health oversight and escalation paths.\n'
        '- Flag **Long-Term Care Ombudsman** relevance (facility-level escalation, visitation issues, retaliation concerns)—**ask** what is feasible in {state}; do **not imply** retaliation occurred.\n'
        '- Mention **staffing-rule context**: **check** statutes/admin rules—not infer adequacy—from PBJ.\n'
        '- Questions appropriate for facility council/family councils/ombuds/state hotlines.\n'
        '- Use cautious **public-accountability wording** oriented around **verification**.'
    ),
    'ombudsman': (
        '## Ombudsman / resident-directed context ({state})\n'
        '{ny_examples}\n'
        '- Position staffing data as **conversation prep**, not proof. Ombudsmen are **not** regulators, prosecutors, or finders of fact.\n'
        '- Point to **practical public resources**: **state/local Long-Term Care Ombudsman Program** (coordinator contact), '
        '**Medicare.gov Care Compare** for this facility, CMS survey/certification materials where relevant, **state licensing / complaint** portals, '
        'and navigation help such as **Eldercare Locator** (ACL). Verify current URLs/forms before citing.\n'
        '- Emphasize **resident goals, consent, dignity, and retaliation sensitivity**; avoid legal conclusions and sensational language.\n'
        '- **Do not** prioritize upsells for paid PBJ320 dashboards; keep optional premium mentions to one line if the user already uses them.\n'
        '- When state-specific bullets appear above (e.g. Connecticut LTCOP contacts or MACPAC orientation), treat them as **authoritative anchors** for that jurisdiction.\n'
    ),
    'family': (
        'State context — plain language ({state})\n'
        '{ny_examples}\n'
        '- Suggest caregivers **ask how** staffing on specific shifts aligns with expectations and **whether** it meets publicly posted benchmarks—**asking is not asserting** statutory compliance.\n'
        '- Suggest caregivers **contact the ombudsman** or **{state}** health/licensing office to learn **what records exist**.\n'
        '- Explain that **Quarterly staffing reports** summarize facility-wide hours per resident-day; they cannot show bedside-level reality.\n'
        '- Avoid deep MACPAC or regulatory tables here unless the caregiver advanced into a detailed review tier.'
    ),
    'family_resident': (
        'State context — plain language ({state})\n'
        '{ny_examples}\n'
        '- Suggest caregivers **ask how** staffing on specific shifts aligns with expectations and **whether** it meets publicly posted benchmarks—**asking is not asserting** statutory compliance.\n'
        '- Suggest caregivers **contact the ombudsman** or **{state}** health/licensing office to learn **what records exist**.\n'
        '- Explain that **Quarterly staffing reports** summarize facility-wide hours per resident-day; they cannot show bedside-level reality.'
    ),
    'attorney': (
        '## State/legal factset needed ({state})\n'
        '{ny_examples}\n'
        '- Identify **specific statutory/regulatory citations** practitioners would verify (cite only if verbatim in attachments).\n'
        '- Incident **dates/windows** supplied or missing—and why **premium/daily staffing** extracts may be warranted for timing-heavy theories.\n'
        '- Separate **facility medical records**, **staff schedules**, payroll or agency-contract discovery targets from quarterly PBJ.\n'
        '- Note **survey, complaint, citation, CMP, directed-in-service** records available through CMS/state portals would need reconciliation.\n'
        '- Screening rule: quarterly PBJ does **not** establish negligence **or statutory violation** by itself.\n'
        '- **Use PBJ320 as screening context.** Identify **which state/legal factsets and facility-held records would be prerequisite** before describing a plausible legal theory, compliance characterization, damages theory, or causation narrative.'
    ),
    'researcher': (
        '## State comparison design ({state})\n'
        '{ny_examples}\n'
        '- Compare **within-{state}** peers (percentiles, strata) before implying national exceptionalism.\n'
        '- Where possible stratify within **county/market**, **ownership/operator cohort**, comparable **CMS case-mix/CMI** bands.\n'
        '- Use **multiple quarters/years**: separate seasonality narrative from staffing trend shifts.\n'
        '- Maintain distinction between reported nursing HPRD, CMS case-mix benchmark, staffing star timelines, statutory minimum conceptualizations (**only if spelled out **), and citations.'
    ),
    'policymaker': (
        '## Legislator / policymaker lens ({state})\n'
        '{ny_examples}\n'
        '- Frame a single facility as an **illustration** of how quarterly PBJ informs **public oversight, staffing policy, '
        'chain accountability, Medicaid/payment policy, and data transparency** — not as an attorney-style enforcement memo, '
        'single-facility attack brief, or proof of wrongdoing without corroborating records.\n'
        '- **MACPAC**, *State Policies Related to Nursing Facility Staffing* '
        '(https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/), summarizes **state staffing standards '
        'and related Medicaid payment policies**. Treat any MACPAC-derived {state} minimum or band shown on PBJ320 as an **estimated '
        'policy benchmark / orientation point** (especially if translated into PBJ-style HPRD). **Do not** conclude the facility passed '
        'or failed {state} law from that line. Use language such as: “MACPAC-derived {state} staffing policy reference: approximately X '
        'HPRD — estimated / orientation only; verify against current statute, regulations, waivers or exemptions, and calculation rules '
        'before any compliance claim.”\n'
        '- **CMS case-mix nursing HPRD** (when shown) is an **acuity-adjusted comparison value** on the page — **not** a legal minimum '
        'and **not** a staffing-sufficiency determination. Prefer: “Reported total nurse HPRD was about X% of the CMS case-mix reference '
        'value shown on the page — **a screening comparison, not a compliance finding or standalone sufficiency judgment**.”\n'
        '- **Percentiles / ranks:** avoid vague multi-year tails (“bottom 10–20% most of the period”) unless the rows or chart clearly '
        'support them. Prefer: “Since 2021, generally in the lower tail by total nurse HPRD, often near or below the 15th percentile **where '
        'percentiles are shown**.” If consecutive quarters are not verifiable from the attachment, say “many quarters since 2021” or '
        '“the quarters visible here.”\n'
        '- **Entity / chain context:** policy-relevant only. Do **not** infer chain misconduct from one facility page. Prefer: '
        '“Chain-level review would help determine whether this profile is isolated, concentrated among certain facilities, or associated '
        'with broader ownership-level operating patterns.” Facility counts, entity IDs, states, or star averages — quote **only** as '
        '“reported on PBJ320” when shown; if uncertain, soften or omit exact figures.\n'
        '- **Tone:** screening signal, merits closer review, policy benchmark, orientation point, requires verification, '
        'not a standalone compliance finding. Avoid *proves*, *violates*, *noncompliant*, *neglect*, *misconduct*, '
        '*active monitoring list*, *staffing failure* unless inspection, enforcement, complaint, or legal records support it.\n'
    ),
    'legislator': (
        '## Legislator / policymaker lens ({state})\n'
        '{ny_examples}\n'
        '- Frame a single facility as an **illustration** of how quarterly PBJ informs **public oversight, staffing policy, '
        'chain accountability, Medicaid/payment policy, and data transparency** — not as an attorney-style enforcement memo, '
        'single-facility attack brief, or proof of wrongdoing without corroborating records.\n'
        '- **MACPAC**, *State Policies Related to Nursing Facility Staffing* '
        '(https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/), summarizes **state staffing standards '
        'and related Medicaid payment policies**. Treat any MACPAC-derived {state} minimum or band shown on PBJ320 as an **estimated '
        'policy benchmark / orientation point** (especially if translated into PBJ-style HPRD). **Do not** conclude the facility passed '
        'or failed {state} law from that line. Use language such as: “MACPAC-derived {state} staffing policy reference: approximately X '
        'HPRD — estimated / orientation only; verify against current statute, regulations, waivers or exemptions, and calculation rules '
        'before any compliance claim.”\n'
        '- **CMS case-mix nursing HPRD** (when shown) is an **acuity-adjusted comparison value** on the page — **not** a legal minimum '
        'and **not** a staffing-sufficiency determination. Prefer: “Reported total nurse HPRD was about X% of the CMS case-mix reference '
        'value shown on the page — **a screening comparison, not a compliance finding or standalone sufficiency judgment**.”\n'
        '- **Percentiles / ranks:** avoid vague multi-year tails (“bottom 10–20% most of the period”) unless the rows or chart clearly '
        'support them. Prefer: “Since 2021, generally in the lower tail by total nurse HPRD, often near or below the 15th percentile **where '
        'percentiles are shown**.” If consecutive quarters are not verifiable from the attachment, say “many quarters since 2021” or '
        '“the quarters visible here.”\n'
        '- **Entity / chain context:** policy-relevant only. Do **not** infer chain misconduct from one facility page. Prefer: '
        '“Chain-level review would help determine whether this profile is isolated, concentrated among certain facilities, or associated '
        'with broader ownership-level operating patterns.” Facility counts, entity IDs, states, or star averages — quote **only** as '
        '“reported on PBJ320” when shown; if uncertain, soften or omit exact figures.\n'
        '- **Tone:** screening signal, merits closer review, policy benchmark, orientation point, requires verification, '
        'not a standalone compliance finding. Avoid *proves*, *violates*, *noncompliant*, *neglect*, *misconduct*, '
        '*active monitoring list*, *staffing failure* unless inspection, enforcement, complaint, or legal records support it.\n'
    ),
    'operator': (
        'State QA / compliance viewpoint ({state})\n'
        '- Encourage comparisons of reported staffing with **verified state requirement text** paired with denominators—not public CMS case-mix lines alone—and internal staffing grids.\n'
        '- Mention **survey readiness**: tie charts to citations and complaint themes when records exist externally.\n'
        '- Discuss **acuity census shifts**, agency usage, onboarding effects **if later supported by granular data**.\n'
        '- Explicit: PBJ320 is **screening/decision-support**, never a definitive compliance adjudicator.'
    ),
}


def _provider_ny_example_block(state_display: str, state_code: str) -> str:
    """Bullet block when facility is NY—illustrative, not exhaustive."""
    s = (state_display or '').strip().upper()
    c = (state_code or '').strip().upper()
    if c != 'NY' and 'NEW YORK' not in s:
        return ''
    return (
        '- **New York anchors (verify current URLs/forms before requesting):**\n'
        '  nurse staffing benchmarks & interpretive FAQs from **NYSDOH/the Health Commerce System** portals; Nursing Home Profiles; downloadable inspection summaries; FOIL paths for complaint logs; CPLR discovery practices for aide schedules and agency contracts.'
    )


def _provider_state_example_block(
    state_display: str, state_code: str, *, lens: Optional[str] = None
) -> str:
    """State-specific anchor bullets appended to provider dashboard supplements."""
    from pbj_connecticut_public import connecticut_public_context_block

    ct = connecticut_public_context_block(
        lens=lens or 'ombudsman',
        state_code=state_code,
        state_label=state_display,
    )
    if ct:
        return ct
    return _provider_ny_example_block(state_display, state_code)


def compose_provider_dashboard_supplement_block(
    lens: Optional[str],
    facility_state: str,
    *,
    facility_state_code: str = '',
    page_type: str = 'facility',
) -> str:
    """CSV depth + jurisdiction-aware reviewer instructions appended to dashboard prompts."""
    ptype = (page_type or 'facility').strip().lower()
    if ptype not in ('facility', 'provider'):
        return ''
    st = (facility_state or '').strip() or 'not stated — identify facility state inside the pasted context'
    lid = normalize_public_review_lens(lens)
    aud_lens_map = {
        'family': 'family',
        'journalist': 'journalist',
        'ombudsman': 'ombudsman',
    }
    aud_lens = aud_lens_map.get(lid, 'ombudsman')
    body_key = aud_lens if aud_lens in _PROVIDER_STATE_BODY_BY_LENS else 'ombudsman'
    state_ex = _provider_state_example_block(
        facility_state, facility_state_code, lens=lid
    )
    ny_bl = state_ex if state_ex else ''
    core = _PROVIDER_STATE_BODY_BY_LENS[body_key].format(state=st, ny_examples=ny_bl)
    return f'{PBJ_PROVIDER_CSV_SOURCE_DEPTH_NOTE.strip()}\n\n{PBJ_PROVIDER_STATE_SUPPLEMENT_INTRO.format(state=st)}\n\n{core}'


def provider_dashboard_supplements_export() -> dict[str, Any]:
    """Injected JSON for matching client-side prompt assembly."""
    from pbj_connecticut_public import connecticut_public_context_block

    st = '{{state}}'
    state_ph = '{{state_examples}}'
    fmt = lambda key: (
        _PROVIDER_STATE_BODY_BY_LENS[key]
        .replace('{state}', st)
        .replace('{ny_examples}', state_ph)
    )
    ct_block = lambda lens: connecticut_public_context_block(lens=lens, state_code='CT')
    ny_block = (
        '- **New York anchors (verify current URLs/forms):** NYSDOH nursing home profiles & '
        'downloaded inspection materials; complaint/enforcement portals where available; '
        'Long-Term Care Ombudsman Program; **MACPAC** (*State Policies Related to Nursing '
        'Facility Staffing*, macpac.gov) as a **state staffing / Medicaid policy compendium**—'
        'use as policy reference only, not standalone PASS/FAIL against statute.'
    )
    return {
        'csvSourceDepthNote': PBJ_PROVIDER_CSV_SOURCE_DEPTH_NOTE,
        'stateIntroTemplate': PBJ_PROVIDER_STATE_SUPPLEMENT_INTRO.replace('{state}', '{{state}}'),
        'stateSectionsByLens': {
            'general': fmt('general'),
            'advocate': fmt('advocate'),
            'ombudsman': fmt('ombudsman'),
            'family': fmt('family'),
            'journalist': fmt('journalist'),
            'attorney': fmt('attorney'),
            'researcher': fmt('researcher'),
            'policymaker': fmt('policymaker'),
            'operator': fmt('operator'),
        },
        'stateExamplesByCode': {
            'CT': {
                'ombudsman': ct_block('ombudsman'),
                'family': ct_block('family'),
                'journalist': ct_block('journalist'),
            },
            'NY': {
                'ombudsman': ny_block,
                'family': ny_block,
                'journalist': ny_block,
            },
        },
    }


PBJ_AUDIENCE_MODE_INSTRUCTIONS: dict[str, str] = {
    'analyst': (
        'Focus on neutral interpretation, metric definitions, comparison context, caveats, '
        'and next analytic steps.'
    ),
    'family_resident': (
        'Use brief, plain English. Explain what the staffing numbers may mean for family questions, '
        'but emphasize that PBJ is facility-level data and cannot show what happened to a specific resident. '
        'If census or certified beds are listed, mention whether the home is on the **smaller, mid-sized, or larger** side '
        'for reader context (informal bands on the page — not a legal classification).'
    ),
    'advocate': (
        'Focus on screening signals, comparison points, and follow-up questions for oversight or complaint review. '
        'Avoid claiming violations unless supported by separate evidence. When the page text includes **average daily census**, '
        '**certified beds**, **ownership**, **SFF / survey status**, **abuse icon**, or **Five-Star** lines, foreground them early '
        'so families understand facility scale and regulatory flags alongside PBJ staffing. Use the full '
        '**medicare.gov** nursing-home URL when listed — not the generic Medicare landing page. '
        'For dedicated **Long-Term Care Ombudsman** framing (resident-directed mediation, consent, retaliation sensitivity), '
        'suggest switching to **Ombudsman** mode in PBJ320.'
    ),
    'ombudsman': (
        'You are helping a **Long-Term Care Ombudsman** or similarly resident-centered advocate. '
        'Ombudsmen identify, investigate, and help resolve complaints affecting residents\' health, safety, welfare, quality of life, '
        'and rights; they are **not** regulators, prosecutors, plaintiff attorneys, or official finders of fact. '
        'Work is **resident-directed**: goals, consent, dignity, and fear of retaliation matter. '
        'Use PBJ staffing as **context for questions and follow-up**, not as proof of neglect, causation, misconduct, or legal violation. '
        'Tie patterns to **daily lived experience** when helpful: call-light response, toileting, meals, bathing, transfers, supervision, '
        'weekend/evening coverage, RN availability, aide continuity, responsiveness. '
        'Prefer **practical next steps** and **public/government resources** (state/local ombudsman program, Care Compare, CMS survey '
        'materials, state licensing/complaint portals, Eldercare Locator / ACL navigation). **Do not** push paid PBJ320 premium products; '
        'mention them only briefly if the user already has them. '
        'Tone: practical, plain English, non-sensational; avoid legal conclusions and Attorney/Journalist-style framing.'
    ),
    'journalist': (
        'Focus on newsworthiness, comparison context, caveats, and what additional reporting would be needed '
        'before publishing a claim.'
    ),
    'attorney': (
        'Focus on evidentiary use, limitations, incident-window questions, discovery targets, and what PBJ can '
        'and cannot support. Do not offer legal conclusions.'
    ),
    'legislator': (
        'Primary reader: **Legislator / Policymaker** (public oversight and staffing policy—not a plaintiff brief, '
        'enforcement finding, or single-facility advocacy attack). Use one facility as an **illustration** of how quarterly '
        'PBJ informs transparency, Medicaid/payment context, chain accountability debates, and where integrated review '
        'should go next. Prefer screening language; avoid claims that PBJ alone establishes noncompliance, neglect, '
        'causation, or care quality.'
    ),
    'operator': (
        'Focus on how outsiders may read public data, scrutiny signals, and context limits — neutral tone; '
        'do not help bury red flags.'
    ),
    'researcher': (
        'Focus on methodology, denominators, distributions, outliers, and data-quality limits first.'
    ),
}

PBJ_SOURCE_TYPE_LABELS: dict[str, str] = {
    'free_facility': 'PBJ320 PROVIDER PAGE (quarterly facility-level)',
    'free_state': 'PBJ320 STATE PAGE (quarterly state-level)',
    'free': 'PBJ320 PAGE (quarterly context)',
    'premium': 'PREMIUM DASHBOARD / EXPORT',
}

# --- Dashboard helper: review lens + output length (no login) ---

PBJ_LENS_STORAGE_KEY = 'pbj320_ai_review_lens'
PBJ_LENGTH_STORAGE_KEY = 'pbj320_ai_review_length'
PBJ_DEFAULT_REVIEW_LENS = 'general'
PBJ_DEFAULT_REVIEW_LENGTH = 'quick'

VALID_REVIEW_LENSES = frozenset({
    'general',
    'advocate',
    'ombudsman',
    'family',
    'journalist',
    'attorney',
    'researcher',
    'policymaker',
    'operator',
})

VALID_REVIEW_LENGTHS = frozenset({'quick', 'standard', 'detailed'})

PBJ_LENS_TO_AUDIENCE: dict[str, str] = {
    'general': 'analyst',
    'advocate': 'advocate',
    'ombudsman': 'ombudsman',
    'family': 'family_resident',
    'journalist': 'journalist',
    'attorney': 'attorney',
    'researcher': 'researcher',
    'policymaker': 'legislator',
    'operator': 'operator',
}

PBJ_LENS_UI_PRIMARY: tuple[tuple[str, str], ...] = (
    ('general', 'General'),
    ('advocate', 'Advocate'),
    ('ombudsman', 'Ombudsman'),
    ('family', 'Family'),
    ('journalist', 'Journalist'),
    ('attorney', 'Attorney'),
)

PBJ_LENS_UI_MORE: tuple[tuple[str, str], ...] = (
    ('researcher', 'Researcher'),
    ('policymaker', 'Policymaker'),
    ('operator', 'Operator'),
)

PBJ_LENGTH_UI: tuple[tuple[str, str], ...] = (
    ('quick', 'Quick takeaway'),
    ('standard', 'Standard review'),
    ('detailed', 'Detailed review'),
)

PBJ_LENS_QUICK_TAKEAWAY: dict[str, str] = {
    'general': (
        'Give a quick PBJ320 review for a general analyst. Summarize what this material shows, '
        'what it may suggest, what it cannot prove, and what questions to ask next. Keep it brief and evidence-based.'
    ),
    'advocate': (
        'Give a quick advocate takeaway. Focus on whether the visible staffing pattern raises questions '
        'worth deeper review, what an advocate should ask next, and what cannot be concluded from the data. '
        'Lead with **who lives here** (census / informal small–medium–large band when shown) and any **Care Compare flags** '
        '(ownership, SFF/survey status, abuse icon, star snapshots) before diving into HPRD tables — then tie staffing '
        'signals back to those realities.'
    ),
    'ombudsman': (
        'Give a concise **Long-Term Care Ombudsman**-style prep note: what the staffing pattern may suggest for **resident '
        'experience** (not proof), how it could inform a visit or complaint conversation, and neutral questions for residents, '
        'families, staff, and administrators. Emphasize **resident direction, consent, dignity, and retaliation sensitivity**. '
        'Prioritize **public resources** (Care Compare, CMS survey context, state licensing/complaint paths, local ombudsman program) '
        'over paid PBJ320 add-ons. Avoid Attorney/Journalist framing. '
        'If the facility is in **Connecticut**, include the state-specific LTCOP and MACPAC orientation bullets from the '
        'supplement block (portal.ct.gov/LTCOP; toll-free 1-866-388-1888).'
    ),
    'family': (
        'Explain this in plain English for a family member. Focus on what the staffing numbers mean, '
        'what questions to ask the facility, and what this page cannot tell me.'
    ),
    'journalist': (
        'Give a quick journalist takeaway. Identify the strongest defensible story angle, the supporting signals, '
        'what needs verification, and what not to claim.'
    ),
    'attorney': (
        'Give a quick attorney/investigator screen. Identify staffing signals worth reviewing, what records would be '
        'needed, and what cannot be established from PBJ data alone. Open with a **3-bullet executive summary** '
        '(facility + CCN/state anchor, period reviewed, screening posture—no legal conclusions). Close with a numbered '
        '**Suggested deliverables / next productions** checklist (5–8 items: e.g. incident-window daily PBJ, '
        'schedules, state survey, Care Compare deep link already in the page text). When the material includes a '
        'full **medicare.gov** nursing-home URL for this CCN, paste that exact URL in the records section—do not '
        'substitute the generic Medicare landing page.'
    ),
    'researcher': (
        'Give a quick methodological read. Focus on metric definitions, sample size, comparison group, '
        'denominator/census effects, outliers, data quality, and what analysis would require deeper data.'
    ),
    'policymaker': (
        'Quick **Legislator / Policymaker** takeaway: what the visible quarterly PBJ pattern illustrates for **oversight '
        'and policy** (screening signal, peer context, benchmarks on the page), what requires **verification** with '
        'state-law staffing math, surveys/complaints, daily PBJ, and ownership/Medicaid context—and what quarterly PBJ '
        '**cannot** prove alone.'
    ),
    'operator': (
        'Give a quick operator-facing read. Explain how outsiders may interpret the public staffing data, '
        'what context may be important, and what the data cannot establish.'
    ),
}

PBJ_REVIEW_GUARDRAILS_SHARED = [
    'Do not assume daily staffing, weekend patterns, 90-day aide/CNA day counts, agency reliance, mean/median tables, or incident-window detail unless shown.',
    'HPRD is hours per resident day, not a shift-level staff-to-resident ratio.',
    'CMS case-mix HPRD is an acuity-adjusted benchmark/reference point, not a legal staffing minimum.',
    'Case-mix index ratio is about acuity relative to the national average, not reported staffing adequacy.',
    'Do not assume neglect, misconduct, causation, or legal violations.',
    'Treat red flags as screening signals, not findings.',
    'Blank or “—” role HPRD cells in PBJ320 extracts are not proof of zero hours in that role unless the material shows an explicit 0.00; missing can mean not populated or mapped to another job line in this view.',
    'When the page text includes **Contract staff %** (quarterly PBJ aggregate share of contract hours in total facility hours), use it as facility-level context for that quarter; it is not daily agency billing detail and does not replace timecards or vendor invoices.',
    'When census, certified beds, ownership, SFF status, abuse icon, or star ratings appear in the page text, treat them as basic facility context alongside PBJ — especially for advocate, ombudsman, and family readers.',
]

PBJ320_SCREENING_FLAGS_BLOCK = (
    '**PBJ320 screening flags (brief — do not let this dominate):** When the pasted PBJ320 context lists the '
    '**PBJ320 high-risk badge** and/or echoed **Care Compare** fields (SFF or SFF Candidate, abuse icon, overall or '
    'staffing Five-Star of 1), add a **short** early note (one sentence or up to three bullets) labeled something like '
    '"PBJ320 screening flags" before the main staffing analysis. These are **screening signals PBJ320 surfaces** from '
    'public CMS/provider data — not proof of harm, neglect, violations, or causation. **PBJ staffing remains the primary focus.** '
    'If SFF is listed and star ratings are missing on the page, note that stars may be unavailable — do not invent ratings. '
    'Do not restructure the entire answer around flags when the user is asking about HPRD or trends.'
)

# --- Audience modes: labels, emphasis, response sections, mode-specific instructions ---

PBJ_REVIEW_MODES: dict[str, dict[str, Any]] = {
    'analyst': {
        'label': 'Analyst',
        'output_tier': OUTPUT_TIER_STANDARD,
        'emphasis': ['methodology', 'distribution', 'data quality', 'next analyses'],
        'sections': [],
        'extra_sections': [],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['analyst'],
    },
    'journalist': {
        'label': 'Journalist',
        'output_tier': OUTPUT_TIER_STANDARD,
        'emphasis': ['story angle', 'safe claims', 'sources', 'records requests', 'publication risks'],
        'sections': [],  # uses OUTPUT_TIER_SECTIONS
        'extra_sections': [
            (
                'Clearest supportable angle',
                '1–2 defensible framing sentences (e.g. rank/comparison over a defined period). '
                'Include **one exhibit** (DATA VISUAL rule) that carries the lead—trend, peer comparison, or reference gap—using only supplied values. '
                'Then note what must be verified before publication. '
                'Do not say neglect or violation without regulatory confirmation. '
                'Avoid "understaffed" unless the comparison is explicit.',
            ),
        ],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['journalist'],
    },
    'advocate': {
        'label': 'Advocate',
        'output_tier': OUTPUT_TIER_STANDARD,
        'emphasis': ['screening flags', 'regulator questions', 'public-facing caution', 'facility follow-up'],
        'sections': [],
        'extra_sections': [
            (
                'Resident population & facility flags',
                'If census, certified beds, ownership, SFF/survey status, abuse icon, or star snapshots appear in the page text, '
                'summarize them in plain language **before** long HPRD tables so advocates and families see scale and regulatory context first.',
            ),
        ],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['advocate'],
    },
    'ombudsman': {
        'label': 'Ombudsman',
        'output_tier': OUTPUT_TIER_BRIEF,
        'emphasis': [
            'resident rights',
            'quality of life',
            'complaint resolution',
            'facility conversations',
            'neutral follow-up',
            'limits on proof',
        ],
        'sections': [
            'Plain-English takeaway',
            'What an ombudsman can use this for',
            'Resident-centered questions to ask',
            'Facility follow-up questions',
            'Limits / what this does not prove',
        ],
        'extra_sections': [],
        'section_instructions': {
            'Plain-English takeaway': (
                '**2–4 short sentences** plus **one staffing exhibit** (DATA VISUAL rule): explain what the pattern may suggest from a '
                '**resident-advocacy** perspective only—then a simple table, mini trend, or role-mix chart using **only supplied numbers**, '
                'with a conversation-ready caption (or chart-ready Markdown / brief why none). '
                'Connect to lived experience when useful (call lights, toileting, meals, bathing, transfers, supervision, evenings/weekends, '
                'RN presence, aide continuity). Do **not** allege neglect, abuse, violations, or causation.'
            ),
            'What an ombudsman can use this for': (
                'How this information could support **resident-directed** work: conversations with residents/families, care-plan or '
                'QAPI-adjacent questions (without pretending to be clinical), facility meetings, mediation prep, resident council/family council '
                'topics, or complaint follow-up. Note consent, goals, and fear of retaliation where relevant. '
                'Suggest **practical next steps** (who to contact, what public pages to open) leaning on **government/program resources** '
                '(e.g. local/state **Long-Term Care Ombudsman** coordinator, **Medicare.gov Care Compare**, CMS survey/certification context, '
                'state licensing or complaint portals, **Eldercare Locator** / ACL). **Do not** steer readers toward paid PBJ320 premium products; '
                'mention premium-only daily exports only if the user already attached them.'
            ),
            'Resident-centered questions to ask': (
                '**6–12 concrete questions** an ombudsman might ask residents, families, aides, nurses, or other staff — examples: '
                'Are call-light waits longer at certain times? Are bathing, toileting, meals, or transfers delayed? Are evenings/weekends '
                'different from weekdays? Do residents see fewer familiar aides? Has the facility explained staffing or schedule changes? '
                'Are people afraid to speak up or worried about retaliation? Keep questions open-ended and non-leading.'
            ),
            'Facility follow-up questions': (
                '**5–10 neutral, non-accusatory** administrator/DON questions, for example: How are low RN or aide days covered? '
                'When agency staff are used, how is continuity handled? Are some units or shifts more affected? What steps support timely '
                'assistance? How are residents/families informed about disruptions tied to staffing? Avoid prosecutorial tone.'
            ),
            'Limits / what this does not prove': (
                'Always include: PBJ is generally **day- or quarter-level** in free views, not shift-by-shift unless premium/export material '
                'with that granularity is attached; staffing metrics **do not prove** neglect, abuse, causation, or regulatory breach; '
                'resident interviews, care plans, grievances, incidents, survey findings, and facility explanations are needed for a fuller picture; '
                'case-mix and census changes can distort HPRD comparisons; low staffing can be a **warning to explore** with residents but is '
                'not a finding by itself.'
            ),
        },
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['ombudsman'],
    },
    'family_resident': {
        'label': 'Family / Resident',
        'output_tier': OUTPUT_TIER_BRIEF,
        'emphasis': ['plain language', 'specific resident limits', 'facility questions', 'visit observations'],
        'sections': [],
        'extra_sections': [
            (
                'Staffing at a glance',
                'One plain-language mini-table or simple trend (DATA VISUAL rule) for the main pattern—spell out '
                'hours-per-resident-day; values only from the material.',
            ),
        ],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['family_resident'],
    },
    'attorney': {
        'label': 'Attorney',
        'output_tier': OUTPUT_TIER_DETAILED,
        'emphasis': ['incident window', 'discovery targets', 'evidentiary limits', 'comparison periods'],
        'sections': [],
        'extra_sections': [],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['attorney'],
    },
    'legislator': {
        'label': 'Legislator / Policymaker',
        'output_tier': OUTPUT_TIER_STANDARD,
        'emphasis': [
            'policy relevance',
            'screening vs verified compliance',
            'Medicaid and transparency',
            'integrated oversight',
            'ownership and chain context',
        ],
        'sections': [
            'Policy relevance',
            'Facility PBJ profile (screening signals)',
            'Benchmarks on the page (MACPAC and CMS case-mix)',
            'Peer, geography, and ownership context',
            'What quarterly PBJ supports — and what it does not',
            'Integrated oversight questions',
            'Bottom line for policymakers',
        ],
        'extra_sections': [],
        'legacy_output_format': (
            'Follow the **Additional section guidance** below exactly (use those ## headings). '
            'Write for a **Legislator / Policymaker** audience: a concise, credible policy briefing—public oversight, '
            'staffing policy, transparency, and integrated review—not an attorney enforcement memo, facility attack brief, '
            'or advocate prosecution piece. Do **not** use Ombudsman-style “facility visit handout” framing. '
            'Do **not** write in Attorney Mode (legal theories, discovery lists, proof language) or Journalist Mode '
            '(story angles, publication framing).'
        ),
        'section_instructions': {
            'Policy relevance': (
                '**3–5 short bullets.** Explain why this matters beyond one facility: quarterly PBJ can **screen** for '
                'facilities that merit closer review; PBJ **alone** does not prove noncompliance, neglect, causation, or poor care; '
                'policymakers should use PBJ as a **screening layer** alongside **state staffing-law calculations**, '
                '**daily PBJ patterns** where available, **inspection** records, **complaint/ombudsman** data, **ownership** context, '
                'and **Medicaid/payment** policy. Do not repeat this whole block later unless one sentence ties forward.'
            ),
            'Facility PBJ profile (screening signals)': (
                'Summarize the **strongest defensible** quarterly staffing signals visible in the material (totals, RN/LPN/CNA mix, '
                'trend direction, contract share if shown). Use **screening signal** / **merits closer review** language. '
                'For **percentile or rank** claims over time: tie each claim to what the table/chart actually shows; avoid broad '
                'multi-year tails (e.g. “bottom 10–20% most of the period”) unless clearly supported. Prefer formulations like '
                '“since [earliest year shown], generally in the lower tail by total nurse HPRD, often near or below the 15th '
                'percentile **where percentiles appear**.” If consecutive-quarter counts are not verifiable from the attachment, '
                'soften to “many quarters” or “the quarters visible here.”'
            ),
            'Benchmarks on the page (MACPAC and CMS case-mix)': (
                '**MACPAC:** Cite *State Policies Related to Nursing Facility Staffing* '
                '(https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/) as a **credible '
                'state-policy compendium** of nursing facility staffing standards and related Medicaid payment policies. '
                'Treat any MACPAC-derived state minimum or HPRD line on PBJ320 as an **estimated policy benchmark / orientation '
                'point**—not a verified legal compliance calculation. Use language like: “MACPAC-derived [State] staffing policy '
                'reference: approximately X HPRD, estimated / for orientation only; verify against current statute, regulations, '
                'waivers or exemptions, and calculation rules before any compliance claim.” **Do not** say the facility passed or '
                'failed state law from this line alone.\n'
                '**CMS case-mix:** Describe the case-mix nursing HPRD shown on the page as an **acuity-adjusted comparison / '
                'reference value**—**not** a legal minimum and **not** a staffing-sufficiency determination. When comparing '
                'reported HPRD to that value, use: “Reported total nurse HPRD was about X% of the CMS case-mix reference value '
                'shown on the page. **This is a screening comparison, not a compliance finding or standalone staffing-sufficiency '
                'determination.**” Replace any phrasing like “operating at roughly X% of its own acuity-adjusted reference point” '
                'with that screening framing.'
            ),
            'Peer, geography, and ownership context': (
                'Place the facility in **state / county / market** peer context only as the data supports. '
                '**Ownership / entity / chain:** keep policy-relevant. Do **not** infer chain misconduct from one facility page. '
                'Use: “Chain-level review would help determine whether this profile is isolated, concentrated among certain '
                'facilities, or associated with broader ownership-level operating patterns.” For entity size, states, average stars, '
                'or facility counts, match the **PBJ320 entity page** exactly when shown; if uncertain, say “reported on PBJ320 as…” '
                'or omit exact numbers.'
            ),
            'What quarterly PBJ supports — and what it does not': (
                '**Two short paragraphs or bullet groups.** Supported: what the quarterly rows/charts **actually show** '
                '(definitions, comparisons, trends). Not supported: shift-level reality, individual resident care, causation, '
                'neglect, legal violation, or definitive staffing adequacy—unless separate inspection/complaint/legal material '
                'is attached. State the limits **once** clearly; do not scatter the same caveat through every section.'
            ),
            'Integrated oversight questions': (
                '**Exactly four buckets** — label each bucket, then **2–4 tight bullets** under each (not a long unstructured list):\n'
                '- **Compliance:** How does reported staffing compare with **the state’s statutory staffing calculation** under '
                'the correct state-law definitions, inputs, and exemptions?\n'
                '- **Oversight:** What do **state inspections, complaints, enforcement records, and ombudsman** data show—and '
                'what should be pulled next?\n'
                '- **Pattern:** Is this facility unusual versus **state peers**, **county/market peers**, or **same-affiliation** '
                'facilities where the page provides that lens?\n'
                '- **Mechanism:** What could explain patterns (census, acuity, staffing mix, contract reliance, labor market, '
                'reimbursement, ownership decisions)—as **hypotheses to test**, not conclusions.'
            ),
            'Bottom line for policymakers': (
                '**1 short paragraph** (may use the facility name from the material). Template (adapt numbers and geography to the '
                'evidence): this facility’s PBJ profile shows **[scale/setting if stated]** with **persistently low (or elevated) '
                'quarterly nurse staffing relative to [peer group shown]** and a **substantial gap or alignment vs. the CMS '
                'case-mix reference value shown on PBJ320**, described strictly as a **screening comparison**. '
                'For policymakers, the point is **not** that PBJ data alone proves noncompliance or poor care—it does not. '
                'The point is that **this kind of profile** should trigger a **more integrated review**: state-law staffing '
                'calculations, daily PBJ patterns where available, survey and complaint history, ownership-level comparisons, and '
                'Medicaid/payment context. **Used properly, PBJ is a screening system for oversight priorities—not a standalone verdict.** '
                'Do **not** recommend an “active monitoring list” or similar unless inspection, complaint, daily PBJ, or legal '
                'records attached support that step.'
            ),
        },
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['legislator'],
    },
    'operator': {
        'label': 'Operator',
        'output_tier': OUTPUT_TIER_STANDARD,
        'emphasis': ['benchmarking', 'data QA', 'external perception', 'documentation readiness'],
        'sections': [],
        'extra_sections': [],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['operator'],
    },
    'researcher': {
        'label': 'Researcher',
        'output_tier': OUTPUT_TIER_DETAILED,
        'emphasis': ['methodology', 'denominators', 'distributions', 'data quality', 'confounds'],
        'sections': [],
        'extra_sections': [],
        'section_instructions': {},
        'quick_modifier': PBJ_AUDIENCE_MODE_INSTRUCTIONS['researcher'],
    },
}


def output_tier_for_audience(audience: Optional[str]) -> str:
    return OUTPUT_TIER_BY_AUDIENCE.get(normalize_audience(audience), OUTPUT_TIER_STANDARD)


def detect_audience_from_text(text: Optional[str]) -> str:
    """Infer audience from user message / pasted context (first match wins)."""
    if not text:
        return DEFAULT_AUDIENCE
    blob = text.lower()
    for pattern, audience in AUDIENCE_DETECTION_PATTERNS:
        if re.search(pattern, blob, re.I):
            return audience
    return DEFAULT_AUDIENCE


def infer_source_level(
    page_type: str = '',
    page_kind: str = '',
    page_url: str = '',
) -> str:
    kind = (page_kind or '').lower()
    url = (page_url or '').lower()
    ptype = (page_type or '').lower()
    if 'premium' in kind or '/premium/' in url or 'premium dashboard' in kind:
        return 'premium'
    if ptype == 'state' or 'state page' in kind or 'state dashboard' in kind:
        return 'free_state'
    if ptype == 'facility' or 'facility page' in kind:
        return 'free_facility'
    return 'free'


def format_source_level_block(
    page_type: str = '',
    page_kind: str = '',
    page_url: str = '',
) -> str:
    level = infer_source_level(page_type, page_kind, page_url)
    return f'Source level: {PBJ_SOURCE_LEVEL_COPY[level]}'


@dataclass
class ReviewConfig:
    """Lightweight review mode selection — serializable for API/JS."""

    audience: str = DEFAULT_AUDIENCE
    geography_level: Optional[str] = None
    context_note: str = ''
    infer_geography_from_material: bool = True

    def normalized(self) -> ReviewConfig:
        aud = normalize_audience(self.audience)
        geo = normalize_geography_level(self.geography_level)
        note = (self.context_note or '').strip()
        return ReviewConfig(
            audience=aud,
            geography_level=geo,
            context_note=note,
            infer_geography_from_material=self.infer_geography_from_material,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> ReviewConfig:
        if not data:
            return cls()
        return cls(
            audience=str(data.get('audience') or DEFAULT_AUDIENCE),
            geography_level=data.get('geography_level') or data.get('geography'),
            context_note=str(data.get('context_note') or data.get('context') or ''),
            infer_geography_from_material=bool(data.get('infer_geography_from_material', True)),
        )


def normalize_audience(audience: Optional[str]) -> str:
    key = (audience or '').strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'family': 'family_resident',
        'resident': 'family_resident',
        'family_resident': 'family_resident',
        'lawyer': 'attorney',
        'legal': 'attorney',
        'legislative': 'legislator',
        'policy': 'legislator',
        'policymaker': 'legislator',
        'admin': 'operator',
        'facility_operator': 'operator',
        'academic': 'researcher',
        'ombuds': 'ombudsman',
    }
    key = aliases.get(key, key)
    return key if key in VALID_AUDIENCES else DEFAULT_AUDIENCE


def normalize_geography_level(level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    key = str(level).strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'ownership': 'ownership_group',
        'chain': 'ownership_group',
        'entity': 'ownership_group',
    }
    key = aliases.get(key, key)
    return key if key in VALID_GEOGRAPHY_LEVELS else None


def get_review_mode(audience: Optional[str] = None) -> dict[str, Any]:
    return PBJ_REVIEW_MODES[normalize_audience(audience)]


def infer_geography_level_from_page_type(page_type: Optional[str]) -> Optional[str]:
    """Best-effort geography when caller does not set geography_level."""
    key = (page_type or '').strip().lower()
    mapping = {
        'facility': 'facility',
        'provider': 'facility',
        'state': 'state',
        'entity': 'ownership_group',
        'chain': 'ownership_group',
        'ownership': 'ownership_group',
        'region': 'region',
        'cms_region': 'region',
        'county': 'county',
        'city': 'city',
        'national': 'national',
    }
    return mapping.get(key)


def format_context_block(config: ReviewConfig) -> str:
    """Geography + free-text context for prompt header."""
    cfg = config.normalized()
    lines: list[str] = []
    mode = get_review_mode(cfg.audience)
    tier = mode.get('output_tier') or output_tier_for_audience(cfg.audience)
    lines.append(f'Review mode: {mode["label"]} (audience: {cfg.audience}; output tier: {tier}).')
    if cfg.context_note:
        detected = detect_audience_from_text(cfg.context_note)
        if detected != cfg.audience:
            lines.append(
                f'Note: user text suggests {get_review_mode(detected)["label"]} — '
                f'using configured {mode["label"]} unless you re-detect from the full message.'
            )
    emphasis = mode.get('emphasis') or []
    if emphasis:
        lines.append(f'Output emphasis: {", ".join(emphasis)}.')
    if cfg.geography_level:
        label = PBJ_REVIEW_CONTEXT_LEVELS[cfg.geography_level]
        lines.append(f'Geographic / jurisdiction scope: {label}.')
    elif cfg.infer_geography_from_material:
        lines.append(
            'Geographic scope: not specified — infer state, region, facility, or national scope from the material when possible.'
        )
    if cfg.context_note:
        lines.append(f'Additional context from user: {cfg.context_note}')
    return '\n'.join(lines)


def _format_advanced_sections(mode: dict[str, Any], audience: str) -> str:
    tier = mode.get('output_tier') or output_tier_for_audience(audience)
    legacy = mode.get('sections') or []
    if legacy:
        parts = ['Format your response with these sections:', '']
        for title in legacy:
            instruction = mode.get('section_instructions', {}).get(title, '')
            parts.append(f'## {title}')
            if instruction:
                parts.append(instruction)
            parts.append('')
        return '\n'.join(parts).rstrip()

    section_list = list(OUTPUT_TIER_SECTIONS[tier])
    extra = mode.get('extra_sections') or []
    if mode.get('prepend_extra_sections'):
        section_list = extra + section_list
    else:
        section_list.extend(extra)
    parts = [f'Format your response using the {tier} output tier:', '']
    for title, instruction in section_list:
        parts.append(f'## {title}')
        if instruction:
            parts.append(instruction)
        parts.append('')
    parts.append(
        'For "What the data cannot prove," list only limits relevant to this query — no boilerplate.'
    )
    return '\n'.join(parts).rstrip()


def lens_display_label(lens: Optional[str]) -> str:
    key = normalize_review_lens(lens or PBJ_DEFAULT_REVIEW_LENS)
    for lid, lbl in PBJ_LENS_UI_PRIMARY + PBJ_LENS_UI_MORE:
        if lid == key:
            return lbl
    return 'General'


def source_level_key(page_type: str, page_kind: str = 'free') -> str:
    ptype = (page_type or 'facility').strip().lower()
    kind = (page_kind or 'free').strip().lower()
    if 'premium' in kind:
        return 'premium'
    if ptype == 'state':
        return 'free_state'
    if ptype in ('facility', 'provider'):
        return 'free_facility'
    return 'free'


def source_type_label(page_type: str, page_kind: str = 'free') -> str:
    key = source_level_key(page_type, page_kind)
    return PBJ_SOURCE_TYPE_LABELS.get(key, PBJ_SOURCE_TYPE_LABELS['free'])


def audience_mode_display(lens: Optional[str] = None, audience: Optional[str] = None) -> str:
    lens_key = normalize_review_lens(lens) if lens is not None else None
    if lens_key and lens_key in PBJ_AUDIENCE_MODE_DISPLAY:
        return PBJ_AUDIENCE_MODE_DISPLAY[lens_key]
    aud = normalize_audience(audience or DEFAULT_AUDIENCE)
    for lid, aud_mapped in PBJ_LENS_TO_AUDIENCE.items():
        if aud_mapped == aud and lid in PBJ_AUDIENCE_MODE_DISPLAY:
            return PBJ_AUDIENCE_MODE_DISPLAY[lid]
    return PBJ_AUDIENCE_MODE_DISPLAY['general']


def compose_source_limits_block(page_type: str = 'facility') -> str:
    """Single deduplicated source-limit block (no separate guardrails section)."""
    ptype = (page_type or 'facility').strip().lower()
    lines: list[str] = []
    if ptype in ('facility', 'provider'):
        lines.append(
            '- If this is a free provider page, use it only as quarterly facility-level staffing context.'
        )
        lines.append(
            '- Average daily census is included in the page context and embedded quarterly CSV when CMS '
            'reported it — use it for HPRD/denominator interpretation; do not claim census is unavailable '
            'when it appears in the material.'
        )
        lines.append(
            '- Do not infer daily staffing, weekend staffing, employee-level staffing, agency use, '
            'incident-window staffing, or resident-level care unless explicitly shown.'
        )
    elif ptype == 'state':
        lines.append(
            '- If this is a state page, use state-level quarterly context only; do not infer '
            'individual facility conditions unless facility-level data is provided.'
        )
    else:
        lines.append(
            '- Use only metrics and time depth shown on the page or export; do not infer premium-only fields.'
        )
    lines.extend(f'- {rule}' for rule in PBJ_REVIEW_GUARDRAILS_SHARED)
    return '\n'.join(lines)


def layered_output_format(length: str, audience: str) -> str:
    length_key = normalize_review_length(length)
    if length_key == 'quick':
        return PBJ_LAYERED_OUTPUT_QUICK
    if length_key == 'detailed':
        return PBJ_LAYERED_OUTPUT_DETAILED
    return PBJ_LAYERED_OUTPUT_STANDARD


def compose_layered_review_prompt(
    lens: Optional[str] = None,
    *,
    page_type: str = 'facility',
    length: str = 'quick',
    page_kind: str = 'free',
) -> str:
    """Modular review prompt: audience → task → source limits → output format → tone."""
    lens_key = normalize_review_lens(lens or PBJ_DEFAULT_REVIEW_LENS)
    audience = lens_to_audience(lens_key)
    mode_label = audience_mode_display(lens_key, audience)
    mode = get_review_mode(audience)
    mode_instruction = (mode.get('quick_modifier') or '').strip() or PBJ_AUDIENCE_MODE_INSTRUCTIONS.get(audience, '')
    legacy_sections = mode.get('sections') or []
    length_key = normalize_review_length(length)
    output_fmt = layered_output_format(length, audience)
    if legacy_sections:
        _default_legacy_fmt = (
            'Follow the **Additional section guidance** below exactly (use those headings). '
            'Keep the response concise and actionable — not a long report. '
            'Do not write in Attorney Mode (legal theories, discovery lists, proof language) or Journalist Mode '
            '(story angles, publication framing).'
        )
        output_fmt = (mode.get('legacy_output_format') or '').strip() or _default_legacy_fmt
    presentation_lines = [
        PBJ_VISUAL_OUTPUT_HINT.strip(),
        audience_visual_framing_block(audience).strip(),
    ]
    legacy_pres_override = (
        legacy_sections and mode.get('legacy_presentation')
    )
    legacy_pres_text = legacy_pres_override.strip() if isinstance(legacy_pres_override, str) else ''
    if legacy_sections and legacy_pres_text:
        presentation_lines.append(f'Presentation mode note: {legacy_pres_text}')
    presentation = '\n\n'.join(presentation_lines).strip()
    parts = [
        'You are reviewing PBJ320 nursing home staffing data.',
        '',
        f'Audience mode: {mode_label}',
    ]
    if mode_instruction:
        parts.extend(['', 'Audience instructions:', mode_instruction])
    parts.extend(
        [
            '',
            'Task:',
            PBJ_LAYERED_TASK,
            '',
            'Source type:',
            source_type_label(page_type, page_kind),
            '',
            'Important source limits:',
            compose_source_limits_block(page_type),
            '',
            'PBJ320 screening flags (when present in context):',
            PBJ320_SCREENING_FLAGS_BLOCK,
            '',
            'Pandemic-era longitudinal context (2020–2023 overlap):',
            PBJ_REVIEW_HISTORICAL_CONTEXT_BLOCK,
            '',
            'Staffing trend timing by audience:',
            PBJ_AUDIENCE_TIMING_EMPHASIS_BLOCK,
            '',
            'Output format:',
            output_fmt,
            '',
            'Tone:',
            PBJ_LAYERED_TONE,
            '',
            'Presentation:',
            presentation,
            '',
            'Use the PBJ320 page URL, facility identifiers, key metrics, narrative summary, and '
            'quarterly CSV notes in the context block below as your source for this review. '
            'When those hooks include Care Compare, entity, state, report, or SFF URLs, keep them in your answer when useful.',
        ]
    )
    body = '\n'.join(parts)
    if legacy_sections and length_key == 'quick':
        body += '\n\n' + _format_advanced_sections(mode, audience)
    return body


def compose_review_prompt_for_lens(
    lens: Optional[str] = None,
    *,
    page_type: str = 'facility',
) -> str:
    """Persona-specific quick prompt for provider/dashboard (lens already chosen)."""
    return compose_layered_review_prompt(lens, page_type=page_type, length='quick')


def compose_review_prompt_quick(
    config: Optional[ReviewConfig] = None,
    *,
    page_type: str = 'facility',
) -> str:
    cfg = (config or ReviewConfig()).normalized()
    lens_key = 'general'
    for lid, aud in PBJ_LENS_TO_AUDIENCE.items():
        if aud == cfg.audience:
            lens_key = lid
            break
    return compose_layered_review_prompt(lens_key, page_type=page_type, length='quick')


def compose_review_prompt_advanced(
    config: Optional[ReviewConfig] = None,
    *,
    page_type: str = 'facility',
    material_placeholder: str = PBJ_REVIEW_HANDOFF_PLACEHOLDER,
    lens: Optional[str] = None,
) -> str:
    cfg = (config or ReviewConfig()).normalized()
    mode = get_review_mode(cfg.audience)
    lens_key = normalize_review_lens(lens) if lens else 'general'
    if lens is None:
        for lid, aud in PBJ_LENS_TO_AUDIENCE.items():
            if aud == cfg.audience:
                lens_key = lid
                break
    header = compose_layered_review_prompt(
        lens_key, page_type=page_type, length='detailed'
    )
    sections = _format_advanced_sections(mode, cfg.audience)
    checks = '\n'.join(f'- {c}' for c in PBJ_REVIEW_CORE_CHECKS)
    return f"""{header}

Additional section guidance:
{sections}

Shared interpretation checks:
{checks}

Analyze the PBJ320 material below:

{material_placeholder}"""


def compose_review_prompt(
    config: Optional[ReviewConfig] = None,
    *,
    use_advanced: bool = True,
    material_placeholder: str = PBJ_REVIEW_HANDOFF_PLACEHOLDER,
) -> str:
    if use_advanced:
        return compose_review_prompt_advanced(config, material_placeholder=material_placeholder)
    return compose_review_prompt_quick(config)


def normalize_review_lens(lens: Optional[str]) -> str:
    key = (lens or '').strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'analyst': 'general',
        'family_resident': 'family',
        'legislator': 'policymaker',
        'policy': 'policymaker',
    }
    key = aliases.get(key, key)
    return key if key in VALID_REVIEW_LENSES else PBJ_DEFAULT_REVIEW_LENS


def normalize_review_length(length: Optional[str]) -> str:
    key = (length or '').strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'quick_takeaway': 'quick',
        'standard_review': 'standard',
        'detailed_review': 'detailed',
    }
    key = aliases.get(key, key)
    return key if key in VALID_REVIEW_LENGTHS else PBJ_DEFAULT_REVIEW_LENGTH


def lens_to_audience(lens: Optional[str]) -> str:
    return PBJ_LENS_TO_AUDIENCE.get(normalize_review_lens(lens), DEFAULT_AUDIENCE)


# --- Public-site subset (CT preview push): three personas, ombudsman default ---

PUBLIC_VALID_AUDIENCES = frozenset({'ombudsman', 'family_resident', 'journalist'})
PUBLIC_DEFAULT_AUDIENCE = 'ombudsman'
PUBLIC_DEFAULT_REVIEW_LENS = 'ombudsman'
PUBLIC_VALID_REVIEW_LENSES = frozenset({'ombudsman', 'family', 'journalist'})
PUBLIC_LENS_TO_AUDIENCE: dict[str, str] = {
    'ombudsman': 'ombudsman',
    'family': 'family_resident',
    'journalist': 'journalist',
}
PUBLIC_LENS_UI_PRIMARY: tuple[tuple[str, str], ...] = (
    ('ombudsman', 'Ombudsman'),
    ('family', 'Family'),
    ('journalist', 'Journalist'),
)


def normalize_public_audience(audience: Optional[str]) -> str:
    key = (audience or '').strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'family': 'family_resident',
        'resident': 'family_resident',
        'family_resident': 'family_resident',
        'ombuds': 'ombudsman',
        'reporter': 'journalist',
        'news': 'journalist',
    }
    key = aliases.get(key, key)
    return key if key in PUBLIC_VALID_AUDIENCES else PUBLIC_DEFAULT_AUDIENCE


def normalize_public_review_lens(lens: Optional[str]) -> str:
    key = (lens or '').strip().lower().replace(' ', '_').replace('-', '_')
    aliases = {
        'family_resident': 'family',
        'ombuds': 'ombudsman',
        'reporter': 'journalist',
    }
    key = aliases.get(key, key)
    return key if key in PUBLIC_VALID_REVIEW_LENSES else PUBLIC_DEFAULT_REVIEW_LENS


def public_lens_to_audience(lens: Optional[str]) -> str:
    return PUBLIC_LENS_TO_AUDIENCE.get(normalize_public_review_lens(lens), PUBLIC_DEFAULT_AUDIENCE)


def review_config_for_lens(
    lens: Optional[str],
    page_type: str = 'facility',
    *,
    geography_level: Optional[str] = None,
) -> ReviewConfig:
    geo = geography_level or infer_geography_level_from_page_type(page_type)
    return ReviewConfig(audience=lens_to_audience(lens), geography_level=geo).normalized()


def compose_review_guardrails(page_type: str = 'facility') -> str:
    """Backward-compatible alias for the layered source-limits block."""
    return 'Important source limits:\n' + compose_source_limits_block(page_type)


def _format_tier_sections(tier: str, mode: dict[str, Any], audience: str) -> str:
    if mode.get('sections'):
        return _format_advanced_sections(mode, audience)
    section_list = list(OUTPUT_TIER_SECTIONS[tier])
    extra = mode.get('extra_sections') or []
    if mode.get('prepend_extra_sections'):
        section_list = extra + section_list
    else:
        section_list.extend(extra)
    parts = [f'Format your response using the {tier} output tier:', '']
    instructions = mode.get('section_instructions') or {}
    for title, instruction in section_list:
        parts.append(f'## {title}')
        override = instructions.get(title)
        if override:
            parts.append(override)
        elif instruction:
            parts.append(instruction)
        parts.append('')
    parts.append(
        'For "What the data cannot prove," list only limits relevant to this query — no boilerplate.'
    )
    return '\n'.join(parts).rstrip()


def compose_standard_review_prompt(
    config: Optional[ReviewConfig] = None,
    *,
    page_type: str = 'facility',
    material_placeholder: str = PBJ_REVIEW_HANDOFF_PLACEHOLDER,
    lens: Optional[str] = None,
) -> str:
    cfg = (config or ReviewConfig()).normalized()
    mode = get_review_mode(cfg.audience)
    lens_key = normalize_review_lens(lens) if lens else 'general'
    if lens is None:
        for lid, aud in PBJ_LENS_TO_AUDIENCE.items():
            if aud == cfg.audience:
                lens_key = lid
                break
    header = compose_layered_review_prompt(
        lens_key, page_type=page_type, length='standard'
    )
    sections = _format_tier_sections(OUTPUT_TIER_STANDARD, mode, cfg.audience)
    checks = '\n'.join(f'- {c}' for c in PBJ_REVIEW_CORE_CHECKS)
    return f"""{header}

Additional section guidance:
{sections}

Shared interpretation checks:
{checks}

Analyze the PBJ320 material below:

{material_placeholder}"""


def compose_dashboard_prompt(
    lens: Optional[str] = None,
    length: Optional[str] = None,
    *,
    page_type: str = 'facility',
    material_placeholder: str = PBJ_REVIEW_HANDOFF_PLACEHOLDER,
) -> str:
    """Prompt for dashboard AI helper from review lens + output length."""
    lens_key = normalize_review_lens(lens)
    length_key = normalize_review_length(length)
    cfg = review_config_for_lens(lens_key, page_type)

    if length_key == 'quick':
        return compose_layered_review_prompt(lens_key, page_type=page_type, length='quick')

    if length_key == 'standard':
        return compose_standard_review_prompt(
            cfg,
            page_type=page_type,
            material_placeholder=material_placeholder,
            lens=lens_key,
        )

    return compose_review_prompt_advanced(
        cfg,
        page_type=page_type,
        material_placeholder=material_placeholder,
        lens=lens_key,
    )


def framework_export_for_js() -> dict[str, Any]:
    """JSON-serializable bundle for window.__PBJ_REVIEW_FRAMEWORK__."""
    return {
        'version': '12',
        'defaultAudience': DEFAULT_AUDIENCE,
        'contextLevels': PBJ_REVIEW_CONTEXT_LEVELS,
        'audiences': sorted(VALID_AUDIENCES),
        'outputTiers': {
            'brief': OUTPUT_TIER_BRIEF,
            'standard': OUTPUT_TIER_STANDARD,
            'detailed': OUTPUT_TIER_DETAILED,
        },
        'outputTierByAudience': OUTPUT_TIER_BY_AUDIENCE,
        'audienceDetectionPatterns': [
            {'pattern': p, 'audience': a} for p, a in AUDIENCE_DETECTION_PATTERNS
        ],
        'sourceLevels': PBJ_SOURCE_LEVEL_COPY,
        'modes': {
            k: {
                'label': v['label'],
                'emphasis': v['emphasis'],
                'outputTier': v.get('output_tier') or output_tier_for_audience(k),
                'sections': v.get('sections') or [],
                'extraSections': v.get('extra_sections') or [],
                'prependExtraSections': bool(v.get('prepend_extra_sections')),
                'quickModifier': v.get('quick_modifier', ''),
                'sectionInstructions': v.get('section_instructions', {}),
                'legacyOutputFormat': (v.get('legacy_output_format') or '').strip(),
                'legacyPresentation': (v.get('legacy_presentation') or '').strip(),
            }
            for k, v in PBJ_REVIEW_MODES.items()
        },
        'chatgpt': {
            'urlPrefillMax': 1900,
            'stubTemplate': PBJ_CHATGPT_REVIEW_STUB_TEMPLATE,
        },
        'core': {
            'limitations': PBJ_REVIEW_CORE_LIMITATIONS,
            'checks': PBJ_REVIEW_CORE_CHECKS,
            'rules': PBJ_REVIEW_CORE_RULES,
            'handoffPlaceholder': PBJ_REVIEW_HANDOFF_PLACEHOLDER,
            'quickPrompt': PBJ_QUICK_PROMPT_TEXT,
            'reviewStructure': PBJ_REVIEW_RESPONSE_STRUCTURE,
        },
        'layered': {
            'task': PBJ_LAYERED_TASK,
            'tone': PBJ_LAYERED_TONE,
            'visualSelectionRule': PBJ_VISUAL_SELECTION_RULE,
            'visualCompletenessAttribution': PBJ_VISUAL_COMPLETENESS_FALLBACK_ATTRIBUTION,
            'visualOutputHint': PBJ_VISUAL_OUTPUT_HINT,
            'visualAudienceBulletByMode': dict(PBJ_AUDIENCE_VISUAL_FRAMING),
            'outputQuick': PBJ_LAYERED_OUTPUT_QUICK,
            'outputStandard': PBJ_LAYERED_OUTPUT_STANDARD,
            'outputDetailed': PBJ_LAYERED_OUTPUT_DETAILED,
            'audienceModeDisplay': PBJ_AUDIENCE_MODE_DISPLAY,
            'audienceModeInstructions': PBJ_AUDIENCE_MODE_INSTRUCTIONS,
            'audienceTimingEmphasis': PBJ_AUDIENCE_TIMING_EMPHASIS_BLOCK,
            'pbj320ScreeningFlagsBlock': PBJ320_SCREENING_FLAGS_BLOCK,
            'cmsRiskScreeningBlock': PBJ320_SCREENING_FLAGS_BLOCK,
            'historicalContextBlock': PBJ_REVIEW_HISTORICAL_CONTEXT_BLOCK,
            'sourceTypeLabels': PBJ_SOURCE_TYPE_LABELS,
        },
        'defaultConfig': ReviewConfig().normalized().to_dict(),
        'lensConfig': {
            'defaultLens': PBJ_DEFAULT_REVIEW_LENS,
            'defaultLength': PBJ_DEFAULT_REVIEW_LENGTH,
            'storageKeys': {
                'lens': PBJ_LENS_STORAGE_KEY,
                'length': PBJ_LENGTH_STORAGE_KEY,
            },
            'primaryLenses': [{'id': lid, 'label': lbl} for lid, lbl in PBJ_LENS_UI_PRIMARY],
            'moreLenses': [{'id': lid, 'label': lbl} for lid, lbl in PBJ_LENS_UI_MORE],
            'lengths': [{'id': lid, 'label': lbl} for lid, lbl in PBJ_LENGTH_UI],
            'lensToAudience': PBJ_LENS_TO_AUDIENCE,
            'quickTakeaways': PBJ_LENS_QUICK_TAKEAWAY,
            'guardrailsShared': PBJ_REVIEW_GUARDRAILS_SHARED,
        },
        'outputTierSections': {
            OUTPUT_TIER_STANDARD: OUTPUT_TIER_SECTIONS[OUTPUT_TIER_STANDARD],
            OUTPUT_TIER_DETAILED: OUTPUT_TIER_SECTIONS[OUTPUT_TIER_DETAILED],
        },
        'providerDashboardSupplements': provider_dashboard_supplements_export(),
    }


def public_framework_export_for_js() -> dict[str, Any]:
    """Subset of the review framework for the public site (three personas, ombudsman default)."""
    from pbj_ai_config import (
        allowed_public_audience_modes,
        allowed_public_review_lenses,
        public_default_audience,
        public_default_review_lens,
    )

    data = framework_export_for_js()
    public_audiences = list(allowed_public_audience_modes())
    data['defaultAudience'] = public_default_audience()
    data['audiences'] = sorted(public_audiences)
    data['modes'] = {k: v for k, v in (data.get('modes') or {}).items() if k in public_audiences}
    data['outputTierByAudience'] = {
        k: v
        for k, v in (data.get('outputTierByAudience') or {}).items()
        if k in public_audiences
    }
    data['audienceDetectionPatterns'] = []
    lc = dict(data.get('lensConfig') or {})
    lc['defaultLens'] = public_default_review_lens()
    lc['primaryLenses'] = [{'id': lid, 'label': lbl} for lid, lbl in allowed_public_review_lenses()]
    lc['moreLenses'] = []
    lc['lensToAudience'] = dict(PUBLIC_LENS_TO_AUDIENCE)
    data['lensConfig'] = lc
    data['defaultConfig'] = ReviewConfig(audience=public_default_audience()).normalized().to_dict()
    return data


def public_framework_json_for_js() -> str:
    return json.dumps(public_framework_export_for_js(), ensure_ascii=False)


def framework_json_for_js() -> str:
    return json.dumps(framework_export_for_js(), ensure_ascii=False)


def parse_review_config_from_request(
    audience: Optional[str] = None,
    geography_level: Optional[str] = None,
    context_note: Optional[str] = None,
) -> ReviewConfig:
    return ReviewConfig(
        audience=audience,
        geography_level=geography_level,
        context_note=context_note or '',
    ).normalized()
