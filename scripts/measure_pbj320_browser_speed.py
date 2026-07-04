#!/usr/bin/env python3
"""Playwright production speed snapshot for key PBJ320 pages (DevTools-equivalent)."""
from __future__ import annotations

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "https://www.pbj320.com"
PAGES = [
    ("report", f"{BASE}/report"),
    ("provider_335513", f"{BASE}/provider/335513"),
    ("provider_676230", f"{BASE}/provider/676230"),
    ("home", f"{BASE}/"),
]

INIT = """
window.__pbjLongTasks = [];
try {
  const obs = new PerformanceObserver((list) => {
    for (const e of list.getEntries()) {
      window.__pbjLongTasks.push({ startTime: e.startTime, duration: e.duration });
    }
  });
  obs.observe({ entryTypes: ['longtask'] });
} catch (_) {}
"""


def _big_resources(page) -> list[dict]:
    return page.evaluate(
        """() => performance.getEntriesByType('resource')
          .map(e => ({
            name: e.name.split('/').slice(-2).join('/'),
            transferSize: e.transferSize || 0,
            duration: Math.round(e.duration),
            startTime: Math.round(e.startTime),
          }))
          .filter(e => e.transferSize > 50000 || e.duration > 500)
          .sort((a,b) => (b.transferSize||0) - (a.transferSize||0))
          .slice(0, 12)"""
    )


def measure_url(page, label: str, url: str) -> dict:
    facility_reqs: list[str] = []
    page.on(
        "request",
        lambda r: facility_reqs.append(r.url)
        if "facility_quarterly" in r.url
        else None,
    )

    t0 = time.perf_counter()
    resp = page.goto(url, wait_until="networkidle", timeout=180_000)
    networkidle_s = round(time.perf_counter() - t0, 2)

    nav = page.evaluate(
        """() => {
          const n = performance.getEntriesByType('navigation')[0];
          if (!n) return {};
          return {
            ttfb_ms: Math.round(n.responseStart),
            domContentLoaded_ms: Math.round(n.domContentLoadedEventEnd),
            load_ms: Math.round(n.loadEventEnd),
            transferSize: n.transferSize || 0,
            encodedBodySize: n.encodedBodySize || 0,
          };
        }"""
    )

    total_transfer = page.evaluate(
        """() => performance.getEntriesByType('resource')
          .reduce((s, e) => s + (e.transferSize || 0), 0)"""
    )

    provider_cache = resp.headers.get("x-pbj-provider-cache") if resp else None

    out = {
        "label": label,
        "url": url,
        "status": resp.status if resp else None,
        "networkidle_s": networkidle_s,
        "navigation": nav,
        "total_resource_transfer_bytes": total_transfer,
        "facility_quarterly_requests": facility_reqs,
        "big_resources": _big_resources(page),
        "long_tasks_over_50ms": [
            t for t in page.evaluate("() => window.__pbjLongTasks || []") if t["duration"] >= 50
        ],
    }

    if label == "report":
        legend = ""
        try:
            page.evaluate("document.getElementById('medianToggleMap')?.click()")
            page.wait_for_timeout(800)
            legend = page.locator(".legend-title").first.inner_text(timeout=5000)
        except Exception as exc:
            legend = f"error: {exc}"
        out["median_toggle_legend"] = legend

    if label.startswith("provider"):
        out["has_hprd_narrative"] = page.evaluate(
            """() => {
              const t = document.body.innerText || '';
              return !/Reported HPRD not available/i.test(t) && /HPRD/i.test(t);
            }"""
        )

    return out


def main() -> int:
    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, url in PAGES:
            page = browser.new_page()
            page.add_init_script(INIT)
            try:
                results.append(measure_url(page, label, url))
            except Exception as exc:
                results.append({"label": label, "url": url, "error": str(exc)})
            finally:
                page.close()
        browser.close()

    print(json.dumps({"measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
