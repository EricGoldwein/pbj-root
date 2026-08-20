"""Tests for canonical ownership store materialization helpers."""
from __future__ import annotations

import unittest

from ownership.canonical_store import _schema_type_for_person_org, _shared_oi_pacs
from ownership.owner_indexability import classify_owner_profile


class CanonicalStoreHelpersTests(unittest.TestCase):
    def test_schema_type(self):
        self.assertEqual(_schema_type_for_person_org("I"), "Person")
        self.assertEqual(_schema_type_for_person_org("O"), "Organization")

    def test_shared_oi(self):
        shared = _shared_oi_pacs([("1111111111", "010001"), ("2222222222", "010001"), ("3333333333", "020002")])
        self.assertIn("1111111111", shared)
        self.assertIn("2222222222", shared)
        self.assertNotIn("3333333333", shared)

    def test_synthetic_profile_classifies_like_full(self):
        profile = {
            "associate_id": "7810804515",
            "display_name": "Benjamin Landa",
            "states": ["NY"],
            "facilities": [
                {"ccn": "111111", "state": "NY", "pbj_matched": True, "role_category": "ownership_interest"},
                {"ccn": "222222", "state": "NY", "pbj_matched": True, "role_category": "ownership_interest"},
            ],
            "portfolio_summary": {"n_facilities": 2, "n_states": 1},
            "profile_kind": "owner",
            "related_associates": [],
            "control_parties": [],
            "chow_transactions": [],
        }
        cl, reason, meta = classify_owner_profile(profile)
        self.assertEqual(cl, "index")
        self.assertEqual(meta["active_facility_count"], 2)
        self.assertIn("two_or_more", reason)


if __name__ == "__main__":
    unittest.main()
