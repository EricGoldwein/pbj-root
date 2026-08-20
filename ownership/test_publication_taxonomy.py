"""Publication taxonomy + mid-period temporal attribution tests."""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from ownership.publication_taxonomy import (
    classify_publication_segment,
    facility_section_label,
    publication_descriptor,
    publication_title_suffix,
    schema_org_type,
)
from ownership.relationship_period import (
    PARTIAL_PERIOD_HPRD_SUPPORTED,
    parse_pbj_quarter_bounds,
    relationship_supported_for_period,
)


class PublicationTaxonomyTests(unittest.TestCase):
    def test_ownership_interest_only(self) -> None:
        profile = {
            "display_name": "Example Holdings LLC",
            "owner_type": "Organization",
            "profile_kind": "owner_control",
            "facilities": [
                {"role_category": "ownership_interest", "pct": "25"},
            ],
        }
        self.assertEqual(classify_publication_segment(profile), "ownership_interest_only")
        self.assertIn("Ownership Interest", publication_title_suffix(profile))
        self.assertIn("25%", publication_descriptor(profile))
        self.assertIn("ownership interest", facility_section_label(profile).lower())

    def test_control_no_ownership(self) -> None:
        profile = {
            "display_name": "Jane Manager",
            "owner_type": "Individual",
            "facilities": [{"role_category": "operational_control"}],
        }
        self.assertEqual(
            classify_publication_segment(profile), "control_managerial_no_ownership"
        )
        self.assertIn("Managing & Control", publication_title_suffix(profile))
        self.assertNotIn("Owner", publication_descriptor(profile))
        self.assertEqual(schema_org_type(profile), "Person")

    def test_unknown_placeholder(self) -> None:
        profile = {"display_name": "Unknown party", "facilities": []}
        self.assertEqual(classify_publication_segment(profile), "unknown_placeholder")

    def test_chow_only(self) -> None:
        profile = {
            "display_name": "Buyer Co LLC",
            "profile_kind": "chow_only",
            "is_chow_only": True,
            "chow_transactions": [{"chow_role": "buyer"}],
            "facilities": [],
        }
        self.assertEqual(classify_publication_segment(profile), "chow_enrollment_party")
        self.assertIn("buyer", publication_descriptor(profile).lower())


class MidPeriodTemporalTests(unittest.TestCase):
    def test_partial_period_flag_false(self) -> None:
        self.assertFalse(PARTIAL_PERIOD_HPRD_SUPPORTED)

    def test_timing_matrix(self) -> None:
        start, end = parse_pbj_quarter_bounds("Q1 2026")
        assert start and end
        cases = [
            ("12/31/2025", "supported"),
            ("01/01/2026", "supported"),
            ("02/01/2026", "uncertain"),
            ("03/31/2026", "uncertain"),
            ("04/01/2026", "exclude"),
        ]
        for assoc, expect in cases:
            with self.subTest(assoc=assoc):
                self.assertEqual(
                    relationship_supported_for_period(
                        assoc,
                        start,
                        end,
                        metric_kind="pbj_hprd",
                        relationship_kind="ownership_interest",
                    ),
                    expect,
                )


if __name__ == "__main__":
    unittest.main()
