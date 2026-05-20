"""PBJ320 AI Support: prompts, page context, HTML helpers, and copy constants.

Evidence-first helper layer for public-site AI handoffs — not a standalone AI product.
"""

from __future__ import annotations

import csv
import html
import io
import json
import re
from collections import defaultdict
from datetime import date
from typing import Any, Mapping, Optional, Sequence

from pbj_ai_config import (
    allowed_public_review_lenses,
    pbj_ai_dashboards_enabled,
    pbj_ai_page_enabled,
    public_default_audience,
    public_default_review_lens,
    should_show_public_ai_tools,
)
from pbj_review_framework import (
    DEFAULT_AUDIENCE,
    PBJ_DEFAULT_REVIEW_LENS,
    PUBLIC_DEFAULT_AUDIENCE,
    PBJ_LENS_STORAGE_KEY,
    PBJ_LENS_UI_MORE,
    PBJ_LENS_UI_PRIMARY,
    PBJ_LENGTH_STORAGE_KEY,
    PBJ_LENGTH_UI,
    PBJ_REVIEW_CONTEXT_LEVELS,
    PBJ_REVIEW_HANDOFF_PLACEHOLDER,
    ReviewConfig,
    compose_dashboard_prompt,
    compose_provider_dashboard_supplement_block,
    compose_review_prompt,
    compose_review_prompt_advanced,
    compose_review_prompt_for_lens,
    compose_review_prompt_quick,
    format_source_level_block,
    framework_export_for_js,
    framework_json_for_js,
    normalize_public_review_lens,
    public_framework_export_for_js,
    public_framework_json_for_js,
    public_lens_to_audience,
    infer_geography_level_from_page_type,
    lens_to_audience,
    normalize_audience,
    normalize_geography_level,
    normalize_review_lens,
    review_config_for_lens,
)

# --- Version ---
PBJ_AI_VERSION = '0.1'
PBJ_AI_LAST_UPDATED = 'May 2026'
PBJ_AI_VERSION_LABEL = f'PBJ320 AI Prompt v{PBJ_AI_VERSION} · Updated {PBJ_AI_LAST_UPDATED}'

# --- Support page hero ---
PBJ_AI_HERO_TITLE = 'Use AI to review PBJ320 staffing data responsibly'
PBJ_AI_HERO_SUBHEAD = (
    'PBJ320 prompts help users review nursing home staffing pages, screenshots, and exports '
    'without overstating what the data can prove. Facility AI handoff tools are in Connecticut preview.'
)
PBJ_AI_HERO_LEAD = (
    'Choose a PBJ320 page or export, copy the review prompt, and ask ChatGPT or Claude '
    'for a structured review that separates what the data shows, what it may suggest, '
    'and what it cannot prove.'
)
PBJ_AI_HERO_CONTEXT = ''
# Back-compat placeholders
PBJ_AI_HERO_SUBTITLE = PBJ_AI_HERO_LEAD
PBJ_AI_HERO_BODY = ''
PBJ_AI_THESIS_LINE = ''
PBJ_AI_FRAMEWORK_BADGE = 'PBJ320 Responsible Review Framework'
PBJ_AI_ANTI_LAUUNDERING = PBJ_AI_FRAMEWORK_BADGE  # back-compat placeholder name

PBJ_AI_HOW_IT_WORKS: tuple[tuple[str, str], ...] = (
    (
        'Open a PBJ320 page or export',
        'Start with a facility page, state page, screenshot, CSV, or premium dashboard.',
    ),
    (
        'Use the PBJ320 review prompt',
        'Paste the prompt into ChatGPT or Claude with the PBJ320 material.',
    ),
    (
        'Get a responsible review',
        'The framework keeps evidence, interpretation, and limits separate — '
        'shows / suggests / cannot prove.',
    ),
)

PBJ_AI_FACILITY_CARD_TITLE = 'Need staffing data to review?'
PBJ_AI_FACILITY_CARD_COPY = (
    'Search for a facility or open a state page, then come back here to copy the AI review prompt.'
)
PBJ_AI_FACILITY_NEXT_STEP = (
    'Open the facility page, then use Copy page context on that page before pasting into AI.'
)

PBJ_AI_PROMPT_CARD_TITLE = 'Copy a PBJ320 review prompt'
PBJ_AI_PROMPT_CARD_COPY = (
    'Use this when asking ChatGPT or Claude to review a PBJ320 page, screenshot, CSV, or export.'
)

PBJ_AI_SOURCE_OPTIONS: tuple[tuple[str, str], ...] = (
    ('facility', 'Facility page'),
    ('state', 'State page'),
    ('screenshot', 'Screenshot'),
    ('csv', 'CSV / export'),
    ('premium', 'Premium dashboard'),
)

PBJ_AI_CLAUDE_CARD_TITLE = 'Deeper analysis on PBJ320 Premium'
PBJ_AI_CLAUDE_CARD_COPY = (
    'Premium dashboards add daily staffing, incident windows, and evidence packets — '
    'with the same cautious shows / suggests / cannot prove framing.'
)
PBJ_AI_CLAUDE_HELPER = (
    'Public pages are a quarterly screening layer. For multi-facility or daily PBJ workflows, '
    'see pbj320.com/premium.'
)

PBJ_AI_RESPONSIBLE_TITLE = 'Responsible AI for nursing home staffing data'
PBJ_AI_RESPONSIBLE_LEAD = (
    'AI can make PBJ staffing data easier to understand, but it can also launder weak claims '
    'into confident conclusions. PBJ320’s review framework is designed to slow that down.'
)
PBJ_AI_RESPONSIBLE_PRINCIPLES: tuple[tuple[str, str], ...] = (
    (
        'Separate evidence from interpretation',
        'PBJ data can show reported staffing patterns. It cannot, by itself, prove why care outcomes happened.',
    ),
    (
        'Respect the limits of the source',
        'PBJ320 free pages summarize quarterly staffing. PBJ320 Premium adds daily PBJ by work date, '
        'trends, roster/Employee Detail, compliance views, and exportable evidence packets — still '
        'requiring records, context, and judgment; do not substitute HPRD × census math for Premium data.',
    ),
    (
        'Use AI to ask better questions',
        'The goal is not automated blame. The goal is sharper follow-up: what changed, what is missing, '
        'and what needs verification.',
    ),
)

# --- Facility / dashboard helper (compact) ---
PBJ_AI_HELPER_TITLE = 'Reviewing this page with AI?'
PBJ_AI_HELPER_BODY = (
    'Pick who you are and how long, then copy or open a PBJ320 packet in Claude or ChatGPT.'
)

PBJ_FACILITY_CSV_LIMITATIONS = (
    'This PBJ320 free quarterly page summarizes CMS PBJ staffing by quarter (visible facility-level metrics). '
    'CMS also collects daily facility-day PBJ; PBJ320 Premium can show daily work-date detail, trends, and roster '
    'exports. This packet does not include daily/shift breakdowns, employee roster rows, or resident-level care — '
    'scope of this page, not missing CMS data.'
)

PBJ_PBJ_SUBMISSION_CONTEXT = (
    'CMS Payroll-Based Journal (PBJ) reflects facility-submitted payroll extracts processed under CMS rules '
    '(edits, validation, and outlier handling apply). It is not a continuous third-party audit of every line item '
    'at submission time; treat it as regulated self-reported administrative data, not independent bedside verification.'
)

PBJ_ROLE_HPRD_SEMANTICS = (
    'Role columns (RN, LPN, nurse aide) in PBJ320 tables or CSVs use “—” or blanks when a value is missing or not '
    'populated in this extract — that is **not the same as** “zero clinical staffing” or “zero reported hours” unless '
    'the source explicitly shows 0.00. PBJ hours are tied to CMS job categories; some licensed practical work may '
    'appear under other lines depending on how the facility mapped positions. Do not narrate long runs of blanks as '
    '“no LPN hours recorded” without that caveat.'
)

PBJ_CSV_ATTACHMENT_NOTE = (
    'If you attach a PBJ320 quarterly CSV, use it as structured quarterly context only. Do not infer daily, '
    'weekend, roster, or incident-date detail from quarterly rows alone.'
)

PBJ_FACILITY_HANDOFF_CSV_NOTE = (
    'A PBJ320 quarterly snapshot or trend CSV may be attached alongside this packet. '
    'Use CSV rows as structured quarterly context only — not as daily or employee-level data.'
)

COPY_PACKET_SUCCESS = 'PBJ320 AI packet copied.'
COPY_PROMPT_ONLY_SUCCESS = 'PBJ320 prompt copied.'


def ai_helper_framework_json_for_js() -> str:
    """Framework bundle for dashboard pages: lens/length prompts + helper copy."""
    data = public_framework_export_for_js()
    data['helper'] = {
        'brandFooter': PBJ_AI_BRAND_FOOTER,
        'csvAttachmentNote': PBJ_CSV_ATTACHMENT_NOTE,
        'csvHandoffNote': PBJ_FACILITY_HANDOFF_CSV_NOTE,
        'briefOutputNote': PBJ_AI_BRIEF_OUTPUT_NOTE,
        'standardOutputNote': PBJ_AI_STANDARD_OUTPUT_NOTE,
        'betaModalStorageKey': PBJ_AI_BETA_MODAL_SEEN_KEY,
        'briefStorageKey': 'pbj320_ai_brief_mode',
    }
    return json.dumps(data, ensure_ascii=False)


PBJ_AI_BRIEF_OUTPUT_NOTE = (
    'RESPONSE LENGTH (brief mode): Keep the answer short — about 6–10 tight bullets or '
    'under 400 words unless the user asks for more. Lead with the strongest supported screening '
    'signal; skip long background and avoid repeating the full framework headings. '
    'Still include the one required DATA VISUAL (compact table, mini chart, or chart-ready Markdown—or why none).'
)

PBJ_AI_STANDARD_OUTPUT_NOTE = (
    'RESPONSE LENGTH (standard mode): Use the full shows / suggests / cannot prove flow with '
    'appropriate detail for the audience — still cautious and evidence-bound.'
)

PBJ_AI_BETA_MODAL_SEEN_KEY = 'pbj320_ai_beta_modal_seen'

# --- Prompts (composed from pbj_review_framework; default = analyst) ---
PBJ_AI_HANDOFF_PLACEHOLDER = PBJ_REVIEW_HANDOFF_PLACEHOLDER
_DEFAULT_REVIEW = ReviewConfig(audience=DEFAULT_AUDIENCE)
_DEFAULT_PUBLIC_REVIEW = ReviewConfig(audience=PUBLIC_DEFAULT_AUDIENCE)
PBJ_AI_PROMPT_QUICK = compose_review_prompt_quick(_DEFAULT_PUBLIC_REVIEW)
PBJ_AI_PROMPT_ADVANCED = compose_review_prompt_advanced(_DEFAULT_PUBLIC_REVIEW)

# Back-compat alias
PBJ_AI_PROMPT = PBJ_AI_PROMPT_ADVANCED

PBJ_AI_LIMITATIONS = (
    'PBJ data can show reported staffing hours, role mix, facility-level patterns, and changes over '
    'time. It cannot prove what happened on a specific shift, whether a specific resident received '
    'care, whether staffing caused an injury, or whether a legal standard was violated.'
)

PBJ_INTERPRETATION_RULES = [
    'Check whether any average is being pulled by outliers.',
    'Compare mean and median where available.',
    'Check whether the time window is large enough to support the conclusion.',
    'If census declined, HPRD may look higher without more staff.',
    'State averages can mask wide within-state variation.',
    'Treat red flags as screening signals, not findings.',
]

PBJ_AI_CAUTION_LINE = (
    'AI can help summarize and organize PBJ staffing information. It cannot prove what happened '
    'on a specific shift, whether a specific resident received care, whether staffing caused an '
    'injury, or whether a legal standard was violated.'
)

