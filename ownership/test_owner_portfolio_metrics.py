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
    PORTFOLIO_HPRD_MIN,
    build_portfolio_summary,
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
    }


class PortfolioPlausibilityTests(unittest.TestCase):
    def test_hprd_bounds_match_cms(self) -> None:
        self.assertFalse(is_plausible_portfolio_hprd(0.5))
        self.assertFalse(is_plausible_portfolio_hprd(1.49))
        self.assertTrue(is_plausible_portfolio_hprd(PORTFOLIO_HPRD_MIN))
        self.assertTrue(is_plausible_portfolio_hprd(PORTFOLIO_HPRD_MAX))
        self.assertFalse(is_plausible_portfolio_hprd(PORTFOLIO_HPRD_MAX + 0.01))

    def test_rating_bounds(self) -> None:
        self.assertTrue(is_plausible_overall_rating(1.0))
        self.assertTrue(is_plausible_overall_rating(5.0))
        self.assertFalse(is_plausible_overall_rating(0.0))
        self.assertFalse(is_plausible_overall_rating(6.0))

    def test_excludes_low_hprd_outlier(self) -> None:
        ps = build_portfolio_summary(
            [
                _fac(hprd="3.0", census="100"),
                _fac(hprd="0.4", census="100"),
            ]
        )
        self.assertEqual(ps["n_hprd_outlier_excluded"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)
        self.assertAlmostEqual(ps["umean_hprd"], 3.0)

    def test_excludes_high_hprd_outlier(self) -> None:
        ps = build_portfolio_summary([_fac(hprd="3.0"), _fac(hprd="13.0")])
        self.assertEqual(ps["n_hprd_outlier_excluded"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)

    def test_missing_hprd_counted_not_averaged(self) -> None:
        ps = build_portfolio_summary([_fac(hprd="3.0"), _fac(hprd=None)])
        self.assertEqual(ps["n_missing_hprd"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)

    def test_star_distribution_counts(self) -> None:
        low_stf = _fac(overall="3", matched=True)
        low_stf["staffing_rating"] = "2"
        ps = build_portfolio_summary(
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
        ps_small = build_portfolio_summary(
            [_fac(overall="5", matched=True), _fac(overall="3", matched=True)]
        )
        self.assertNotIn("owner-dist-card", _portfolio_distribution_html(ps_small))
        ps_large = build_portfolio_summary(
            [_fac(overall="5", matched=True) for _ in range(5)]
        )
        self.assertIn("owner-dist-card", _portfolio_distribution_html(ps_large))
        from ownership.owner_profile_html import _portfolio_state_distribution

        self.assertEqual("", _portfolio_state_distribution([("NY", 1)], 1))

    def test_unmatched_facility_excluded_from_means(self) -> None:
        ps = build_portfolio_summary(
            [
                _fac(hprd="3.0", matched=True),
                _fac(hprd="1.0", matched=False),
            ]
        )
        self.assertAlmostEqual(ps["wmean_hprd"], 3.0)

    def test_no_weight_fallback_to_one(self) -> None:
        ps = build_portfolio_summary(
            [
                _fac(hprd="4.0", census="200", beds=None),
                _fac(hprd="2.0", census=None, beds=None),
            ]
        )
        self.assertEqual(ps["n_missing_resident_weight"], 1)
        self.assertAlmostEqual(ps["wmean_hprd"], 4.0)
        self.assertAlmostEqual(ps["umean_hprd"], 3.0)

    def test_rating_outlier_excluded(self) -> None:
        ps = build_portfolio_summary(
            [
                _fac(overall="3"),
                _fac(overall="9"),
            ]
        )
        self.assertEqual(ps["n_rating_outlier_excluded"], 1)
        self.assertEqual(ps["mean_overall_rating"], 3.0)


if __name__ == "__main__":
    unittest.main()
