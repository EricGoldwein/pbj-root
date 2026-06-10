"""Public-site constants for trust pages, robots.txt, sitemaps, and security headers."""

from __future__ import annotations

import os
import re

# Canonical public origin (www). Override in staging via PBJ_PUBLIC_BASE_URL.
_PUBLIC_ORIGIN_RAW = (
    os.environ.get('PBJ_PUBLIC_BASE_URL') or os.environ.get('PUBLIC_BASE_URL') or 'https://www.pbj320.com'
).strip().rstrip('/')


def normalize_public_site_origin(origin: str | None = None) -> str:
    """Force production host to https://www.pbj320.com; leave other hosts (staging) unchanged."""
    o = (origin or _PUBLIC_ORIGIN_RAW or 'https://www.pbj320.com').strip().rstrip('/')
    if 'pbj320.com' in o.lower():
        return 'https://www.pbj320.com'
    return o


PUBLIC_SITE_ORIGIN = normalize_public_site_origin(_PUBLIC_ORIGIN_RAW)

# Canonical CMS external URLs (verify with scripts/check_site_links.py).
CMS_PBJ_STAFFING_SUBMISSION_URL = (
    'https://www.cms.gov/medicare/quality/nursing-home-improvement/staffing-data-submission'
)
CMS_PBJ_POLICY_MANUAL_URL = (
    'https://www.cms.gov/medicare/quality-initiatives-patient-assessment-instruments/nursinghomequalityinits/downloads/pbj-policy-manual-final-v25-11-19-2018.pdf'
)
CMS_PBJ_DAILY_DATASET_URL = (
    'https://data.cms.gov/quality-of-care/payroll-based-journal-daily-nurse-staffing'
)
CMS_PBJ_EMPLOYEE_DETAIL_URL = (
    'https://data.cms.gov/quality-of-care/payroll-based-journal-employee-detail-nursing-home-staffing'
)
CMS_PBJ_PUF_DOCUMENTATION_URL = (
    'https://data.cms.gov/sites/default/files/2023-06/PBJ_PUF_Documentation_July_2023.pdf'
)
CMS_PROVIDER_INFO_DATASET_URL = 'https://data.cms.gov/provider-data/dataset/4pq5-n9py'
CMS_NURSING_HOME_IMPROVEMENT_URL = (
    'https://www.cms.gov/medicare/quality/nursing-home-improvement'
)
CMS_MDS_URL = (
    'https://www.cms.gov/medicare/quality/nursing-home-improvement/minimum-data-sets-swing-bed-providers'
)
CMS_SFF_PROGRAM_URL = (
    'https://www.cms.gov/Medicare/Provider-Enrollment-and-Certification/SurveyCertificationGenInfo/Policy-and-Memos-to-States-and-Regions-Items/CMS1215978'
)
CMS_2001_STAFFING_STUDY_URL = (
    'https://www.justice.gov/sites/default/files/elderjustice/legacy/2015/07/12/Appropriateness_of_Minimum_Nurse_Staffing_Ratios_in_Nursing_Homes.pdf'
)
CMS_OPEN_DATA_URL = 'https://data.cms.gov/'
MACPAC_STATE_STAFFING_URL = (
    'https://www.macpac.gov/publication/state-policies-related-to-nursing-facility-staffing/'
)
CARE_COMPARE_URL = 'https://www.medicare.gov/care-compare/'

# Placeholders replaced at serve time in public HTML (see inject_public_html_cms_urls).
PUBLIC_HTML_CMS_PLACEHOLDERS: dict[str, str] = {
    '__CMS_PBJ_STAFFING_SUBMISSION__': CMS_PBJ_STAFFING_SUBMISSION_URL,
    '__CMS_PBJ_PUF_DOCUMENTATION__': CMS_PBJ_PUF_DOCUMENTATION_URL,
    '__CMS_PBJ_DAILY_DATASET__': CMS_PBJ_DAILY_DATASET_URL,
    '__CMS_PBJ_EMPLOYEE_DETAIL__': CMS_PBJ_EMPLOYEE_DETAIL_URL,
    '__CMS_PROVIDER_INFO_DATASET__': CMS_PROVIDER_INFO_DATASET_URL,
    '__CMS_OPEN_DATA__': CMS_OPEN_DATA_URL,
    '__MACPAC_STATE_STAFFING__': MACPAC_STATE_STAFFING_URL,
    '__CARE_COMPARE__': CARE_COMPARE_URL,
    '__FEC__': 'https://www.fec.gov/',
}


