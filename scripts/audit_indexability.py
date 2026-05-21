#!/usr/bin/env python3
"""Audit PBJ320 indexability: sitemap, canonical host, provider HTML, redirects, API noindex."""

from __future__ import annotations

import argparse
import re
import socket
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from site_public_config import (
    ROBOTS_TXT,
    SITEMAP_FORBIDDEN_FRAGMENTS,
    pbjpedia_is_public,
    sitemap_loc_is_allowed,
)
from utils.seo_utils import find_forbidden_dashboard_body_markers

DEFAULT_BASE = 'https://www.pbj320.com'
DEFAULT_TIMEOUT = 10.0
DEFAULT_SITEMAP_SAMPLE = 10
SITEMAP_XML_MAX_BYTES = 8_000_000
HTML_PROBE_MAX_BYTES = 256_000
JSON_PROBE_MAX_BYTES = 32_768

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

ENTITY_SAMPLE = ['237', '1', '100']

# PBJpedia must stay 404 + out of sitemap until PBJPEDIA_PUBLIC=1 (see docs/PBJPEDIA_LAUNCH.md).
PBJPEDIA_PROBE_PATHS = (
    '/pbjpedia/',
    '/pbjpedia/overview',
    '/pbjpedia/metrics',
    '/pbjpedia/state-standards',
    '/pbjpedia/history',
)

FETCH_USER_AGENT = (
    'Mozilla/5.0 (compatible; PBJ320IndexabilityAudit/1.0; +https://www.pbj320.com)'
)

SITEMAP_FORBIDDEN = SITEMAP_FORBIDDEN_FRAGMENTS


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = build_opener(_NoRedirect())
_VERBOSE = False


def _progress(label: str) -> None:
    print(label, flush=True)


def _verbose(msg: str) -> None:
    if _VERBOSE:
        print(msg, flush=True)


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


def _is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    if isinstance(exc, URLError) and isinstance(getattr(exc, 'reason', None), (TimeoutError, socket.timeout)):
        return True
    msg = str(exc).lower()
    return 'timed out' in msg or 'timeout' in msg


def _fetch(
    url: str,
    timeout: float,
    *,
    follow: bool = True,
    max_bytes: int = HTML_PROBE_MAX_BYTES,
) -> tuple[int, str, dict[str, str], bytes]:
    opener = build_opener() if follow else _NO_REDIRECT
    req = Request(url, headers={'User-Agent': FETCH_USER_AGENT})
    with opener.open(req, timeout=timeout) as resp:
        if max_bytes > 0:
            body = resp.read(max_bytes + 1)
            if len(body) > max_bytes:
                body = body[:max_bytes]
        else:
            body = resp.read()
        headers = {k: v for k, v in resp.headers.items()}
        return resp.status, resp.geturl(), headers, body


def _fetch_safe(
    url: str,
    timeout: float,
    *,
    follow: bool = True,
    max_bytes: int = HTML_PROBE_MAX_BYTES,
) -> tuple[Optional[int], str, dict[str, str], bytes, Optional[str]]:
    """Fetch URL; return error string instead of raising on timeout/network failure."""
    try:
        status, final, headers, body = _fetch(
            url, timeout, follow=follow, max_bytes=max_bytes
        )
        return status, final, headers, body, None
    except HTTPError as e:
        hdrs = {k: v for k, v in (e.headers.items() if e.headers else [])}
        return e.code, e.geturl() if hasattr(e, 'geturl') else url, hdrs, b'', None
    except (URLError, TimeoutError, socket.timeout) as e:
        if _is_timeout_error(e):
            return None, url, {}, b'', f'timeout after {timeout:g}s'
        return None, url, {}, b'', str(e.reason if isinstance(e, URLError) and e.reason else e)


def _fetch_no_redirect(
    url: str, timeout: float, *, max_bytes: int = HTML_PROBE_MAX_BYTES
) -> tuple[Optional[int], str, dict[str, str], bytes, Optional[str]]:
    return _fetch_safe(url, timeout, follow=False, max_bytes=max_bytes)


