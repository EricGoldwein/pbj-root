"""Smoke: DOW chart updates when staff-mix radios change (Playwright)."""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"


def main() -> None:
    html = HTML.read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("#dowChart", state="attached", timeout=60_000)
        page.wait_for_function("() => typeof Chart !== 'undefined' && Chart.getChart('dowChart')")
        time.sleep(0.5)

        def mon_pct() -> float | None:
            return page.evaluate(
                """() => {
                  const c = Chart.getChart('dowChart');
                  return c ? c.data.datasets[0].data[0] : null;
                }"""
            )

        base = mon_pct()
        page.evaluate(
            """() => {
              window.PBJ320ReportMode.setMetricMode('broad_pbj_total_hprd', { scope: 'dow' });
            }"""
        )
        time.sleep(0.2)
        broad = mon_pct()
        page.evaluate(
            """() => {
              window.PBJ320ReportMode.setMetricMode('ny_mapped_include_don_sensitivity', { scope: 'dow' });
            }"""
        )
        time.sleep(0.2)
        don = mon_pct()
        browser.close()

    print(f"Mon Direct pct: {base}")
    print(f"Mon Total pct: {broad}")
    print(f"Mon Direct+DON pct: {don}")
    assert base != broad, "Total mode should change Monday bar"
    assert base != don, "Direct+DON mode should change Monday bar"
    assert broad != don, "Total and Direct+DON should differ"
    print("OK: mode toggles update DOW chart")


if __name__ == "__main__":
    main()