PBJ_AI_DO_BULLETS = [
    'Include facility name, CCN, quarter, state, and the date range you are reviewing.',
    'Ask for shows, suggests, and cannot prove — plus follow-up questions, not a final verdict.',
    'Ask whether the pattern depends on mean vs median, outliers, census, or a short time window.',
    'Say whether you are on a free quarterly page or a premium daily/export view.',
    'Works with paste/upload or a browser AI sidebar — keep the source material attached.',
]

PBJ_AI_AVOID_BULLETS = [
    'Do not treat PBJ data alone as proof of neglect or a legal violation.',
    'Do not treat CMS case-mix hours as a legal staffing minimum.',
    'Do not trust one extreme day, one average, or an AI summary without the source page.',
]

PBJ_AI_INTERPRETATION_CHECKS = [
    ('Mean vs. median', 'One outlier day can drag averages; check the median when you can.'),
    ('Census & HPRD', 'Fewer residents can make HPRD look higher without more staff.'),
    ('Time window', 'A week, a quarter, and a year can tell different stories.'),
    ('State averages', '“Near the state average” can still be weak among local peers.'),
    ('Red flags', 'Screening signals — not findings on their own.'),
]

PBJ_AI_FREE_TIER = [
    'Quarterly facility context on public pages',
    'Visible facility-level comparisons',
    'Quick AI prompt and basic page context (Connecticut preview)',
    'General interpretation checks',
]

PBJ_AI_PREMIUM_TIER = [
    'Daily staffing exports',
    '90-day aide/CNA pattern review',
    'Mean/median/outlier tables',
    'Trend tables',
    'Incident-window context',
    'Facility evidence packets',
    'Tailored records-to-request checklist',
    'Custom interpretation',
]

PBJ_AI_AUDIENCES = [
    (
        'Ombudsman',
        'Resident-centered triage — practical questions for visits and complaints without alleging violations.',
    ),
    ('Families', 'Plain-English questions — what the page shows and what to ask the facility.'),
    ('Journalists', 'Defensible story angles and what to verify before publication.'),
]

PBJ_AI_AUDIENCE_TAGS = (
    'Ombudsman',
    'Families',
    'Journalists',
)

# Back-compat alias for scripts/docs
PBJ_AI_DIFFERENT_USERS = [(name, '', 'chart') for name in PBJ_AI_AUDIENCE_TAGS]

_PERSONA_ICONS: dict[str, str] = {
    'home': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>'
        '</svg>'
    ),
    'megaphone': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="m3 11 18-5v12L3 13v-2z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>'
        '</svg>'
    ),
    'newspaper': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/>'
        '<path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/>'
        '</svg>'
    ),
    'chart': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>'
        '</svg>'
    ),
    'scale': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
        '<path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
        '<path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>'
        '</svg>'
    ),
    'capitol': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M3 21h18"/><path d="M5 21V9l7-4 7 4v12"/><path d="M9 21v-6h6v6"/>'
        '<path d="M9 9h.01"/><path d="M15 9h.01"/>'
        '</svg>'
    ),
    'building': (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/>'
        '<path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/>'
        '<path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/>'
        '<path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/>'
        '</svg>'
    ),
}

CLAUDE_INSTALL_INSTRUCTIONS = """1. Download the PBJ320 Claude Skill ZIP.
2. Open Claude.
3. Go to Customize → Skills.
4. Upload the ZIP file.
5. Enable the Skill.
6. Start a new Claude chat and paste or upload a PBJ320 page, screenshot, dashboard, or export.
7. Ask Claude: "Use the PBJ320 Staffing Review Skill to analyze this."

Claude Skill availability and setup may vary by Claude plan and workspace settings."""

CLAUDE_SKILL_BLURB = (
    'Best for repeat use — same shows / suggests / cannot prove framework as the copy prompt.'
)

PBJ_AI_BRAND_FOOTER = (
    '---\n'
    'PBJ320 (pbj320.com) · public CMS Payroll Based Journal data presented by 320 Consulting.\n'
    'Premium dashboards & evidence packets: pbj320.com/premium · eric@320insight.com'
)

SKILL_ZIP_PATH = 'downloads/pbj320-staffing-review.zip'
SKILL_ZIP_URL = '/downloads/pbj320-staffing-review.zip'

# Copy success toasts (JS should match)
COPY_PROMPT_SUCCESS = 'PBJ320 prompt copied.'
COPY_CONTEXT_SUCCESS = 'PBJ320 context copied.'

PBJ_BROWSER_AI_CAUTION = (
    'On facility pages, use Copy page context — cleaner than browser scraping.'
)

PBJ_AI_HELPER_HINT = (
    'For cleaner AI review, copy the structured page context instead of relying only on browser scraping.'
)

PBJ_HPRD_DEFINITION = (
    'HPRD means hours per resident day. It estimates reported staffing hours per resident day across the period. '
    'It is not a shift-level staff-to-resident ratio.'
)

PBJ_CASE_MIX_INDEX_DEF = (
    'Case-mix index reflects modeled resident acuity. Higher values generally suggest residents are modeled as needing more nursing care.'
)

PBJ_CASE_MIX_RATIO_DEF = (
    'Case-mix index ratio compares the facility\'s nursing case-mix acuity to the national average. '
    'It is not a measure of reported staffing adequacy.'
)

PBJ_CMS_CASE_MIX_HPRD_DEF = (
    'CMS case-mix HPRD is an acuity-adjusted benchmark/reference point shown on PBJ320. It is not a legal staffing minimum.'
)

PBJ_DEFINITIONS_BLOCK = [
    PBJ_HPRD_DEFINITION,
    PBJ_CASE_MIX_INDEX_DEF,
    PBJ_CASE_MIX_RATIO_DEF,
    PBJ_CMS_CASE_MIX_HPRD_DEF,
]

PBJ_FACILITY_INTERPRETATION_CHECKS = [
    'This is a quarterly snapshot, not a daily staffing review.',
    'Check whether averages are hiding daily variation, but daily data is not shown on this page unless explicitly provided.',
    'When average daily census appears in the context or embedded quarterly CSV, use it for HPRD/denominator interpretation (do not treat census as unavailable).',
    'State averages can mask wide within-state variation.',
    'Treat red flags as screening signals, not findings.',
    PBJ_ROLE_HPRD_SEMANTICS,
]

PBJ_STATE_INTERPRETATION_CHECKS = [
    'Check whether the page is showing mean, median, percentile, or facility distribution.',
    'State averages can mask wide within-state variation.',
    'Check sample size / number of facilities if shown.',
    'Do not infer facility-level conditions from state-level aggregates alone.',
    'Treat top/bottom lists or red flags as screening signals, not findings.',
]

PBJ_FACILITY_LIMITATIONS = (
    'PBJ data can show reported staffing hours, role mix, facility-level patterns, and changes over time. '
    'This page cannot prove what happened on a specific shift, whether a specific resident received care, '
    'whether staffing caused an injury, or whether a legal standard was violated.'
)

PBJ_STATE_LIMITATIONS = (
    'State-level PBJ data can show aggregate staffing patterns and comparison context. '
    'It cannot prove what happened at a specific facility, on a specific shift, or to a specific resident '
    'without facility-level and source-level records.'
)

_SUMMARY_NOISE_PATTERNS = (
    re.compile(r'≈\s*[\d.,]+\s*residents\s+per\s+total\s+staff', re.I),
    re.compile(r'residents\s+per\s+total\s+staff', re.I),
    re.compile(r'residents\s+sharing\s+each\s+nurse', re.I),
    re.compile(r'residents\s+per\s+nurse\s+staff\s+hour', re.I),
    re.compile(r'font-size\s*:', re.I),
    re.compile(r'rgba\s*\(', re.I),
    re.compile(r'display\s*:\s*(inline|flex|block)', re.I),
    re.compile(r'padding\s*:\s*\d', re.I),
    re.compile(r'border-radius\s*:', re.I),
    re.compile(r'CMS\s+would\s+expect', re.I),
    re.compile(r'CMS\s+expected\s+staffing', re.I),
    re.compile(r'required\s+staffing', re.I),
    re.compile(r'staffing\s+floor', re.I),
    re.compile(r'staffing\s+adequacy', re.I),
    re.compile(r'failed\s+case-mix\s+standard', re.I),
)


