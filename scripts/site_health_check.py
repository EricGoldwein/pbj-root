#!/usr/bin/env python3
"""HTTP health check for PBJ320 public URLs (status, redirects, headers, sitemap)."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_URLS = [
    'https://www.pbj320.com/',
    'https://www.pbj320.com/report',
    'https://www.pbj320.com/provider/075182',
    'https://www.pbj320.com/provider/335513',
    'https://www.pbj320.com/premium',
    'https://www.pbj320.com/robots.txt',
    'https://www.pbj320.com/sitemap.xml',
    'https://www.pbj320.com/about',
    'https://www.pbj320.com/contact',
    'https://www.pbj320.com/press',
]

SECURITY_HEADERS = (
    'Strict-Transport-Security',
    'X-Content-Type-Options',
    'Referrer-Policy',
    'Permissions-Policy',
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / 'reports' / 'site_health_latest.csv'


@dataclass
class CheckResult:
    url: str
    final_status: Optional[int] = None
    final_url: str = ''
    redirect_chain: str = ''
    response_time_ms: Optional[float] = None
    headers_present: str = ''
    headers_missing: str = ''
    notes: str = ''
    error: str = ''


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not follow redirects — caller records the chain explicitly."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())


def _fetch_no_redirect(url: str, timeout: float) -> tuple[int, str, dict[str, str], float]:
    req = Request(url, method='GET', headers={'User-Agent': 'PBJ320-site-health-check/1.0'})
    start = time.perf_counter()
    with _NO_REDIRECT_OPENER.open(req, timeout=timeout) as resp:
        elapsed_ms = (time.perf_counter() - start) * 1000
        headers = {k: v for k, v in resp.headers.items()}
        return resp.status, resp.geturl(), headers, elapsed_ms


def check_url(url: str, timeout: float, max_redirects: int = 12) -> CheckResult:
    result = CheckResult(url=url)
    chain: list[str] = []
    current = url

    try:
        from urllib.parse import urljoin

        for _ in range(max_redirects + 1):
            try:
                status, final_url, headers, elapsed_ms = _fetch_no_redirect(current, timeout)
            except HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    status = e.code
                    headers = {k: v for k, v in (e.headers.items() if e.headers else [])}
                    final_url = e.geturl() if hasattr(e, 'geturl') else current
                    elapsed_ms = 0.0
                else:
                    raise
            chain.append(f'{status} {current}')
            if status in (301, 302, 303, 307, 308):
                location = headers.get('Location') or headers.get('location')
                if not location:
                    result.final_status = status
                    result.final_url = final_url
                    result.response_time_ms = round(elapsed_ms, 1) if elapsed_ms else None
                    result.notes = 'redirect without Location header'
                    break
                current = urljoin(current, location)
                continue
            result.final_status = status
            result.final_url = final_url
            result.response_time_ms = round(elapsed_ms, 1)
            present = [h for h in SECURITY_HEADERS if h in headers]
            missing = [h for h in SECURITY_HEADERS if h not in headers]
            result.headers_present = '; '.join(present)
            result.headers_missing = '; '.join(missing)
            break
        else:
            result.error = f'too many redirects (>{max_redirects})'
    except HTTPError as e:
        result.final_status = e.code
        result.final_url = e.geturl() if hasattr(e, 'geturl') else url
        result.error = str(e.reason) if e.reason else 'HTTPError'
    except URLError as e:
        result.error = str(e.reason) if getattr(e, 'reason', None) else str(e)
    except Exception as e:
        result.error = str(e)

    result.redirect_chain = ' -> '.join(chain) if chain else '(none)'
    if len(chain) == 1 and not result.error:
        hop_status = chain[0].split(' ', 1)[0]
        if hop_status == '200' and result.final_url.rstrip('/') == url.rstrip('/'):
            result.redirect_chain = '(none)'
    return result


def audit_sitemap(sitemap_url: str, timeout: float, sample_limit: int = 50) -> list[str]:
    """Return sitemap audit notes (HTTPS locs, obvious http:// locs)."""
    notes: list[str] = []
    req = Request(sitemap_url, headers={'User-Agent': 'PBJ320-site-health-check/1.0'})
    try:
        with _NO_REDIRECT_OPENER.open(req, timeout=timeout) as resp:
            body = resp.read()
    except Exception as e:
        return [f'sitemap fetch failed: {e}']

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return [f'sitemap XML parse error: {e}']

    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locs = [el.text.strip() for el in root.findall('.//sm:loc', ns) if el.text and el.text.strip()]
    if not locs:
        locs = [el.text.strip() for el in root.iter() if el.tag.endswith('loc') and el.text]

    if not locs:
        notes.append('sitemap: no <loc> entries found')
        return notes

    http_locs = [u for u in locs if u.lower().startswith('http://')]
    non_https = [u for u in locs if not u.lower().startswith('https://')]
    notes.append(f'sitemap: {len(locs)} URLs')
    if http_locs:
        notes.append(f'sitemap: {len(http_locs)} http:// loc(s) (should be https)')
    if non_https:
        notes.append(f'sitemap: {len(non_https)} non-HTTPS loc(s)')

    # Spot-check a sample for redirecting http URLs (only if http locs exist)
    for bad in http_locs[: min(5, len(http_locs))]:
        r = check_url(bad, timeout)
        if r.final_status and r.final_status >= 300:
            notes.append(f'sitemap http loc redirects: {bad} -> {r.final_status}')

    https_sample = [u for u in locs if u.lower().startswith('https://')][:sample_limit]
    redirecting = 0
    for u in https_sample:
        r = check_url(u, timeout)
        if r.redirect_chain and r.redirect_chain != '(none)':
            redirecting += 1
    if redirecting:
        notes.append(f'sitemap: {redirecting}/{len(https_sample)} sampled HTTPS URLs had redirect chains')

    return notes


def print_table(results: list[CheckResult]) -> None:
    cols = ('URL', 'Status', 'Time ms', 'Final URL', 'Redirects', 'Missing headers')
    widths = [42, 8, 9, 42, 28, 24]
    header = ''.join(c.ljust(w) for c, w in zip(cols, widths))
    print(header)
    print('-' * len(header))
    for r in results:
        missing = r.headers_missing or (r.error or r.notes or '—')
        print(
            f"{r.url[:widths[0]].ljust(widths[0])}"
            f"{str(r.final_status or '—').ljust(widths[1])}"
            f"{str(r.response_time_ms or '—').ljust(widths[2])}"
            f"{(r.final_url or '—')[:widths[3]].ljust(widths[3])}"
            f"{(r.redirect_chain or '—')[:widths[4]].ljust(widths[4])}"
            f"{missing[:widths[5]]}"
        )


def write_csv(path: Path, results: list[CheckResult], sitemap_notes: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now(timezone.utc).isoformat()
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'checked_at_utc', 'url', 'final_status', 'final_url', 'response_time_ms',
            'redirect_chain', 'headers_present', 'headers_missing', 'notes', 'error',
        ])
        for r in results:
            w.writerow([
                checked_at, r.url, r.final_status, r.final_url, r.response_time_ms,
                r.redirect_chain, r.headers_present, r.headers_missing, r.notes, r.error,
            ])
        if sitemap_notes:
            w.writerow([])
            w.writerow(['sitemap_audit', '; '.join(sitemap_notes)])


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='PBJ320 public site health check')
    parser.add_argument('--base', default='https://pbj320.com', help='Base origin (default: https://pbj320.com)')
    parser.add_argument('--timeout', type=float, default=30.0, help='Per-request timeout seconds')
    parser.add_argument('--csv', type=Path, default=DEFAULT_CSV, help='Output CSV path')
    parser.add_argument('urls', nargs='*', help='URLs to check (default: standard public list)')
    args = parser.parse_args(argv)

    urls = args.urls or DEFAULT_URLS
    if args.base.rstrip('/') != 'https://pbj320.com':
        base = args.base.rstrip('/')
        urls = [re.sub(r'^https://pbj320\.com', base, u) for u in urls]

    print(f'PBJ320 site health check — {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}\n')
    results = [check_url(u, args.timeout) for u in urls]

    sitemap_notes: list[str] = []
    robots = next((r for r in results if r.url.endswith('/robots.txt')), None)
    if robots and robots.final_status == 200:
        sitemap_notes.append('robots.txt: reachable (200)')
    elif robots:
        sitemap_notes.append(f'robots.txt: status {robots.final_status or "error"}')

    sitemap = next((r for r in results if r.url.endswith('/sitemap.xml')), None)
    if sitemap and sitemap.final_status == 200:
        sitemap_notes.extend(audit_sitemap(sitemap.url, args.timeout))
    elif sitemap:
        sitemap_notes.append(f'sitemap.xml: status {sitemap.final_status or "error"}')

    print_table(results)
    if sitemap_notes:
        print('\nSitemap / robots:')
        for line in sitemap_notes:
            print(f'  - {line}')

    write_csv(args.csv, results, sitemap_notes)
    print(f'\nCSV written to {args.csv}')

    bad = [r for r in results if r.error or not r.final_status or r.final_status >= 400]
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