def inject_public_html_cms_urls(html: str) -> str:
    """Substitute CMS URL placeholders in static public HTML files."""
    for placeholder, url in PUBLIC_HTML_CMS_PLACEHOLDERS.items():
        html = html.replace(placeholder, url)
    return html


# Bing Webmaster Tools — single source for production <head> injection.
BING_WEBMASTER_VERIFICATION_META = (
    '<meta name="msvalidate.01" content="CC0F94D1A8752537CA398E018C7F316E" />'
)
_HEAD_OPEN_RE = re.compile(r'(<head(?:\s[^>]*)?>)', re.IGNORECASE)


def inject_public_site_verification_meta(html: str) -> str:
    """Insert Bing Webmaster Tools verification meta once per HTML document."""
    if 'msvalidate.01' in html:
        return html
    return _HEAD_OPEN_RE.sub(r'\1\n' + BING_WEBMASTER_VERIFICATION_META, html, count=1)


# NY staffing compliance report — public vs pre-publication preview (unlisted, noindex).
NY_STAFFING_REPORT_HTML = 'insights-ny-minimum-staffing.html'
NY_STAFFING_REPORT_PREVIEW_SLUG = 'ny-staffing-compliance-2025'
NY_STAFFING_REPORT_PUBLIC_PATH = '/insights/ny-minimum-staffing'
# Default token reduces casual discovery; override in production via NY_STAFFING_REPORT_PREVIEW_TOKEN.
NY_STAFFING_REPORT_PREVIEW_TOKEN_DEFAULT = 'p4v8nq'


def ny_staffing_report_preview_token() -> str:
    raw = (os.environ.get('NY_STAFFING_REPORT_PREVIEW_TOKEN') or NY_STAFFING_REPORT_PREVIEW_TOKEN_DEFAULT).strip()
    return raw.lower()


def ny_staffing_report_preview_path(*, include_token: bool = True) -> str:
    base = f'/preview/{NY_STAFFING_REPORT_PREVIEW_SLUG}'
    if include_token:
        tok = ny_staffing_report_preview_token()
        if tok:
            return f'{base}/{tok}'
    return base


