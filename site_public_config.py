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
PBJ_SITE_UNIVERSAL_JS_VERSION = '21'

OPERATOR_LEGAL_NAME = '320 Consulting LLC'

FOOTER_TRUST_BLURB = (
    f'PBJ320 is a nursing home data platform from {OPERATOR_LEGAL_NAME}, built from CMS Payroll-Based Journal '
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
