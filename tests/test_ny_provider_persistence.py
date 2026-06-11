"""Provider-level daily persistence @ NY-mapped 3.50 HPRD."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "public" / "downloads" / "PBJ320_NY_2025_daily_staffing_verification_csvs"
HTML = ROOT / "insights-ny-minimum-staffing.html"

ANCHOR = {
    "at_least_50pct": 348,
    "at_least_75pct": 228,
    "at_least_90pct": 158,
    "all_analyzed_days": 58,
    "zero_days": 21,
}


def _load_persistence_json(html: str) -> dict:
    marker = "window.PBJ_REPORT_PROVIDER_PERSISTENCE = "
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
    raise AssertionError("PBJ_REPORT_PROVIDER_PERSISTENCE not found")


class NyProviderPersistenceTest(unittest.TestCase):
    def test_facility_summary_persistence_flags(self):
        fac = pd.read_csv(CSV_DIR / "facility_summary.csv")
        self.assertEqual(len(fac), 596)
        self.assertIn("below_350_ge_50pct_days", fac.columns)
        self.assertIn("provider_day_band", fac.columns)
        counts = {
            "at_least_50pct": int(fac["below_350_ge_50pct_days"].sum()),
            "at_least_75pct": int(fac["below_350_ge_75pct_days"].sum()),
            "at_least_90pct": int(fac["below_350_ge_90pct_days"].sum()),
            "all_analyzed_days": int(fac["below_350_all_analyzed_days"].sum()),
            "zero_days": int(fac["below_350_zero_days"].sum()),
        }
        self.assertEqual(counts, ANCHOR)

    def test_persistence_summary_csv(self):
        summary = pd.read_csv(CSV_DIR / "provider_persistence_summary.csv")
        row_50 = summary.loc[
            summary["measure"].str.contains(">=50%", regex=False), "facilities"
        ].iloc[0]
        self.assertEqual(int(row_50), 348)

    def test_day_bands_csv_sums_to_596(self):
        bands = pd.read_csv(CSV_DIR / "provider_day_bands_summary.csv")
        self.assertEqual(int(bands["facility_count"].sum()), 596)
        self.assertEqual(int(bands.loc[bands["provider_day_band"] == "100% of days", "facility_count"].iloc[0]), 58)

    def test_report_embed_matches_csv(self):
        html = HTML.read_text(encoding="utf-8")
        payload = _load_persistence_json(html)
        self.assertEqual(payload["facility_count"], 596)
        for key, expected in ANCHOR.items():
            self.assertEqual(payload["thresholds"][key]["facilities"], expected)

    @staticmethod
    def _provider_lead_visible_text(html: str) -> str:
        match = re.search(
            r'id="provider-days-below-lead"[^>]*>(.*?)</p>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            raise AssertionError("provider-days-below-lead paragraph not found")
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        return re.sub(r"\s+", " ", text).strip()

    def test_report_prose_mentions_half_and_90(self):
        html = HTML.read_text(encoding="utf-8")
        lead = self._provider_lead_visible_text(html)
        self.assertRegex(lead, re.compile(r"six in ten", re.I))
        self.assertRegex(lead, re.compile(r"one-quarter", re.I))
        self.assertRegex(lead, re.compile(r"one in seven", re.I))
        self.assertIn("90%", lead)
        self.assertIn("3.50 HPRD", lead)
        self.assertNotRegex(lead, re.compile(r"compliance|violation|enforcement", re.I))

    def test_math_audit_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_ny_minimum_staffing_math.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