def ny_staffing_report_preview_redirect_to_public() -> bool:
    return os.environ.get('NY_STAFFING_REPORT_PREVIEW_REDIRECT', '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    )


def is_ny_staffing_report_preview_path(path: str) -> bool:
    p = (path or '').split('?', 1)[0].rstrip('/') or '/'
    prefix = f'/preview/{NY_STAFFING_REPORT_PREVIEW_SLUG}'
    return p == prefix or p.startswith(prefix + '/')


_NY_PREVIEW_ROBOTS_META = '<meta name="robots" content="noindex, nofollow">'
_NY_PREVIEW_BANNER_STYLES = """
<style id="ny-staffing-preview-banner-styles">
body.pbj-insights-report-page:has(.ny-staffing-preview-chrome) {
  margin: 0;
  --ny-preview-banner-offset: calc(0.65rem * 2 + 0.9rem * 1.35 + 1px);
}
.ny-staffing-preview-chrome {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  position: sticky;
  top: 0;
  z-index: 10001;
  isolation: isolate;
  transform: translateZ(0);
  -webkit-transform: translateZ(0);
}
.ny-staffing-preview-banner {
  position: relative;
  top: auto;
  flex: 0 0 auto;
  width: 100%;
  margin: 0;
  padding: 0.65rem 1rem;
  border-bottom: none;
  background: #eef2ff;
  color: #312e81;
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 0.9rem;
  line-height: 1.35;
  text-align: center;
  box-shadow: 0 1px 0 #c7d2fe;
  box-sizing: border-box;
}
body.pbj-insights-report-page:has(.ny-staffing-preview-chrome) .ny-staffing-preview-chrome .navbar {
  position: relative !important;
  top: auto !important;
  flex: 0 0 auto;
  margin: 0 !important;
  z-index: 0;
  border-top: none !important;
}
@media (prefers-color-scheme: dark) {
  .ny-staffing-preview-banner {
    border-bottom-color: rgba(129, 140, 248, 0.45);
    background: #1e1b4b;
    color: #e0e7ff;
  }
}
@media (max-width: 640px) {
  .ny-staffing-preview-banner {
    font-size: 0.85rem;
    padding: 0.55rem 0.65rem;
    line-height: 1.3;
  }
}
</style>
<script>
(function () {
  function syncPreviewChromeHeight() {
    var el = document.querySelector('.ny-staffing-preview-chrome');
    if (!el) return;
    document.documentElement.style.setProperty('--ny-preview-banner-offset', el.offsetHeight + 'px');
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncPreviewChromeHeight);
  } else {
    syncPreviewChromeHeight();
  }
  window.addEventListener('resize', syncPreviewChromeHeight, { passive: true });
  window.addEventListener('scroll', function () {
    requestAnimationFrame(syncPreviewChromeHeight);
  }, { passive: true });
})();
</script>
"""
_NY_PREVIEW_CHROME_OPEN = '<div class="ny-staffing-preview-chrome">'
_REPORT_SITE_HEADER_OPEN_RE = re.compile(r'(<div class="report-site-header">)', re.IGNORECASE)
_REPORT_SITE_HEADER_BEFORE_HERO_RE = re.compile(
    r'(</div>\s*)(?=<header class="hero")',
    re.IGNORECASE,
)
_NAVBAR_OPEN_RE = re.compile(r'(<nav\s+class=["\']navbar["\'])', re.IGNORECASE)
_NAVBAR_CLOSE_RE = re.compile(r'(</nav>)', re.IGNORECASE)
_NY_PREVIEW_BANNER_TEXT = (
    'Preview report. May be updated before publication.'
)
_NY_PREVIEW_BANNER_HTML = (
    f'<div class="ny-staffing-preview-banner" role="status">{_NY_PREVIEW_BANNER_TEXT}</div>'
)
NY_PREVIEW_DEFINITIONS_HEADING = (
    'Nearly half of NY facility-days fell below 3.50 direct care HPRD'
)
_DEFINITIONS_HEADING_RE = re.compile(
    r'<h2 id="definitions-heading">.*?</h2>',
    re.DOTALL,
)
_VIEWPORT_META_RE = re.compile(
    r'(<meta\s+name=["\']viewport["\'][^>]*>)',
    re.IGNORECASE,
)
_BODY_OPEN_RE = re.compile(r'(<body(?:\s[^>]*)?>)', re.IGNORECASE)


def inject_ny_staffing_report_preview(html: str, preview_path: str) -> str:
    """Mark NY report HTML as an unlisted preview (noindex banner, preview canonical/og:url)."""
    if _NY_PREVIEW_ROBOTS_META not in html:
        if _VIEWPORT_META_RE.search(html):
            html = _VIEWPORT_META_RE.sub(r'\1\n' + _NY_PREVIEW_ROBOTS_META, html, count=1)
        else:
            html = _HEAD_OPEN_RE.sub(r'\1\n' + _NY_PREVIEW_ROBOTS_META, html, count=1)
    if 'ny-staffing-preview-banner-styles' not in html:
        html = html.replace('</head>', _NY_PREVIEW_BANNER_STYLES + '</head>', 1)
    if 'class="ny-staffing-preview-banner"' not in html:
        if _REPORT_SITE_HEADER_OPEN_RE.search(html):
            html = _REPORT_SITE_HEADER_OPEN_RE.sub(
                _NY_PREVIEW_CHROME_OPEN + _NY_PREVIEW_BANNER_HTML + r'\1',
                html,
                count=1,
            )
            if 'ny-staffing-preview-chrome' in html:
                html = _REPORT_SITE_HEADER_BEFORE_HERO_RE.sub(r'\1</div>', html, count=1)
        elif _NAVBAR_OPEN_RE.search(html):
            html = _NAVBAR_OPEN_RE.sub(
                _NY_PREVIEW_CHROME_OPEN + _NY_PREVIEW_BANNER_HTML + r'\1',
                html,
                count=1,
            )
            if 'ny-staffing-preview-chrome' in html:
                html = _NAVBAR_CLOSE_RE.sub(r'\1</div>', html, count=1)
        else:
            html = _BODY_OPEN_RE.sub(
                r'\1\n' + _NY_PREVIEW_CHROME_OPEN + _NY_PREVIEW_BANNER_HTML,
                html,
                count=1,
            )
    origin = PUBLIC_SITE_ORIGIN.rstrip('/')
    path = (preview_path or ny_staffing_report_preview_path()).rstrip('/') or ny_staffing_report_preview_path()
    canonical = f'{origin}{path}'
    for old in (
        'https://www.pbj320.com/insights/ny-minimum-staffing',
        'https://www.pbj320.com/insights/ny-minimum-staffing/',
    ):
        html = html.replace(old, canonical)
    html = _DEFINITIONS_HEADING_RE.sub(
        f'<h2 id="definitions-heading">{NY_PREVIEW_DEFINITIONS_HEADING}</h2>',
        html,
        count=1,
    )
    return html


# Path fragments that must never appear in sitemap.xml <loc> entries.
SITEMAP_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    '/preview/',
    '/api/',
    '.json',
    '/premium/',
    '/dashboard/',
    '/pbjpedia/',
    '/login',
    '/logout',
    '/static/',
    '/owners/api/',
    '/owners/_dev/',
    '/owner/',
    '/admin',
    '/test/',
)


