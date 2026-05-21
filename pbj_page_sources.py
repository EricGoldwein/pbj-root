"""Compact page footers: CMS source links, PBJ quarter, and per-page data dialogs."""

from __future__ import annotations

import html

CMS_PBJ_DAILY_URL = (
    'https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing'
)
CMS_PROVIDER_INFO_URL = 'https://data.cms.gov/provider-data/dataset/4pq5-n9py'
CMS_CHAIN_PERF_URL = (
    'https://data.cms.gov/quality-of-care/nursing-home-chain-performance-measures/data'
)
MACPAC_STAFFING_URL = (
    'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
)
DATA_SOURCES_PAGE = '/data-sources'


def _ext_link(href: str, label: str) -> str:
    return (
        f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">'
        f'{html.escape(label)}</a>'
    )


def _about_data_button(dialog_id: str) -> str:
    return (
        f'<button type="button" class="pbj-sources-about-btn" '
        f'data-pbj-sources-open="{html.escape(dialog_id, quote=True)}">About data</button>'
    )


def _sources_dialog(dialog_id: str, sections: list[tuple[str, str]]) -> str:
    items = ''.join(
        f'<li><strong>{html.escape(title)}</strong> {body}</li>'
        for title, body in sections
    )
    return (
        f'<dialog id="{html.escape(dialog_id, quote=True)}" class="pbj-sources-dialog">'
        f'<div class="pbj-sources-dialog__panel" role="document">'
        f'<h2 class="pbj-sources-dialog__title">Data on this page</h2>'
        f'<ul class="pbj-sources-dialog__list">{items}</ul>'
        f'<p class="pbj-sources-dialog__more">Full reference: '
        f'<a href="{DATA_SOURCES_PAGE}">Data sources</a>.</p>'
        f'<form method="dialog">'
        f'<button type="submit" class="pbj-sources-dialog__close">Close</button>'
        f'</form></div></dialog>'
    )


def render_facility_sources_footer(
    pbj_quarter_display: str,
    *,
    include_chow: bool = False,
    include_macpac: bool = False,
) -> str:
    """Facility page: PBJ quarter + Provider Information (+ optional CHOW / MACPAC)."""
    dialog_id = 'pbj-sources-facility'
    q = (pbj_quarter_display or '').strip()
    q_suffix = (
        f'<span class="pbj-sources-quarter"> through {html.escape(q)}</span>'
        if q
        else ''
    )
    line_parts = [
        f'<span class="pbj-sources-item">{_ext_link(CMS_PBJ_DAILY_URL, "PBJ")}{q_suffix}</span>',
        f'<span class="pbj-sources-item">{_ext_link(CMS_PROVIDER_INFO_URL, "Provider Information")}</span>',
        f'<span class="pbj-sources-item">{_about_data_button(dialog_id)}</span>',
    ]
    line = '<span class="pbj-sources-label">Sources:</span> ' + ' <span class="pbj-sources-sep" aria-hidden="true">·</span> '.join(
        line_parts
    )

    q_note = f' Staffing on this page reflects PBJ through <strong>{html.escape(q)}</strong>.' if q else ''
    sections: list[tuple[str, str]] = [
        (
            'CMS Payroll-Based Journal (PBJ)',
            f'Charts, HPRD, and quarterly staffing metrics.{q_note} '
            'PBJ is the primary staffing source on facility pages.',
        ),
        (
            'CMS Provider Information',
            'Star ratings, ownership type, case-mix, certified beds, and related fields. '
            'These snapshots may reflect a <em>newer</em> CMS posting than the PBJ quarter above.',
        ),
    ]
    if include_macpac:
        sections.append(
            (
                'MACPAC state staffing reference',
                f'State minimum HPRD lines on charts use {_ext_link(MACPAC_STAFFING_URL, "MACPAC")} '
                'policy estimates (not statutory text).',
            )
        )
    if include_chow:
        sections.append(
            (
                'CMS ownership changes (CHOW)',
                'Change-of-ownership events shown in the Ownership section, where published by CMS.',
            )
        )

    return (
        f'<p class="pbj-page-footer-sources">{line}</p>'
        f'{_sources_dialog(dialog_id, sections)}'
    )


def render_entity_sources_footer(
    pbj_quarter_display: str,
    *,
    chain_label: str = '',
    care_compare_url: str = '',
) -> str:
    """Entity page: PBJ for facility staffing + chain performance measures."""
    dialog_id = 'pbj-sources-entity'
    q = (pbj_quarter_display or '').strip()
    q_suffix = (
        f'<span class="pbj-sources-quarter"> through {html.escape(q)}</span>'
        if q
        else ''
    )
    chain_link = _ext_link(CMS_CHAIN_PERF_URL, 'Chain performance')
    if (chain_label or '').strip():
        chain_link += f' <span class="pbj-sources-quarter">({html.escape(chain_label.strip())})</span>'
    line_parts = [
        f'<span class="pbj-sources-item">{_ext_link(CMS_PBJ_DAILY_URL, "PBJ")}{q_suffix} <span class="pbj-sources-quarter">(facility staffing)</span></span>',
        f'<span class="pbj-sources-item">{chain_link}</span>',
    ]
    cc = (care_compare_url or '').strip()
    if cc:
        line_parts.append(
            f'<span class="pbj-sources-item">'
            f'<a href="{html.escape(cc, quote=True)}" target="_blank" rel="noopener">Care Compare</a>'
            f'</span>'
        )
    line_parts.append(f'<span class="pbj-sources-item">{_about_data_button(dialog_id)}</span>')
    line = '<span class="pbj-sources-label">Sources:</span> ' + ' <span class="pbj-sources-sep" aria-hidden="true">·</span> '.join(
        line_parts
    )
    q_note = f' through <strong>{html.escape(q)}</strong>' if q else ''
    sections = [
        (
            'CMS Payroll-Based Journal (PBJ)',
            f'Per-facility staffing in the table below{q_note}.',
        ),
        (
            'CMS nursing home chain performance',
            'Entity-level ratings, fines, SFF counts, ownership summaries, and related chain metrics. '
            'May update on a different schedule than PBJ staffing files.',
        ),
    ]
    return (
        f'<p class="pbj-page-footer-sources">{line}</p>'
        f'{_sources_dialog(dialog_id, sections)}'
    )
