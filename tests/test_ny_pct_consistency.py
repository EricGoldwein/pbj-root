"""NY staffing report: precomputed pct fields must match numerator/denominator."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_interactive(html: str) -> dict:
    import json

    marker = "window.PBJ_REPORT_INTERACTIVE = "
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
    raise AssertionError("interactive JSON not found")


class NyPctConsistencyTest(unittest.TestCase):
    def test_pct_field_audit_exits_zero(self):
        script = ROOT / "scripts" / "audit_ny_pct_field_consistency.py"
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_math_audit_exits_zero(self):
        script = ROOT / "scripts" / "audit_ny_minimum_staffing_math.py"
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_weekend_nyc_consistency_at_default_threshold(self):
        html = (ROOT / "insights-ny-minimum-staffing.html").read_text(encoding="utf-8")
        interactive = _load_interactive(html)
        default_key = interactive.get("default_mode", "ny_mapped_non_admin_hprd")
        mode = interactive["modes"][default_key]
        pt = next(p for p in mode["curves"]["weekend_nyc"] if abs(p["threshold"] - 3.5) < 0.001)
        cards = {c["curve"]: c["facility_days"] for c in mode.get("weekend_cards", [])}
        fd = cards.get("weekend_nyc") or mode.get("curve_facility_days", {}).get("weekend_nyc")
        self.assertIsNotNone(fd)
        self.assertEqual(pt["below"], 14162)
        expected = round(100.0 * pt["below"] / fd, 2)
        self.assertAlmostEqual(pt["pct_below"], expected, places=2)
        self.assertAlmostEqual(round(100.0 * pt["below"] / fd, 1), 83.4, places=1)
        self.assertEqual(fd, 16978)

    def test_broad_comparison_weekend_nyc_not_stale(self):
        html = (ROOT / "insights-ny-minimum-staffing.html").read_text(encoding="utf-8")
        self.assertNotIn('"facility_days":17082', html)
        self.assertNotIn("17,082", html)
        self.assertNotIn("82.3%", html)

        interactive = _load_interactive(html)
        broad = interactive["modes"]["broad_pbj_total_hprd"]
        card = next(c for c in broad["weekend_cards"] if c["curve"] == "weekend_nyc")
        pt = next(p for p in broad["curves"]["weekend_nyc"] if abs(p["threshold"] - 3.5) < 0.001)
        self.assertEqual(card["facility_days"], 16978)
        expected = round(100.0 * pt["below"] / card["facility_days"], 2)
        self.assertAlmostEqual(pt["pct_below"], expected, places=2)


if __name__ == "__main__":
    unittest.main()