def pbjpedia_is_public() -> bool:
    """True when PBJpedia HTML routes should be served (default off until launch)."""
    return os.environ.get('PBJPEDIA_PUBLIC', '').strip().lower() in ('1', 'true', 'yes', 'on')


def sitemap_loc_is_allowed(loc: str, robots_disallow_prefixes: set[str] | None = None) -> bool:
    """True when a fully qualified sitemap URL is indexable public HTML."""
    loc_l = (loc or '').strip().lower()
    if not loc_l.startswith('https://www.pbj320.com'):
        return False
    for frag in SITEMAP_FORBIDDEN_FRAGMENTS:
        if frag in loc_l:
            return False
    if robots_disallow_prefixes:
        path = loc_l.split('www.pbj320.com', 1)[-1] or '/'
        for prefix in robots_disallow_prefixes:
            p = (prefix or '').rstrip('/') or '/'
            if p == '/' and path != '/':
                continue
            if path == p or path.startswith(p + '/'):
                return False
    return True

PUBLIC_CONTACT_EMAIL = (os.environ.get('PBJ_PUBLIC_CONTACT_EMAIL') or 'eric@320insight.com').strip()

# Bump when pbj-site-universal.js changes (footer, Premium nav, shell styles).
PBJ_SITE_UNIVERSAL_JS_VERSION = '49'

OPERATOR_LEGAL_NAME = '320 Consulting LLC'

FOOTER_TRUST_BLURB = (
    f'PBJ320 is a nursing home data platform from {OPERATOR_LEGAL_NAME}, built from CMS Payroll-Based Journal '
    'and other public federal and state datasets.'
)

# Sitemap policy: only list URLs allowed by ROBOTS_TXT and not served with noindex.
# Include /provider/, /entity/, and public /owners/<10-digit PAC> (CT/NY CMS profiles).
# Omit /owner/ (FEC search tool), /owners/api/, and /premium/.

# Paths that must never appear in sitemap.xml (legacy, gated, or unfinished pages).
SITEMAP_EXCLUDED_PATHS: frozenset[str] = frozenset({
    '/owner',
    '/owner/',
    '/attorneys',
    '/pbj-ai-support',
    '/pbjpedia',
    '/pbjpedia/',
    '/pbjpedia/overview',
    '/pbjpedia/metrics',
    '/pbjpedia/methodology',
    '/pbjpedia/state-standards',
    '/pbjpedia/non-nursing-staff',
    '/pbjpedia/data-limitations',
    '/pbjpedia/history',
})

