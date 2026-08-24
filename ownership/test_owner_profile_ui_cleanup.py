"""Focused checks for owner-profile UI cleanup (summary spacing, states popover, CMS source)."""
from __future__ import annotations

import unittest

from ownership.owner_profile_html import (
    _cms_source_badge_html,
    _owner_profile_header_html,
    _states_breakdown_modal_html,
)
from ownership.portfolio_display import owner_portfolio_snapshot_html, snapshot_metric_card_html


class OwnerProfileUiCleanupTests(unittest.TestCase):
    def test_states_card_uses_help_button_not_full_card_action(self):
        html = snapshot_metric_card_html(
            "States",
            "7",
            "",
            "",
            label_short="States",
            label_suffix_html=(
                '<button type="button" class="owner-info-btn owner-states-help" '
                'data-owner-states-open>?</button>'
            ),
        )
        self.assertIn("data-owner-states-open", html)
        self.assertNotIn("owner-snapshot-card--action", html)
        self.assertIn("owner-snapshot-label", html)
        self.assertRegex(
            html,
            r'owner-snapshot-label">[\s\S]*?data-owner-states-open[\s\S]*?</div>\s*'
            r'<div class="owner-snapshot-value-row">',
        )

    def test_states_popover_markup_is_compact_list(self):
        profile = {
            "portfolio_summary": {
                "by_state": [("FL", 16), ("KY", 12), ("NJ", 8)],
            }
        }
        html = _states_breakdown_modal_html(profile)
        self.assertIn('id="ownerStatesPopover"', html)
        self.assertIn("Facilities by state", html)
        self.assertIn("owner-states-list", html)
        self.assertIn("owner-states-code", html)
        self.assertIn("owner-states-count", html)
        self.assertIn(">FL<", html)
        self.assertIn(">16<", html)
        self.assertNotIn("owner-states-modal-close", html)
        self.assertNotIn("ownerStatesModal", html)

    def test_cms_source_in_header_aside_opposite_identity(self):
        profile = {
            "associate_id": "3870870553",
            "display_name": "Nochum Freund",
            "publication_segment": "ownership_interest_only",
            "facilities": [{"pct": "100%"}],
        }
        html = _owner_profile_header_html(
            profile,
            name="Nochum Freund",
            owner_type="Individual",
            states_meta="",
            kind="owner_control",
            pac="3870870553",
            en_label="Enrollment PAC",
            ow_label="Owner PAC",
        )
        self.assertIn("owner-profile-header-main", html)
        self.assertIn("owner-profile-header-identity", html)
        self.assertIn("owner-profile-header-aside", html)
        self.assertIn("owner-cms-source", html)
        # Aside follows identity inside header-main (right column).
        id_at = html.find("owner-profile-header-identity")
        aside_at = html.find("owner-profile-header-aside")
        self.assertGreater(aside_at, id_at)
        badge = _cms_source_badge_html("3870870553")
        self.assertIn("CMS source", badge)
        self.assertIn("↗", badge)

    def test_owner_snapshot_states_help_wiring(self):
        profile = {
            "portfolio_summary": {
                "n_facilities": 52,
                "n_states": 7,
                "by_state": [("FL", 16), ("KY", 12)],
                "mean_overall": 3.2,
                "wmean_hprd": 3.1,
                "n_hprd_supported_facilities": 40,
            },
            "facilities": [{"ccn": "105001"}],
        }
        html = owner_portfolio_snapshot_html(profile)
        self.assertIn("Linked facilities", html)
        self.assertIn("data-owner-states-open", html)
        self.assertIn('aria-controls="ownerStatesPopover"', html)
        self.assertNotIn("owner-snapshot-card--action", html)


if __name__ == "__main__":
    unittest.main()
