"""SEO metadata helper functions for Flask templates and dynamic pages.

Dashboard convention (provider, entity, owner, state shells):
- Use page_title, meta_description, and JSON-LD only for SEO prose.
- *_page_intro_html() on dashboards MUST return '' (no visible SEO paragraphs).
- Full article copy belongs only on EXPLAINER_PAGES routes (/what-is-hprd, /phoebe, etc.).
"""
from __future__ import annotations

import html
import json
import os
import re
from typing import Any

from site_public_config import (
    CARE_COMPARE_URL,
    CMS_2001_STAFFING_STUDY_URL,
    CMS_PBJ_DAILY_DATASET_URL,
    CMS_PBJ_EMPLOYEE_DETAIL_URL,
    CMS_PBJ_POLICY_MANUAL_URL,
    CMS_PBJ_PUF_DOCUMENTATION_URL,
    CMS_PBJ_STAFFING_SUBMISSION_URL as CMS_PBJ_PROGRAM_URL,
    CMS_PROVIDER_INFO_DATASET_URL,
    MACPAC_STATE_STAFFING_URL,
    PUBLIC_SITE_ORIGIN,
    normalize_public_site_origin,
)

STATE_ABBR_TO_NAME = {
    'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
    'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
    'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
    'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
    'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
    'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
    'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
    'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'pr': 'Puerto Rico', 'ri': 'Rhode Island', 'sc': 'South Carolina',
    'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
    'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
    'dc': 'District of Columbia'
}


def get_state_name(code: str) -> str:
    """Convert state code to full state name."""
    return STATE_ABBR_TO_NAME.get(code.lower(), code.upper())


def get_region_name(region_num):
    """Convert CMS region number to region name"""
    region_names = {
        1: 'Boston',
        2: 'New York',
        3: 'Philadelphia',
        4: 'Atlanta',
        5: 'Chicago',
        6: 'Dallas',
        7: 'Kansas City',
        8: 'Denver',
        9: 'San Francisco',
        10: 'Seattle'
    }
    return region_names.get(int(region_num), f'Region {region_num}')


def _latest_pbj_quarter_labels():
    """Return tuple (display, compact) like ('Q4 2025', '2025Q4')."""
    fallback_display = 'latest PBJ quarter'
    fallback_compact = 'latest quarter'
    q_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'latest_quarter_data.json')
    try:
        if not os.path.exists(q_path):
            return fallback_display, fallback_compact
        with open(q_path, 'r', encoding='utf-8') as f:
            q_data = json.load(f)
        display = str(q_data.get('quarter_display') or '').strip()
        compact = str(q_data.get('quarter') or '').strip()
        if not display and compact and re.match(r'^\d{4}Q[1-4]$', compact):
            display = f"Q{compact[5]} {compact[:4]}"
        if not compact and display:
            m = re.match(r'^Q([1-4])\s+(\d{4})$', display)
            if m:
                compact = f"{m.group(2)}Q{m.group(1)}"
        return display or fallback_display, compact or fallback_compact
    except Exception:
        return fallback_display, fallback_compact


