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

OPERATOR_LEGAL_NAME = '320 Consulting LLC'

FOOTER_TRUST_BLURB = (
    f'PBJ320 is a nursing-home staffing data platform operated by {OPERATOR_LEGAL_NAME}. '
    'Data sources include CMS Payroll-Based Journal staffing data and CMS Provider Information. '
    f'Contact: <a href="mailto:{PUBLIC_CONTACT_EMAIL}">{PUBLIC_CONTACT_EMAIL}</a>.'
)

# Static trust pages included in sitemap (path, priority, changefreq).
SITEMAP_TRUST_PAGES: tuple[tuple[str, str, str], ...] = (
    ('/about', '0.8', 'monthly'),
    ('/contact', '0.7', 'monthly'),
    ('/data-sources', '0.8', 'monthly'),
    ('/privacy', '0.5', 'yearly'),
    ('/terms', '0.5', 'yearly'),
)

ROBOTS_TXT = f"""User-agent: *
Allow: /
Disallow: /owners/
Disallow: /owner/
Disallow: /api/
Disallow: /test/

Sitemap: {PUBLIC_SITE_ORIGIN}/sitemap.xml
"""

SECURITY_HEADER_VALUES = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
}

HEALTH_CHECK_SECURITY_HEADERS = tuple(SECURITY_HEADER_VALUES.keys())
