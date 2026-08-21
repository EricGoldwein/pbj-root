"""Regression: portfolio_snapshot_section_html always binds dist_prefix."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.portfolio_display import (  # noqa: E402
    owner_portfolio_snapshot_html,
    portfolio_snapshot_section_html,
)


def _ps_with_dist(*, n: int = 12, n_states: int = 3) -> dict:
    # Enough rated facilities for distribution bars (PORTFOLIO_STAR_DIST_MIN).
    overall = {1: 1, 2: 2, 3: 3, 4: 3, 5: 3}
    staffing = {1: 2, 2: 2, 3: 2, 4: 3, 5: 3}
    return {
        "n_facilities": n,
        "n_states": n_states,
        "by_state": [("FL", 5), ("NY", 4), ("TX", 3)][:n_states],
        "wmean_hprd": 3.45,
        "n_hprd_supported_facilities": n,
        "n_with_overall_for_dist": n,
        "n_with_staffing_for_dist": n,
        "overall_star_counts": overall,
        "staffing_star_counts": staffing,
    }


class PortfolioSnapshotDistPrefixTests(unittest.TestCase):
    def test_owner_with_distribution_uses_ownerDist_ids(self) -> None:
        html = portfolio_snapshot_section_html(_ps_with_dist(), context="owner")
        self.assertIn("Linked facilities", html)
        self.assertIn("ownerDistTabOverall", html)
        self.assertIn("ownerDistPanelOverall", html)
        self.assertNotIn("entityDist", html)
        self.assertIn("CMS ratings", html)

    def test_owner_without_distribution_still_renders(self) -> None:
        ps = {
            "n_facilities": 2,
            "n_states": 1,
            "by_state": [("FL", 2)],
            "wmean_hprd": 3.1,
            "n_hprd_supported_facilities": 2,
            "n_with_overall_for_dist": 0,
            "n_with_staffing_for_dist": 0,
            "overall_star_counts": {},
            "staffing_star_counts": {},
        }
        html = portfolio_snapshot_section_html(ps, context="owner")
        self.assertIn("Linked facilities", html)
        self.assertIn("States", html)
        self.assertNotIn("ownerDistTabOverall", html)

    def test_entity_uses_entityDist_ids(self) -> None:
        html = portfolio_snapshot_section_html(_ps_with_dist(), context="entity")
        self.assertIn("entityDistTabOverall", html)
        self.assertNotIn("ownerDistTabOverall", html)

    def test_owner_portfolio_snapshot_html_wrapper(self) -> None:
        profile = {
            "portfolio_summary": _ps_with_dist(),
            "publication_segment": "ownership_interest_only",
        }
        html = owner_portfolio_snapshot_html(profile)
        self.assertIn("Ownership-interest facilities", html)
        self.assertIn("ownerDistTabOverall", html)


if __name__ == "__main__":
    unittest.main()