def get_seo_metadata(path):
    """
    Get SEO metadata based on the request path.
    Returns a dict with title, description, og_title, og_description, canonical_url, og_url, and include_image.
    """
    base_url = normalize_public_site_origin(PUBLIC_SITE_ORIGIN)
    
    quarter_display, _ = _latest_pbj_quarter_labels()

    # Default values for wrapped pages
    default_metadata = {
        'title': f'PBJ Wrapped {quarter_display} — Nursing Home Staffing Data by State and Region | PBJ320',
        'description': f'Explore {quarter_display} nursing home staffing data across all 50 states, CMS regions, and the United States. Interactive staffing insights from CMS Payroll-Based Journal (PBJ) data. Comprehensive analysis of 15,000+ nursing homes and long-term care facilities.',
        'og_title': f'PBJ Wrapped {quarter_display} — Nursing Home Staffing Data',
        'og_description': f'Interactive nursing home staffing data for {quarter_display}. Explore staffing levels, trends, and insights by state, region, and nationally from CMS PBJ data.',
        'canonical_url': base_url + '/wrapped',
        'og_url': base_url + '/wrapped',
        'include_image': True,
        'og_image': base_url + '/images/phoebe-wrapped-wide.png',
    }
    
    # Normalize path (ensure leading slash, handle trailing slash)
    if not path:
        path = '/'
    if not path.startswith('/'):
        path = '/' + path
    
    # Handle SFF pages
    if path.startswith('/sff'):
        # Normalize /sff and /sff/ to /sff/usa
        if path == '/sff' or path == '/sff/':
            path = '/sff/usa'
        
        if path == '/sff/usa' or path == '/sff/usa/':
            return {
                'title': 'Special Focus Facilities Program — United States | PBJ320',
                'description': f'United States Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ {quarter_display}.',
                'og_title': 'Special Focus Facilities Program — United States',
                'og_description': f'United States Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ {quarter_display}.',
                'canonical_url': base_url + '/sff/usa',
                'og_url': base_url + '/sff/usa',
                'include_image': True,
                'og_image': base_url + '/og-image-1200x630.png',
            }
        elif '/sff/region' in path.lower():
            # Extract region number
            import re
            region_match = re.search(r'region-?(\d+)', path.lower())
            region_num = region_match.group(1) if region_match else ''
            return {
                'title': f'SFF Program: CMS Region {region_num} | PBJ320',
                'description': f'CMS Region {region_num} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ {quarter_display}.',
                'og_title': f'SFF Program: CMS Region {region_num}',
                'og_description': f'CMS Region {region_num} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ {quarter_display}.',
                'canonical_url': base_url + path.rstrip('/'),
                'og_url': base_url + path.rstrip('/'),
                'include_image': True,
                'og_image': base_url + '/og-image-1200x630.png',
            }
        else:
            # Extract state code
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2 and parts[0] == 'sff':
                state_code = parts[1].lower()
                if state_code and state_code not in ('sff', 'usa'):
                    state_name = get_state_name(state_code)
                    return {
                        'title': f'{state_name} Special Focus Facilities | PBJ320',
                        'description': f'{state_name} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ {quarter_display}.',
                        'og_title': f'{state_name} Special Focus Facilities',
                        'og_description': f'{state_name} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ {quarter_display}.',
                        'canonical_url': base_url + path.rstrip('/'),
                        'og_url': base_url + path.rstrip('/'),
                        'include_image': True,
                        'og_image': f'{base_url}/og-image-1200x630.png',
                    }
    
    # Handle wrapped pages
    if path.startswith('/wrapped'):
        # Check if it's a region page (e.g., /wrapped/region1, /wrapped/region-1)
        import re
        region_match = re.search(r'/wrapped/region[-_]?(\d+)', path.lower())
        if region_match:
            region_num = region_match.group(1)
            region_name = get_region_name(int(region_num))
            return {
                'title': f'PBJ Wrapped {quarter_display} — CMS Region {region_num} ({region_name}) Nursing Home Staffing Data | PBJ320',
                'description': f'{quarter_display} nursing home staffing data for CMS Region {region_num} ({region_name}). Explore regional staffing levels, rankings, trends, and insights from CMS Payroll-Based Journal (PBJ) data.',
                'og_title': f'PBJ Wrapped {quarter_display} — CMS Region {region_num} Nursing Home Staffing',
                'og_description': f'CMS Region {region_num} ({region_name}) nursing home staffing data and trends for {quarter_display}. Staffing levels, rankings, and insights from CMS PBJ data.',
                'canonical_url': base_url + path.rstrip('/'),
                'og_url': base_url + path.rstrip('/'),
                'include_image': True,
                'og_image': base_url + '/images/phoebe-wrapped-wide.png',
            }
        
        # Check if it's a state page (e.g., /wrapped/ny, /wrapped/ga)
        # Exclude /wrapped, /wrapped/, and /wrapped/usa
        parts = [p for p in path.split('/') if p]
        if len(parts) >= 2 and parts[0] == 'wrapped':
            identifier = parts[1].lower()
            # Check if it's a valid state code (2 letters, not 'usa', not 'region')
            if (len(identifier) == 2 and 
                identifier in STATE_ABBR_TO_NAME and 
                identifier != 'usa' and 
                not identifier.startswith('region')):
                state_name = get_state_name(identifier)
                return {
                    'title': f'PBJ Wrapped {quarter_display} — {state_name} Nursing Home Staffing Data | PBJ320',
                    'description': f'{quarter_display} nursing home staffing data for {state_name}. Explore state-level staffing levels, rankings, trends, and insights from CMS Payroll-Based Journal (PBJ) data. Analysis of nursing homes and long-term care facilities in {state_name}.',
                    'og_title': f'PBJ Wrapped {quarter_display} — {state_name} Nursing Home Staffing',
                    'og_description': f'{state_name} nursing home staffing data and trends for {quarter_display}. Staffing levels, rankings, and insights from CMS PBJ data.',
                    'canonical_url': base_url + path.rstrip('/'),
                    'og_url': base_url + path.rstrip('/'),
                    'include_image': True,
                    'og_image': base_url + '/images/phoebe-wrapped-wide.png',
                }
        
        # For other wrapped pages (default/usa), update canonical and og:url to match path
        default_metadata['canonical_url'] = base_url + path.rstrip('/')
        default_metadata['og_url'] = base_url + path.rstrip('/')
    
    return default_metadata


