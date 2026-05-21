#!/usr/bin/env python3
"""Find broken external https links in user-facing site source (concurrent HTTP checks)."""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIR_NAMES = {
    '__pycache__',
    '.git',
    '.pytest_cache',
    'node_modules',
    'pbj-wrapped',
    'wrapped-template',
    'donor',
    'downloads',
    '_ericized_skill_inspect',
    '.cursor',
}
PUBLIC_ONLY_ROOT_FILES = {
    'about.html',
    'chow.html',
    'contact.html',
    'data-sources.html',
    'index.html',
    'insights.html',
    'newsletter.html',
    'pbj-ai-support.html',
    'phoebe.html',
    'press.html',
    'privacy.html',
    'report.html',
    'terms.html',
}
PUBLIC_ONLY_DIRS = ('premium', 'PBJPedia', 'insights_posts', 'templates')
SCAN_SUFFIXES = {'.html', '.md', '.py', '.tsx'}
URL_RE = re.compile(r'https?://[^\s\)"\'<>]+', re.I)
TRAIL = re.compile(r'[.,;:\]\)]+$', )

USER_AGENT = 'Mozilla/5.0 (compatible; PBJ320-link-check/1.0; +https://www.pbj320.com)'

# Known-good or bot-blocked; not actionable broken links in source.
SKIP_URL_SUBSTRINGS = (
    'example.com',
    'fonts.googleapis.com',
    'fonts.gstatic.com',
    'linkedin.com/in/',
    'congress.gov/bill/',
    'purl.org/rss',
    'http://...}',
    'onlinelibrary.wiley.com',
)
# Routes verified in app.py; live 404 until deploy (checked separately).
SKIP_OWN_SITE_PREFIXES = (
    'https://www.pbj320.com/premium/',
    'https://www.pbj320.com/pbj-ai-support',
)


def _should_scan(path: Path, *, public_only: bool) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return False
    if 'premium/samples/' in rel.as_posix():
        return False
    if path.suffix.lower() not in SCAN_SUFFIXES:
        return False
    if not public_only:
        return True
    if rel.name in PUBLIC_ONLY_ROOT_FILES:
        return True
    return rel.parts[0] in PUBLIC_ONLY_DIRS


def _collect_url_from_match(raw: str) -> str | None:
    u = TRAIL.sub('', raw.strip())
    if not u or u.startswith('http://localhost') or '127.0.0.1' in u:
        return None
    if any(s in u for s in SKIP_URL_SUBSTRINGS):
        return None
    if any(u.startswith(p) for p in SKIP_OWN_SITE_PREFIXES):
        return None
    # Skip truncated URLs from split Python string literals.
    if u.endswith('/') and 'cms.gov' in u and u.count('/') <= 5:
        return None
    return u


def _iter_files(public_only: bool) -> list[Path]:
    if public_only:
        files: list[Path] = []
        for name in PUBLIC_ONLY_ROOT_FILES:
            p = ROOT / name
            if p.is_file():
                files.append(p)
        for dirname in PUBLIC_ONLY_DIRS:
            d = ROOT / dirname
            if d.is_dir():
                for path in d.rglob('*'):
                    if path.is_file() and _should_scan(path, public_only=True):
                        files.append(path)
        files.extend(ROOT.glob('utils/*.py'))
        files.append(ROOT / 'site_public_config.py')
        files.append(ROOT / 'pbj_page_sources.py')
        return sorted(set(files))
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and _should_scan(p, public_only=False))


def collect_urls(public_only: bool) -> dict[str, set[Path]]:
    by_url: dict[str, set[Path]] = defaultdict(set)
    for path in _iter_files(public_only):
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for raw in URL_RE.findall(text):
            url = _collect_url_from_match(raw)
            if url:
                by_url[url].add(path)
    return by_url


def check_url(url: str, timeout: float) -> tuple[int | None, str]:
    headers = {'User-Agent': USER_AGENT}
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.status
                if 200 <= code < 400:
                    return code, 'ok'
                return code, f'http {code}'
        except urllib.error.HTTPError as exc:
            if method == 'GET' or exc.code in (405, 403):
                return exc.code, f'http {exc.code}'
        except Exception as exc:  # noqa: BLE001
            if method == 'GET':
                return None, str(exc)[:100]
    return None, 'unreachable'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=12.0)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--cms-only', action='store_true')
    parser.add_argument(
        '--public-only',
        action='store_true',
        help='Scan public HTML/templates/PBJPedia only (fast pre-deploy check)',
    )
    args = parser.parse_args()

    by_url = collect_urls(args.public_only or args.cms_only)
    if args.cms_only:
        by_url = {u: p for u, p in by_url.items() if 'cms.gov' in u or 'medicare.gov' in u or 'justice.gov' in u}

    urls = sorted(by_url.keys())
    print(f'Checking {len(urls)} URLs ({args.workers} workers)...')
    failures: list[tuple[str, int | None, str, list[Path]]] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(check_url, url, args.timeout): url for url in urls}
        done = 0
        for fut in as_completed(futures):
            url = futures[fut]
            status, detail = fut.result()
            done += 1
            if done % 20 == 0 or done == len(urls):
                print(f'  ... {done}/{len(urls)}', flush=True)
            if status is None or status >= 400:
                failures.append((url, status, detail, sorted(by_url[url], key=lambda p: p.as_posix())))

    print(f'\nDone. {len(failures)} broken URL(s).\n')
    for url, status, detail, paths in sorted(failures, key=lambda x: x[0]):
        print(f'FAIL [{status}] {detail}')
        print(f'  {url}')
        for p in paths[:6]:
            print(f'    - {p.relative_to(ROOT)}')
        if len(paths) > 6:
            print(f'    ... +{len(paths) - 6} more')
        print()
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
