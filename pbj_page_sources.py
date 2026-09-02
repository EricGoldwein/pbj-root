"""Compact page footers: CMS source links, PBJ quarter, and per-page data dialogs."""

from __future__ import annotations

import html

from site_public_config import (
    CMS_PBJ_DAILY_DATASET_URL as CMS_PBJ_DAILY_URL,
    CMS_PROVIDER_INFO_DATASET_URL as CMS_PROVIDER_INFO_URL,
)
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
        f'<a href="{DATA_SOURCES_PAGE}">Data sources &amp; methodology</a>.</p>'
        f'<form method="dialog">'
        f'<button type="submit" class="pbj-sources-dialog__close">Close</button>'
        f'</form></div></dialog>'
    )


def render_facility_sources_footer(
    pbj_quarter_display: str,
    *,
    include_chow: bool = False,
    include_macpac: bool = False,
    care_compare_url: str = '',
    csv_export_html: str = '',
) -> str:
    """Facility page: PBJ quarter + CMS Provider Info + Care Compare (one footer line)."""
    _ = include_chow, include_macpac
    try:
        from public_source_vintage import source_vintage_label

        pbj_label = (pbj_quarter_display or '').strip() or source_vintage_label('cms.pbj_nurse_staffing')
        pi_label = source_vintage_label('cms.provider_info')
    except Exception:
        pbj_label = (pbj_quarter_display or '').strip()
        pi_label = ''
    pbj_link_label = f'CMS PBJ ({pbj_label})' if pbj_label and pbj_label != '—' else 'CMS PBJ'
    pi_link_label = f'CMS Provider Info ({pi_label})' if pi_label and pi_label != '—' else 'CMS Provider Info'
    line_parts = [
        f'<span class="pbj-sources-item">{_ext_link(CMS_PBJ_DAILY_URL, pbj_link_label)}</span>',
        f'<span class="pbj-sources-item">{_ext_link(CMS_PROVIDER_INFO_URL, pi_link_label)}</span>',
    ]
    cc = (care_compare_url or '').strip()
    if cc:
        line_parts.append(
            f'<span class="pbj-sources-item">'
            f'<a href="{html.escape(cc, quote=True)}" target="_blank" rel="noopener">Care Compare</a>'
            f'</span>'
        )
    if (csv_export_html or '').strip():
        line_parts.append(str(csv_export_html).strip())
    line = '<span class="pbj-sources-label">Sources:</span> ' + ' <span class="pbj-sources-sep" aria-hidden="true">·</span> '.join(
        line_parts
    )

    return f'<p class="pbj-page-footer-sources">{line}</p>'


def render_entity_sources_footer(
    pbj_quarter_display: str,
    *,
    chain_label: str = '',
    care_compare_url: str = '',
) -> str:
    """Entity page: PBJ + CMS chain metrics + optional Care Compare."""
    try:
        from public_source_vintage import source_vintage_label

        pbj_label = (pbj_quarter_display or '').strip() or source_vintage_label('cms.pbj_nurse_staffing')
        chain_label_text = (chain_label or '').strip() or source_vintage_label('cms.chain_performance')
    except Exception:
        pbj_label = (pbj_quarter_display or '').strip()
        chain_label_text = (chain_label or '').strip()
    pbj_link_label = f'CMS PBJ ({pbj_label})' if pbj_label and pbj_label != '—' else 'CMS PBJ'
    chain_link_label = 'CMS Chain Metrics'
    if chain_label_text and chain_label_text != '—':
        chain_link_label = f'CMS Chain Metrics ({chain_label_text})'
    chain_link = _ext_link(CMS_CHAIN_PERF_URL, chain_link_label)
    line_parts = [
        f'<span class="pbj-sources-item">{_ext_link(CMS_PBJ_DAILY_URL, pbj_link_label)}</span>',
        f'<span class="pbj-sources-item">{chain_link}</span>',
    ]
    cc = (care_compare_url or '').strip()
    if cc:
        line_parts.append(
            f'<span class="pbj-sources-item">'
            f'<a href="{html.escape(cc, quote=True)}" target="_blank" rel="noopener">Care Compare</a>'
            f'</span>'
        )
    line = '<span class="pbj-sources-label">Sources:</span> ' + ' <span class="pbj-sources-sep" aria-hidden="true">·</span> '.join(
        line_parts
    )
    return f'<p class="pbj-page-footer-sources">{line}</p>'
