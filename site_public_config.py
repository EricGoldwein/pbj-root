"""Public-site constants for trust pages, robots.txt, sitemaps, and security headers."""

from __future__ import annotations

import os

# Canonical public origin (apex). Override in staging via PBJ_PUBLIC_BASE_URL.
PUBLIC_SITE_ORIGIN = (
    (os.environ.get('PBJ_PUBLIC_BASE_URL') or os.environ.get('PUBLIC_BASE_URL') or 'https://pbj320.com')
    .strip()
    .rstrip('/')
)

PUBLIC_CONTACT_EMAIL = (os.environ.get('PBJ_PUBLIC_CONTACT_EMAIL') or 'eric@320insight.com').strip()

# Bump when pbj-site-universal.js changes (footer, Premium nav, shell styles).
PBJ_SITE_UNIVERSAL_JS_VERSION = '26'

OPERATOR_LEGAL_NAME = '320 Consulting LLC'

FOOTER_TRUST_BLURB = (
    f'PBJ320 is a nursing-home data platform from {OPERATOR_LEGAL_NAME}, built from CMS Payroll-Based Journal '
    'and other public federal and state datasets.'
)

# Sitemap policy: only list URLs allowed by ROBOTS_TXT and not served with noindex.
# Include /provider/ and /entity/ (CMS-linked records). Omit /owners/ (disallowed).
# Omit /premium/ and other private/dashboard paths. When multi-state owner profiles launch,
# a dedicated public route (e.g. /operator/<slug>) may be preferable to unblocking /owners/.

# Static trust pages included in sitemap (path, priority, changefreq).
SITEMAP_TRUST_PAGES: tuple[tuple[str, str, str], ...] = (
    ('/about', '0.8', 'monthly'),
    ('/contact', '0.7', 'monthly'),
    ('/data-sources', '0.7', 'monthly'),
)

def build_llms_txt(origin: str | None = None) -> str:
    """Plain-text site guide for AI/search tools (llms.txt convention). Not a data API."""
    base = (origin or PUBLIC_SITE_ORIGIN).rstrip('/')
    return f"""# PBJ320

> Public nursing home staffing and facility context from CMS Payroll-Based Journal (PBJ) and related federal datasets. Operated by {OPERATOR_LEGAL_NAME}. Not affiliated with CMS.

## What this site is

- Free lookup for ~15,000 U.S. nursing homes: quarterly PBJ staffing (HPRD), state rankings, chain/entity summaries, and limited ownership context.
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

- Each public facility page includes JSON-LD (`MedicalOrganization`) with CMS CCN, city/county/state when available, up to the **last four PBJ quarters** of staffing (census, total nurse HPRD, RN HPRD, CNA HPRD, contract % where reported), optional **PBJ320 facility flags** when shown on the page, separate **Latest CMS Provider Information** (Five-Star ratings only), and associated entity links when present.
- This is supplementary to visible page content, not a substitute for reading the page or CMS primary sources.

## Paths not intended for broad crawling

- /premium/ — paid dashboards and demos (not public data dumps).
- /owners/ — limited ownership research tool.
- /api/ — internal JSON for the site UI.

## Contact and methodology

- Data sources and limitations: {base}/data-sources
- About: {base}/about
- Contact: {base}/contact
- Press: {base}/press

## Operator

{OPERATOR_LEGAL_NAME} — https://www.320insight.com/
"""


LLMS_TXT = build_llms_txt()

ROBOTS_TXT = f"""User-agent: *
Allow: /
Disallow: /owners/
Disallow: /owner/
Disallow: /api/
Disallow: /test/
Disallow: /premium/
Disallow: /report_builder
Disallow: /admin
Disallow: /static/data/raw

User-agent: Claude-SearchBot
User-agent: SleepBot
Disallow: /provider/
Disallow: /entity/

Sitemap: {PUBLIC_SITE_ORIGIN}/sitemap.xml
"""

SECURITY_HEADER_VALUES = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
}

HEALTH_CHECK_SECURITY_HEADERS = tuple(SECURITY_HEADER_VALUES.keys())
