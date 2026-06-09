#!/usr/bin/env python3
"""Measure state page server payload and aggregate status (local or production)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request

DEFAULT_PAGES = [
    ('WY', '/state/wyoming'),
    ('NY', '/state/new-york'),
    ('TX', '/state/texas'),
    ('CA', '/state/california'),
    ('FL', '/state/florida'),
    ('NJ', '/state/new-jersey'),
    ('USA', '/state/usa'),
    ('PROV', '/provider/335513'),
]


def fetch(base: str, path: str) -> dict:
    url = base.rstrip('/') + path
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={'User-Agent': 'PBJ320-state-audit/3'})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        hdr = dict(r.headers)
    elapsed = round(time.perf_counter() - t0, 3)
    text = body.decode('utf-8', 'replace')
    css = re.findall(r'<link[^>]+href="([^"]+\.css[^"]*)"', text)
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', text)
    return {
        'path': path,
        'bytes': len(body),
        'elapsed_s': elapsed,
        'provider_links_ssr': len(re.findall(r'/provider/\d{6}', text)),
        'state_hr_rows_ssr': len(re.findall(r'class="state-hr-facility-name"', text)),
        'lazy_high_risk': 'data-state-high-risk="1"' in text,
        'css': css,
        'scripts': len(scripts),
        'aggregates_header': hdr.get('X-PBJ-State-Aggregates') or hdr.get('x-pbj-state-aggregates'),
        'cache_control': hdr.get('Cache-Control'),
    }


def warmup(base: str) -> dict:
    url = base.rstrip('/') + '/warmup'
    req = urllib.request.Request(url, headers={'User-Agent': 'PBJ320-state-audit/3'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', default='http://127.0.0.1:10000')
    args = p.parse_args()
    base = args.base_url.rstrip('/')

    out: dict = {'base_url': base, 'measured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'pages': []}
    try:
        w = warmup(base)
        out['warmup'] = w.get('checks', {}).get('state_page_aggregates')
        out['warmup_ok'] = w.get('ok')
    except Exception as e:
        out['warmup_error'] = str(e)

    for label, path in DEFAULT_PAGES:
        try:
            row = fetch(base, path)
            row['label'] = label
            out['pages'].append(row)
        except Exception as e:
            out['pages'].append({'label': label, 'path': path, 'error': str(e)})

    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