_PROVIDER_TITLE_SUFFIX = ' | PBJ320'
_PROVIDER_TITLE_BUDGET = 70  # approximate SERP display limit including suffix

# Visible HTML on dashboard shells must not contain these (audit + regression tests).
FORBIDDEN_DASHBOARD_BODY_MARKERS: tuple[str, ...] = (
    'pbj-provider-seo',
    'Latest staffing snapshot',
    'PBJ320 tracks its CMS Payroll-Based Journal',
    'CMS-linked entity record for',
    'not a curated owner/operator profile',
    'Medicare-certified nursing home in',
)


def dashboard_intro_must_be_empty(intro_html: str, *, context: str) -> None:
    """Raise AssertionError when a dashboard route injects visible SEO intro HTML."""
    if (intro_html or '').strip():
        raise AssertionError(f'{context}: dashboard intro_html must be empty, got {len(intro_html)} chars')


def find_forbidden_dashboard_body_markers(html: str) -> list[str]:
    """Return forbidden SEO boilerplate substrings found in dashboard page HTML."""
    text = html or ''
    return [m for m in FORBIDDEN_DASHBOARD_BODY_MARKERS if m in text]


def provider_page_title(
    facility_name: str,
    *,
    city: str = '',
    state_name: str = '',
    state_code: str = '',
) -> str:
    """Title for /provider/<ccn> pages."""
    del city, state_name, state_code
    name = (facility_name or 'Nursing home').strip()
    core = f'{name} Staffing Data'
    title = core + _PROVIDER_TITLE_SUFFIX
    if len(title) <= _PROVIDER_TITLE_BUDGET:
        return title
    max_name = _PROVIDER_TITLE_BUDGET - len('… Staffing Data' + _PROVIDER_TITLE_SUFFIX)
    if max_name > 12:
        short = name[: max_name - 1].rstrip() + '…'
        return f'{short} Staffing Data{_PROVIDER_TITLE_SUFFIX}'
    return f'{name[:20].rstrip()}… Staffing Data{_PROVIDER_TITLE_SUFFIX}'


def provider_page_meta_description(
    facility_name: str,
    *,
    city: str = '',
    state_name: str = '',
    quarter_display: str = '',
    hprd_val: str = '',
    ownership: str = '',
) -> str:
    """Meta/OG description for facility provider pages."""
    del quarter_display, hprd_val, ownership
    name = (facility_name or 'this nursing home').strip()
    if city and state_name:
        where = f'{city}, {state_name}'
    elif state_name:
        where = state_name
    else:
        where = 'the United States'
    return (
        f'CMS Payroll-Based Journal staffing data for {name} in {where}, including nurse staffing, '
        'RN staffing, aide staffing, and facility staffing trends by quarter since 2017.'
    )


def provider_page_intro_html(facility_name: str, **_kwargs: Any) -> str:
    """No visible boilerplate on provider pages (meta description + JSON-LD carry SEO copy)."""
    del facility_name, _kwargs
    return ''


def _owner_profile_state_codes(profile: dict[str, Any]) -> list[str]:
    """USPS codes from facilities listed on this owner profile page only."""
    codes: list[str] = []
    for fac in profile.get('facilities') or []:
        st = (str(fac.get('state') or '')).strip().upper()[:2]
        if st and st not in codes:
            codes.append(st)
    return codes


def _state_names_for_owner_profile(profile: dict[str, Any]) -> list[str]:
    """Full state names from facilities on this page (for meta/geo copy)."""
    codes = _owner_profile_state_codes(profile)
    if len(codes) == 1:
        return [get_state_name(codes[0])]
    if len(codes) > 1:
        return [get_state_name(c) for c in codes[:6]]
    return []


def owner_page_title(display_name: str, profile: dict[str, Any] | None = None) -> str:
    """Browser tab title for /owners/<pac> (not the on-page H1)."""
    del profile
    name = (display_name or 'Organization').strip()
    return f'{name} Nursing Home Ownership | PBJ320'


