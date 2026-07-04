#!/usr/bin/env python3
from playwright.sync_api import sync_playwright

URL = "https://www.pbj320.com/insights/ny-minimum-staffing#calendar"
EXPECTED = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(URL, wait_until="networkidle", timeout=120_000)
    page.wait_for_selector("#dowChart", timeout=30_000)
    page.wait_for_timeout(1500)
    init = page.evaluate(
        """() => {
          const c = window.PBJ320Threshold.chartStore.dowChart;
          return {
            labels: c.data.labels.slice(),
            data: c.data.datasets[0].data.slice(),
            yMin: c.scales.y.min,
            yMax: c.scales.y.max,
            ticks: c.scales.y.ticks.map(t => t.label),
          };
        }"""
    )
    page.evaluate(
        """() => {
          const s = document.getElementById('hprd-slider');
          s.value = '4.00';
          s.dispatchEvent(new Event('input', { bubbles: true }));
          s.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )
    page.wait_for_timeout(800)
    after = page.evaluate(
        """() => {
          const c = window.PBJ320Threshold.chartStore.dowChart;
          return { labels: c.data.labels.slice(), data: c.data.datasets[0].data.slice() };
        }"""
    )
    browser.close()

ok = (
    init["labels"] == EXPECTED
    and len(init["data"]) == 7
    and after["labels"] == EXPECTED
    and len(after["data"]) == 7
    and all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in init["data"])
    and init["yMin"] < init["yMax"]
    and all(str(t).endswith("%") and str(t)[:-1].lstrip("-").isdigit() for t in init["ticks"] if t)
)
print("PASS" if ok else "FAIL", init, after)