def strip_html_to_plain(text: Optional[str]) -> str:
    if not text:
        return ''
    s = re.sub(r'<br\s*/?>', '\n', str(text), flags=re.I)
    s = re.sub(r'</p>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def sanitize_context_text(text: Optional[str]) -> str:
    """Strip HTML/UI noise and HPRD-to-resident-ratio phrasing from pasted summaries."""
    s = strip_html_to_plain(text)
    if not s:
        return ''
    for pat in _SUMMARY_NOISE_PATTERNS:
        s = pat.sub('', s)
    s = re.sub(r'\(\s*\)', '', s)
    s = re.sub(r'\s{2,}', ' ', s).strip(' ,.;')
    return s


def _casemix_benchmark_phrase(above_below: Optional[str], case_mix_hprd: Any) -> str:
    cm = str(case_mix_hprd or '').strip()
    if not cm or cm in ('—', 'N/A', 'n/a', '-'):
        return ''
    rel = (above_below or '').strip().lower()
    if rel in ('above', 'below', 'around'):
        return f'{rel} the CMS case-mix benchmark ({cm} total nurse HPRD)'
    return f'compared with the CMS case-mix benchmark ({cm} total nurse HPRD)'


def build_facility_summary_plain(
    *,
    facility_name: str = '',
    total_hprd: Any = None,
    quarter: str = '',
    state_comparison: str = '',
    above_below_casemix: Optional[str] = None,
    case_mix_hprd: Any = None,
    fallback_summary: str = '',
) -> str:
    name = (facility_name or 'This facility').strip()
    hprd = str(total_hprd or '').strip()
    period = (quarter or '').strip()
    if hprd and hprd not in ('—', 'N/A') and period:
        parts = [f'{name} reported {hprd} total nurse HPRD in {period}']
        sc = (state_comparison or '').strip().rstrip('.')
        if sc:
            if sc.lower().startswith(('it ranks', 'and ranks', 'ranked')):
                parts.append(sc)
            else:
                parts.append(sc)
        cm_phrase = _casemix_benchmark_phrase(above_below_casemix, case_mix_hprd)
        if cm_phrase:
            if parts[-1].endswith('.'):
                parts[-1] = parts[-1].rstrip('.')
            parts.append(f', {cm_phrase}')
        return ' '.join(parts).replace('  ', ' ').strip().rstrip('.') + '.'
    cleaned = sanitize_context_text(fallback_summary)
    return cleaned


def _append_definitions(lines: list[str]) -> None:
    lines.append('')
    lines.append('Definitions:')
    for d in PBJ_DEFINITIONS_BLOCK:
        lines.append(f'- {d}')


def _append_metric_section(lines: list[str], heading: str, metric_lines: list[Optional[str]]) -> None:
    lines.append('')
    lines.append(heading)
    shown = [ln for ln in metric_lines if ln]
    if shown:
        lines.extend(shown)
    else:
        lines.append('- [not shown on this page]')


def _metric_line(label: str, value: Any, suffix: str = '') -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ('—', 'N/A', 'n/a', '-'):
        return None
    if suffix and not s.lower().endswith(suffix.strip().lower()):
        s = f'{s}{suffix}'
    return f'- {label}: {s}'


def _ul_html(items: list[str]) -> str:
    return '<ul>' + ''.join(f'<li>{html.escape(i)}</li>' for i in items) + '</ul>'


def hero_lead_html() -> str:
    """Hero lead with bold evidence-triad keywords."""
    text = html.escape(PBJ_AI_HERO_LEAD)
    for kw in ('shows', 'suggests', 'cannot prove'):
        text = text.replace(kw, f'<strong>{kw}</strong>')
    return text


def interpretation_checks_html() -> str:
    items = ''.join(
        f'<li><strong>{html.escape(title)}</strong> — {html.escape(body)}</li>'
        for title, body in PBJ_AI_INTERPRETATION_CHECKS
    )
    return f'<ul class="ai-checks-compact">{items}</ul>'


def audiences_html() -> str:
    parts = []
    for title, body in PBJ_AI_AUDIENCES:
        parts.append(
            f'<article class="ai-audience-card"><h3>{html.escape(title)}</h3>'
            f'<p>{html.escape(body)}</p></article>'
        )
    return '\n'.join(parts)


def different_users_html() -> str:
    tags = ''.join(
        f'<span class="ai-audience-tag">{html.escape(name)}</span>'
        for name in PBJ_AI_AUDIENCE_TAGS
    )
    return f'<p class="ai-audience-tags">{tags}</p>'


def how_it_works_html() -> str:
    steps = ''.join(
        f'<li class="ai-step"><span class="ai-step__num">{i}</span>'
        f'<div class="ai-step__body"><strong>{html.escape(title)}</strong>'
        f'<p>{html.escape(body)}</p></div></li>'
        for i, (title, body) in enumerate(PBJ_AI_HOW_IT_WORKS, start=1)
    )
    return f'<ol class="ai-steps">{steps}</ol>'


def responsible_ai_html() -> str:
    cards = ''.join(
        f'<article class="ai-principle"><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>'
        for title, body in PBJ_AI_RESPONSIBLE_PRINCIPLES
    )
    return f'<div class="ai-principles">{cards}</div>'


def prompt_role_options_html() -> str:
    opts = []
    default_lens = public_default_review_lens()
    for lid, lbl in allowed_public_review_lenses():
        sel = ' selected' if lid == default_lens else ''
        opts.append(f'<option value="{html.escape(lid)}"{sel}>{html.escape(lbl)}</option>')
    return '\n'.join(opts)


def prompt_source_options_html() -> str:
    return '\n'.join(
        f'<option value="{html.escape(sid)}">{html.escape(lbl)}</option>'
        for sid, lbl in PBJ_AI_SOURCE_OPTIONS
    )


def free_premium_boundary_html() -> str:
    free = _ul_html(PBJ_AI_FREE_TIER)
    premium = _ul_html(PBJ_AI_PREMIUM_TIER)
    return f"""
<div class="ai-grid-2 ai-free-premium">
  <div class="ai-boundary ai-boundary--can">
    <h3>Free</h3>
    {free}
  </div>
  <div class="ai-boundary ai-boundary--premium">
    <h3>Premium</h3>
    {premium}
  </div>
</div>"""


def review_config_for_page(
    page_type: str = 'facility',
    *,
    audience: Optional[str] = None,
    geography_level: Optional[str] = None,
    context_note: str = '',
) -> ReviewConfig:
    """Default review config for a dashboard/page type (analyst + inferred geography)."""
    geo = geography_level or infer_geography_level_from_page_type(page_type)
    return ReviewConfig(
        audience=audience or DEFAULT_AUDIENCE,
        geography_level=geo,
        context_note=context_note,
    ).normalized()


def build_page_context(
    *,
    page_type: str = 'facility',
    page_url: str = '',
    page_kind: str = '',
    period: str = '',
    summary: str = '',
    facility_name: str = '',
    ccn: str = '',
    state_name: str = '',
    entity_name: str = '',
    rn_hprd: Any = None,
    lpn_hprd: Any = None,
    na_hprd: Any = None,
    total_hprd: Any = None,
    case_mix_index: Any = None,
    case_mix_index_ratio: Any = None,
    case_mix_hprd: Any = None,
    staffing_percentile: Any = None,
    state_comparison: str = '',
    above_below_casemix: Optional[str] = None,
    facility_count: Any = None,
    state_median: Any = None,
    top_bottom_summary: str = '',
    copied_date: Optional[str] = None,
    review_config: Optional[ReviewConfig] = None,
    county_name: str = '',
    ownership_type: str = '',
    care_compare_url: str = '',
    macpac_reference_line: str = '',
    cms_overall_star_line: str = '',
    cms_staffing_star_line: str = '',
    premium_dashboard_note: str = '',
    entity_page_url: str = '',
    contract_staff_pct: Any = None,
    entity_portfolio_summary: str = '',
    facility_snapshot_context: str = '',
    cms_risk_screening_line: str = '',
    ownership_chow_context: str = '',
    **kwargs: Any,
) -> str:
    """Structured page context for copy/paste into any AI tool."""
    if kwargs:
        pass  # ignore legacy/extra keys from callers without breaking
    cfg = (review_config or review_config_for_page(page_type)).normalized()
    copied_date = copied_date or date.today().isoformat()
    ptype = (page_type or 'facility').strip().lower()

    if ptype == 'state':
        return _build_state_page_context(
            page_url=page_url,
            page_kind=page_kind,
            period=period,
            state_name=state_name,
            rn_hprd=rn_hprd,
            lpn_hprd=lpn_hprd,
            na_hprd=na_hprd,
            total_hprd=total_hprd,
            state_median=state_median,
            facility_count=facility_count,
            staffing_percentile=staffing_percentile,
            top_bottom_summary=top_bottom_summary,
            summary=summary,
            copied_date=copied_date,
            ownership_chow_context=(ownership_chow_context or '').strip(),
        )

    if ptype == 'facility':
        return _build_facility_page_context(
            page_url=page_url,
            page_kind=page_kind,
            period=period,
            facility_name=facility_name,
            ccn=ccn,
            state_name=state_name,
            rn_hprd=rn_hprd,
            lpn_hprd=lpn_hprd,
            na_hprd=na_hprd,
            total_hprd=total_hprd,
            case_mix_index=case_mix_index,
            case_mix_index_ratio=case_mix_index_ratio,
            case_mix_hprd=case_mix_hprd,
            staffing_percentile=staffing_percentile,
            state_comparison=state_comparison or (staffing_percentile or ''),
            above_below_casemix=above_below_casemix,
            summary=summary,
            copied_date=copied_date,
            county_name=county_name,
            ownership_type=ownership_type,
            care_compare_url=care_compare_url,
            macpac_reference_line=macpac_reference_line,
            cms_overall_star_line=cms_overall_star_line,
            cms_staffing_star_line=cms_staffing_star_line,
            premium_dashboard_note=premium_dashboard_note,
            entity_name=(entity_name or '').strip(),
            entity_page_url=(entity_page_url or '').strip(),
            contract_staff_pct=contract_staff_pct,
            entity_portfolio_summary=(entity_portfolio_summary or '').strip(),
            facility_snapshot_context=(facility_snapshot_context or '').strip(),
            cms_risk_screening_line=(cms_risk_screening_line or '').strip(),
            ownership_chow_context=(ownership_chow_context or '').strip(),
        )

    return _build_generic_page_context(
        page_type=ptype,
        page_url=page_url,
        page_kind=page_kind,
        period=period,
        facility_name=facility_name,
        ccn=ccn,
        state_name=state_name,
        entity_name=entity_name,
        total_hprd=total_hprd,
        rn_hprd=rn_hprd,
        summary=summary,
        copied_date=copied_date,
        cfg=cfg,
    )


def _build_facility_page_context(
    *,
    page_url: str,
    page_kind: str,
    period: str,
    facility_name: str,
    ccn: str,
    state_name: str,
    rn_hprd: Any,
    lpn_hprd: Any,
    na_hprd: Any,
    total_hprd: Any,
    case_mix_index: Any,
    case_mix_index_ratio: Any,
    case_mix_hprd: Any,
    staffing_percentile: Any,
    state_comparison: str,
    above_below_casemix: Optional[str],
    summary: str,
    copied_date: str,
    county_name: str = '',
    ownership_type: str = '',
    care_compare_url: str = '',
    macpac_reference_line: str = '',
    cms_overall_star_line: str = '',
    cms_staffing_star_line: str = '',
    premium_dashboard_note: str = '',
    entity_name: str = '',
    entity_page_url: str = '',
    contract_staff_pct: Any = None,
    entity_portfolio_summary: str = '',
    facility_snapshot_context: str = '',
    cms_risk_screening_line: str = '',
    ownership_chow_context: str = '',
) -> str:
    lines: list[str] = ['PBJ320 page context', '']
    if facility_name:
        lines.append(f'Facility: {facility_name}')
    if ccn:
        lines.append(f'CCN: {ccn}')
    if state_name:
        lines.append(f'State: {state_name}')
    _cc_url = (care_compare_url or '').strip()
    if _cc_url:
        lines.append(
            'CMS Care Compare — this facility (use this exact URL in memos; do not substitute the generic '
            f'medicare.gov landing page): {_cc_url}'
        )
    _ent = (entity_name or '').strip()
    if _ent:
        lines.append(f'Affiliated entity / chain (as linked on PBJ320): {_ent}')
    _ent_url = (entity_page_url or '').strip()
    if _ent_url:
        lines.append(f'Entity overview (PBJ320): {_ent_url}')
    _eps = (entity_portfolio_summary or '').strip()
    if _eps:
        lines.append(f'Affiliated entity — portfolio snapshot (CMS chain file / PBJ320): {_eps}')
    if period:
        lines.append(f'Quarter / period: {period}')
    if page_url:
        lines.append(f'PBJ320 URL: {page_url}')
    _fop = (facility_snapshot_context or '').strip()
    if _fop:
        lines.append('')
        lines.append(
            'Facility operating context (Care Compare / provider snapshot fields echoed on this page — not from PBJ hours alone):'
        )
        for sub in _fop.splitlines():
            s = (sub or '').strip()
            if s:
                lines.append(s)
    _cms_risk = (cms_risk_screening_line or '').strip()
    if _cms_risk:
        lines.append('')
        lines.append(_cms_risk)
    _own_chow = (ownership_chow_context or '').strip()
    if _own_chow:
        lines.append('')
        lines.append('Ownership / CHOW (CMS enrollment screening — not proof of control or staffing impact):')
        lines.append(_own_chow)
    lines.append(format_source_level_block('facility', page_kind, page_url))
    lines.append(f'Date copied: {copied_date}')
    lines.append('')
    lines.append(PBJ_CSV_ATTACHMENT_NOTE)
    lines.append(PBJ_FACILITY_HANDOFF_CSV_NOTE)

    _append_metric_section(
        lines,
        'Key metrics shown on this page:',
        [
            _metric_line('RN HPRD', rn_hprd),
            _metric_line('LPN HPRD', lpn_hprd),
            _metric_line('Nurse aide HPRD', na_hprd),
            _metric_line('Total nurse HPRD', total_hprd),
            _metric_line(
                'Contract staff % (quarterly PBJ aggregate; share of contract hours in facility total hours)',
                contract_staff_pct,
            ),
            _metric_line('MACPAC / state minimum reference (chart footnote on this page)', macpac_reference_line),
            _metric_line('CMS case-mix benchmark', case_mix_hprd, suffix=' total nurse HPRD'),
            _metric_line('Case-mix index', case_mix_index),
            _metric_line('Case-mix index ratio', case_mix_index_ratio),
            _metric_line('Staffing percentile / comparison group', staffing_percentile),
            _metric_line('State comparison value shown', state_comparison if state_comparison != staffing_percentile else None),
        ],
    )
    _append_definitions(lines)

    main_summary = build_facility_summary_plain(
        facility_name=facility_name,
        total_hprd=total_hprd,
        quarter=period,
        state_comparison=state_comparison,
        above_below_casemix=above_below_casemix,
        case_mix_hprd=case_mix_hprd,
        fallback_summary=summary,
    )
    lines.append('')
    lines.append('Main PBJ320 summary:')
    lines.append(main_summary if main_summary else '[not shown on this page]')

    lines.append('')
    lines.append('Interpretation checks:')
    lines.extend(f'- {c}' for c in PBJ_FACILITY_INTERPRETATION_CHECKS)
    lines.extend([
        '',
        'Important limitations:',
        PBJ_FACILITY_LIMITATIONS,
        PBJ_FACILITY_CSV_LIMITATIONS,
        PBJ_PBJ_SUBMISSION_CONTEXT,
    ])
    def _fact_line(label: str, val: str) -> Optional[str]:
        v = (val or '').strip()
        if not v:
            return f'- {label}: [not included on this page]'
        return f'- {label}: {v}'

    lines.extend([
        '',
        'Follow-up factset hooks (only use explicitly listed lines; '
        'if a line reads [not included…], tell the reader it is missing—do not invent URLs, filings, citations, or inspection IDs):',
    ])
    for bit in (
        _fact_line('State', state_name),
        _fact_line('Quarter / reporting period anchor', period),
        _fact_line('Facility CCN', ccn),
        _fact_line('County / parish (when shown)', county_name),
        _fact_line('Ownership type (when shown)', ownership_type),
        _fact_line('MACPAC-associated state staffing minimum reference (same text as chart footnote)', macpac_reference_line),
        _fact_line('CMS Care Compare facility deep link (same URL as header line above)', care_compare_url),
        _fact_line(
            'CMS staffing Five-Star snapshot on page',
            cms_staffing_star_line,
        ),
        _fact_line(
            'CMS overall Five-Star snapshot on page',
            cms_overall_star_line,
        ),
        _fact_line(
            'PBJ320 premium / daily dashboard context',
            (premium_dashboard_note or '').strip(),
        ),
        _fact_line('Affiliated entity / chain (when shown on this page)', (entity_name or '').strip()),
        _fact_line('PBJ320 entity overview URL (when entity is linked)', (entity_page_url or '').strip()),
        _fact_line('CMS CHOW / ownership-change context (when available)', (ownership_chow_context or '').strip()),
    ):
        if bit:
            lines.append(bit)
    lines.extend([
        '',
        'County / market benchmarking: Compare against same-state peers or county strata only when comparable facility lists are explicitly attached — do not imply county-relative standing without peer tables.',
        'Multi-quarter longitudinal work: Prefer the downloadable quarterly CSVs or bundled context files when verifying trends; cite the quarter range explicitly.',
        '',
        'Review scope: Facility-level quarterly review. When an affiliated entity/chain is listed above, mention it where ownership or portfolio context matters (e.g. journalist, attorney, regulator follow-up).',
    ])
    return '\n'.join(lines)


def _build_state_page_context(
    *,
    page_url: str,
    page_kind: str,
    period: str,
    state_name: str,
    rn_hprd: Any,
    lpn_hprd: Any,
    na_hprd: Any,
    total_hprd: Any,
    state_median: Any,
    facility_count: Any,
    staffing_percentile: Any,
    top_bottom_summary: str,
    summary: str,
    copied_date: str,
    ownership_chow_context: str = '',
) -> str:
    lines: list[str] = ['PBJ320 state page context', '']
    if state_name:
        lines.append(f'State: {state_name}')
    if period:
        lines.append(f'Quarter / period: {period}')
    if page_url:
        lines.append(f'PBJ320 URL: {page_url}')
    lines.append(format_source_level_block('state', page_kind, page_url))
    lines.append(f'Date copied: {copied_date}')
    _own_chow = (ownership_chow_context or '').strip()
    if _own_chow:
        lines.append('')
        lines.append(_own_chow)

    _append_metric_section(
        lines,
        'Key state-level metrics shown on this page:',
        [
            _metric_line('Total nurse HPRD', total_hprd),
            _metric_line('RN HPRD', rn_hprd),
            _metric_line('LPN HPRD', lpn_hprd),
            _metric_line('Nurse aide HPRD', na_hprd),
            _metric_line('State median/average shown', state_median),
            _metric_line('Number of facilities shown or included', facility_count),
            _metric_line('Visible ranking / percentile context', staffing_percentile),
            _metric_line('Top/bottom facility lists or percentiles', top_bottom_summary),
        ],
    )

    lines.append('')
    lines.append('Definitions:')
    lines.append(f'- {PBJ_HPRD_DEFINITION}')
    lines.append('- State averages and medians can hide wide facility-level variation.')
    lines.append('- Facility-level conclusions require facility-level data.')
    lines.append(
        '- Daily, roster, or incident-date staffing review needs facility-level or Premium daily PBJ — not '
        'this state quarterly page alone.'
    )

    st = (state_name or 'This state').strip()
    per = (period or 'the selected period').strip()
    lines.append('')
    lines.append('Main PBJ320 summary:')
    cleaned = sanitize_context_text(summary)
    if cleaned:
        lines.append(cleaned)
    else:
        lines.append(
            f'This PBJ320 state page shows quarterly staffing context for {st} in {per}. '
            'Use it to understand broad state-level patterns and comparison context, not to infer what happened '
            'at a specific facility, shift, or resident unless facility-specific data is provided.'
        )

    lines.append('')
    lines.append('Interpretation checks:')
    lines.extend(f'- {c}' for c in PBJ_STATE_INTERPRETATION_CHECKS)
    lines.extend(['', 'Important limitations:', PBJ_STATE_LIMITATIONS, '', 'Review scope: State-level quarterly review.'])
    return '\n'.join(lines)


def _build_generic_page_context(
    *,
    page_type: str,
    page_url: str,
    page_kind: str,
    period: str,
    facility_name: str,
    ccn: str,
    state_name: str,
    entity_name: str,
    total_hprd: Any,
    rn_hprd: Any,
    summary: str,
    copied_date: str,
    cfg: ReviewConfig,
) -> str:
    title = 'PBJ320 page context' if page_type != 'entity' else 'PBJ320 entity page context'
    lines: list[str] = [title, '']
    if entity_name:
        lines.append(f'Entity / chain: {entity_name}')
    if facility_name:
        lines.append(f'Facility: {facility_name}')
    if state_name:
        lines.append(f'State: {state_name}')
    if ccn:
        lines.append(f'CCN: {ccn}')
    if period:
        lines.append(f'Quarter / period: {period}')
    if page_url:
        lines.append(f'PBJ320 URL: {page_url}')
    lines.append(format_source_level_block(page_type, page_kind, page_url))
    lines.append(f'Date copied: {copied_date}')
    _append_metric_section(
        lines,
        'Key metrics shown on this page:',
        [_metric_line('Total nurse HPRD', total_hprd), _metric_line('RN HPRD', rn_hprd)],
    )
    cleaned = sanitize_context_text(summary)
    if cleaned:
        lines.extend(['', 'Main PBJ320 summary:', cleaned])
    lines.append('')
    lines.append('Interpretation checks:')
    lines.extend(f'- {c}' for c in PBJ_INTERPRETATION_RULES)
    lines.extend(['', 'Important limitations:', PBJ_AI_LIMITATIONS])
    if cfg.geography_level:
        lines.append(f'Review scope: {PBJ_REVIEW_CONTEXT_LEVELS[cfg.geography_level]} ({cfg.audience} mode).')
    return '\n'.join(lines)


build_dashboard_context = build_page_context


def _compact_facility_material(
    ctx: str,
    *,
    page_url: str = '',
    facility_name: str = '',
    max_summary: int = 900,
) -> str:
    """Facility-specific facts for one-shot AI prefill (URL, metrics, summary — no boilerplate)."""
    lines: list[str] = ['--- This facility (PBJ320 quarterly page) ---']
    seen: set[str] = set()
    for raw in (ctx or '').splitlines():
        line = raw.strip()
        if line.startswith(
            (
                'Facility:',
                'CCN:',
                'State:',
                'Quarter / period:',
                'PBJ320 URL:',
                'CMS Care Compare',
                'Affiliated entity — portfolio snapshot',
                'Facility operating context',
                'Reported average daily census',
                'Ownership type (Care Compare',
                'CMS Special Focus',
                'CMS abuse icon',
                'PBJ320 screening flags',
                'PBJ320 high-risk',
            )
        ):
            if line not in seen:
                lines.append(line)
                seen.add(line)
    if facility_name and not any(l.startswith('Facility:') for l in lines):
        lines.append(f'Facility: {facility_name}')
    if page_url and not any('PBJ320 URL:' in l for l in lines):
        lines.append(f'PBJ320 URL: {page_url}')

    metrics: list[str] = []
    in_metrics = False
    for raw in (ctx or '').splitlines():
        if raw.startswith('Key metrics shown on this page:'):
            in_metrics = True
            continue
        if in_metrics:
            if raw.startswith(('Definitions', 'Main PBJ320 summary:', 'Interpretation checks:')):
                break
            if raw.strip().startswith('- '):
                metrics.append(raw.strip())
                if len(metrics) >= 8:
                    break
    if metrics:
        lines.append('')
        lines.append('Key metrics on page:')
        lines.extend(metrics)

    summary_parts: list[str] = []
    in_summary = False
    for raw in (ctx or '').splitlines():
        if raw.strip() == 'Main PBJ320 summary:':
            in_summary = True
            continue
        if in_summary:
            if raw.startswith(('Interpretation checks:', 'Important limitations:')):
                break
            if raw.strip():
                summary_parts.append(raw.strip())
    if summary_parts:
        summary = ' '.join(summary_parts)
        if len(summary) > max_summary:
            summary = summary[: max(0, max_summary - 3)].rstrip() + '...'
        lines.append('')
        lines.append('Summary on page:')
        lines.append(summary)

    return '\n'.join(lines)


def _facility_anchor_one_line(
    *,
    facility_name: str = '',
    ccn: str = '',
    page_url: str = '',
) -> str:
    """Single line before long review prompts so Claude/?q= truncation still names the facility."""
    bits: list[str] = []
    fn = (facility_name or '').strip()
    if fn:
        bits.append(f'Facility: {fn}')
    c = (ccn or '').strip()
    if c:
        bits.append(f'CCN: {c}')
    u = (page_url or '').strip()
    if u:
        bits.append(f'PBJ320 URL: {u}')
    if not bits:
        return ''
    return ' | '.join(bits)


def build_facility_oneshot_prefill(
    page_context: str,
    *,
    lens: Optional[str] = None,
    page_type: str = 'facility',
    page_url: str = '',
    facility_name: str = '',
    ccn: str = '',
    facility_state: str = '',
    facility_state_code: str = '',
    max_chars: int = 11500,
) -> str:
    """Self-contained chat prefill: persona prompt + compact facility facts (good without file upload)."""
    ctx = (page_context or '').strip()
    if not ctx:
        return ''
    lens_key = normalize_public_review_lens(lens)
    sd, sc = (facility_state or '').strip(), (facility_state_code or '').strip()
    if not sd:
        sd, sc_g = _facility_state_from_page_context(ctx)
        if not sc:
            sc = sc_g
    prompt = compose_dashboard_prompt(
        lens_key, 'quick', page_type=page_type, material_placeholder=''
    )
    prompt += compose_provider_dashboard_supplement_block(
        lens_key,
        sd,
        facility_state_code=sc,
        page_type=page_type,
    )
    head = _facility_anchor_one_line(facility_name=facility_name, ccn=ccn, page_url=page_url)
    prefix = f'{head}\n\n' if head else ''
    optional = (
        '\n\n(Optional: an extended context file may download with quarterly history and '
        'annual summaries for longitudinal work; CSVs also available. Not required for this review.)'
    )
    for summary_cap in (900, 650, 450, 280, 160):
        compact = _compact_facility_material(
            ctx, page_url=page_url, facility_name=facility_name, max_summary=summary_cap
        )
        packet = f'{prefix}{prompt}\n\n{compact}{optional}'
        if len(packet) <= max_chars:
            return packet
    anchor = _facility_packet_anchor(ctx)
    if not anchor and (page_url or facility_name):
        bits = ['--- This facility (PBJ320 quarterly page) ---']
        if facility_name:
            bits.append(f'Facility: {facility_name}')
        if page_url:
            bits.append(f'PBJ320 URL: {page_url}')
        anchor = '\n'.join(bits)
    fallback = f'{prefix}{prompt}\n\n{anchor or ctx[:1200]}{optional}'
    return fallback[:max_chars] if len(fallback) > max_chars else fallback


def _facility_packet_anchor(ctx: str) -> str:
    """Short facility + URL block at top of material (duplicates lines already in full context)."""
    pick: list[str] = []
    for line in (ctx or '').splitlines():
        if line.startswith(
            (
                'Facility:',
                'CCN:',
                'PBJ320 URL:',
                'Quarter / period:',
                'State:',
                'CMS Care Compare',
                'Reported average daily census',
            )
        ):
            pick.append(line)
        if len(pick) >= 8:
            break
    if not pick:
        return ''
    return '--- Facility under review ---\n' + '\n'.join(pick)


def build_facility_dashboard_packet(
    page_context: str,
    *,
    page_type: str = 'facility',
    lens: Optional[str] = None,
    page_url: str = '',
    facility_name: str = '',
    facility_state: str = '',
    facility_state_code: str = '',
    include_csv_notes: bool = False,
) -> str:
    """Server-built copy packet for provider dashboard (lens quick prompt + page context)."""
    ctx = (page_context or '').strip()
    if not ctx:
        return ''
    lens_key = normalize_public_review_lens(lens)
    sd, sc = (facility_state or '').strip(), (facility_state_code or '').strip()
    if not sd:
        sd, sc_g = _facility_state_from_page_context(ctx)
        if not sc:
            sc = sc_g
    prompt = compose_dashboard_prompt(
        lens_key, 'quick', page_type=page_type, material_placeholder=''
    )
    prompt += compose_provider_dashboard_supplement_block(
        lens_key,
        sd,
        facility_state_code=sc,
        page_type=page_type,
    )
    anchor = _facility_packet_anchor(ctx)
    if not anchor and (page_url or facility_name):
        anchor_lines = ['--- Facility under review ---']
        if facility_name:
            anchor_lines.append(f'Facility: {facility_name}')
        if page_url:
            anchor_lines.append(f'PBJ320 URL: {page_url}')
        anchor = '\n'.join(anchor_lines)
    material = ctx
    if anchor and anchor not in ctx[: min(len(ctx), 400)]:
        material = f'{anchor}\n\n{ctx}'
    packet = f'{prompt}\n\n--- PBJ320 page context ---\n\n{material}\n\n{PBJ_AI_BRAND_FOOTER}'
    if include_csv_notes and PBJ_CSV_ATTACHMENT_NOTE not in ctx:
        packet = (
            f'{packet}\n\n---\n'
            f'{PBJ_CSV_ATTACHMENT_NOTE}\n'
            f'{PBJ_FACILITY_HANDOFF_CSV_NOTE}'
        )
    return packet


def build_ai_handoff(
    page_context: str,
    use_advanced: bool = True,
    review_config: Optional[ReviewConfig] = None,
    *,
    include_csv_guidance: bool = False,
) -> str:
    ctx = (page_context or '').strip()
    if not ctx:
        return ''
    cfg = (review_config or ReviewConfig()).normalized()
    template = compose_review_prompt(cfg, use_advanced=use_advanced)
    if use_advanced:
        body = template.replace(PBJ_AI_HANDOFF_PLACEHOLDER, ctx)
        packet = f'{body}\n\n{PBJ_AI_BRAND_FOOTER}'
    else:
        packet = f'{template}\n\n{ctx}\n\n{PBJ_AI_BRAND_FOOTER}'
    if include_csv_guidance:
        packet = (
            f'{packet}\n\n---\n'
            f'{PBJ_CSV_ATTACHMENT_NOTE}\n'
            f'{PBJ_FACILITY_HANDOFF_CSV_NOTE}'
        )
    return packet


def slugify_facility_name(name: str, *, max_len: int = 48) -> str:
    """URL/filename-safe slug from facility name."""
    raw = (name or '').strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '-', raw)
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    if not slug:
        slug = 'facility'
    return slug[:max_len].rstrip('-') or 'facility'


