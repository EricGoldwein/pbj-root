"""Regression tests for owner-profile index back links."""
from __future__ import annotations

import unittest

from ownership.owner_profile_html import _owner_index_back_link_html


class OwnerProfileBackLinkTests(unittest.TestCase):
    def test_multistate_owner_links_to_national_owners_hub(self) -> None:
        profile = {
            "states": ["FL", "NY"],
            "portfolio_summary": {"by_state": [("FL", 12), ("NY", 2)]},
        }
        link = _owner_index_back_link_html(profile)
        self.assertIn('href="/owners"', link)
        self.assertIn('>← Owners</a>', link)
        self.assertNotIn('/owners/fl', link)

    def test_single_state_owner_keeps_state_back_link(self) -> None:
        profile = {
            "states": ["NY"],
            "portfolio_summary": {"by_state": [("NY", 4)]},
        }
        link = _owner_index_back_link_html(profile)
        self.assertIn('href="/owners/ny"', link)
        self.assertIn('>← NY owners</a>', link)

    def test_states_outside_summary_still_make_profile_multistate(self) -> None:
        profile = {
            "states": ["DE", "FL"],
            "portfolio_summary": {"by_state": [("FL", 8)]},
        }
        self.assertIn('href="/owners"', _owner_index_back_link_html(profile))


if __name__ == "__main__":
    unittest.main()
