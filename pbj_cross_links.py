"""Compact cross-links between PBJ320 pages (facility / state / entity / report / SFF / wrapped)."""

from __future__ import annotations

import html
import re
from typing import Callable, Mapping, Optional


def render_cross_links_html(
    links: list[tuple[str, str]],
    *,
    label: str = 'Related',
) -> str:
    """One muted line: Related: link · link · … (max 4). Empty if no links."""
    items: list[str] = []
    for link_label, href in links[:4]:
        link_label = (link_label or '').strip()
        href = (href or '').strip()
        if not link_label or not href:
            continue
        items.append(
            f'<a href="{html.escape(href, quote=True)}">{html.escape(link_label)}</a>'
        )
    if not items:
        return ''
    sep = ' <span class="pbj-cross-sep" aria-hidden="true">·</span> '
    label_text = (label or '').strip()
    label_html = (
        f'<span class="pbj-cross-links-label">{html.escape(label_text)}:</span> '
        if label_text
        else ''
    )
    return (
        '<p class="pbj-cross-links" aria-label="Related pages on PBJ320">'
        + label_html
        + sep.join(items)
        + '</p>'
    )


def report_href_for_state(state_slug: str = '') -> str:
    slug = (state_slug or '').strip().lower()
    if slug and re.fullmatch(r'[a-z0-9-]+', slug):
        return f'/report?state={slug}'
    return '/report'


def state_rank_link_html(
    rank: int | str | None,
    total_states: int | str | None,
    *,
    state_slug: str = '',
) -> str:
    """Inline rank phrase for narratives; links to rankings when rank is known."""
    if not rank or not total_states:
        return ''
    try:
        r = int(rank)
        t = int(total_states)
    except (TypeError, ValueError):
        return f'<strong>#{html.escape(str(rank))}</strong> out of {html.escape(str(total_states))} states'
    href = report_href_for_state(state_slug)
    return (
        f' and ranks <a href="{href}" class="pbj-inline-link">#{r}</a> '
        f'out of {t} states'
    )


def cross_links_for_state(
    *,
    state_code: str,
    state_name: str,
    state_slug: str,
    has_sff: bool = False,
) -> str:
    code = (state_code or '').strip().upper()[:2]
    slug = (state_slug or '').strip().lower()
    name = (state_name or '').strip() or code
    links: list[tuple[str, str]] = [
        (f'{name} staffing rankings', report_href_for_state(slug)),
    ]
    if has_sff and code:
        links.append(('Special Focus Facilities', f'/sff/{code.lower()}'))
    return render_cross_links_html(links)


def cross_links_for_facility(
    *,
    state_code: str,
    state_slug: str,
    is_sff: bool = False,
) -> str:
    """Skip state/entity when already in subtitle — only contextual horizontal hops."""
    code = (state_code or '').strip().upper()[:2]
    slug = (state_slug or '').strip().lower()
    # State is already in breadcrumb/subtitle — only show cross-links when SFF adds context.
    links: list[tuple[str, str]] = []
    if is_sff and code:
        links.append(('Special Focus Facilities', f'/sff/{code.lower()}'))
    return render_cross_links_html(links)


def cross_links_for_entity(
    *,
    entity_id: str | int,
    top_states: list[tuple[str, str]] | None = None,
) -> str:
    """top_states: [(display name, canonical slug), ...] up to 2."""
    links: list[tuple[str, str]] = [('Staffing rankings', '/report')]
    for name, slug in (top_states or [])[:2]:
        slug = (slug or '').strip().lower()
        name = (name or '').strip()
        if slug and name:
            links.append((name, f'/state/{slug}'))
    return render_cross_links_html(links)


def resolve_home_deep_link(
    args,
    *,
    state_code_to_name: Mapping[str, str],
    get_canonical_slug: Callable[[str], str],
    normalize_ccn: Callable[[object], str],
) -> Optional[str]:
    """Return redirect path for ?facility= / ?ccn= / ?state= / ?entity= or None."""
    fac = (args.get('facility') or args.get('ccn') or '').strip()
    if fac:
        ccn = normalize_ccn(fac)
        if ccn and len(ccn) == 6 and ccn.isdigit():
            return f'/provider/{ccn}'

    entity = (args.get('entity') or args.get('chain') or '').strip()
    if entity and re.fullmatch(r'\d+', entity):
        return f'/entity/{entity}'

    state_raw = (args.get('state') or '').strip()
    if not state_raw:
        return None

    key = state_raw.strip()
    upper = key.upper()
    if len(upper) == 2 and upper in state_code_to_name:
        return f'/state/{get_canonical_slug(upper)}'

    slug_candidate = key.lower().replace(' ', '-')
    for code, name in state_code_to_name.items():
        if get_canonical_slug(code) == slug_candidate:
            return f'/state/{slug_candidate}'
        if name.lower() == key.lower():
            return f'/state/{get_canonical_slug(code)}'

    if re.fullmatch(r'[a-z][a-z0-9-]*', slug_candidate):
        return f'/state/{slug_candidate}'
    return None
