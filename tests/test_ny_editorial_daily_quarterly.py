"""Editorial rule: daily=3.50 HPRD, quarterly=full statutory mapping."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "insights-ny-minimum-staffing.html"


def load_window_var(html: str, name: str) -> dict:
    marker = f"window.{name} = "
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
    raise RuntimeError(name)


class NyEditorialDailyQuarterlyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")

    def test_daily_primary_embed_uses_350_only(self):
        primary = load_window_var(self.html, "PBJ_REPORT_STANDARD_PRIMARY")
        self.assertEqual(primary["below_days"], primary["below_350_days"])
        self.assertEqual(primary["below_pct"], primary["below_350_pct"])
        self.assertEqual(primary["below_days"], 123428)
        self.assertAlmostEqual(primary["below_pct"], 57.1)

    def test_quarterly_embed_has_full_statutory_fields(self):
        q = load_window_var(self.html, "PBJ_REPORT_QUARTERLY_STATUTORY")
        for key in (
            "facility_quarters_below_220_cna_side",
            "facility_quarters_below_110_licensed",
            "facilities_below_350_at_least_one_quarter",
            "facilities_below_350_all_four_quarters",
            "facilities_missing_any_floor_at_least_one_quarter",
            "facilities_missing_any_floor_all_four_quarters",
        ):
            self.assertIn(key, q, msg=key)
        self.assertEqual(q["facilities_below_350_all_four_quarters"], 284)

    def test_no_standalone_daily_role_floor_appendix(self):
        self.assertNotIn('id="statute-sensitivity"', self.html)

    def test_quarterly_disclaimer_copy_present(self):
        self.assertIn(
            "New York determines staffing compliance quarterly",
            self.html,
        )
        self.assertIn("not NY DOH enforcement determinations", self.html)

    def test_provider_table_has_quarterly_miss_column(self):
        self.assertIn('data-sort="qtrs_miss"', self.html)
        self.assertIn('data-label="Qtrs missed floor"', self.html)
        self.assertIn(
            "Quarterly values are statutory-style PBJ mappings",
            self.html,
        )

    def test_methods_daily_vs_quarterly_distinction(self):
        self.assertIn("Daily vs. quarterly:", self.html)
        self.assertIn("facility-quarter level", self.html)


if __name__ == "__main__":
    unittest.main()
