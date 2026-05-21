#!/usr/bin/env python3
"""Audit PBJ320 indexability: sitemap, canonical host, provider HTML, redirects, API noindex."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

from site_public_config import SITEMAP_FORBIDDEN_FRAGMENTS, sitemap_loc_is_allowed

DEFAULT_BASE = 'https://www.pbj320.com'

PROVIDER_SAMPLE = [
    '676489',
    '475029',
    '395660',
    '395616',
    '335256',
    '365343',
]

REDIRECT_SAMPLE = [
    ('https://pbj320.com/provider/365343', 'https://www.pbj320.com/provider/365343'),
    ('http://pbj320.com/', 'https://www.pbj320.com/'),
    ('http://www.pbj320.com/', 'https://www.pbj320.com/'),
]

API_JSON_SAMPLE = [
    '/search_index.json',
    '/quarters_list.json',
    '/api/entity-summary/237',
]

SITEMAP_FORBIDDEN = SITEMAP_FORBIDDEN_FRAGMENTS


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = build_opener(_NoRedirect())


@dataclass
class Issue:
    url: str
    reason: str


@dataclass
class AuditReport:
    base: str
    failures: list[Issue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sitemap_total: int = 0
    sitemap_bad_host: int = 0
    sitemap_forbidden: int = 0
    sitemap_checked: int = 0
    sitemap_ok_200_html: int = 0
    sitemap_redirect_or_error: int = 0

    def fail(self, url: str, reason: str) -> None:
        self.failures.append(Issue(url, reason))

    def ok(self, msg: str) -> None:
        self.notes.append(msg)


def _fetch(url: str, timeout: float, follow: bool = True, max_bytes: int = 0) -> tuple[int, str, dict[str, str], bytes]:
    opener = build_opener() if follow else _NO_REDIRECT
    req = Request(url, headers={'User-Agent': 'PBJ320-audit-indexability/1.0'})
    with opener.open(req, timeout=timeout) as resp:
        if max_bytes and max_bytes > 0:
            body = resp.read(max_bytes)
        else:
            body = resp.read()
        headers = {k: v for k, v in resp.headers.items()}
        return resp.status, resp.geturl(), headers, body


def _fetch_no_redirect(url: str, timeout: float) -> tuple[int, str, dict[str, str], bytes]:
    return _fetch(url, timeout, follow=False)


def audit_sitemap(report: AuditReport, timeout: float, sample_limit: int) -> None:
    sitemap_url = f'{report.base}/sitemap.xml'
    try:
        status, final, headers, body = _fetch(sitemap_url, timeout, follow=True, max_bytes=0)
    except (HTTPError, URLError) as e:
        report.fail(sitemap_url, f'fetch failed: {e}')
        return
    if status != 200:
        report.fail(sitemap_url, f'HTTP {status}')
        return
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        report.fail(sitemap_url, f'invalid XML: {e}')
        return
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locs = [el.text.strip() for el in root.findall('.//sm:loc', ns) if el.text]
    report.sitemap_total = len(locs)
    for loc in locs:
        if not loc.startswith('https://www.pbj320.com'):
            report.sitemap_bad_host += 1
            report.fail(loc, 'sitemap loc must start with https://www.pbj320.com')
        for frag in SITEMAP_FORBIDDEN:
            if frag in loc.lower():
                report.sitemap_forbidden += 1
                report.fail(loc, f'sitemap loc contains forbidden fragment {frag!r}')
        if not sitemap_loc_is_allowed(loc):
            report.fail(loc, 'failed sitemap_loc_is_allowed policy check')

    to_check = locs if sample_limit <= 0 or sample_limit >= len(locs) else locs[:: max(1, len(locs) // sample_limit)][:sample_limit]
    for loc in to_check:
        report.sitemap_checked += 1
        try:
            st, fin, hdrs, _ = _fetch_no_redirect(loc, timeout)
        except HTTPError as e:
            st = e.code
            fin = e.geturl() if hasattr(e, 'geturl') else loc
            hdrs = dict(e.headers.items()) if e.headers else {}
        except URLError as e:
            report.sitemap_redirect_or_error += 1
            report.fail(loc, f'fetch error: {e}')
            continue
        if st in (301, 302, 303, 307, 308):
            report.sitemap_redirect_or_error += 1
            report.fail(loc, f'redirect HTTP {st} -> {hdrs.get("Location", fin)}')
            continue
        if st != 200:
            report.sitemap_redirect_or_error += 1
            report.fail(loc, f'HTTP {st}')
            continue
        ct = (hdrs.get('Content-Type') or '').split(';')[0].strip().lower()
        if 'html' not in ct:
            report.sitemap_redirect_or_error += 1
            report.fail(loc, f'expected text/html, got {ct or "unknown"}')
            continue
        report.sitemap_ok_200_html += 1

    report.ok(
        f'sitemap: {report.sitemap_total} URLs; checked {report.sitemap_checked} '
        f'({report.sitemap_ok_200_html} OK HTML 200)'
    )


def _html_has_noindex(body: bytes, headers: dict[str, str]) -> bool:
    xrt = (headers.get('X-Robots-Tag') or headers.get('x-robots-tag') or '').lower()
    if 'noindex' in xrt:
        return True
    text = body.decode('utf-8', errors='replace').lower()
    return bool(re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', text))


def audit_provider_pages(report: AuditReport, timeout: float) -> None:
    for ccn in PROVIDER_SAMPLE:
        url = f'{report.base}/provider/{ccn}'
        try:
            st, fin, hdrs, body = _fetch_no_redirect(url, timeout)
        except (HTTPError, URLError) as e:
            report.fail(url, f'fetch failed: {e}')
            continue
        if st in (301, 302, 303, 307, 308):
            report.fail(url, f'unexpected redirect {st}')
            continue
        if st != 200:
            report.fail(url, f'HTTP {st}')
            continue
        if _html_has_noindex(body, hdrs):
            report.fail(url, 'has noindex (meta or X-Robots-Tag)')
        text = body.decode('utf-8', errors='replace')
        canon_m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', text, re.I)
        if not canon_m:
            report.fail(url, 'missing canonical link')
        elif canon_m.group(1).strip() != url:
            report.fail(url, f'canonical mismatch: {canon_m.group(1)}')
        title_m = re.search(r'<title[^>]*>([^<]+)</title>', text, re.I)
        if not title_m or not title_m.group(1).strip():
            report.fail(url, 'missing <title>')
        if not re.search(r'<h1[^>]*>', text, re.I):
            report.fail(url, 'missing <h1>')
        if ccn not in text and not re.search(r'staffing', text, re.I):
            report.fail(url, 'missing facility-specific text')
        if not re.search(r'hprd|staffing', text, re.I):
            report.fail(url, 'missing HPRD/staffing metrics in HTML')
        if 'pbj-provider-seo' not in text and 'Latest staffing snapshot' not in text:
            report.fail(url, 'missing server-rendered provider SEO block (deploy pending?)')
    report.ok(f'provider sample: {len(PROVIDER_SAMPLE)} URLs checked')


def audit_redirects(report: AuditReport, timeout: float) -> None:
    for start, expected_final in REDIRECT_SAMPLE:
        chain = [start]
        current = start
        try:
            for _ in range(8):
                try:
                    st, fin, hdrs, _ = _fetch_no_redirect(current, timeout)
                except HTTPError as e:
                    if e.code in (301, 302, 303, 307, 308):
                        st = e.code
                        hdrs = {k: v for k, v in (e.headers.items() if e.headers else [])}
                        fin = e.geturl() if hasattr(e, 'geturl') else current
                    else:
                        raise
                if st in (301, 302, 303, 307, 308):
                    loc = hdrs.get('Location') or hdrs.get('location')
                    if not loc:
                        report.fail(start, f'redirect {st} without Location')
                        break
                    current = urljoin(current, loc)
                    chain.append(current)
                    continue
                exp = expected_final.rstrip('/')
                got = (fin or current).rstrip('/')
                if got != exp:
                    report.fail(start, f'expected final {expected_final}, got {fin} (chain: {" -> ".join(chain)})')
                break
            else:
                report.fail(start, 'too many redirects')
        except (HTTPError, URLError) as e:
            report.fail(start, str(e))
    report.ok(f'redirect sample: {len(REDIRECT_SAMPLE)} URLs')


def audit_api_json(report: AuditReport, timeout: float, sitemap_locs: set[str]) -> None:
    for path in API_JSON_SAMPLE:
        url = f'{report.base}{path}'
        if url in sitemap_locs:
            report.fail(url, 'must not appear in sitemap')
        try:
            st, fin, hdrs, _ = _fetch(url, timeout, follow=True)
        except (HTTPError, URLError) as e:
            report.fail(url, f'fetch failed: {e}')
            continue
        xrt = (hdrs.get('X-Robots-Tag') or hdrs.get('x-robots-tag') or '').lower()
        if 'noindex' not in xrt:
            report.fail(url, f'missing X-Robots-Tag noindex (got {xrt or "none"})')
    report.ok(f'API/JSON sample: {len(API_JSON_SAMPLE)} endpoints')


def audit_robots_sitemap_line(report: AuditReport, timeout: float) -> None:
    url = f'{report.base}/robots.txt'
    try:
        _, _, _, body = _fetch(url, timeout)
    except (HTTPError, URLError) as e:
        report.fail(url, str(e))
        return
    text = body.decode('utf-8', errors='replace')
    if f'Sitemap: {report.base}/sitemap.xml' not in text:
        report.fail(url, f'robots.txt must include Sitemap: {report.base}/sitemap.xml')
    else:
        report.ok('robots.txt sitemap line OK')


def print_report(report: AuditReport) -> int:
    print('\n=== PBJ320 indexability audit ===')
    print(f'Base: {report.base}')
    print(f'Sitemap URLs: {report.sitemap_total}')
    print(f'  non-www locs: {report.sitemap_bad_host}')
    print(f'  forbidden fragments: {report.sitemap_forbidden}')
    print(f'  sampled checks: {report.sitemap_checked} ({report.sitemap_ok_200_html} OK HTML 200, {report.sitemap_redirect_or_error} bad)')
    for note in report.notes:
        print(f'  [ok] {note}')
    if report.failures:
        print(f'\nFailures ({len(report.failures)}):')
        for issue in report.failures:
            print(f'  - {issue.url}\n    {issue.reason}')
        return 1
    print('\nAll checks passed.')
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', default=DEFAULT_BASE, help='Canonical site origin (default www)')
    p.add_argument('--timeout', type=float, default=25.0)
    p.add_argument('--sitemap-sample', type=int, default=40, help='Max sitemap URLs to HTTP-check (0=all)')
    args = p.parse_args(argv)
    base = args.base_url.rstrip('/')
    report = AuditReport(base=base)

    sitemap_locs: set[str] = set()
    try:
        _, _, _, body = _fetch(f'{base}/sitemap.xml', args.timeout)
        root = ET.fromstring(body)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        sitemap_locs = {el.text.strip() for el in root.findall('.//sm:loc', ns) if el.text}
    except Exception:
        pass

    audit_robots_sitemap_line(report, args.timeout)
    audit_sitemap(report, args.timeout, args.sitemap_sample)
    audit_provider_pages(report, args.timeout)
    audit_redirects(report, args.timeout)
    audit_api_json(report, args.timeout, sitemap_locs)
    return print_report(report)


if __name__ == '__main__':
    raise SystemExit(main())
