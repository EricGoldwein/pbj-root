#!/usr/bin/env python3
"""Break down /state page HTML weight by section (local or production).

Usage:
    python scripts/audit_state_page_payload.py --base-url https://www.pbj320.com
    python scripts/audit_state_page_payload.py --base-url http://127.0.0.1:10000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser


class _DomCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nodes = 0
        self.hidden_nodes = 0

    def handle_starttag(self, tag, attrs) -> None:
        self.nodes += 1
        attrs_d = dict(attrs)
        if attrs_d.get('hidden') is not None or attrs_d.get('aria-hidden') == 'true':
            self.hidden_nodes += 1


def _fetch(url: str) -> tuple[bytes, dict[str, str], float]:
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={'User-Agent': 'PBJ320-payload-audit/1'})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        hdr = {k.lower(): v for k, v in r.headers.items()}
    return body, hdr, round(time.perf_counter() - t0, 3)


def _section_bytes(text: str, start_pat: str, end_pat: str | None = None) -> int:
    m = re.search(start_pat, text, re.I | re.S)
    if not m:
        return 0
    start = m.start()
    if end_pat:
        m2 = re.search(end_pat, text[m.end() :], re.I | re.S)
        end = m.end() + m2.start() if m2 else len(text)
    else:
        end = len(text)
    return end - start


def analyze_page(base: str, path: str) -> dict:
    url = base.rstrip('/') + path
    body, hdr, elapsed = _fetch(url)
    text = body.decode('utf-8', 'replace')
    counter = _DomCounter()
    try:
        counter.feed(text)
    except Exception:
        pass

    chow_stores = len(re.findall(r'class="chow-detail-store"', text))
    chow_lazy = len(re.findall(r'data-chow-lazy-id=', text))
    hr_loading = len(re.findall(r'state-hr-loading', text))
    hr_ssr = len(re.findall(r'class="state-hr-facility-name"', text))
    script_inline = sum(len(m.group(0)) for m in re.finditer(r'<script(?![^>]*\ssrc=)[^>]*>.*?</script>', text, re.S))
    script_src = len(re.findall(r'<script[^>]+src=', text))

    sections = {
        'hero_h1_subtitle': _section_bytes(text, r'<h1 class="pbj-state-title"', r'id="pbj-takeaway"'),
        'takeaway_card': _section_bytes(text, r'id="pbj-takeaway"', r'pbj-state-staffing-table|chartStaffing|pbj-page-bottom-stack'),
        'staffing_chart': _section_bytes(text, r'chartStaffing|id="chart', r'pbj-state-staffing-table|pbj-page-bottom-stack'),
        'staffing_stats_table': _section_bytes(text, r'pbj-state-staffing-table', r'pbj-page-bottom-stack'),
        'high_risk_section': _section_bytes(text, r'data-state-high-risk', r'pbj-details-top-owners|pbj-details-ownership-chow|render_methodology'),
        'top_owners': _section_bytes(text, r'pbj-details-top-owners', r'pbj-details-ownership-chow|render_methodology'),
        'chow_block': _section_bytes(text, r'pbj-details-ownership-chow', r'render_methodology|pbj-page-bottom-stack'),
        'inline_scripts': script_inline,
    }

    return {
        'path': path,
        'url': url,
        'bytes': len(body),
        'fetch_s': elapsed,
        'aggregates_header': hdr.get('x-pbj-state-aggregates'),
        'dom_nodes': counter.nodes,
        'dom_hidden_nodes': counter.hidden_nodes,
        'chow_detail_stores': chow_stores,
        'chow_lazy_detail_buttons': chow_lazy,
        'state_hr_rows_ssr': hr_ssr,
        'state_hr_loading_rows': hr_loading,
        'lazy_high_risk': 'data-state-high-risk="1"' in text,
        'external_scripts': script_src,
        'provider_links_ssr': len(re.findall(r'/provider/\d{6}', text)),
        'sections_bytes': sections,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', default='http://127.0.0.1:10000')
    p.add_argument('--paths', nargs='*', default=['/state/texas', '/state/new-york'])
    args = p.parse_args()
    base = args.base_url.rstrip('/')

    out: dict = {
        'base_url': base,
        'measured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'pages': [],
    }
    try:
        wurl = base + '/warmup'
        with urllib.request.urlopen(
            urllib.request.Request(wurl, headers={'User-Agent': 'PBJ320-payload-audit/1'}),
            timeout=60,
        ) as r:
            w = json.loads(r.read().decode('utf-8'))
        out['warmup_aggregates'] = w.get('checks', {}).get('state_page_aggregates')
    except Exception as e:
        out['warmup_error'] = str(e)

    for path in args.paths:
        try:
            out['pages'].append(analyze_page(base, path))
        except Exception as e:
            out['pages'].append({'path': path, 'error': str(e)})

    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
