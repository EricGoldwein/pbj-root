"""Tests for owner portfolio summary plausibility rules."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.owner_portfolio_metrics import (  # noqa: E402
    PORTFOLIO_HPRD_MAX,
    _rollup_portfolio_metrics,
    is_plausible_overall_rating,
    is_plausible_portfolio_hprd,
)


def _fac(
    *,
    hprd: str | None = "3.5",
    overall: str | None = "3",
    census: str | None = "100",
    beds: str | None = None,
    matched: bool = True,
) -> dict:
    return {
        "ccn": "075001",
        "ccn_match_method": "legal_exact" if matched else "fuzzy",
        "hprd": hprd,
        "overall_rating": overall,
        "census": census,
        "beds": beds,
        "pbj_matched": matched,
        "hprd_portfolio_inclusion_status": "supported" if matched else "uncertain",
        "role_category": "ownership_interest",
    }


def _summary(rows: list[dict]) -> dict:
    """Rollup without enrich_facilities (fixtures already carry attribution)."""
    return _rollup_portfolio_metrics(rows, context="owner")


class PortfolioPlausibilityTests(unittest.TestCase):
    def test_hprd_bounds_match_cms_current_rule(self) -> None:
        self.assertFalse(is_plausible_portfolio_hprd(0.0))
        self.assertTrue(is_plausible_portfolio_hprd(0.5))
        self.assertTrue(is_plausible_portfolio_hprd(1.49))
        self.assertTrue(is_plausible_portfolio_hprd(1.5))
        self.assertTrue(is_plausible_portfolio_hprd(PORTFOLIO_HPRD_MAX))
        self.assertFalse(is_plausible_portfolio_hprd(PORTFOLIO_HPRD_MAX + 0.01))

    def test_rating_bounds(self) -> None:
        self.assertTrue(is_plausible_overall_rating(1.0))
        self.assertTrue(is_plausible_overall_rating(5.0))
        self.assertFalse(is_plausible_overall_rating(0.0))
        self.assertFalse(is_plausible_overall_rating(6.0))

    def test_excludes_low_hprd_outlier(self) -> None:
        ps = _summary(
            [
                _fac(hprd="3.0", census="100"),
                _fac(hprd="0.0", census="100"),
            ]
        )
        self.assertEqual(ps["n_hprd_le_zero_excluded"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)
        self.assertAlmostEqual(ps["umean_hprd"], 3.0)

    def test_includes_valid_hprd_below_obsolete_1_5_floor(self) -> None:
        ps = _summary(
            [
                _fac(hprd="3.0", census="100"),
                _fac(hprd="0.5", census="100"),
            ]
        )
        self.assertEqual(ps["n_hprd_portfolio_facilities"], 2)
        self.assertEqual(ps["n_obsolete_below_1_5_included"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 1.75)

    def test_excludes_high_hprd_outlier(self) -> None:
        ps = _summary([_fac(hprd="3.0"), _fac(hprd="13.0")])
        self.assertEqual(ps["n_hprd_outlier_excluded"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)

    def test_missing_hprd_counted_not_averaged(self) -> None:
        ps = _summary([_fac(hprd="3.0"), _fac(hprd=None)])
        self.assertEqual(ps["n_missing_hprd"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)

    def test_star_distribution_counts(self) -> None:
        low_stf = _fac(overall="3", matched=True)
        low_stf["staffing_rating"] = "2"
        ps = _summary(
            [
                _fac(overall="5", matched=True),
                _fac(overall="3", matched=True),
                low_stf,
            ]
        )
        self.assertEqual(ps["n_with_overall_for_dist"], 3)
        self.assertEqual(ps["overall_star_counts"].get(5), 1)
        self.assertEqual(ps["overall_star_counts"].get(3), 2)
        self.assertEqual(ps["n_with_staffing_for_dist"], 1)
        self.assertEqual(ps["pct_low_staffing_rating"], 33)

    def test_star_distribution_render_threshold(self) -> None:
        from ownership.owner_portfolio_metrics import PORTFOLIO_STAR_DIST_MIN
        from ownership.owner_profile_html import _portfolio_distribution_html

        self.assertEqual(PORTFOLIO_STAR_DIST_MIN, 5)
        ps_small = _summary(
            [_fac(overall="5", matched=True), _fac(overall="3", matched=True)]
        )
        self.assertNotIn("owner-dist-section", _portfolio_distribution_html(ps_small))
        ps_large = _summary([_fac(overall="5", matched=True) for _ in range(5)])
        self.assertIn("owner-dist-section", _portfolio_distribution_html(ps_large))
        from ownership.owner_profile_html import _portfolio_state_distribution

        self.assertEqual("", _portfolio_state_distribution([("NY", 1)], 1))

    def test_unmatched_facility_excluded_from_means(self) -> None:
        ps = _summary(
            [
                _fac(hprd="3.0", matched=True),
                _fac(hprd="1.0", matched=False),
            ]
        )
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)

    def test_no_weight_fallback_to_one(self) -> None:
        ps = _summary(
            [
                _fac(hprd="4.0", census="200", beds=None),
                _fac(hprd="2.0", census=None, beds=None),
            ]
        )
        self.assertEqual(ps["n_missing_resident_weight"], 1)
        self.assertEqual(ps["n_hprd_weight_excluded"], 1)
        self.assertEqual(ps["n_hprd_portfolio_facilities"], 1)
        # No-weight facilities are excluded from both weighted and unweighted means;
        # n equals CCNs contributing to the weighted Portfolio HPRD.
        self.assertAlmostEqual(ps["wmean_hprd"], 4.0)
        self.assertAlmostEqual(ps["umean_hprd"], 4.0)

    def test_rating_outlier_excluded(self) -> None:
        ps = _summary(
            [
                _fac(overall="3"),
                _fac(overall="9"),
            ]
        )
        self.assertEqual(ps["n_rating_outlier_excluded"], 1)
        # Owner pages do not expose Care Compare means as owner-period performance.
        self.assertIsNone(ps["mean_overall_rating"])
        self.assertEqual(ps["overall_star_counts"].get(3), 1)
        self.assertEqual(ps["n_with_overall_for_dist"], 1)

    def test_enrollment_exact_receives_full_enrichment(self) -> None:
        """enrollment_exact CCNs must get provider enrichment, HPRD, stars, census, flags."""
        from unittest.mock import patch

        from ownership.owner_portfolio_metrics import enrich_facility_row

        fake_lookup = {
            "075001": {
                "provider_name": "Sunrise Nursing Home",
                "state": "TX",
                "city": "Houston",
                "county": "Harris",
                "beds": "120",
                "census": "105",
                "hprd": "4.2",
                "overall_rating": "4",
                "staffing_rating": "5",
                "health_inspection_rating": "3",
                "qm_rating": "4",
                "sff": "N",
                "sff_status": "N",
                "abuse_icon": "N",
                "quarter": "2026 Q1",
            }
        }
        fac = {
            "ccn": "075001",
            "ccn_match_method": "enrollment_exact",
            "facility_name": "Sunrise Nursing",
            "state": "TX",
        }
        with patch(
            "ownership.owner_portfolio_metrics._ccn_provider_lookup",
            return_value=fake_lookup,
        ):
            enriched = enrich_facility_row(fac)

        self.assertTrue(enriched.get("pbj_matched"))
        self.assertEqual(enriched.get("hprd"), "4.2")
        self.assertEqual(enriched.get("overall_rating"), "4")
        self.assertEqual(enriched.get("census"), "105")
        self.assertEqual(enriched.get("provider_name"), "Sunrise Nursing Home")
        self.assertEqual(enriched.get("county"), "Harris")
        self.assertEqual(enriched.get("sff_status"), "N")
        self.assertFalse(enriched.get("has_abuse"))

    def test_enrollment_exact_generates_verified_link(self) -> None:
        """enrollment_exact must produce a provider link in HTML tables."""
        from ownership.owner_profile_html import _facilities_owner_rows

        fac = {
            "ccn": "075001",
            "ccn_match_method": "enrollment_exact",
            "facility_name": "Sunrise Nursing",
            "provider_name": "Sunrise Nursing Home",
            "state": "TX",
            "city": "Houston",
            "county": "Harris",
            "role": "Managing Employee",
            "role_code": "43",
            "role_category": "operational_control",
            "hprd": "4.2",
            "census": "105",
            "overall_rating": "4",
            "staffing_rating": "5",
            "flags": "",
            "sff_status": "",
            "has_abuse": False,
            "pbj_matched": True,
        }
        rows = _facilities_owner_rows([fac])
        self.assertEqual(len(rows), 1)
        html = rows[0]
        self.assertIn("/provider/075001/", html)
        self.assertIn("Sunrise Nursing Home", html)


if __name__ == "__main__":
    unittest.main()
