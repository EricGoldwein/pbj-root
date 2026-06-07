"""Tests for SFF entity metric cards and explainers."""
from __future__ import annotations

import unittest

from ownership.sff_display import (
    PBJ_SFF_LINK_LABEL,
    PBJ_SFF_URL,
    entity_high_risk_metrics_section_html,
    sff_info_button_html,
)


class TestSffDisplay(unittest.TestCase):
    def test_sff_info_button_has_modal_attrs(self) -> None:
        btn = sff_info_button_html("sff")
        self.assertIn('data-info-format="sff"', btn)
        self.assertIn(PBJ_SFF_URL, btn)
        self.assertIn(PBJ_SFF_LINK_LABEL, btn)
        self.assertNotIn("data-info-cms-url", btn)

    def test_entity_high_risk_section_includes_sff_cards(self) -> None:
        html = entity_high_risk_metrics_section_html(
            "Genesis Healthcare",
            sff_count=2,
            sff_cand_count=1,
            one_star_count=3,
            abuse_count=0,
            high_risk_tooltip="test tooltip",
        )
        self.assertIn("entity-high-risk-metrics", html)
        self.assertIn("Special Focus Facilities", html)
        self.assertIn("SFF Candidates", html)
        self.assertIn('data-info-format="sff"', html)
        self.assertIn(PBJ_SFF_URL, html)
