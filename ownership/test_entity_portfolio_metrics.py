"""Entity roster portfolio summary + display gates."""
from __future__ import annotations

import unittest

from ownership.owner_portfolio_metrics import (
    PORTFOLIO_STAR_DIST_MIN,
    build_entity_portfolio_summary,
    entity_facility_for_portfolio,
)
from ownership.portfolio_display import (
    entity_portfolio_block_html,
    portfolio_distribution_html,
)


class TestEntityPortfolioMetrics(unittest.TestCase):
    def _fac(self, ccn: str = "123456", *, hprd: float = 3.2, **extra) -> dict:
        row = {
            "ccn": ccn,
            "name": "Test NH",
            "city": "Town",
            "state": "NY",
            "Total_Nurse_HPRD": hprd,
        }
        row.update(extra)
        return row

    def _pi(self, ccn: str, **fields) -> dict:
        base = {
            "overall_rating": "3",
            "staffing_rating": "2",
            "avg_residents_per_day": "100",
        }
        base.update(fields)
        return {ccn: base}

    def test_entity_row_uses_pbj_hprd_first(self) -> None:
        fac = self._fac(hprd=4.5)
        pi = self._pi("123456", reported_total_nurse_hrs_per_resident_per_day="2.0")
        row = entity_facility_for_portfolio(fac, pi)
        self.assertEqual(row["hprd"], "4.5")
        self.assertTrue(row["pbj_matched"])

    def test_small_entity_no_star_distribution(self) -> None:
        facilities = [self._fac(ccn=f"{i:06d}") for i in range(1, 3)]
        provider_info = {
            f"{i:06d}": {"overall_rating": str(3 + (i % 2)), "staffing_rating": "2"}
            for i in range(1, 3)
        }
        ps = build_entity_portfolio_summary(facilities, provider_info)
        self.assertEqual(ps["n_with_overall_for_dist"], 2)
        self.assertNotIn("owner-dist-card", portfolio_distribution_html(ps, id_prefix="entityDist"))

    def test_large_entity_star_distribution(self) -> None:
        facilities = [self._fac(ccn=f"{i:06d}") for i in range(1, 6)]
        provider_info = {
            f"{i:06d}": {"overall_rating": "3", "staffing_rating": "2", "avg_residents_per_day": "50"}
            for i in range(1, 6)
        }
        ps = build_entity_portfolio_summary(facilities, provider_info)
        self.assertGreaterEqual(ps["n_with_overall_for_dist"], PORTFOLIO_STAR_DIST_MIN)
        html = portfolio_distribution_html(ps, id_prefix="entityDist")
        self.assertIn("owner-dist-card", html)

    def test_entity_block_includes_snapshot(self) -> None:
        facilities = [self._fac()]
        provider_info = self._pi("123456", overall_rating="4")
        ps = build_entity_portfolio_summary(facilities, provider_info)
        block = entity_portfolio_block_html(ps)
        self.assertIn("entity-portfolio-root", block)
        self.assertIn("owner-snapshot-section", block)
        self.assertIn("Overall rating", block)


if __name__ == "__main__":
    unittest.main()
