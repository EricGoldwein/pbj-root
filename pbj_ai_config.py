"""PBJ320 AI Support feature flags (pre-launch vs public).

Set environment variable PBJ_AI_SUPPORT:

  off         — default; nothing public (pre-AI)
  dashboards  — compact “Use with AI” on facility/state/entity pages only (preview)
  page        — /pbj-ai-support + zip download only
  all         — page + dashboard helpers + sample page block

Examples (PowerShell):
  $env:PBJ_AI_SUPPORT = "dashboards"   # preview on provider pages
  $env:PBJ_AI_SUPPORT = "all"          # full launch
"""

from __future__ import annotations

import os
import re

_VALID = frozenset({'off', 'dashboards', 'page', 'all'})

_PUBLIC_AI_LAUNCH_STATES = frozenset({'CT', 'NY'})

_STATE_NAME_ALIASES: dict[str, str] = {
    'ct': 'CT',
    'connecticut': 'CT',
    'ny': 'NY',
    'new york': 'NY',
}


def pbj_ai_support_mode() -> str:
    raw = (os.environ.get('PBJ_AI_SUPPORT') or 'off').strip().lower()
    aliases = {
        '1': 'all',
        'true': 'all',
        'on': 'all',
        'yes': 'all',
        'preview': 'dashboards',
        'dash': 'dashboards',
        'helper': 'dashboards',
    }
    mode = aliases.get(raw, raw)
    return mode if mode in _VALID else 'off'


def pbj_ai_page_enabled() -> bool:
    return pbj_ai_support_mode() in ('page', 'all')


def pbj_ai_dashboards_enabled() -> bool:
    return pbj_ai_support_mode() in ('dashboards', 'all')


def pbj_ai_skill_zip_public_enabled() -> bool:
    """Full Claude skill ZIP is never exposed on the public site (premium/internal only)."""
    return False


def pbj_ai_zip_download_enabled() -> bool:
    """Skill zip route stays disabled for conservative public pushes."""
    if not pbj_ai_skill_zip_public_enabled():
        return False
    return pbj_ai_page_enabled() or pbj_ai_dashboards_enabled()


def pbj_ai_sample_enabled() -> bool:
    """Sample dashboard AI block (only when launching everything)."""
    return pbj_ai_support_mode() == 'all'


def normalize_state_code_for_ai(
    state_code: str | None = None,
    *,
    state: str | None = None,
    state_label: str | None = None,
) -> str:
    """Return uppercase USPS code when known, else normalized token (may be empty)."""
    for raw in (state_code, state, state_label):
        if raw is None:
            continue
        token = str(raw).strip()
        if not token:
            continue
        upper = token.upper()
        if re.fullmatch(r'[A-Z]{2}', upper):
            return upper
        lower = token.lower().replace('-', ' ').strip()
        if lower in _STATE_NAME_ALIASES:
            return _STATE_NAME_ALIASES[lower]
    return ''


def is_public_ai_launch_state_facility(
    *,
    state_code: str | None = None,
    state: str | None = None,
    state_label: str | None = None,
) -> bool:
    return normalize_state_code_for_ai(state_code, state=state, state_label=state_label) in _PUBLIC_AI_LAUNCH_STATES


def is_connecticut_facility(
    *,
    state_code: str | None = None,
    state: str | None = None,
    state_label: str | None = None,
) -> bool:
    return normalize_state_code_for_ai(state_code, state=state, state_label=state_label) == 'CT'


def should_show_public_ai_tools(
    *,
    state_code: str | None = None,
    state: str | None = None,
    state_label: str | None = None,
) -> bool:
    """Facility AI buttons, CSV handoff, and Claude/ChatGPT launchers (CT + NY public launch)."""
    if not pbj_ai_dashboards_enabled():
        return False
    return is_public_ai_launch_state_facility(
        state_code=state_code, state=state, state_label=state_label
    )


def allowed_public_audience_modes() -> tuple[str, ...]:
    """Internal audience keys exposed on the public site."""
    return ('ombudsman', 'family_resident', 'journalist')


def allowed_public_review_lenses() -> tuple[tuple[str, str], ...]:
    """(lens_id, UI label) for public persona dropdowns."""
    return (
        ('ombudsman', 'Ombudsman'),
        ('family', 'Family'),
        ('journalist', 'Journalist'),
    )


def public_default_audience() -> str:
    return 'ombudsman'


def public_default_review_lens() -> str:
    return 'ombudsman'
