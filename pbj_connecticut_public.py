"""Connecticut-only public context for AI prompts (CT facility preview).

MACPAC figures below match the Connecticut row in MACPAC's state staffing compendium
and ``state_standards.json`` (3.06 HPRD total estimated). Verify against current
statute, DPH regulations, and waivers before any compliance claim.
"""

from __future__ import annotations

from pbj_ai_config import is_connecticut_facility, normalize_state_code_for_ai

# MACPAC *State Policies Related to Nursing Facility Staffing* — Connecticut summary (2021 collection)
CT_MACPAC_TOTAL_ESTIMATED_HPRD = 3.06
CT_MACPAC_DIRECT_CARE_HPRD = 3.00  # RNs + LPNs + CNAs combined (SB 1030 / PA 21-2)
CT_MACPAC_DON_HPRD = 0.06
CT_DIRECT_CARE_STATUTE_NOTE = (
    'Public Act 21-2 (SB 1030): DPH to establish minimum direct-care staffing of '
    '3.00 hours per resident per day (effective October 1, 2021; requirements by January 1, 2022).'
)
CT_DON_REG_NOTE = (
    'CT regs (R.C.S.A. tit. 19 § 19-13-D8t): DON time/scheduling rules (e.g. full-time, '
    '7 a.m.–9 p.m. coverage; ADON at 120+ beds) — not interchangeable with PBJ RN lines.'
)

CT_LTCOP_HOME = 'https://portal.ct.gov/LTCOP'
CT_LTCOP_CONTACT = 'https://portal.ct.gov/ltcop/content/contact-us/contact'
CT_LTCOP_TOLL_FREE = '1-866-388-1888'
CT_LTCOP_MAIN_PHONE = '860-424-5200'
CT_LTCOP_EMAIL = 'ltcop@ct.gov'

CT_DPH_NURSING_HOME_GUIDANCE = (
    'https://portal.ct.gov/DPH/Health-Care-Systems--Facilities--and-Regulation/Health-'
    'Care-Systems/Healthcare-Associated-Infections-and-Antimicrobial-Resistance/'
    'Nursing-Home-Guidance'
)
CT_MACPAC_STATE_PAGE = (
    'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
)


def connecticut_public_context_block(
  *,
  lens: str = 'ombudsman',
  state_code: str | None = None,
  state_label: str | None = None,
) -> str:
    """Return CT-specific reviewer bullets, or empty string for non-CT facilities."""
    if not is_connecticut_facility(
        state_code=state_code, state=state_label, state_label=state_label
    ):
        return ''
    code = normalize_state_code_for_ai(state_code, state=state_label, state_label=state_label)
    lens_key = (lens or 'ombudsman').strip().lower().replace('-', '_')
    if lens_key in ('family', 'family_resident'):
        return _ct_family_block(code)
    if lens_key == 'journalist':
        return _ct_journalist_block(code)
    return _ct_ombudsman_block(code)


def _ct_macpac_orientation_block() -> str:
    return (
        '- **Connecticut staffing policy orientation (MACPAC compendium — verify current law):**\n'
        f'  - MACPAC summarizes **~{CT_MACPAC_TOTAL_ESTIMATED_HPRD:.2f} HPRD** total estimated '
        'staffing requirement for Connecticut.\n'
        f'  - **{CT_MACPAC_DIRECT_CARE_HPRD:.2f} HPRD** combined RN+LPN+CNA direct care minimum '
        f'({CT_DIRECT_CARE_STATUTE_NOTE})\n'
        f'  - **{CT_MACPAC_DON_HPRD:.2f} HPRD** DON component in regulation ({CT_DON_REG_NOTE})\n'
        '  - **PBJ reported HPRD is not proof** a facility met Connecticut statutory minimums — '
        'different role definitions, numerators/denominators, exclusions, and DPH calculation rules '
        'must be verified before any compliance or "under state law" language.\n'
        f'  - MACPAC state table: {CT_MACPAC_STATE_PAGE}'
    )


def _ct_ombudsman_block(_state_code: str) -> str:
    return (
        '- **Connecticut Long-Term Care Ombudsman Program (LTCOP) — primary partner for residents:**\n'
        f'  - Program hub: {CT_LTCOP_HOME}\n'
        f'  - Contact page (verify before citing): {CT_LTCOP_CONTACT}\n'
        f'  - Toll-free: {CT_LTCOP_TOLL_FREE} · Main office: {CT_LTCOP_MAIN_PHONE} · Email: {CT_LTCOP_EMAIL}\n'
        '  - Use the LTCOP site for **regional ombudsman assignments** (town list / map), resident rights '
        'materials, complaint navigation, visitation resources, and Silver Panther / council materials.\n'
        '- **Ombudsman practice reminders for Connecticut:**\n'
        '  - Staffing numbers are **visit and conversation prep** — not findings, violations, or neglect.\n'
        '  - Emphasize **resident direction, informed consent, dignity, and retaliation sensitivity**.\n'
        '  - Pair PBJ with **Medicare.gov Care Compare** (this facility), **DPH** licensing/survey context, '
        'and **resident/family council** channels where appropriate.\n'
        '  - For **staffing-rule questions**, distinguish **CMS case-mix reference HPRD** (acuity benchmark) '
        'from **Connecticut direct-care minimums** — ask DPH or counsel what calculation applies; do not '
        'tell residents a home "failed state law" from PBJ alone.\n'
        f'{_ct_macpac_orientation_block()}\n'
        '- **Connecticut Department of Public Health (DPH):** licensing, inspections, complaint intake — '
        'confirm current portal URLs and forms on ct.gov/DPH before citing.\n'
        '- **Optional navigation:** Eldercare Locator (ACL) for caregivers unsure which local program to call.'
    )


def _ct_family_block(_state_code: str) -> str:
    return (
        '- **Connecticut help lines (verify current hours/forms):**\n'
        f'  - Long-Term Care Ombudsman: {CT_LTCOP_TOLL_FREE} ({CT_LTCOP_HOME})\n'
        '  - State health/licensing complaints: Connecticut DPH (confirm current complaint portal).\n'
        '- Ask the facility **how** weekend/evening staffing is planned — quarterly PBJ cannot show a specific shift.\n'
        f'{_ct_macpac_orientation_block()}'
    )


def _ct_journalist_block(_state_code: str) -> str:
    return (
        '- **Connecticut reporting anchors (verify before publish):**\n'
        f'  - LTCOP for resident-directed context: {CT_LTCOP_HOME} · {CT_LTCOP_CONTACT}\n'
        '  - DPH nursing home guidance / inspection postings; CMS Care Compare staffing history.\n'
        '- Safe now: reported HPRD vs CMS case-mix reference **as screening comparison**; not compliance.\n'
        '- Not publishable from PBJ alone: "violated CT minimum staffing law" — need statute/reg text, '
        'DPH interpretation, and facility-specific calculations.\n'
        f'{_ct_macpac_orientation_block()}'
    )
