"""Discover current CMS PBJ policy-manual PDF URL from the staffing-data-submission hub."""
from __future__ import annotations

import re
import urllib.request

CMS_PBJ_HUB_URL = 'https://www.cms.gov/medicare/quality/nursing-home-improvement/staffing-data-submission'
CMS_ORIGIN = 'https://www.cms.gov'
USER_AGENT = 'Mozilla/5.0 (compatible; PBJ320-cms-sync/1.0; +https://www.pbj320.com)'

_POLICY_MANUAL_RE = re.compile(
    r'href="(/medicare/[^"]*pbj-policy-manual-final[^"]*\.pdf)"',
    re.I,
)


def _abs_cms_url(path: str) -> str:
    path = path.strip()
    if path.startswith('http'):
        return path
    return CMS_ORIGIN.rstrip('/') + ('/' + path.lstrip('/'))


def fetch_policy_manual_pdf_url(*, hub_url: str = CMS_PBJ_HUB_URL, timeout: float = 30.0) -> str | None:
    """Return the policy-manual PDF href CMS lists on the PBJ hub (prefers final-v over FAQ)."""
    req = urllib.request.Request(hub_url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    matches = [_abs_cms_url(m) for m in _POLICY_MANUAL_RE.findall(html)]
    if not matches:
        return None
    finals = [u for u in matches if 'policy-manual-final' in u.lower() and 'faq' not in u.lower()]
    return (finals or matches)[0]
