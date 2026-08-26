"""Role-aware CCN HPRD attribution: dual roles, role-specific dates, one weight."""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.owner_portfolio_metrics import (  # noqa: E402
    build_portfolio_summary,
    enrich_facility_row,
)
from ownership.relationship_period import (  # noqa: E402
    attribution_status_for_facility,
    hprd_attribution_from_roles,
    parse_pbj_quarter_bounds,
    relationship_supported_for_period,
)


def _bounds():
    b = parse_pbj_quarter_bounds("Q1 2026")
    assert b is not None
    return b


class RoleAwareHprdAttributionTests(unittest.TestCase):
    def test_dual_40_plus_63_qualifies_via_63_date(self) -> None:
        start, end = _bounds()
        roles = [
            {
                "role": "Corporate Officer",
                "role_code": "40",
                "role_category": "corporate_governance",
                "association_date": "01/01/2020",
            },
            {
                "role": "Managing Control - Governing Body",
                "role_code": "63",
                "role_category": "operational_control",
                "association_date": "06/01/2019",
            },
        ]
        # Governance alone would not qualify; 63 with full-period date does.
        self.assertEqual(
            relationship_supported_for_period(
                "01/01/2020",
                start,
                end,
                metric_kind="pbj_hprd",
                relationship_kind="governance",
                role_code="40",
            ),
            "uncertain",
        )
        self.assertEqual(
            hprd_attribution_from_roles(roles, start, end),
            "supported",
        )

    def test_dual_40_plus_43_qualifies_via_43_date(self) -> None:
        start, end = _bounds()
        roles = [
            {
                "role": "Corporate Officer",
                "role_code": "40",
                "role_category": "corporate_governance",
                "association_date": "01/01/2018",
            },
            {
                "role": "Operational/Managerial Control",
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "12/31/2025",
            },
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "supported")

    def test_role_specific_dates_not_shared_facility_date(self) -> None:
        """Late governance date must not poison an earlier qualifying 43 date."""
        start, end = _bounds()
        roles = [
            {
                "role": "Corporate Officer",
                "role_code": "40",
                "role_category": "corporate_governance",
                # After quarter end — would be exclude if this date were used for 43.
                "association_date": "05/01/2026",
            },
            {
                "role": "Operational/Managerial Control",
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "01/01/2020",
            },
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "supported")
        # First-seen-only (40 after end) must not be the attribution rule.
        self.assertEqual(
            relationship_supported_for_period(
                roles[0]["association_date"],
                start,
                end,
                metric_kind="pbj_hprd",
                relationship_kind="governance",
                role_code="40",
            ),
            "uncertain",
        )

    def test_governance_only_visible_but_not_supported(self) -> None:
        start, end = _bounds()
        roles = [
            {
                "role": "Corporate Officer",
                "role_code": "40",
                "role_category": "corporate_governance",
                "association_date": "01/01/2015",
            },
            {
                "role": "Corporate Director",
                "role_code": "41",
                "role_category": "corporate_governance",
                "association_date": "01/01/2016",
            },
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "uncertain")

    def test_qualifying_43_after_quarter_end_excludes(self) -> None:
        start, end = _bounds()
        roles = [
            {
                "role": "Operational/Managerial Control",
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "05/01/2026",
            }
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "exclude")

    def test_one_ccn_one_weight_even_with_dual_qualifying_roles(self) -> None:
        """Dual 43+63 on one CCN contributes a single weighted row."""
        facilities = [
            {
                "ccn": "123456",
                "facility_name": "Dual Control NH",
                "state": "TX",
                "ccn_match_method": "enrollment_exact",
                "pbj_matched": True,
                "hprd": "4.0",
                "census": "100",
                "role": "Operational/Managerial Control; Managing Control - Governing Body",
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "01/01/2020",
                "roles": [
                    {
                        "role": "Operational/Managerial Control",
                        "role_code": "43",
                        "role_category": "operational_control",
                        "association_date": "01/01/2020",
                    },
                    {
                        "role": "Managing Control - Governing Body",
                        "role_code": "63",
                        "role_category": "operational_control",
                        "association_date": "01/01/2019",
                    },
                ],
                "hprd_attribution_status": "supported",
            }
        ]
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(facilities)
        self.assertEqual(ps.get("n_facilities"), 1)
        self.assertEqual(ps.get("n_hprd_supported_facilities"), 1)
        self.assertAlmostEqual(ps.get("wmean_hprd"), 4.0)

    def test_attribution_status_for_facility_uses_roles_list(self) -> None:
        start, end = _bounds()
        fac = {
            "role_code": "40",
            "role_category": "corporate_governance",
            "association_date": "05/01/2026",
            "roles": [
                {
                    "role_code": "40",
                    "role_category": "corporate_governance",
                    "association_date": "05/01/2026",
                },
                {
                    "role_code": "63",
                    "role_category": "operational_control",
                    "association_date": "01/01/2018",
                },
            ],
        }
        self.assertEqual(
            attribution_status_for_facility(
                fac, metric_start=start, metric_end=end, metric_kind="pbj_hprd"
            ),
            "supported",
        )

    def test_early_40_plus_post_quarter_43_excludes(self) -> None:
        """Early governance + post-quarter 43 → exclude (no supported qualifying role)."""
        start, end = _bounds()
        roles = [
            {
                "role_code": "40",
                "role_category": "corporate_governance",
                "association_date": "01/01/2015",
            },
            {
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "05/01/2026",
            },
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "exclude")

    def test_early_40_plus_post_quarter_63_excludes(self) -> None:
        start, end = _bounds()
        roles = [
            {
                "role_code": "40",
                "role_category": "corporate_governance",
                "association_date": "01/01/2015",
            },
            {
                "role_code": "63",
                "role_category": "operational_control",
                "association_date": "04/15/2026",
            },
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "exclude")

    def test_mid_quarter_plus_post_quarter_qualifying_is_uncertain(self) -> None:
        """Mid-quarter 43 + post-quarter 63 → uncertain (qualifying uncertain beats exclude)."""
        start, end = _bounds()
        roles = [
            {
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "02/15/2026",
            },
            {
                "role_code": "63",
                "role_category": "operational_control",
                "association_date": "05/01/2026",
            },
        ]
        self.assertEqual(hprd_attribution_from_roles(roles, start, end), "uncertain")

    def test_weighted_hprd_label_when_n_hprd_is_one(self) -> None:
        from ownership.portfolio_display import portfolio_snapshot_section_html

        ps = {
            "n_facilities": 10,
            "n_pbj_matched": 8,
            "n_states": 2,
            "wmean_hprd": 3.5,
            "umean_hprd": 3.5,
            "n_hprd_supported_facilities": 1,
            "hprd_eligible_label": "PBJ HPRD across 1 facility with supported ownership-period overlap",
            "by_state": [("TX", 6), ("CA", 4)],
            "overall_star_counts": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "staffing_star_counts": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        }
        html = portfolio_snapshot_section_html(ps, context="owner")
        self.assertIn("Weighted HPRD", html)
        self.assertIn("n = 1", html)
        self.assertIn("owner-snapshot-sub", html)

    def test_one_ccn_multiple_qualifying_roles_single_weight_row(self) -> None:
        """OI + 43 + 63 on one CCN still yields exactly one weighted contribution."""
        facilities = [
            {
                "ccn": "999001",
                "facility_name": "Triple Role NH",
                "state": "FL",
                "ccn_match_method": "enrollment_exact",
                "pbj_matched": True,
                "hprd": "3.25",
                "census": "80",
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "01/01/2018",
                "roles": [
                    {
                        "role_code": "35",
                        "role_category": "ownership_interest",
                        "association_date": "01/01/2017",
                    },
                    {
                        "role_code": "43",
                        "role_category": "operational_control",
                        "association_date": "01/01/2018",
                    },
                    {
                        "role_code": "63",
                        "role_category": "operational_control",
                        "association_date": "01/01/2019",
                    },
                ],
                "hprd_attribution_status": "supported",
            },
            {
                "ccn": "999001",  # duplicate CCN must not double-count if present
                "facility_name": "Triple Role NH Dup",
                "state": "FL",
                "ccn_match_method": "enrollment_exact",
                "pbj_matched": True,
                "hprd": "3.25",
                "census": "80",
                "role_code": "43",
                "role_category": "operational_control",
                "association_date": "01/01/2018",
                "roles": [
                    {
                        "role_code": "43",
                        "role_category": "operational_control",
                        "association_date": "01/01/2018",
                    }
                ],
                "hprd_attribution_status": "supported",
            },
        ]
        # Production rollup is per facility row; profile dedupes to one row per CCN.
        # Assert the intended one-CCN universe (deduped) contributes once.
        deduped = {f["ccn"]: f for f in facilities}
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(list(deduped.values()))
        self.assertEqual(ps.get("n_facilities"), 1)
        self.assertEqual(ps.get("n_hprd_supported_facilities"), 1)
        self.assertAlmostEqual(ps.get("wmean_hprd"), 3.25)


if __name__ == "__main__":
    unittest.main()