def quarter_slug_for_filename(raw_quarter: str) -> str:
    """2025Q4 -> q4_2025 for CSV filenames."""
    s = (raw_quarter or '').strip()
    m = re.match(r'^(\d{4})Q([1-4])$', s, re.I)
    if m:
        return f'q{m.group(2).lower()}_{m.group(1)}'
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_') or 'quarter'


def _csv_cell(value: Any) -> str:
    if value is None:
        return ''
    s = str(value).strip()
    if s in ('—', 'N/A', 'n/a', '-', 'None'):
        return ''
    return s


def _rows_to_csv(columns: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(columns), extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({col: _csv_cell(row.get(col)) for col in columns})
    return buf.getvalue()


def _hprd_vs_case_mix(reported: Any, case_mix: Any) -> str:
    try:
        r, c = float(reported), float(case_mix)
    except (TypeError, ValueError):
        return ''
    if c <= 0:
        return ''
    diff = round(r - c, 2)
    sign = '+' if diff > 0 else ''
    return f'{sign}{diff:.2f}'


def _hprd_pct_of_case_mix(reported: Any, case_mix: Any) -> str:
    try:
        r, c = float(reported), float(case_mix)
    except (TypeError, ValueError):
        return ''
    if c <= 0:
        return ''
    return f'{round(100 * r / c, 1):.1f}%'


SNAPSHOT_CSV_COLUMNS: tuple[str, ...] = (
    'ccn',
    'facility_name',
    'state',
    'city',
    'quarter',
    'pbj320_url',
    'source_level',
    'avg_daily_census',
    'rn_hprd',
    'lpn_hprd',
    'nurse_aide_hprd',
    'total_nurse_hprd',
    'state_total_nurse_hprd_comparison',
    'state_percentile_total_nurse_hprd',
    'case_mix_index',
    'case_mix_index_ratio',
    'cms_case_mix_total_nurse_hprd',
    'total_nurse_hprd_vs_case_mix_hprd',
    'total_nurse_hprd_pct_of_case_mix',
    'ownership_type',
    'certified_beds',
    'hprd_definition',
    'case_mix_index_definition',
    'case_mix_index_ratio_definition',
    'cms_case_mix_hprd_definition',
    'limitations',
)

# Same rows as snapshot-detail download, but omit repeated definition/limitation columns per row (token-heavy for LLMs).
SNAPSHOT_EMBED_DETAIL_CSV_COLUMNS: tuple[str, ...] = tuple(
    c
    for c in SNAPSHOT_CSV_COLUMNS
    if c
    not in (
        'hprd_definition',
        'case_mix_index_definition',
        'case_mix_index_ratio_definition',
        'cms_case_mix_hprd_definition',
        'limitations',
    )
)

TREND_CSV_COLUMNS: tuple[str, ...] = (
    'ccn',
    'facility_name',
    'state',
    'quarter',
    'pbj320_url',
    'source_level',
    'avg_daily_census',
    'rn_hprd',
    'lpn_hprd',
    'nurse_aide_hprd',
    'total_nurse_hprd',
    'case_mix_index',
    'case_mix_index_ratio',
    'cms_case_mix_total_nurse_hprd',
    'state_percentile_total_nurse_hprd',
    'notes_or_limitations',
)

TREND_EMBED_CSV_COLUMNS: tuple[str, ...] = tuple(
    c for c in TREND_CSV_COLUMNS if c != 'notes_or_limitations'
)

PBJ_FACILITY_SOURCE_LEVEL = (
    'PBJ320 free provider page / quarterly CSV — quarterly facility-level summary from CMS PBJ (daily PBJ exists in '
    'CMS and in Premium; not in this packet unless attached).'
)


def build_facility_snapshot_csv_row(
    *,
    ccn: str,
    facility_name: str,
    state: str,
    city: str,
    quarter_display: str,
    pbj320_url: str,
    rn_hprd: Any = None,
    lpn_hprd: Any = None,
    nurse_aide_hprd: Any = None,
    total_nurse_hprd: Any = None,
    state_total_nurse_hprd: Any = None,
    state_percentile: Any = None,
    case_mix_index: Any = None,
    case_mix_index_ratio: Any = None,
    cms_case_mix_total_nurse_hprd: Any = None,
    ownership_type: str = '',
    certified_beds: Any = None,
    avg_daily_census: Any = None,
) -> dict[str, Any]:
    reported_num = total_nurse_hprd
    case_mix_num = cms_case_mix_total_nurse_hprd
    return {
        'ccn': ccn,
        'facility_name': facility_name,
        'state': state,
        'city': city,
        'quarter': quarter_display,
        'pbj320_url': pbj320_url,
        'source_level': PBJ_FACILITY_SOURCE_LEVEL,
        'avg_daily_census': avg_daily_census,
        'rn_hprd': rn_hprd,
        'lpn_hprd': lpn_hprd,
        'nurse_aide_hprd': nurse_aide_hprd,
        'total_nurse_hprd': total_nurse_hprd,
        'state_total_nurse_hprd_comparison': state_total_nurse_hprd,
        'state_percentile_total_nurse_hprd': state_percentile,
        'case_mix_index': case_mix_index,
        'case_mix_index_ratio': case_mix_index_ratio,
        'cms_case_mix_total_nurse_hprd': cms_case_mix_total_nurse_hprd,
        'total_nurse_hprd_vs_case_mix_hprd': _hprd_vs_case_mix(reported_num, case_mix_num),
        'total_nurse_hprd_pct_of_case_mix': _hprd_pct_of_case_mix(reported_num, case_mix_num),
        'ownership_type': ownership_type,
        'certified_beds': certified_beds,
        'hprd_definition': PBJ_HPRD_DEFINITION,
        'case_mix_index_definition': PBJ_CASE_MIX_INDEX_DEF,
        'case_mix_index_ratio_definition': PBJ_CASE_MIX_RATIO_DEF,
        'cms_case_mix_hprd_definition': PBJ_CMS_CASE_MIX_HPRD_DEF,
        'limitations': PBJ_FACILITY_CSV_LIMITATIONS,
    }


def build_facility_trend_csv_row(
    *,
    ccn: str,
    facility_name: str,
    state: str,
    quarter_display: str,
    pbj320_url: str,
    rn_hprd: Any = None,
    lpn_hprd: Any = None,
    nurse_aide_hprd: Any = None,
    total_nurse_hprd: Any = None,
    case_mix_index: Any = None,
    case_mix_index_ratio: Any = None,
    cms_case_mix_total_nurse_hprd: Any = None,
    state_percentile: Any = None,
    avg_daily_census: Any = None,
) -> dict[str, Any]:
    return {
        'ccn': ccn,
        'facility_name': facility_name,
        'state': state,
        'quarter': quarter_display,
        'pbj320_url': pbj320_url,
        'source_level': PBJ_FACILITY_SOURCE_LEVEL,
        'avg_daily_census': avg_daily_census,
        'rn_hprd': rn_hprd,
        'lpn_hprd': lpn_hprd,
        'nurse_aide_hprd': nurse_aide_hprd,
        'total_nurse_hprd': total_nurse_hprd,
        'case_mix_index': case_mix_index,
        'case_mix_index_ratio': case_mix_index_ratio,
        'cms_case_mix_total_nurse_hprd': cms_case_mix_total_nurse_hprd,
        'state_percentile_total_nurse_hprd': state_percentile,
        'notes_or_limitations': PBJ_FACILITY_CSV_LIMITATIONS,
    }


def facility_snapshot_csv_filename(ccn: str, facility_name: str, raw_quarter: str) -> str:
    slug = slugify_facility_name(facility_name)
    qslug = quarter_slug_for_filename(raw_quarter)
    return f'pbj320_{ccn}_{slug}_snapshot_detail_asof_{qslug}.csv'


def _facility_state_from_page_context(ctx: str) -> tuple[str, str]:
    """Extract (state_display, state_code_guess) from copy-paste facility context lines."""
    txt = ctx or ''
    state_line = ''
    for line in txt.splitlines():
        if line.strip().lower().startswith('state:'):
            state_line = line.split(':', 1)[-1].strip()
            break
    if not state_line:
        return '', ''
    parts = [p.strip() for p in state_line.split(',')]
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return state_line, parts[-1].upper()
    if len(state_line) == 2 and state_line.isalpha():
        return state_line, state_line.upper()
    return state_line, ''
def facility_trends_csv_filename(ccn: str, facility_name: str) -> str:
    slug = slugify_facility_name(facility_name)
    return f'pbj320_{ccn}_{slug}_quarterly_trends.csv'


def build_facility_snapshot_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    return _rows_to_csv(SNAPSHOT_CSV_COLUMNS, rows)


def build_facility_trends_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    return _rows_to_csv(TREND_CSV_COLUMNS, rows)


def _slim_embed_snapshot_csv_text(full_csv: str) -> str:
    raw = (full_csv or '').strip()
    if not raw:
        return ''
    reader = csv.DictReader(io.StringIO(raw))
    rows = [dict(r) for r in reader]
    if not rows:
        return raw
    return _rows_to_csv(SNAPSHOT_EMBED_DETAIL_CSV_COLUMNS, rows)


def _slim_embed_trends_csv_text(full_csv: str) -> str:
    raw = (full_csv or '').strip()
    if not raw:
        return ''
    reader = csv.DictReader(io.StringIO(raw))
    rows = [dict(r) for r in reader]
    if not rows:
        return raw
    return _rows_to_csv(TREND_EMBED_CSV_COLUMNS, rows)


def _extract_context_field(ctx: str, label: str) -> str:
    """First 'Label: value' line where label matches (case-insensitive, no colon in label)."""
    want = (label or '').strip().lower().rstrip(':')
    if not want:
        return ''
    for line in (ctx or '').splitlines():
        s = (line or '').strip()
        if ':' not in s:
            continue
        head, rest = s.split(':', 1)
        if head.strip().lower() == want:
            return rest.strip()
    return ''


def _build_facility_snapshot_meta_block(
    *,
    ccn: str = '',
    facility_name: str = '',
    page_url: str = '',
    page_quarter: str = '',
    embed_snapshot_detail: bool = False,
    embed_trends: bool = False,
    quarters_in_history: int = 0,
    quarters_span: str = '',
) -> str:
    lines = [
        '--- PBJ320 snapshot meta (machine-readable) ---',
        'format=PBJ320_facility_snapshot_v1',
        f'ccn={_csv_cell(ccn) or "[unknown]"}',
        f'facility_name={_csv_cell(facility_name) or "[unknown]"}',
        f'pbj320_page_url={_csv_cell(page_url) or "[unknown]"}',
        f'display_quarter={_csv_cell(page_quarter) or "[see page context]"}',
        f'embedded_csv_snapshot_detail={"1" if embed_snapshot_detail else "0"}',
        f'embedded_csv_trends={"1" if embed_trends else "0"}',
        f'quarters_in_longitudinal_tsv={int(quarters_in_history)}',
    ]
    if (quarters_span or '').strip():
        lines.append(f'quarters_span_in_file={quarters_span.strip()}')
    lines.extend(['source_level=free_quarterly_facility', '--- end meta ---'])
    return '\n'.join(lines)


def _parse_metric_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace(',', '')
    if not s or s in ('—', 'N/A', 'n/a', '-', 'None'):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _quarter_sort_key(quarter_label: str) -> tuple[int, int]:
    s = str(quarter_label or '').strip()
    m = re.match(r'Q([1-4])\s+(\d{4})', s, re.I)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.match(r'(\d{4})Q([1-4])', s, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (0, 0)


def _year_from_quarter(quarter_label: str) -> Optional[int]:
    year, _ = _quarter_sort_key(quarter_label)
    return year if year > 0 else None


def _format_hprd_cell(val: Any) -> str:
    n = _parse_metric_float(val)
    if n is None:
        return '—'
    return f'{n:.2f}'


def _trend_rows_from_csv(csv_text: str) -> list[dict[str, Any]]:
    if not (csv_text or '').strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    return [dict(row) for row in reader]


def build_facility_longitudinal_context(
    trend_rows: Sequence[Mapping[str, Any]],
    *,
    max_quarters_in_table: int = 36,
    include_csv_attachment_note: bool = True,
) -> str:
    """Quarterly table + calendar-year rollups for AI context file uploads."""
    if not trend_rows:
        return ''
    rows = sorted(trend_rows, key=lambda r: _quarter_sort_key(str(r.get('quarter', ''))))
    quarters = [
        str(r.get('quarter', '')).strip() for r in rows if str(r.get('quarter', '')).strip()
    ]
    if not quarters:
        return ''

    lines: list[str] = []
    lines.append('--- Quarterly staffing history (CMS PBJ) ---')
    lines.append(f'Quarters in file: {len(rows)} ({quarters[0]} through {quarters[-1]})')
    lines.append(
        'Tab-separated: quarter, avg daily census, total nurse HPRD, RN, LPN, nurse aide, '
        'CMS case-mix total HPRD, state percentile (total nurse).'
    )
    lines.append(PBJ_ROLE_HPRD_SEMANTICS)

    table_rows = rows[-max_quarters_in_table:] if len(rows) > max_quarters_in_table else rows
    omitted = len(rows) - len(table_rows)
    if omitted > 0:
        lines.append(
            f'(Most recent {len(table_rows)} quarters shown in this table; {omitted} earlier omitted — '
            'full quarter rows are embedded in the CSV sections of this same snapshot file.)'
        )
    lines.append('')
    lines.append('quarter\tcensus\ttotal\trn\tlpn\tna\tcase_mix\tstate_pctile')
    for row in table_rows:
        q = str(row.get('quarter', '')).strip()
        census_cell = _csv_cell(row.get('avg_daily_census')) or '—'
        lines.append(
            '\t'.join(
                [
                    q,
                    census_cell,
                    _format_hprd_cell(row.get('total_nurse_hprd')),
                    _format_hprd_cell(row.get('rn_hprd')),
                    _format_hprd_cell(row.get('lpn_hprd')),
                    _format_hprd_cell(row.get('nurse_aide_hprd')),
                    _format_hprd_cell(row.get('cms_case_mix_total_nurse_hprd')),
                    _csv_cell(row.get('state_percentile_total_nurse_hprd')) or '—',
                ]
            )
        )

    by_year: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        year = _year_from_quarter(str(row.get('quarter', '')))
        if not year:
            continue
        for field, slot in (
            ('total_nurse_hprd', 'total'),
            ('cms_case_mix_total_nurse_hprd', 'case_mix'),
        ):
            n = _parse_metric_float(row.get(field))
            if n is not None:
                by_year[year][slot].append(n)

    if by_year:
        lines.append('')
        lines.append('--- Annual summary (calendar year; mean of available quarters) ---')
        prev_avg: Optional[float] = None
        for year in sorted(by_year.keys()):
            slots = by_year[year]
            totals = slots.get('total') or []
            case_mix = slots.get('case_mix') or []
            if not totals:
                lines.append(f'{year}: no total HPRD values in file')
                continue
            avg = sum(totals) / len(totals)
            lo, hi = min(totals), max(totals)
            n_q = len(totals)
            parts = [
                f'{year} ({n_q} quarter{"s" if n_q != 1 else ""}): '
                f'avg total nurse HPRD {avg:.2f} (range {lo:.2f}–{hi:.2f})'
            ]
            if case_mix:
                cm_avg = sum(case_mix) / len(case_mix)
                parts.append(f'avg CMS case-mix HPRD {cm_avg:.2f}')
            if prev_avg is not None and prev_avg > 0:
                delta = avg - prev_avg
                pct = 100 * delta / prev_avg
                sign = '+' if delta >= 0 else ''
                parts.append(f'YoY vs prior year {sign}{delta:.2f} HPRD ({sign}{pct:.1f}%)')
            lines.append('; '.join(parts))
            prev_avg = avg

    first_total = _parse_metric_float(rows[0].get('total_nurse_hprd'))
    last_total = _parse_metric_float(rows[-1].get('total_nurse_hprd'))
    lines.append('')
    lines.append('--- Longitudinal highlights ---')
    if first_total is not None:
        lines.append(f'Earliest quarter ({quarters[0]}): total nurse HPRD {first_total:.2f}')
    if last_total is not None:
        lines.append(f'Latest quarter ({quarters[-1]}): total nurse HPRD {last_total:.2f}')
    if first_total is not None and last_total is not None and first_total > 0:
        delta = last_total - first_total
        pct = 100 * delta / first_total
        sign = '+' if delta >= 0 else ''
        lines.append(f'Span earliest → latest: {sign}{delta:.2f} HPRD ({sign}{pct:.1f}%)')
    if include_csv_attachment_note:
        lines.append(PBJ_CSV_ATTACHMENT_NOTE)
    return '\n'.join(lines)


def build_facility_context_data_file(
    page_context: str,
    *,
    trend_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    trends_csv: str = '',
    snapshot_detail_csv: str = '',
    meta_ccn: str = '',
    meta_facility_name: str = '',
    meta_page_url: str = '',
) -> str:
    """Single upload-friendly snapshot: page context, longitudinal summaries, embedded CSV exports."""
    ctx = (page_context or '').strip()
    rows: list[dict[str, Any]] = list(trend_rows) if trend_rows else []
    if not rows and (trends_csv or '').strip():
        rows = _trend_rows_from_csv(trends_csv)
    sorted_rows = (
        sorted(rows, key=lambda r: _quarter_sort_key(str(r.get('quarter', '')))) if rows else []
    )
    qs = [str(r.get('quarter', '')).strip() for r in sorted_rows if str(r.get('quarter', '')).strip()]
    quarters_span = ''
    if len(qs) >= 2:
        quarters_span = f'{qs[0]} through {qs[-1]}'
    elif len(qs) == 1:
        quarters_span = qs[0]

    ccn_m = (meta_ccn or _extract_context_field(ctx, 'CCN')).strip()
    fac_m = (meta_facility_name or _extract_context_field(ctx, 'Facility')).strip()
    url_m = (meta_page_url or _extract_context_field(ctx, 'PBJ320 URL')).strip()
    quarter_m = _extract_context_field(ctx, 'Quarter / period')

    snap_raw = (snapshot_detail_csv or '').strip()
    tr_raw = (trends_csv or '').strip()
    slim_snap = _slim_embed_snapshot_csv_text(snap_raw) if snap_raw else ''
    slim_tr = _slim_embed_trends_csv_text(tr_raw) if tr_raw else ''

    meta = _build_facility_snapshot_meta_block(
        ccn=ccn_m,
        facility_name=fac_m,
        page_url=url_m,
        page_quarter=quarter_m,
        embed_snapshot_detail=bool(slim_snap),
        embed_trends=bool(slim_tr),
        quarters_in_history=len(qs),
        quarters_span=quarters_span,
    )
    intro = (
        'PBJ320 facility snapshot (one file)\n'
        'Attach alongside the prefilled Claude/ChatGPT message. Includes this page\'s staffing context, '
        'longitudinal summaries, and quarterly staffing data embedded as CSV text below '
        '(no need to attach separate spreadsheet downloads unless you want them).\n'
        'Quarterly facility aggregates only — not daily or employee-level data.\n'
    )
    guide = (
        'For quarter-by-quarter numeric staffing (average daily census, HPRD, CMS case-mix reference value, '
        'state percentile), prefer the tab-separated block under \'Quarterly staffing history\' and/or the '
        '<<<BEGIN_EMBEDDED_CSV>>>…<<<END_EMBEDDED_CSV>>> sections below (embedded CSV wins over narrative if they disagree).'
    )
    parts = [
        intro.rstrip(),
        '',
        meta,
        '',
        guide,
        '',
        '--- Current page context ---',
        '',
        ctx,
    ]
    longitudinal = (
        build_facility_longitudinal_context(sorted_rows, include_csv_attachment_note=False)
        if sorted_rows
        else ''
    )
    if longitudinal:
        parts.extend(['', longitudinal.rstrip()])
    if slim_snap:
        parts.extend(
            [
                '',
                '--- Embedded CSV: quarterly snapshot-detail (token-slim copy for AI) ---',
                'Spreadsheet download uses full columns including repeated definitions per row; this embed omits those columns.',
                '',
                '<<<BEGIN_EMBEDDED_CSV:snapshot_detail>>>',
                slim_snap.rstrip(),
                '<<<END_EMBEDDED_CSV:snapshot_detail>>>',
            ]
        )
    if slim_tr:
        parts.extend(
            [
                '',
                '--- Embedded CSV: quarterly trends (token-slim copy for AI) ---',
                'Omits per-row notes column; see page context for interpretation limits.',
                '',
                '<<<BEGIN_EMBEDDED_CSV:trends>>>',
                slim_tr.rstrip(),
                '<<<END_EMBEDDED_CSV:trends>>>',
            ]
        )
    parts.extend(['', PBJ_AI_BRAND_FOOTER])
    return '\n'.join(parts)


def _render_lens_select(active_lens: str) -> str:
    opts = []
    active = normalize_public_review_lens(active_lens)
    for lid, lbl in allowed_public_review_lenses():
        sel = ' selected' if lid == active else ''
        opts.append(f'<option value="{html.escape(lid)}"{sel}>{html.escape(lbl)}</option>')
    return (
        '<label class="pbj-ai-lens-wrap">'
        '<span class="pbj-ai-lens-label">Review as</span>'
        '<select class="pbj-ai-lens-select" data-pbj-lens-select aria-label="Review as, audience">'
        f'{"".join(opts)}</select></label>'
    )


def _render_pbjai_info_btn() -> str:
    return (
        '<button type="button" class="pbj-ai-pbjai-info" data-pbj-ai-beta-open '
        'title="How PBJAI works (beta)" aria-label="About PBJAI beta">'
        '<span class="pbj-ai-pbjai-mark">'
        '<span class="pbj-ai-pbjai-pbj">PBJ</span><span class="pbj-ai-pbjai-ai">AI</span>'
        '</span>'
        '<span class="pbj-ai-beta-tag">beta</span>'
        '</button>'
    )


def _render_ai_brief_toggle(*, active_brief: bool = False) -> str:
    full_on = not active_brief
    full_cls = ' is-active' if full_on else ''
    brief_cls = ' is-active' if active_brief else ''
    return (
        '<div class="pbj-ai-length-mode" role="group" aria-label="AI response length">'
        f'<button type="button" class="pbj-ai-length-mode__btn{full_cls}" data-pbj-brief-toggle '
        f'data-brief-value="0" aria-pressed="{"true" if full_on else "false"}">Full</button>'
        f'<button type="button" class="pbj-ai-length-mode__btn{brief_cls}" data-pbj-brief-toggle '
        f'data-brief-value="1" aria-pressed="{"true" if active_brief else "false"}">Brief</button>'
        '</div>'
    )


def render_pbj_ai_beta_modal(helper_uid: str = 'default') -> str:
    """Explainer modal for PBJAI (beta) on facility pages."""
    uid = re.sub(r'[^a-zA-Z0-9_-]', '', str(helper_uid or 'default'))[:48] or 'default'
    mid = f'pbj-ai-beta-modal-{uid}'
    cid = f'{mid}-close'
    return (
        f'<div class="pbj-ai-beta-modal-host">'
        f'<div class="pbj-casemix-modal pbj-ai-beta-modal" id="{html.escape(mid)}" aria-hidden="true">'
        f'<div class="pbj-casemix-modal-card" role="dialog" aria-modal="true" aria-labelledby="{mid}-title">'
        f'<button type="button" class="pbj-casemix-modal-close" id="{cid}" aria-label="Close">&times;</button>'
        f'<h3 id="{mid}-title">'
        f'<span class="pbj-ai-pbjai-mark">'
        f'<span class="pbj-ai-pbjai-pbj">PBJ</span><span class="pbj-ai-pbjai-ai">AI</span>'
        f'</span><span class="pbj-ai-beta-tag">beta</span></h3>'
        '<p class="pbj-ai-beta-lead">Opens a structured staffing review in Claude or ChatGPT using '
        'this facility&apos;s PBJ320 data.</p>'
        '<p class="pbj-ai-beta-verify"><strong>Verify with CMS.</strong> Check HPRD, census, ratings, and '
        'ownership against '
        '<a href="https://www.medicare.gov/care-compare/" target="_blank" rel="noopener">Care Compare</a> '
        'and '
        '<a href="https://data.cms.gov/provider-data/dataset/4pq5-n9py" target="_blank" rel="noopener">official PBJ files</a> '
        'before treating any AI summary as fact.</p>'
        '<h4>What this does</h4>'
        '<ul class="pbj-ai-beta-list">'
        '<li>Builds a PBJ data-driven AI review for ombudsmen, families, and journalists.</li>'
        '<li>Uses this facility&apos;s PBJ320 staffing metrics.</li>'
        '<li>Copies a full review packet to your clipboard; a facility snapshot <code>.txt</code> may download for upload.</li>'
        '<li>Asks the model to cite real HPRD numbers and include one small chart when it helps.</li>'
        '</ul>'
        '<h4>PBJ/AI limitations</h4>'
        '<ul class="pbj-ai-beta-list">'
        '<li>Quarterly PBJ is a <strong>screening layer</strong> — not neglect, causation, noncompliance, or care quality.</li>'
        '<li>CMS <strong>case-mix</strong> and state policy references are benchmarks — not legal minimums.</li>'
        '<li class="pbj-ai-beta-list-item--desktop-only">No shift-level, resident-level, or incident-window proof unless you supply other records.</li>'
        '<li>AI can misread or overstate patterns — treat outputs as drafts, not findings.</li>'
        '</ul>'
        '<p class="pbj-ai-beta-foot"><button type="button" class="pbj-ai-beta-got-it" data-pbj-ai-beta-close>'
        'Got it</button></p>'
        '</div></div></div>'
    )


def _render_length_select(active_length: str) -> str:
    opts = []
    for lid, lbl in PBJ_LENGTH_UI:
        sel = ' selected' if lid == active_length else ''
        opts.append(f'<option value="{html.escape(lid)}"{sel}>{html.escape(lbl)}</option>')
    return (
        f'<label class="pbj-ai-length-wrap"><span class="pbj-ai-length-label">Length</span>'
        f'<select class="pbj-ai-length-select" data-pbj-length-select aria-label="Review length">'
        f'{"".join(opts)}</select></label>'
    )


def render_ai_page_helper(
    page_context_text: str,
    *,
    helper_uid: str = 'default',
    page_type: str = 'facility',
    snapshot_csv: str = '',
    snapshot_csv_filename: str = '',
    trends_csv: str = '',
    trends_csv_filename: str = '',
) -> str:
    """Lens + length AI helper for free pages; packet composed client-side."""
    if not pbj_ai_dashboards_enabled():
        return ''
    ctx = (page_context_text or '').strip()
    if not ctx:
        return ''
    uid = re.sub(r'[^a-zA-Z0-9_-]', '', str(helper_uid or 'default'))[:48] or 'default'
    ctx_id = f'pbj-ai-context-{uid}'
    snap_id = f'pbj-ai-csv-snapshot-{uid}'
    trend_id = f'pbj-ai-csv-trends-{uid}'
    ptype = (page_type or 'facility').strip().lower()
    default_lens = normalize_public_review_lens(None)
    default_length = 'quick'
    snap_fn = html.escape(snapshot_csv_filename or 'pbj320_snapshot.csv', quote=True)
    trend_fn = html.escape(trends_csv_filename or 'pbj320_quarterly_trends.csv', quote=True)
    csv_flag = '1' if ptype in ('facility', 'provider') and (snapshot_csv or trends_csv) else '0'
    lens_sel = _render_lens_select(default_lens)
    length_sel = _render_length_select(default_length)
    snap_attr = html.escape(snap_id, quote=True) if snapshot_csv else ''
    trend_attr = html.escape(trend_id, quote=True) if trends_csv else ''
    footer_csv: list[str] = []
    if snapshot_csv:
        footer_csv.append(
            f'<button type="button" class="pbj-ai-page-helper__footer-link pbj-ai-download-csv" '
            f'data-csv-id="{snap_id}" data-csv-filename="{snap_fn}" data-pbj-track="download_snapshot_csv">'
            f'Snapshot CSV</button>'
        )
    if trends_csv:
        footer_csv.append(
            f'<button type="button" class="pbj-ai-page-helper__footer-link pbj-ai-download-csv" '
            f'data-csv-id="{trend_id}" data-csv-filename="{trend_fn}" data-pbj-track="download_trends_csv">'
            f'Quarterly trends CSV</button>'
        )
    more_items = [
        f'<button type="button" class="pbj-ai-popover__item pbj-ai-copy-prompt-only" '
        f'data-context-id="{ctx_id}" data-pbj-track="copy_ai_prompt_only">Copy prompt only</button>',
        f'<button type="button" class="pbj-ai-popover__item pbj-ai-copy-context" '
        f'data-context-id="{ctx_id}" data-pbj-track="copy_dashboard_context">Copy page context</button>',
    ]
    if pbj_ai_page_enabled():
        more_items.append(
            '<a href="/pbj-ai-support" class="pbj-ai-popover__item pbj-ai-popover__link" '
            'data-pbj-track="open_ai_support_guide">Learn more</a>'
        )
    footer_csv_html = ''
    if footer_csv:
        footer_csv_html = (
            '<span class="pbj-ai-page-helper__footer-csv">'
            + '<span class="pbj-ai-page-helper__footer-sep" aria-hidden="true">·</span>'.join(footer_csv)
            + '</span>'
        )
    more_html = ''
    if more_items:
        more_html = (
            '<span class="pbj-ai-chip pbj-ai-page-helper__more">'
            '<button type="button" class="pbj-ai-page-helper__footer-link pbj-ai-chip__menu" '
            'aria-expanded="false" aria-haspopup="true" data-pbj-track="ai_helper_more_options">More</button>'
            '<div class="pbj-ai-popover" hidden role="menu">'
            + chr(10).join(more_items)
            + '</div></span>'
        )
    footer_inner = footer_csv_html
    if footer_csv_html and more_html:
        footer_inner = (
            footer_csv_html
            + '<span class="pbj-ai-page-helper__footer-sep" aria-hidden="true">·</span>'
            + more_html
        )
    elif more_html:
        footer_inner = more_html
    footer_block = ''
    if footer_inner:
        footer_block = f'<div class="pbj-ai-page-helper__footer">{footer_inner}</div>'
    hidden_fields = [
        f'<textarea id="{ctx_id}" class="pbj-ai-context-data" readonly hidden aria-hidden="true">{html.escape(ctx)}</textarea>',
    ]
    if snapshot_csv:
        hidden_fields.append(
            f'<textarea id="{snap_id}" class="pbj-ai-csv-data" readonly hidden aria-hidden="true">{html.escape(snapshot_csv)}</textarea>'
        )
    if trends_csv:
        hidden_fields.append(
            f'<textarea id="{trend_id}" class="pbj-ai-csv-data" readonly hidden aria-hidden="true">{html.escape(trends_csv)}</textarea>'
        )
    data_attrs = (
        f'data-page-type="{html.escape(ptype)}" data-context-id="{ctx_id}" '
        f'data-csv-enabled="{csv_flag}" data-helper-uid="{html.escape(uid)}"'
    )
    if snap_attr:
        data_attrs += f' data-snapshot-csv-id="{snap_attr}"'
    if trend_attr:
        data_attrs += f' data-trends-csv-id="{trend_attr}"'
    return f"""<div class="pbj-ai-helper-compact pbj-ai-page-helper" data-pbj-track="ai_helper_view" {data_attrs}>
<p class="pbj-ai-helper-compact__title">{html.escape(PBJ_AI_HELPER_TITLE)}</p>
<p class="pbj-ai-helper-compact__body">{html.escape(PBJ_AI_HELPER_BODY)}</p>
<div class="pbj-ai-page-helper__controls">
{lens_sel}
{length_sel}
</div>
<div class="pbj-ai-page-helper__actions">
<span class="pbj-ai-page-helper__icons" role="group" aria-label="Open in Claude or ChatGPT">
<button type="button" class="pbj-ai-icon-btn pbj-ai-launch pbj-ai-launch-packet" data-ai="claude" title="Copy packet and open Claude" aria-label="Claude"><img src="/ai-icons/claude.svg" alt="" width="16" height="16" class="pbj-ai-brand-icon"></button>
<button type="button" class="pbj-ai-icon-btn pbj-ai-launch pbj-ai-launch-packet" data-ai="chatgpt" title="Copy packet and open ChatGPT" aria-label="ChatGPT"><img src="/ai-icons/chatgpt.svg" alt="" width="16" height="16" class="pbj-ai-brand-icon"></button>
</span>
<button type="button" class="pbj-ai-helper-compact__btn pbj-ai-helper-compact__btn--primary pbj-ai-copy-packet" data-context-id="{ctx_id}" data-pbj-track="copy_ai_packet">Copy AI packet</button>
</div>
{footer_block}
{''.join(hidden_fields)}
</div>"""


def render_ai_minimal_bar(
    page_context_text: str,
    *,
    helper_uid: str = 'default',
    page_type: str = 'facility',
    page_url: str = '',
    facility_name: str = '',
    ccn: str = '',
    state_label: str = '',
    state_code: str = '',
    state_standard_available: bool = False,
    snapshot_csv: str = '',
    trends_csv: str = '',
    snapshot_csv_filename: str = '',
    trends_csv_filename: str = '',
    trend_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    share_html: str = '',
) -> str:
    """One row: persona dropdown + Claude/ChatGPT icons. CSV lives in page footer."""
    if not should_show_public_ai_tools(state_code=state_code, state_label=state_label):
        return ''
    ctx = (page_context_text or '').strip()
    if not ctx:
        return ''
    uid = re.sub(r'[^a-zA-Z0-9_-]', '', str(helper_uid or 'default'))[:48] or 'default'
    ctx_id = f'pbj-ai-context-{uid}'
    snap_id = f'pbj-ai-csv-snapshot-{uid}'
    trend_id = f'pbj-ai-csv-trends-{uid}'
    ptype = (page_type or 'facility').strip().lower()
    csv_flag = '1' if ptype in ('facility', 'provider') and (snapshot_csv or trends_csv) else '0'
    default_lens = normalize_public_review_lens('ombudsman')
    lens_sel = _render_lens_select(default_lens)
    pbjai_info_btn = _render_pbjai_info_btn()
    brief_toggle = _render_ai_brief_toggle(active_brief=False)
    share_block = (share_html or '').strip()
    data_attrs = (
        f'data-page-type="{html.escape(ptype)}" data-context-id="{ctx_id}" '
        f'data-csv-enabled="{csv_flag}" data-helper-uid="{html.escape(uid)}" '
        f'data-pbj-length="standard" data-pbj-brief="0" data-pbj-lens="{html.escape(default_lens)}"'
    )
    if snapshot_csv:
        data_attrs += f' data-snapshot-csv-id="{html.escape(snap_id, quote=True)}"'
        if snapshot_csv_filename:
            data_attrs += (
                f' data-snapshot-csv-filename="{html.escape(snapshot_csv_filename, quote=True)}"'
            )
    if trends_csv:
        data_attrs += f' data-trends-csv-id="{html.escape(trend_id, quote=True)}"'
        if trends_csv_filename:
            data_attrs += (
                f' data-trends-csv-filename="{html.escape(trends_csv_filename, quote=True)}"'
            )
    handoff_id = f'pbj-ai-handoff-{uid}'
    include_csv_notes = csv_flag == '1'
    handoff = build_facility_dashboard_packet(
        ctx,
        page_type=ptype,
        page_url=page_url,
        facility_name=facility_name,
        facility_state=state_label,
        facility_state_code=state_code,
        include_csv_notes=include_csv_notes,
    )
    prefill_id = f'pbj-ai-prefill-{uid}'
    extended_id = f'pbj-ai-extended-{uid}'
    oneshot_prefill = build_facility_oneshot_prefill(
        ctx,
        page_type=ptype,
        page_url=page_url,
        facility_name=facility_name,
        ccn=ccn,
        facility_state=state_label,
        facility_state_code=state_code,
    )
    extended_context = build_facility_context_data_file(
        ctx,
        trend_rows=trend_rows,
        trends_csv=trends_csv,
        snapshot_detail_csv=snapshot_csv,
        meta_ccn=str(ccn or '').strip(),
        meta_facility_name=str(facility_name or '').strip(),
        meta_page_url=str(page_url or '').strip(),
    )
    data_attrs += f' data-handoff-id="{html.escape(handoff_id, quote=True)}"'
    data_attrs += f' data-prefill-id="{html.escape(prefill_id, quote=True)}"'
    data_attrs += f' data-extended-context-id="{html.escape(extended_id, quote=True)}"'
    if page_url:
        data_attrs += f' data-page-url="{html.escape(page_url, quote=True)}"'
    if facility_name:
        data_attrs += f' data-facility-name="{html.escape(facility_name, quote=True)}"'
    if state_label:
        data_attrs += f' data-ai-state-label="{html.escape(state_label, quote=True)}"'
    if state_code:
        data_attrs += f' data-ai-state-code="{html.escape(state_code, quote=True)}"'
    if (ccn or '').strip():
        data_attrs += f' data-ai-ccn="{html.escape(str(ccn).strip(), quote=True)}"'
    data_attrs += (
        f' data-ai-state-standard-available="{"1" if state_standard_available else "0"}"'
    )
    beta_modal = render_pbj_ai_beta_modal(uid)
    share_wrapped = (
        f'<span class="pbj-ai-provider-bar__share">{share_block}</span>' if share_block else ''
    )
    return f"""<div class="pbj-ai-provider-bar pbj-ai-page-helper" data-pbj-track="ai_helper_view" {data_attrs}>
<div class="pbj-ai-provider-bar__row pbj-ai-provider-bar__row--top">
{pbjai_info_btn}
<span class="pbj-ai-provider-bar__sep" aria-hidden="true">|</span>
{lens_sel}
</div>
<div class="pbj-ai-provider-bar__row pbj-ai-provider-bar__row--actions">
<span class="pbj-ai-provider-bar__actions">
<span class="pbj-ai-provider-bar__cta" role="group" aria-label="Review this staffing page with AI">
<button type="button" class="pbj-ai-provider-ai pbj-ai-provider-ai--cta pbj-ai-launch pbj-ai-launch-packet" data-ai="claude" data-handoff-id="{handoff_id}" title="Open Claude with this facility review prefilled"><img src="/ai-icons/claude.svg" alt="" width="14" height="14" class="pbj-ai-brand-icon" aria-hidden="true"><span>Ask Claude</span></button>
<button type="button" class="pbj-ai-provider-ai pbj-ai-provider-ai--cta pbj-ai-launch pbj-ai-launch-packet" data-ai="chatgpt" data-handoff-id="{handoff_id}" title="Open ChatGPT with this facility review prefilled"><img src="/ai-icons/chatgpt.svg" alt="" width="14" height="14" class="pbj-ai-brand-icon" aria-hidden="true"><span>Ask ChatGPT</span></button>
</span>
{brief_toggle}
</span>
<span class="pbj-ai-provider-bar__spacer" aria-hidden="true"></span>
{share_wrapped}
</div>
<textarea id="{handoff_id}" class="pbj-ai-handoff-data" readonly hidden aria-hidden="true">{html.escape(handoff)}</textarea>
<textarea id="{prefill_id}" class="pbj-ai-prefill-data" readonly hidden aria-hidden="true">{html.escape(oneshot_prefill)}</textarea>
<textarea id="{extended_id}" class="pbj-ai-extended-data" readonly hidden aria-hidden="true">{html.escape(extended_context)}</textarea>
<textarea id="{ctx_id}" class="pbj-ai-context-data" readonly hidden aria-hidden="true">{html.escape(ctx)}</textarea>
{beta_modal}
</div>"""


def render_facility_csv_page_footer(
    *,
    helper_uid: str = 'default',
    snapshot_csv: str = '',
    snapshot_csv_filename: str = '',
    trends_csv: str = '',
    trends_csv_filename: str = '',
    care_compare_url: str = '',
    state_code: str = '',
    state_label: str = '',
) -> str:
    """Care Compare + one subtle PBJ spreadsheet download; hidden CSV payloads for the AI bar data-* ids."""
    cc = (care_compare_url or '').strip()
    uid = re.sub(r'[^a-zA-Z0-9_-]', '', str(helper_uid or 'default'))[:48] or 'default'
    snap_id = f'pbj-ai-csv-snapshot-{uid}'
    trend_id = f'pbj-ai-csv-trends-{uid}'
    ai_on = should_show_public_ai_tools(state_code=state_code, state_label=state_label)
    has_csv = bool(snapshot_csv or trends_csv)
    hidden: list[str] = []
    if ai_on:
        if snapshot_csv:
            hidden.append(
                f'<textarea id="{snap_id}" class="pbj-ai-csv-data" readonly hidden aria-hidden="true">{html.escape(snapshot_csv)}</textarea>'
            )
        if trends_csv:
            hidden.append(
                f'<textarea id="{trend_id}" class="pbj-ai-csv-data" readonly hidden aria-hidden="true">{html.escape(trends_csv)}</textarea>'
            )
    show_csv_btn = ai_on and has_csv
    if not cc and not hidden and not show_csv_btn:
        return ''
    parts: list[str] = ['<div class="pbj-care-footer-row">']
    if cc:
        esc_cc = html.escape(cc, quote=True)
        parts.append(
            f'<a href="{esc_cc}" target="_blank" rel="noopener" class="pbj-care-compare-badge">View on Care Compare</a>'
        )
    if show_csv_btn:
        if cc:
            parts.append('<span class="pbj-care-footer-sep" aria-hidden="true">·</span>')
        parts.append(
            f'<button type="button" class="pbj-footer-csv-bundle" data-csv-bundle-for="{html.escape(uid, quote=True)}" '
            'title="Download quarterly snapshot-detail and trends CSVs" aria-label="Download PBJ CSVs">'
            'Download PBJ</button>'
        )
    parts.append('</div>')
    parts.append(''.join(hidden))
    return ''.join(parts)


def render_ai_facility_helper(
    page_context_text: str,
    handoff_text: str = '',
    *,
    helper_uid: str = 'default',
    page_url: str = '',
    facility_name: str = '',
    ccn: str = '',
    state_label: str = '',
    state_code: str = '',
    state_standard_available: bool = False,
    review_config: Optional[ReviewConfig] = None,
    snapshot_csv: str = '',
    snapshot_csv_filename: str = '',
    trends_csv: str = '',
    trends_csv_filename: str = '',
    trend_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    share_html: str = '',
) -> str:
    _ = handoff_text, review_config, snapshot_csv_filename, trends_csv_filename
    return render_ai_minimal_bar(
        page_context_text,
        helper_uid=helper_uid,
        page_type='facility',
        page_url=page_url,
        facility_name=facility_name,
        ccn=ccn,
        state_label=state_label,
        state_code=state_code,
        state_standard_available=state_standard_available,
        snapshot_csv=snapshot_csv,
        trends_csv=trends_csv,
        snapshot_csv_filename=snapshot_csv_filename,
        trends_csv_filename=trends_csv_filename,
        trend_rows=trend_rows,
        share_html=share_html,
    )


def render_ai_dashboard_helper(
    page_context_text: str,
    helper_uid: str = 'default',
    review_config: Optional[ReviewConfig] = None,
    page_type: Optional[str] = None,
) -> str:
    _ = review_config
    return render_ai_page_helper(
        page_context_text,
        helper_uid=helper_uid,
        page_type=page_type or 'facility',
    )
