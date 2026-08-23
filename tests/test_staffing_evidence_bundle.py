"""Staffing day-evidence bundle tests."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import staffing_evidence_bundle as seb  # noqa: E402


class StaffingEvidenceBundleTests(unittest.TestCase):
    TEST_METRIC = "RN_HPRD"

    @classmethod
    def setUpClass(cls) -> None:
        if not seb.bundle_available(str(REPO)):
            raise unittest.SkipTest("staffing day-evidence bundle not present locally")
        seb.invalidate_caches()
        seb.materialize_sqlite(str(REPO))
        import sqlite3

        db = seb.sqlite_path(str(REPO))
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT ccn, work_date, rn_hprd FROM day_fact ORDER BY ccn, work_date LIMIT 1"
        ).fetchone()
        conn.close()
        if not row:
            raise unittest.SkipTest("day_fact table empty")
        cls.TEST_CCN = row[0]
        cls.TEST_DATE = row[1]
        cls.TEST_VALUE = float(row[2])

    def test_lookup_returns_evidence(self):
        ev = seb.lookup_day_evidence(str(REPO), self.TEST_CCN, self.TEST_DATE, self.TEST_METRIC)
        self.assertIsNotNone(ev)
        assert ev is not None
        self.assertEqual(ev.get("ccn"), self.TEST_CCN)
        self.assertAlmostEqual(float(ev.get("value") or 0), self.TEST_VALUE, places=6)
        self.assertIn("numerator", ev)
        self.assertIn("denominator", ev)

    def test_ccn_zero_padding(self):
        ev = seb.lookup_day_evidence(str(REPO), self.TEST_CCN, self.TEST_DATE, self.TEST_METRIC)
        self.assertIsNotNone(ev)

    def test_manifest_schema(self):
        manifest = seb.load_manifest(str(REPO))
        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(int(manifest.get("bundle_schema_version")), 2)
        self.assertEqual(manifest.get("schema"), "day_fact")
        self.assertFalse(manifest.get("ein_included"))
        self.assertIn(self.TEST_METRIC, manifest.get("metrics") or [])

    def test_no_employee_records_in_public_payload(self):
        ev = seb.lookup_day_evidence(str(REPO), self.TEST_CCN, self.TEST_DATE, self.TEST_METRIC)
        assert ev is not None
        self.assertEqual(ev.get("employee_count"), 0)
        self.assertNotIn("employee_records", ev)

    def test_value_comes_from_stored_hprd_not_division(self):
        """Assembler must use stored float; poisoning hours must not change value."""
        fact = seb._fetch_day_fact(str(REPO), self.TEST_CCN, self.TEST_DATE)
        assert fact is not None
        poisoned = dict(fact)
        poisoned["hrs_rn"] = 99999.0
        assembled = seb.assemble_evidence_from_day_fact(poisoned, "RN_HPRD")
        assert assembled is not None
        self.assertAlmostEqual(float(assembled["value"]), float(fact["rn_hprd"]), places=6)


class EvidenceReleasePolicyTests(unittest.TestCase):
    def test_ownership_release_from_policy_not_mtime(self):
        from ownership.ownership_release_policy import active_release_date, load_policy

        pol = load_policy(REPO)
        active = active_release_date(pol)
        self.assertTrue(active)
        self.assertIn(active, pol.get("releases", {}))


if __name__ == "__main__":
    unittest.main()