def audit_sitemap(report: AuditReport, timeout: float, sample_limit: int) -> list[str]:
    sitemap_url = f'{report.base}/sitemap.xml'
    _progress(f'Fetching sitemap: {sitemap_url} (timeout {timeout:g}s)')
    status, _, _, body, err = _fetch_safe(
        sitemap_url, timeout, follow=True, max_bytes=SITEMAP_XML_MAX_BYTES
    )
    if err:
        report.fail(sitemap_url, f'fetch failed: {err}')
        return []
    if status != 200:
        report.fail(sitemap_url, f'HTTP {status}')
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        report.fail(sitemap_url, f'invalid XML: {e}')
        return []
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locs = [el.text.strip() for el in root.findall('.//sm:loc', ns) if el.text]
    report.sitemap_total = len(locs)
    _verbose(f'Parsed {len(locs)} sitemap URLs')

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

    if sample_limit <= 0 or sample_limit >= len(locs):
        to_check = locs
    else:
        step = max(1, len(locs) // sample_limit)
        to_check = locs[::step][:sample_limit]

    for i, loc in enumerate(to_check, start=1):
        _progress(f'  [{i}/{len(to_check)}] GET {loc}')
        report.sitemap_checked += 1
        st, fin, hdrs, _, err = _fetch_no_redirect(loc, timeout)
        if err:
            report.sitemap_redirect_or_error += 1
            report.fail(loc, err)
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
        _verbose(f'    -> {st} {ct}')

    report.ok(
        f'sitemap: {report.sitemap_total} URLs; checked {report.sitemap_checked} '
        f'({report.sitemap_ok_200_html} OK HTML 200)'
    )
    return locs


def _html_has_noindex(body: bytes, headers: dict[str, str]) -> bool:
    xrt = (headers.get('X-Robots-Tag') or headers.get('x-robots-tag') or '').lower()
    if 'noindex' in xrt:
        return True
    text = body.decode('utf-8', errors='replace').lower()
    return bool(re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', text))


def audit_provider_pages(report: AuditReport, timeout: float) -> None:
    _progress(f'Provider sample ({len(PROVIDER_SAMPLE)} URLs)')
    for i, ccn in enumerate(PROVIDER_SAMPLE, start=1):
        url = f'{report.base}/provider/{ccn}'
        _progress(f'  [{i}/{len(PROVIDER_SAMPLE)}] GET {url}')
        st, _, hdrs, body, err = _fetch_no_redirect(url, timeout)
        if err:
            report.fail(url, err)
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
        markers = find_forbidden_dashboard_body_markers(text)
        if markers:
            report.fail(url, f'forbidden visible SEO boilerplate: {", ".join(markers)}')
    report.ok(f'provider sample: {len(PROVIDER_SAMPLE)} URLs checked')


def audit_redirects(report: AuditReport, timeout: float) -> None:
    _progress(f'Redirect sample ({len(REDIRECT_SAMPLE)} URLs)')
    for i, (start, expected_final) in enumerate(REDIRECT_SAMPLE, start=1):
        _progress(f'  [{i}/{len(REDIRECT_SAMPLE)}] GET {start}')
        chain = [start]
        current = start
        failed = False
        for hop in range(8):
            st, fin, hdrs, _, err = _fetch_no_redirect(current, timeout, max_bytes=4096)
            if err:
                report.fail(start, err)
                failed = True
                break
            if st in (301, 302, 303, 307, 308):
                loc = hdrs.get('Location') or hdrs.get('location')
                if not loc:
                    report.fail(start, f'redirect {st} without Location')
                    failed = True
                    break
                current = urljoin(current, loc)
                chain.append(current)
                _verbose(f'    -> {st} {loc}')
                continue
            exp = expected_final.rstrip('/')
            got = (fin or current).rstrip('/')
            if got != exp:
                report.fail(start, f'expected final {expected_final}, got {fin} (chain: {" -> ".join(chain)})')
            break
        else:
            if not failed:
                report.fail(start, 'too many redirects')
    report.ok(f'redirect sample: {len(REDIRECT_SAMPLE)} URLs')


def audit_api_json(report: AuditReport, timeout: float, sitemap_locs: set[str]) -> None:
    _progress(f'API/JSON sample ({len(API_JSON_SAMPLE)} URLs)')
    for i, path in enumerate(API_JSON_SAMPLE, start=1):
        url = f'{report.base}{path}'
        _progress(f'  [{i}/{len(API_JSON_SAMPLE)}] GET {url}')
        if url in sitemap_locs:
            report.fail(url, 'must not appear in sitemap')
        st, _, hdrs, _, err = _fetch_safe(url, timeout, follow=True, max_bytes=JSON_PROBE_MAX_BYTES)
        if err:
            report.fail(url, err)
            continue
        xrt = (hdrs.get('X-Robots-Tag') or hdrs.get('x-robots-tag') or '').lower()
        if 'noindex' not in xrt:
            report.fail(url, f'missing X-Robots-Tag noindex (got {xrt or "none"})')
    report.ok(f'API/JSON sample: {len(API_JSON_SAMPLE)} endpoints')


def _robots_disallow_prefixes_for_star(text: str) -> set[str]:
    prefixes: set[str] = set()
    in_star = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        low = line.lower()
        if low.startswith('user-agent:'):
            agent = line.split(':', 1)[1].strip()
            in_star = agent == '*'
            continue
        if in_star and low.startswith('disallow:'):
            path = line.split(':', 1)[1].strip()
            if path:
                prefixes.add(path.rstrip('/') or '/')
    return prefixes


def audit_pbjpedia_gated(report: AuditReport, timeout: float, sitemap_locs: set[str]) -> None:
    """PBJpedia is draft: 404 on routes, absent from sitemap, disallowed in robots."""
    if pbjpedia_is_public():
        report.fail('config', 'PBJPEDIA_PUBLIC is set — production audit expects PBJpedia gated off')
        return
    if 'Disallow: /pbjpedia/' not in ROBOTS_TXT:
        report.fail('robots.txt (repo)', 'ROBOTS_TXT missing Disallow: /pbjpedia/')
    for loc in sitemap_locs:
        if '/pbjpedia/' in loc.lower() or loc.rstrip('/').endswith('/pbjpedia'):
            report.fail(loc, 'PBJpedia URL must not appear in sitemap while gated')
    _progress(f'PBJpedia gated probe ({len(PBJPEDIA_PROBE_PATHS)} URLs, expect 404)')
    for i, path in enumerate(PBJPEDIA_PROBE_PATHS, start=1):
        url = f'{report.base}{path}'
        _progress(f'  [{i}/{len(PBJPEDIA_PROBE_PATHS)}] GET {url}')
        st, fin, _, _, err = _fetch_no_redirect(url, timeout)
        if err:
            report.fail(url, err)
            continue
        if st in (301, 302, 303, 307, 308):
            report.fail(url, f'expected 404 while gated, got redirect {st} -> {fin}')
            continue
        if st != 404:
            report.fail(url, f'expected HTTP 404 while gated, got {st}')
    pbj_failures = [i for i in report.failures if '/pbjpedia' in i.url or i.url in ('config', 'robots.txt (repo)')]
    if not pbj_failures:
        report.ok(
            f'pbjpedia gated: {len(PBJPEDIA_PROBE_PATHS)} URLs return 404; '
            'no /pbjpedia/ in sitemap; robots Disallow present'
        )


def audit_robots_txt(report: AuditReport, timeout: float, sitemap_locs: set[str]) -> None:
    url = f'{report.base}/robots.txt'
    _progress(f'GET {url}')
    status, _, hdrs, body, err = _fetch_safe(url, timeout, max_bytes=16_384)
    if err:
        report.fail(url, err)
        return
    if status == 403:
        report.fail(url, 'HTTP 403 — cannot verify robots.txt (Cloudflare/bot block)')
        return
    if status != 200:
        report.fail(url, f'HTTP {status}')
        return
    text = body.decode('utf-8', errors='replace')
    want_sitemap = f'Sitemap: {report.base}/sitemap.xml'
    if want_sitemap not in text:
        report.fail(url, f'missing line: {want_sitemap}')
    if 'Sitemap: https://pbj320.com/sitemap.xml' in text:
        report.fail(url, 'must not include apex Sitemap: https://pbj320.com/sitemap.xml')
    if re.search(r'^Disallow:\s*/provider/', text, re.MULTILINE | re.IGNORECASE):
        report.fail(url, 'must not Disallow: /provider/ (any user-agent block)')
    star_disallow = _robots_disallow_prefixes_for_star(text)
    blocked = 0
    for loc in sitemap_locs:
        path = loc.split('www.pbj320.com', 1)[-1] or '/'
        for prefix in star_disallow:
            p = prefix.rstrip('/') or '/'
            if p == '/' and path != '/':
                continue
            if path == p or path.startswith(p + '/'):
                report.fail(loc, f'blocked by robots.txt Disallow: {prefix} (User-agent: *)')
                blocked += 1
                break
    if blocked:
        _verbose(f'robots.txt blocks {blocked} sitemap paths (User-agent: *)')
    origin_hdr = (hdrs.get('X-PBJ-Robots-Source') or hdrs.get('x-pbj-robots-source') or '').strip()
    if origin_hdr and origin_hdr != 'flask-origin':
        report.fail(url, f'unexpected X-PBJ-Robots-Source: {origin_hdr}')
    if not any(i.url == url for i in report.failures):
        extra = ' (flask-origin)' if origin_hdr == 'flask-origin' else ''
        report.ok(f'robots.txt: www sitemap line, no /provider/ block, sitemap paths allowed{extra}')


def audit_entity_pages(report: AuditReport, timeout: float) -> None:
    _progress(f'Entity sample ({len(ENTITY_SAMPLE)} URLs)')
    for i, eid in enumerate(ENTITY_SAMPLE, start=1):
        url = f'{report.base}/entity/{eid}'
        _progress(f'  [{i}/{len(ENTITY_SAMPLE)}] GET {url}')
        st, _, hdrs, body, err = _fetch_no_redirect(url, timeout)
        if err:
            report.fail(url, err)
            continue
        if st in (301, 302, 303, 307, 308):
            report.fail(url, f'unexpected redirect {st}')
            continue
        if st == 404:
            _verbose(f'    -> 404 (skipped)')
            continue
        if st != 200:
            report.fail(url, f'HTTP {st}')
            continue
        if _html_has_noindex(body, hdrs):
            report.fail(url, 'has noindex')
        text = body.decode('utf-8', errors='replace')
        canon_m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', text, re.I)
        if not canon_m or canon_m.group(1).strip() != url:
            report.fail(url, f'canonical mismatch: {canon_m.group(1) if canon_m else "missing"}')
        if not re.search(r'<h1[^>]*>', text, re.I):
            report.fail(url, 'missing <h1>')
        if '/provider/' not in text and 'facility' not in text.lower():
            report.fail(url, 'missing facility links or entity roster content')
        markers = find_forbidden_dashboard_body_markers(text)
        if markers:
            report.fail(url, f'forbidden visible SEO boilerplate: {", ".join(markers)}')
    report.ok(f'entity sample: {len(ENTITY_SAMPLE)} URLs checked')


def print_report(report: AuditReport) -> int:
    print('\n=== PBJ320 indexability audit ===', flush=True)
    print(f'Base: {report.base}', flush=True)
    print(f'Sitemap URLs: {report.sitemap_total}', flush=True)
    print(f'  non-www locs: {report.sitemap_bad_host}', flush=True)
    print(f'  forbidden fragments: {report.sitemap_forbidden}', flush=True)
    print(
        f'  sampled checks: {report.sitemap_checked} '
        f'({report.sitemap_ok_200_html} OK HTML 200, {report.sitemap_redirect_or_error} bad)',
        flush=True,
    )
    for note in report.notes:
        print(f'  [ok] {note}', flush=True)
    if report.failures:
        print(f'\nFailures ({len(report.failures)}):', flush=True)
        for issue in report.failures:
            print(f'  - {issue.url}\n    {issue.reason}', flush=True)
        return 1
    print('\nAll checks passed.', flush=True)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    global _VERBOSE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', default=DEFAULT_BASE, help='Canonical site origin (default www)')
    p.add_argument(
        '--timeout',
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f'Per-request timeout in seconds (default {DEFAULT_TIMEOUT:g})',
    )
    p.add_argument(
        '--sitemap-sample',
        type=int,
        default=DEFAULT_SITEMAP_SAMPLE,
        help=f'Max sitemap URLs to HTTP-check (0=all, default {DEFAULT_SITEMAP_SAMPLE})',
    )
    p.add_argument('--verbose', action='store_true', help='Print extra per-request details')
    args = p.parse_args(argv)
    _VERBOSE = args.verbose
    base = args.base_url.rstrip('/')
    report = AuditReport(base=base)

    print(
        f'Starting audit (timeout={args.timeout:g}s, sitemap-sample={args.sitemap_sample})',
        flush=True,
    )
    sitemap_locs = audit_sitemap(report, args.timeout, args.sitemap_sample)
    sitemap_set = set(sitemap_locs)
    audit_pbjpedia_gated(report, args.timeout, sitemap_set)
    audit_robots_txt(report, args.timeout, sitemap_set)
    audit_provider_pages(report, args.timeout)
    audit_entity_pages(report, args.timeout)
    audit_redirects(report, args.timeout)
    audit_api_json(report, args.timeout, set(sitemap_locs))
    return print_report(report)


if __name__ == '__main__':
    raise SystemExit(main())
