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
        dow = next(c for c in _extract_charts() if c.get("id") == "dowChart")
        self.assertEqual(dow["labels"], EXPECTED_LABELS)
        self.assertEqual(len(dow["values"]), 7)
        self.assertEqual(len(dow["dows"]), 7)
        self.assertEqual(set(dow["facility_days"]), set(dow["dows"]))

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
