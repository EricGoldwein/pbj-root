"""Measure CLS for #facilitySnapshotSection on a premium dashboard URL (Playwright)."""
from __future__ import annotations

import json
import sys
from typing import Any

from playwright.sync_api import sync_playwright

PATCH_CSS = """
#hprdTrendChartAboveProvider {
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  min-height: 450px;
}
@media (max-width: 1365.98px) {
  #hprdTrendChartAboveProvider { min-height: 400px; }
}
@media (max-width: 1023.98px) {
  #hprdTrendChartAboveProvider { min-height: 350px; }
}
@media (max-width: 767.98px) {
  #hprdTrendChartAboveProvider { min-height: 640px; }
}
.pbj-summary-audit-scope-footer { min-height: 2.85rem; }
"""

INIT_SCRIPT = """
(() => {
  window.__pbjClsLog = [];
  const obs = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (entry.hadRecentInput) continue;
      const sources = [];
      for (const src of entry.sources || []) {
        let node = src.node;
        if (node && node.nodeType === 3) node = node.parentElement;
        const id = node && node.id ? String(node.id) : '';
        const cls = node && node.className ? String(node.className).slice(0, 120) : '';
        sources.push({
          id,
          cls,
          tag: node ? node.tagName : '',
          inSnapshot: !!(node && document.getElementById('facilitySnapshotSection')?.contains(node)),
        });
      }
      window.__pbjClsLog.push({ value: entry.value, sources });
    }
  });
  obs.observe({ type: 'layout-shift', buffered: true });
})();
"""


def measure(
    url: str,
    viewport: dict[str, int],
    *,
    wait_ms: int = 15000,
    inject_cls_patch: bool = False,
    device_name: str | None = "Pixel 5",
) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if device_name and device_name in p.devices:
            context = browser.new_context(**p.devices[device_name])
        else:
            context = browser.new_context(viewport=viewport)
        page = context.new_page()
        if inject_cls_patch:
            page.add_init_script(
                f"""
                (() => {{
                  const style = document.createElement('style');
                  style.id = 'pbj-cls-patch-probe';
                  style.textContent = {json.dumps(PATCH_CSS)};
                  document.documentElement.appendChild(style);
                }})();
                """
            )
        page.add_init_script(INIT_SCRIPT)
        page.goto(url, wait_until="networkidle", timeout=180_000)
        page.wait_for_timeout(wait_ms)
        try:
            page.wait_for_function(
                "() => typeof Plotly !== 'undefined' && !!document.querySelector('#hprdTrendChartAboveProvider .js-plotly-plot, #hprdTrendChartAboveProvider .plotly')",
                timeout=120_000,
            )
        except Exception:
            pass
        page.wait_for_timeout(3000)
        result = page.evaluate(
            """() => {
              const sec = document.getElementById('facilitySnapshotSection');
              let total = 0;
              let section = 0;
              const shifts = [];
              for (const entry of window.__pbjClsLog || []) {
                total += entry.value;
                const inSec = (entry.sources || []).some((s) => s.inSnapshot);
                if (inSec) {
                  section += entry.value;
                  shifts.push(entry);
                }
              }
              const rect = sec ? sec.getBoundingClientRect() : null;
              const chart = document.getElementById('hprdTrendChartAboveProvider');
              return {
                total_cls: total,
                facility_snapshot_section_cls: section,
                section_height: rect ? rect.height : null,
                chart_height: chart ? chart.getBoundingClientRect().height : null,
                chart_has_plot: !!chart?.querySelector('.js-plotly-plot'),
                shift_count_in_section: shifts.length,
                top_shifts: shifts
                  .sort((a, b) => b.value - a.value)
                  .slice(0, 8),
              };
            }"""
        )
        browser.close()
        return result


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.pbj320.com/premium/335513"
    patch = "--patch" in sys.argv
    profiles = {
        "mobile": {"width": 390, "height": 844},
        "desktop": {"width": 1366, "height": 900},
    }
    out: dict[str, Any] = {"url": url, "patch_css": patch}
    for name, vp in profiles.items():
        device = "Pixel 5" if name == "mobile" else None
        out[name] = measure(url, vp, inject_cls_patch=patch, device_name=device)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
