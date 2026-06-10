#!/usr/bin/env python3
"""Browser-side /state page performance audit (Playwright).

Usage:
    python scripts/audit_state_page_playwright.py --base-url https://www.pbj320.com
"""
from __future__ import annotations

import argparse
import json
import sys
import time


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--base-url', default='http://127.0.0.1:10000')
    p.add_argument('--paths', nargs='*', default=['/state/texas', '/state/new-york'])
    args = p.parse_args()
    base = args.base_url.rstrip('/')

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('playwright not installed', file=sys.stderr)
        return 1

    out: dict = {
        'base_url': base,
        'measured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'pages': [],
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for path in args.paths:
            url = base + path
            row: dict = {'path': path, 'url': url}
            try:
                resp = page.goto(url, wait_until='load', timeout=120_000)
                row['status'] = resp.status if resp else None
                timing = page.evaluate(
                    """() => {
                      const nav = performance.getEntriesByType('navigation')[0] || {};
                      const paints = performance.getEntriesByType('paint');
                      const fcp = paints.find(p => p.name === 'first-contentful-paint');
                      let lcp = null;
                      try {
                        const obs = performance.getEntriesByType('largest-contentful-paint');
                        if (obs.length) lcp = obs[obs.length - 1].startTime;
                      } catch (e) {}
                      return {
                        ttfb_ms: nav.responseStart != null ? Math.round(nav.responseStart) : null,
                        dom_content_loaded_ms: nav.domContentLoadedEventEnd != null
                          ? Math.round(nav.domContentLoadedEventEnd) : null,
                        load_ms: nav.loadEventEnd != null ? Math.round(nav.loadEventEnd) : null,
                        fcp_ms: fcp ? Math.round(fcp.startTime) : null,
                        lcp_ms: lcp != null ? Math.round(lcp) : null,
                        transfer_bytes: nav.transferSize != null ? nav.transferSize : null,
                        dom_nodes: document.getElementsByTagName('*').length,
                        chow_stores: document.querySelectorAll('.chow-detail-store').length,
                        chow_lazy: document.querySelectorAll('[data-chow-lazy-id]').length,
                      };
                    }"""
                )
                row.update(timing)
            except Exception as e:
                row['error'] = str(e)
            out['pages'].append(row)

        browser.close()

    print(json.dumps(out, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
