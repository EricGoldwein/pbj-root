"""Tests for owner page indexability classification."""
from __future__ import annotations

import unittest

from ownership.owner_indexability import (
    classify_owner_profile,
    is_suppress_owner_name,
    meaningful_context_flags,
)


def _fac(**kwargs):
    base = {"ccn": "123456", "state": "NY", "pbj_matched": True}
    base.update(kwargs)
    return base


class OwnerIndexabilityTests(unittest.TestCase):
    def test_suppress_blank_name(self):
        self.assertTrue(is_suppress_owner_name(""))
        self.assertTrue(is_suppress_owner_name("Unknown"))

    def test_index_two_active_facilities(self):
        profile = {
            "associate_id": "7810804515",
            "display_name": "Benjamin Landa",
            "states": ["NY"],
            "facilities": [_fac(ccn="111111"), _fac(ccn="222222")],
            "portfolio_summary": {"n_states": 1},
        }
        cl, reason, meta = classify_owner_profile(profile)
        self.assertEqual(cl, "index")
        self.assertEqual(meta["active_facility_count"], 2)
        self.assertIn("two_or_more", reason)

    def test_index_single_with_abuse(self):
        profile = {
            "associate_id": "1234567890",
            "display_name": "Acme Holdings LLC",
            "states": ["CT"],
            "facilities": [_fac(has_abuse=True)],
        }
        cl, reason, _meta = classify_owner_profile(profile)
        self.assertEqual(cl, "index")
        self.assertIn("abuse", reason)

    def test_noindex_single_no_context(self):
        profile = {
            "associate_id": "1234567890",
            "display_name": "Acme Holdings LLC",
            "states": ["CT"],
            "facilities": [_fac()],
        }
        cl, reason, _meta = classify_owner_profile(profile)
        self.assertEqual(cl, "noindex_follow")
        self.assertEqual(reason, "single_facility_no_context")

    def test_meaningful_chow_flag(self):
        profile = {
            "display_name": "Buyer Org",
            "chow_transactions": [{"effective_date": "2025-01-15"}],
            "facilities": [],
        }
        flags = meaningful_context_flags(profile)
        self.assertIn("recent_chow", flags)


if __name__ == "__main__":
    unittest.main()
