"""NY staffing report: day-of-week chart renders exactly seven weekday bars."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"
EXPECTED_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EXPECTED_DOWS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
ANCHOR_STATEWIDE_FD = 216_134


def _playwright_chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


def _extract_charts() -> list[dict]:
    html = HTML.read_text(encoding="utf-8")
    marker = "window.PBJ_REPORT_CHARTS = "
    start = html.index(marker) + len(marker)
    depth = 0
    for j in range(start, len(html)):
        c = html[j]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start : j + 1])
    raise ValueError("PBJ_REPORT_CHARTS not found")


class NyDowChartTest(unittest.TestCase):
    def test_static_dow_spec_has_seven_weekdays(self):
        """PBJ_REPORT_CHARTS dowChart schema:
        - labels: short Mon–Sun display labels (7)
        - dows: full weekday names (7)
        - values: % below standard at default threshold (7)
        - facility_days: per-weekday facility-day denominators (7 ints, not weekday names)
        """
        dow = next(c for c in _extract_charts() if c.get("id") == "dowChart")
        self.assertEqual(dow["labels"], EXPECTED_LABELS)
        self.assertEqual(dow["dows"], EXPECTED_DOWS)
        self.assertEqual(len(dow["values"]), 7)
        self.assertEqual(len(dow["facility_days"]), 7)
        self.assertEqual(len(dow.get("tooltips", [])), 7)
        self.assertTrue(all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in dow["values"]))
        self.assertTrue(
            all(isinstance(fd, int) and fd > 0 for fd in dow["facility_days"]),
            msg=f"facility_days must be positive ints: {dow['facility_days']!r}",
        )
        self.assertEqual(
            sum(dow["facility_days"]),
            ANCHOR_STATEWIDE_FD,
            msg="weekday facility-day counts must sum to statewide denominator",
        )

    def test_update_dow_chart_uses_indexed_facility_days(self):
        """Runtime updateDowChart must index facility_days by position, not weekday name."""
        html = HTML.read_text(encoding="utf-8")
        start = html.index("function updateDowChart(threshold)")
        end = html.index("function updateCountyChart(threshold)", start)
        block = html[start:end]
        self.assertNotIn("facility_days[d]", block, msg="weekday name must not index facility_days array")
        self.assertIn("facility_days[i]", block)

    @unittest.skipUnless(
        _playwright_chromium_available(),
        "Playwright Chromium browser not installed (run: playwright install chromium)",
    )
    def test_dow_chart_playwright_seven_bars(self):
        script = ROOT / "scripts" / "audit_ny_dow_chart_playwright.py"
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
