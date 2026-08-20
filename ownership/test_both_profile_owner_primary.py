"""Regression: both-profile owner-primary for large owner portfolios (Life Care)."""
from __future__ import annotations

import unittest

from ownership.owner_profile import load_owner_profile_resolved


LIFE_CARE_PAC = "6608783543"


class BothProfileOwnerPrimaryTests(unittest.TestCase):
    def test_life_care_owner_primary_facility_count(self) -> None:
        """
        PAC 6608783543 (Life Care) is enrollment+owner. Owner side has ~141
        facilities; enrollment side is thin (~1). Primary portfolio must use
        owner/control facilities so Total Facilities is not 1.
        """
        profile = load_owner_profile_resolved(LIFE_CARE_PAC)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.get("profile_kind"), "both")
        self.assertEqual(profile.get("both_primary"), "owner_control")
        ps = profile.get("portfolio_summary") or {}
        n = int(ps.get("n_facilities") or 0)
        # Prefer exact when deterministic; allow >= 100 if enrichment filters some.
        self.assertGreaterEqual(
            n,
            100,
            f"expected owner-primary n_facilities >= 100, got {n} "
            f"(facilities={len(profile.get('facilities') or [])})",
        )
        self.assertGreaterEqual(len(profile.get("facilities") or []), 100)
        # Enrollment side parked, not primary.
        en = profile.get("enrollment_section") or {}
        self.assertTrue(en.get("facilities") is not None)
        self.assertLessEqual(len(en.get("facilities") or []), 5)


if __name__ == "__main__":
    unittest.main()