def owner_page_meta_description(
    display_name: str,
    *,
    facility_count: int = 0,
    state_names: list[str] | None = None,
    owner_type: str = '',
    profile: dict[str, Any] | None = None,
) -> str:
    del profile
    name = (display_name or 'this organization').strip()
    parts = [f'CMS ownership and facility links for {name} on PBJ320.']
    if facility_count > 0:
        n = facility_count
        parts.append(
            f'{n} facilit{"y" if n == 1 else "ies"} linked on this page.'
        )
    states = [s for s in (state_names or []) if s]
    if len(states) == 1:
        parts.append(f'Facilities shown on this page are in {states[0]}.')
    elif len(states) > 1:
        parts.append(
            'Facilities shown on this page span '
            + ', '.join(states[:4])
            + ('…' if len(states) > 4 else '')
            + '.'
        )
    if owner_type and owner_type not in ('—', '-', ''):
        parts.append(f'CMS owner type: {owner_type.strip()}.')
    return ' '.join(parts)


def owner_page_intro_html(
    display_name: str,
    *,
    state_names: list[str] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    """Visible intro removed — name, type, and states already appear in the page header."""
    del display_name, state_names, profile
    return ''


def owner_page_seo_from_profile(profile: dict[str, Any]) -> tuple[str, str, str]:
    """Return (page_title, meta_description, intro_html) for /owners/<pac>."""
    display = str(profile.get('display_name') or 'Organization').strip()
    facilities = profile.get('facilities') or []
    owner_type = str(profile.get('owner_type') or '').strip()
    state_names = _state_names_for_owner_profile(profile)
    title = owner_page_title(display, profile)
    meta = owner_page_meta_description(
        display,
        facility_count=len(facilities),
        state_names=state_names,
        owner_type=owner_type,
        profile=profile,
    )
    intro = owner_page_intro_html(display, state_names=state_names, profile=profile)
    return title, meta, intro


def entity_page_title(entity_name: str, facility_count: int = 0) -> str:
    name = (entity_name or 'CMS entity').strip()
    if facility_count > 0:
        n = facility_count
        return f'{name} ({n} nursing home{"s" if n != 1 else ""}) | PBJ320'
    return f'{name} | PBJ320'


def entity_page_meta_description(entity_name: str, *, facility_count: int = 0, states_count: int = 0) -> str:
    name = (entity_name or 'This entity').strip()
    parts = [
        f'Affiliated nursing home facilities for {name} on PBJ320.',
        'Public CMS PBJ staffing and Provider Information',
    ]
    if facility_count > 0:
        parts.append(f'({facility_count} facilit{"y" if facility_count == 1 else "ies"} in PBJ320 data)')
    if states_count > 0:
        parts.append(f'across {states_count} state{"s" if states_count != 1 else ""}')
    return ' '.join(parts) + '. Chain metrics from CMS Care Compare where available.'


def entity_page_intro_html(entity_name: str) -> str:
    """No visible boilerplate on entity pages (meta description + JSON-LD carry SEO copy)."""
    del entity_name
    return ''


# Future product note: when multi-state owner/operator pages launch, a dedicated public route
# (e.g. /operator/<slug>) with its own robots/sitemap policy may be cleaner than unblocking /owners/.

# Lightweight explainer pages (canonical paths; fuller reference in PBJPedia when launched).
# User-first copy; titles/descriptions carry SEO. See-also footers are short (2 links max).
EXPLAINER_SEE_ALSO: dict[str, tuple[tuple[str, str], ...]] = {
    'what-is-hprd': (
        ('PBJ explained', '/phoebe'),
        ('Search facilities', '/'),
    ),
    'nursing-home-staffing-data': (
        ('PBJ explained', '/phoebe'),
        ('What is HPRD?', '/what-is-hprd'),
    ),
}

EXPLAINER_PAGES: dict[str, dict[str, str]] = {
    'what-is-hprd': {
        'path': '/what-is-hprd',
        'title': 'What is HPRD? Nursing Home Staffing Metric | PBJ320',
        'description': (
            'What is HPRD (hours per resident day)? Nursing home staffing metric from CMS Payroll-Based Journal '
            '(PBJ) data—formula, RN/LPN/aide splits, and how to read it on PBJ320.'
        ),
        'h1': 'What is HPRD?',
        'body': (
            '<p><strong>Hours per resident day (HPRD)</strong> is the usual way to compare nursing home staffing. '
            'Take total paid nursing hours for a period and divide by resident days in that same period:</p>'
            '<p><strong>HPRD = total paid nursing hours ÷ resident days</strong></p>'
            '<p>Example: 400 nursing hours and 100 resident days → HPRD of <strong>4.0</strong>.</p>'
            '<h2>On facility pages</h2>'
            '<p>PBJ320 often shows <strong>total nurse HPRD</strong> plus splits for RNs, LPNs/LVNs, and nurse aides, '
            'based on CMS nursing job categories. Some views also show <strong>direct-care nurse HPRD</strong>, which '
            'drops DON and administrative RN/LPN hours.</p>'
            '<h2>Read it carefully</h2>'
            '<p>HPRD is a quarterly or daily <em>average</em>—it does not show who was on each shift. More hours does '
            'not automatically mean better care, and resident acuity varies. Use it with inspections, complaints, and '
            'other facility context. Background: <a href="/phoebe">PBJ explained</a>.</p>'
        ),
    },
    'nursing-home-staffing-data': {
        'path': '/nursing-home-staffing-data',
        'title': 'Nursing Home Staffing Data by Facility | PBJ320',
        'description': (
            'Nursing home staffing data by facility from CMS Payroll-Based Journal (PBJ) on PBJ320—quarterly HPRD, '
            'RN/LPN/aide mix, contract share where reported, and state comparisons from public federal files.'
        ),
        'h1': 'Nursing Home Staffing Data by Facility',
        'body': (
            '<p>PBJ320 turns public CMS Payroll-Based Journal (PBJ) files into nursing home staffing data you can '
            'look up by facility—quarterly HPRD, RN/LPN/aide mix, contract share where reported, and state '
            'comparisons for the same quarter.</p>'
            '<h2>Good for</h2>'
            '<p>Spotting trends, comparing facilities or states, and preparing follow-up questions—not for proving '
            'harm, neglect, or regulatory violations on its own. PBJ does not show shift-by-shift bedside staffing; '
            'confirm anything important on Care Compare or CMS source files.</p>'
            '<p>Background: <a href="/phoebe">PBJ explained</a> · '
            '<a href="/what-is-hprd">What is HPRD?</a></p>'
            '<h2>Try it</h2>'
            '<p class="pbj-explainer-try-lead">Search by facility on the <a href="/">homepage</a>.</p>'
            '<ul class="pbj-explainer-try-list">'
            '<li><a href="/"><strong>Search by facility</strong></a> — nursing home name, CCN, chain, or state; '
            'quarterly HPRD and RN/LPN/aide staffing for that facility.</li>'
            '<li><a href="/report"><strong>U.S. nursing home staffing rankings</strong></a> — compare states and CMS '
            'regions on the interactive map and tables.</li>'
            '</ul>'
        ),
    },
}


def explainer_see_also_html(slug: str) -> str:
    """One-line contextual footer (at most two links) for Flask explainer routes."""
    links = EXPLAINER_SEE_ALSO.get((slug or '').strip().lower(), (('PBJ explained', '/phoebe'),))
    parts = [f'<a href="{html.escape(path)}">{html.escape(label)}</a>' for label, path in links]
    return f'<p class="pbj-explainer-see-also">See also: {" · ".join(parts)}</p>'


def explainer_related_guides_html(current_path: str | None = None) -> str:
    """Backward-compatible alias; prefer explainer_see_also_html(slug) from app routes."""
    del current_path
    return ''


def get_explainer_page(slug: str) -> dict[str, str] | None:
    return EXPLAINER_PAGES.get((slug or '').strip().lower())


def explainer_page_title(slug: str) -> str:
    """Browser title for explainer routes (always includes | PBJ320)."""
    page = get_explainer_page(slug)
    if not page:
        return 'PBJ320'
    title = (page.get('title') or 'PBJ320').strip()
    if '| PBJ320' not in title:
        title = f'{title} | PBJ320'
    return title


__all__ = [
    'entity_page_intro_html',
    'entity_page_meta_description',
    'entity_page_title',
    'explainer_page_title',
    'explainer_related_guides_html',
    'explainer_see_also_html',
    'get_explainer_page',
    'get_seo_metadata',
    'provider_page_intro_html',
    'provider_page_meta_description',
    'provider_page_title',
    'sitemap_paths_blocked_by_robots',
    'EXPLAINER_PAGES',
    'EXPLAINER_SEE_ALSO',
]


def sitemap_paths_blocked_by_robots(robots_txt: str) -> set[str]:
    """Path prefixes disallowed in robots.txt (for sitemap QA)."""
    blocked: set[str] = set()
    for line in robots_txt.splitlines():
        line = line.strip()
        if line.lower().startswith('disallow:'):
            path = line.split(':', 1)[1].strip()
            if path:
                blocked.add(path.rstrip('/') or '/')
    return blocked


