"""State page lazy high-risk API and SSR shell guardrails."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("PBJ_SKIP_PROVIDER_PAGE_CACHE", "1")

_SAMPLE_BUCKETS = {
    "sff": [{"ccn": "015009", "name": "Alpha Care", "city": "Hartford", "status": "SFF"}],
    "sffCandidates": [],
    "oneStarOverall": [
        {"ccn": "015010", "name": "Beta Home", "city": "New Haven", "overall_rating": "1"},
    ],
    "abuse": [],
}


class TestHighRiskTablePayload(unittest.TestCase):
    def test_pagination_and_row_shape(self):
        from app import _high_risk_table_api_payload

        with patch("app.load_provider_info", return_value={}):
            page0 = _high_risk_table_api_payload(
                "NY", "all", 0, 1, _SAMPLE_BUCKETS, cy_qtr="2025Q4"
            )
        self.assertIsNotNone(page0)
        assert page0 is not None
        self.assertEqual(page0["total"], 2)
        self.assertTrue(page0["has_more"])
        self.assertIn("state-hr-facility-name", page0["rows_html"])
        self.assertIn("/provider/015009", page0["rows_html"])

        with patch("app.load_provider_info", return_value={}):
            page1 = _high_risk_table_api_payload(
                "NY", "all", 1, 1, _SAMPLE_BUCKETS, cy_qtr="2025Q4"
            )
        assert page1 is not None
        self.assertFalse(page1["has_more"])
        self.assertIn("/provider/015010", page1["rows_html"])

    def test_empty_non_all_category(self):
        from app import _high_risk_table_api_payload

        out = _high_risk_table_api_payload("NY", "abuse", 0, 10, _SAMPLE_BUCKETS)
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["rows_html"], "")
        self.assertFalse(out["has_more"])

    def test_empty_all_returns_none(self):
        from app import _high_risk_table_api_payload

        self.assertIsNone(_high_risk_table_api_payload("NY", "all", 0, 10, {}))


class TestHighRiskApiRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import app

        cls.client = app.test_client()

    def test_invalid_category_400(self):
        resp = self.client.get("/api/state/NY/high-risk-table?category=not-a-tab")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_valid_response_shape_and_header(self):
        sample = dict(_SAMPLE_BUCKETS)
        with patch("app._high_risk_buckets_for_state_page", return_value=sample):
            with patch("app.load_sff_facilities", return_value=[]):
                with patch("app.load_provider_info", return_value={}):
                    resp = self.client.get(
                        "/api/state/NY/high-risk-table?category=all&offset=0&limit=10"
                    )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("total", data)
        self.assertIn("rows_html", data)
        self.assertIn("has_more", data)
        self.assertIn("state-hr-facility-name", data["rows_html"])
        hdr = resp.headers.get("X-PBJ-High-Risk-Source") or resp.headers.get(
            "x-pbj-high-risk-source"
        )
        self.assertIn(hdr, ("aggregate_cache", "live_fallback"))

    def test_pagination_offset_via_route(self):
        sample = dict(_SAMPLE_BUCKETS)
        with patch("app._high_risk_buckets_for_state_page", return_value=sample):
            with patch("app.load_sff_facilities", return_value=[]):
                with patch("app.load_provider_info", return_value={}):
                    r0 = self.client.get(
                        "/api/state/NY/high-risk-table?category=all&offset=0&limit=1"
                    )
                    r1 = self.client.get(
                        "/api/state/NY/high-risk-table?category=all&offset=1&limit=1"
                    )
        self.assertTrue(r0.get_json()["has_more"])
        self.assertFalse(r1.get_json()["has_more"])


class TestLazyHighRiskShell(unittest.TestCase):
    def test_lazy_shell_markers(self):
        from app import _render_state_pbj_high_risk_section_lazy

        html = _render_state_pbj_high_risk_section_lazy(
            "New York",
            "NY",
            _SAMPLE_BUCKETS,
            raw_quarter="2025Q4",
        )
        self.assertIn('data-state-high-risk="1"', html)
        self.assertIn('data-state-code="NY"', html)
        self.assertIn('data-category="all"', html)
        self.assertIn("state-hr-tab-btn", html)
        self.assertIn("/api/state/", html)
        self.assertIn("Show more", html)
        self.assertNotIn('class="state-hr-facility-name"', html)
        self.assertIn("@media (max-width: 640px)", html)

    def test_empty_high_risk_omits_section(self):
        from app import _render_state_pbj_high_risk_section_lazy

        self.assertEqual(_render_state_pbj_high_risk_section_lazy("Wyoming", "WY", {}), "")


class TestStatePageOwnershipContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import app

        cls.client = app.test_client()

    def test_ny_page_retains_ownership_markers_when_enabled(self):
        from ownership.beta_gate import ownership_beta_enabled_for_state

        if not ownership_beta_enabled_for_state("NY"):
            self.skipTest("NY ownership preview not enabled in this environment")
        resp = self.client.get("/state/new-york")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("pbj-details-top-owners", body)
        self.assertIn("chow-state-block", body)
        from ownership.state_owner_index import state_index_canonical_path

        self.assertIn(state_index_canonical_path("NY").lower(), body.lower())

    def test_chow_cap_shows_full_index_link(self):
        from ownership.page_integrations import _render_state_chow_recent_table

        fake_rows = [
            {
                "chow_id": f"r{i}",
                "effective_date": "2025-01-01",
                "buyer_org_name": f"Buyer {i}",
                "seller_org_name": f"Seller {i}",
                "ccn": f"{i:06d}",
                "state": "TX",
                "buyer_owner_url": "/owners/buyer",
                "seller_owner_url": "/owners/seller",
            }
            for i in range(150)
        ]
        with patch(
            "ownership.page_integrations.chow_records_for_state",
            return_value=fake_rows,
        ):
            html = _render_state_chow_recent_table("TX")
        self.assertIn("chow-state-truncate-note", html)
        self.assertIn("Browse full TX ownership", html)

    def test_state_page_aggregate_response_header(self):
        resp = self.client.get("/state/wyoming")
        self.assertEqual(resp.status_code, 200)
        hdr = resp.headers.get("X-PBJ-State-Aggregates") or resp.headers.get(
            "x-pbj-state-aggregates"
        )
        self.assertIn(hdr, ("hydrated", "live_fallback"))


class TestWarmupAggregateDiagnostics(unittest.TestCase):
    def test_warmup_reports_explicit_aggregate_failure(self):
        from app import app

        client = app.test_client()
        resp = client.get("/warmup")
        data = resp.get_json()
        agg = data.get("checks", {}).get("state_page_aggregates", {})
        self.assertIn("bundle_exists", agg)
        self.assertIn("validation_reason", agg)
        self.assertIn("live_fallback", agg)
        self.assertIn("failure", agg)


if __name__ == "__main__":
    unittest.main()
