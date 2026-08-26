"""Portfolio HPRD: timing-only linked-facility inclusion (any CMS role)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.owner_portfolio_metrics import (  # noqa: E402
    PORTFOLIO_HPRD_CARD_HELP,
    build_portfolio_summary,
    classify_portfolio_hprd_terminal_bucket,
    is_plausible_portfolio_hprd,
    reconcile_portfolio_hprd_buckets,
)
from ownership.portfolio_display import portfolio_snapshot_section_html  # noqa: E402
from ownership.relationship_period import (  # noqa: E402
    hprd_portfolio_inclusion_from_roles,
    parse_pbj_quarter_bounds,
    portfolio_inclusion_status_for_facility,
    relationship_supported_for_period,
)


def _bounds():
    b = parse_pbj_quarter_bounds("Q1 2026")
    assert b is not None
    return b


def _role(
    code: str,
    category: str,
    assoc: str,
    *,
    role: str = "",
) -> dict:
    return {
        "role": role or f"Role {code}",
        "role_code": code,
        "role_category": category,
        "association_date": assoc,
    }


class PortfolioHprdValidityTests(unittest.TestCase):
    def test_zero_hprd_excluded(self) -> None:
        self.assertFalse(is_plausible_portfolio_hprd(0.0))

    def test_valid_below_1_5_included(self) -> None:
        self.assertTrue(is_plausible_portfolio_hprd(0.5))
        self.assertTrue(is_plausible_portfolio_hprd(1.49))

    def test_exactly_1_5_included(self) -> None:
        self.assertTrue(is_plausible_portfolio_hprd(1.5))

    def test_exactly_12_included(self) -> None:
        self.assertTrue(is_plausible_portfolio_hprd(12.0))

    def test_greater_than_12_excluded(self) -> None:
        self.assertFalse(is_plausible_portfolio_hprd(12.01))
        self.assertFalse(is_plausible_portfolio_hprd(13.0))


class PortfolioHprdInclusionTests(unittest.TestCase):
    def test_active_governance_only_ccn_included(self) -> None:
        start, end = _bounds()
        roles = [_role("40", "corporate_governance", "01/01/2015")]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "supported")
        self.assertEqual(
            relationship_supported_for_period(
                "01/01/2015",
                start,
                end,
                metric_kind="pbj_hprd",
                relationship_kind="governance",
                role_code="40",
            ),
            "supported",
        )

    def test_active_adp_only_ccn_included(self) -> None:
        start, end = _bounds()
        roles = [_role("72", "administrative_disclosure", "06/01/2019")]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "supported")

    def test_active_financial_other_role_ccn_included(self) -> None:
        start, end = _bounds()
        for code, cat in (
            ("36", "financial_interest"),
            ("37", "financial_interest"),
            ("44", "other"),
            ("25", "operational_control"),
            ("42", "operational_control"),
        ):
            with self.subTest(code=code):
                roles = [_role(code, cat, "01/01/2020")]
                self.assertEqual(
                    hprd_portfolio_inclusion_from_roles(roles, start, end),
                    "supported",
                )

    def test_post_quarter_relationship_excluded(self) -> None:
        start, end = _bounds()
        roles = [_role("40", "corporate_governance", "05/01/2026")]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "exclude")

    def test_missing_timing_uncertain(self) -> None:
        start, end = _bounds()
        roles = [_role("43", "operational_control", "")]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "uncertain")

    def test_one_active_plus_one_later_includes_once(self) -> None:
        start, end = _bounds()
        roles = [
            _role("40", "corporate_governance", "01/01/2018"),
            _role("43", "operational_control", "05/01/2026"),
        ]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "supported")

    def test_dual_40_plus_63_qualifies_via_earliest_timing(self) -> None:
        start, end = _bounds()
        roles = [
            _role("40", "corporate_governance", "01/01/2020"),
            _role("63", "operational_control", "06/01/2019"),
        ]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "supported")

    def test_role_specific_dates_later_does_not_override_earlier(self) -> None:
        start, end = _bounds()
        roles = [
            _role("40", "corporate_governance", "05/01/2026"),
            _role("72", "administrative_disclosure", "01/01/2020"),
        ]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "supported")

    def test_early_40_plus_post_quarter_43_still_includes_via_40(self) -> None:
        start, end = _bounds()
        roles = [
            _role("40", "corporate_governance", "01/01/2015"),
            _role("43", "operational_control", "05/01/2026"),
        ]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "supported")

    def test_mid_quarter_plus_post_quarter_is_uncertain(self) -> None:
        start, end = _bounds()
        roles = [
            _role("43", "operational_control", "02/15/2026"),
            _role("63", "operational_control", "05/01/2026"),
        ]
        self.assertEqual(hprd_portfolio_inclusion_from_roles(roles, start, end), "uncertain")

    def test_duplicate_roles_never_duplicate_weight(self) -> None:
        facilities = [
            {
                "ccn": "123456",
                "facility_name": "Dual Role NH",
                "state": "TX",
                "ccn_match_method": "enrollment_exact",
                "pbj_matched": True,
                "hprd": "4.0",
                "census": "100",
                "role_code": "40",
                "role_category": "corporate_governance",
                "association_date": "01/01/2020",
                "roles": [
                    _role("40", "corporate_governance", "01/01/2020"),
                    _role("63", "operational_control", "01/01/2019"),
                ],
                "hprd_portfolio_inclusion_status": "supported",
            }
        ]
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(facilities)
        self.assertEqual(ps.get("n_facilities"), 1)
        self.assertEqual(ps.get("n_hprd_portfolio_facilities"), 1)
        self.assertAlmostEqual(ps.get("wmean_hprd"), 4.0)

    def test_unmatched_pbj_and_invalid_hprd_excluded(self) -> None:
        facilities = [
            {
                "ccn": "000001",
                "facility_name": "Unmatched",
                "state": "TX",
                "pbj_matched": False,
                "hprd": "4.0",
                "census": "100",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "000002",
                "facility_name": "Outlier",
                "state": "TX",
                "pbj_matched": True,
                "hprd": "13.0",
                "census": "100",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "000003",
                "facility_name": "Good",
                "state": "TX",
                "pbj_matched": True,
                "hprd": "3.5",
                "census": "50",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "000004",
                "facility_name": "LowButValid",
                "state": "TX",
                "pbj_matched": True,
                "hprd": "0.8",
                "census": "50",
                "hprd_portfolio_inclusion_status": "supported",
            },
        ]
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(facilities)
        self.assertEqual(ps.get("n_hprd_portfolio_facilities"), 2)
        self.assertEqual(ps.get("n_hprd_gt_12_excluded"), 1)
        self.assertEqual(ps.get("n_obsolete_below_1_5_included"), 1)
        # (3.5*50 + 0.8*50) / 100 = 2.15
        self.assertAlmostEqual(ps.get("wmean_hprd"), 2.15)

    def test_rendered_n_equals_contributing_ccn_count(self) -> None:
        ps = {
            "n_facilities": 10,
            "n_pbj_matched": 8,
            "n_states": 2,
            "wmean_hprd": 3.5,
            "umean_hprd": 3.5,
            "n_hprd_supported_facilities": 1,
            "n_hprd_portfolio_facilities": 1,
            "by_state": [("TX", 6), ("CA", 4)],
            "overall_star_counts": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "staffing_star_counts": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        }
        html = portfolio_snapshot_section_html(ps, context="owner")
        self.assertIn("Portfolio HPRD", html)
        self.assertIn("n = 1", html)
        self.assertIn(PORTFOLIO_HPRD_CARD_HELP[:40], html)
        self.assertNotIn("Weighted HPRD", html)

    def test_portfolio_inclusion_status_for_facility_uses_roles_list(self) -> None:
        start, end = _bounds()
        fac = {
            "role_code": "40",
            "role_category": "corporate_governance",
            "association_date": "05/01/2026",
            "roles": [
                _role("40", "corporate_governance", "05/01/2026"),
                _role("72", "administrative_disclosure", "01/01/2018"),
            ],
        }
        self.assertEqual(
            portfolio_inclusion_status_for_facility(
                fac, metric_start=start, metric_end=end, metric_kind="pbj_hprd"
            ),
            "supported",
        )

    def test_terminal_buckets_are_mutually_exclusive(self) -> None:
        facilities = [
            {
                "ccn": "1",
                "pbj_matched": True,
                "hprd": "4",
                "census": "10",
                "hprd_portfolio_inclusion_status": "exclude",
            },
            {
                "ccn": "2",
                "pbj_matched": False,
                "hprd": "4",
                "census": "10",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "3",
                "pbj_matched": True,
                "hprd": None,
                "census": "10",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "4",
                "pbj_matched": True,
                "hprd": "0",
                "census": "10",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "5",
                "pbj_matched": True,
                "hprd": "13",
                "census": "10",
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "6",
                "pbj_matched": True,
                "hprd": "3",
                "census": None,
                "beds": None,
                "hprd_portfolio_inclusion_status": "supported",
            },
            {
                "ccn": "7",
                "pbj_matched": True,
                "hprd": "0.9",
                "census": "10",
                "hprd_portfolio_inclusion_status": "supported",
            },
        ]
        recon = reconcile_portfolio_hprd_buckets(facilities)
        self.assertTrue(recon["reconcile_ok"])
        self.assertEqual(recon["total_unique_ccns"], 7)
        self.assertEqual(recon["buckets"]["timing_excluded_or_uncertain"], 1)
        self.assertEqual(recon["buckets"]["pbj_match_excluded"], 1)
        self.assertEqual(recon["buckets"]["missing_hprd"], 1)
        self.assertEqual(recon["buckets"]["hprd_le_zero"], 1)
        self.assertEqual(recon["buckets"]["hprd_gt_12"], 1)
        self.assertEqual(recon["buckets"]["missing_invalid_weight"], 1)
        self.assertEqual(recon["buckets"]["included"], 1)
        self.assertEqual(recon["obsolete_below_1_5_now_included"], 1)
        self.assertEqual(
            classify_portfolio_hprd_terminal_bucket(facilities[-1]), "included"
        )


class PortfolioHprdLivePacTests(unittest.TestCase):
    """Exact Burnam / Landa / Mitchell Portfolio HPRD results with exclusive buckets."""

    EXPECTED = {
        "9739195553": None,  # filled after first compute in setUpModule pattern
        "7810804515": None,
        "0648429498": None,
    }

    def _reconcile(self, pac: str) -> dict:
        from ownership.owner_profile import load_owner_profile_resolved
        from ownership.owner_portfolio_metrics import (
            _parse_float,
            _portfolio_metric_weight,
            reconcile_portfolio_hprd_buckets,
        )

        profile = load_owner_profile_resolved(pac)
        self.assertIsNotNone(profile)
        assert profile is not None
        facs = list(profile.get("facilities") or [])
        recon = reconcile_portfolio_hprd_buckets(facs)
        self.assertTrue(recon["reconcile_ok"], msg=recon)
        buckets = recon["buckets"]
        included_facs = [
            f
            for f in facs
            if classify_portfolio_hprd_terminal_bucket(f) == "included"
        ]
        num = sum(
            _parse_float(f["hprd"]) * _portfolio_metric_weight(f) for f in included_facs
        )
        den = sum(_portfolio_metric_weight(f) for f in included_facs)
        wmean = num / den if den else None
        return {
            "profile": profile,
            "recon": recon,
            "buckets": buckets,
            "included": len(included_facs),
            "num": num,
            "den": den,
            "wmean": wmean,
        }

    def test_burnam_exclusive_reconciliation(self) -> None:
        from ownership.owner_profile_html import render_owner_profile_body

        r = self._reconcile("9739195553")
        b = r["buckets"]
        self.assertEqual(r["recon"]["total_unique_ccns"], 351)
        self.assertEqual(
            sum(b.values()),
            351,
        )
        # Timing first: unmatched CCN with exclude status is timing, not PBJ.
        self.assertEqual(b["timing_excluded_or_uncertain"], 12)
        self.assertEqual(b["pbj_match_excluded"], 0)
        self.assertEqual(b["missing_hprd"], 5)
        self.assertEqual(b["hprd_le_zero"], 0)
        self.assertEqual(b["hprd_gt_12"], 0)
        self.assertEqual(b["missing_invalid_weight"], 0)
        self.assertEqual(b["included"], 334)
        self.assertEqual(r["included"], 334)
        ps = r["profile"].get("portfolio_summary") or {}
        self.assertEqual(ps.get("n_hprd_portfolio_facilities"), 334)
        self.assertEqual(ps.get("hprd_terminal_buckets"), b)
        self.assertAlmostEqual(float(ps.get("wmean_hprd") or 0), round(r["wmean"], 3), places=3)
        body, *_ = render_owner_profile_body(r["profile"])
        self.assertIn("Portfolio HPRD", body)
        self.assertIn(f"n = {r['included']}", body)
        # No attribution-field aliasing on enriched rows.
        for f in r["profile"].get("facilities") or []:
            self.assertIn("hprd_portfolio_inclusion_status", f)
            self.assertNotIn("hprd_attribution_status", f)
            self.assertNotIn("attribution_status", f)

    def test_landa_exclusive_reconciliation(self) -> None:
        from ownership.owner_profile_html import render_owner_profile_body

        r = self._reconcile("7810804515")
        b = r["buckets"]
        self.assertEqual(r["recon"]["total_unique_ccns"], 106)
        self.assertEqual(sum(b.values()), 106)
        self.assertEqual(b["timing_excluded_or_uncertain"], 0)
        self.assertEqual(b["pbj_match_excluded"], 0)
        self.assertEqual(b["missing_hprd"], 2)
        self.assertEqual(b["included"], 104)
        ps = r["profile"].get("portfolio_summary") or {}
        self.assertEqual(ps.get("n_hprd_portfolio_facilities"), 104)
        body, *_ = render_owner_profile_body(r["profile"])
        self.assertIn("n = 104", body)

    def test_mitchell_exclusive_reconciliation(self) -> None:
        from ownership.owner_profile_html import render_owner_profile_body

        r = self._reconcile("0648429498")
        b = r["buckets"]
        self.assertEqual(r["recon"]["total_unique_ccns"], 274)
        self.assertEqual(sum(b.values()), 274)
        self.assertEqual(b["included"] + b["timing_excluded_or_uncertain"]
                         + b["pbj_match_excluded"] + b["missing_hprd"]
                         + b["hprd_le_zero"] + b["hprd_gt_12"]
                         + b["missing_invalid_weight"], 274)
        ps = r["profile"].get("portfolio_summary") or {}
        self.assertEqual(ps.get("n_hprd_portfolio_facilities"), b["included"])
        body, *_ = render_owner_profile_body(r["profile"])
        self.assertIn(f"n = {b['included']}", body)


if __name__ == "__main__":
    unittest.main()