# Static trust pages included in sitemap (path, priority, changefreq).
SITEMAP_TRUST_PAGES: tuple[tuple[str, str, str], ...] = (
    ('/about', '0.8', 'monthly'),
    ('/contact', '0.7', 'monthly'),
    ('/corrections', '0.6', 'monthly'),
    ('/data-sources', '0.7', 'monthly'),
)

def build_llms_txt(origin: str | None = None) -> str:
    """Plain-text site guide for AI/search tools (llms.txt convention). Not a data API."""
    base = (origin or PUBLIC_SITE_ORIGIN).rstrip('/')
    return f"""# PBJ320

> Public nursing home staffing and facility context from CMS Payroll-Based Journal (PBJ) and related federal datasets. Operated by {OPERATOR_LEGAL_NAME}. Not affiliated with CMS.

## What this site is

- Free lookup for ~15,000 U.S. nursing homes: quarterly PBJ staffing (HPRD), state rankings, chain/entity summaries, and ownership links where available.
- Facility pages summarize CMS-reported data for one CCN (Certification Number). Charts and badges on the page match the same underlying quarterly files used in structured metadata.

## How to cite

- Prefer the canonical facility URL: {base}/provider/{{ccn}} (6-digit CCN, zero-padded).
- Example: {base}/provider/335513
- Name the source: PBJ320 ({base}) and the underlying CMS datasets listed on {base}/data-sources.
- State context: {base}/state/{{state-slug}} (e.g. {base}/state/ct).
- Nursing home chain / affiliated entity: {base}/entity/{{entity-id}}.

## Data cadence (important)

- **PBJ staffing** (hours, HPRD, census, contract share on facility pages): aligned to CMS PBJ quarters; the latest loaded quarter is shown on each page and in JSON-LD where present.
- **Provider Information** (Five-Star ratings, turnover, ownership type, case-mix): may reflect a **newer** CMS snapshot than the PBJ quarter on the same page. Do not assume all fields share one posting date.
- Case-mix on historic PBJ quarters may be omitted by design; see {base}/data-sources.

## Machine-readable hints on facility pages

- Each public facility page includes JSON-LD (`MedicalOrganization`) with CMS CCN, city/county/state when available, up to the **last four PBJ quarters** of staffing (census, total nurse HPRD, RN HPRD, nurse aide HPRD, contract % where reported), then optional **PBJ320 facility flags**, **Latest CMS ratings** (Five-Star only), and associated entity links only when the provider page already shows that chain link.
- This is supplementary to visible page content, not a substitute for reading the page or CMS primary sources.

## Paths not intended for broad crawling

- /premium/ — paid dashboards and demos (not public data dumps).
- /owners/ — limited ownership research tool.
- /api/ — internal JSON for the site UI.
- /pbjpedia/ — reference wiki (draft; not public until launched).

## Contact and methodology

- Data sources and methodology: {base}/data-sources
- About: {base}/about
- Contact: {base}/contact
- Press: {base}/press

## Operator

{OPERATOR_LEGAL_NAME} — https://www.320insight.com/
"""


LLMS_TXT = build_llms_txt()

# Canonical robots.txt body — www sitemap only; never disallow /provider/ or /entity/.
ROBOTS_TXT_CANONICAL = """User-agent: *
Allow: /
Allow: /owners/
Disallow: /owner/
Disallow: /owners/api/
Disallow: /owners/_dev/
Disallow: /owners-test/
Disallow: /api/
Disallow: /test/
Disallow: /premium/
Disallow: /dashboard/
Disallow: /login
Disallow: /logout
Disallow: /report_builder
Disallow: /admin
Disallow: /static/data/raw
Disallow: /pbjpedia/
Disallow: /preview/
Disallow: /search_index.json
Disallow: /quarters_list.json
Disallow: /chow_index.json

Sitemap: https://www.pbj320.com/sitemap.xml
"""


def build_robots_txt() -> str:
    """Return production robots.txt (fixed www sitemap; no bot-specific provider blocks)."""
    return ROBOTS_TXT_CANONICAL


ROBOTS_TXT = build_robots_txt()

SECURITY_HEADER_VALUES = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
}

HEALTH_CHECK_SECURITY_HEADERS = tuple(SECURITY_HEADER_VALUES.keys())
