"""HPRD supported-denominator visibility on owner portfolio cards."""
from __future__ import annotations

import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.owner_portfolio_metrics import (  # noqa: E402
    _parse_float,
    build_portfolio_summary,
    is_plausible_portfolio_hprd,
)
from ownership.portfolio_display import portfolio_snapshot_section_html  # noqa: E402
from ownership.role_classification import (  # noqa: E402
    CATEGORY_ADMIN,
    CATEGORY_FINANCIAL,
    CATEGORY_GOVERNANCE,
    CATEGORY_OPERATIONAL,
    CATEGORY_OTHER,
    CATEGORY_OWNERSHIP,
)


def _fac(
    *,
    ccn: str,
    hprd: str = "4.0",
    census: str = "100",
    matched: bool = True,
    attribution: str = "supported",
    role_category: str = "ownership_interest",
    state: str = "TX",
) -> dict:
    return {
        "ccn": ccn,
        "facility_name": f"NH {ccn}",
        "state": state,
        "ccn_match_method": "legal_exact" if matched else "fuzzy",
        "hprd": hprd,
        "census": census,
        "pbj_matched": matched,
        "hprd_attribution_status": attribution,
        "role_category": role_category,
        "overall_rating": "3",
        "staffing_rating": "3",
    }


def _tax_bucket(cat: str) -> str:
    mapping = {
        CATEGORY_OWNERSHIP: "ownership_interest",
        CATEGORY_OPERATIONAL: "managing_control",
        CATEGORY_GOVERNANCE: "governance",
        CATEGORY_ADMIN: "enrollment_admin",
        CATEGORY_FINANCIAL: "other",
        CATEGORY_OTHER: "other",
        "": "other",
    }
    return mapping.get(str(cat or "").strip(), "other")


def _hprd_bucket(fac: dict) -> str:
    status = str(fac.get("hprd_attribution_status") or "").strip()
    if not fac.get("pbj_matched"):
        return "missing_pbj"
    if status == "exclude":
        return "exclude"
    if status == "supported":
        h = _parse_float(fac.get("hprd"))
        if h is None or not is_plausible_portfolio_hprd(h):
            return "missing_pbj"
        return "supported"
    return "uncertain"


class HprdVisibleDenominatorTests(unittest.TestCase):
    def test_visible_sublabel_uses_supported_not_linked_count(self) -> None:
        facilities = [
            _fac(ccn="000001", attribution="supported"),
            _fac(ccn="000002", attribution="supported"),
            _fac(ccn="000003", attribution="uncertain"),
            _fac(ccn="000004", attribution="exclude"),
        ]
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(facilities)
        self.assertEqual(ps.get("n_facilities"), 4)
        self.assertEqual(ps.get("n_hprd_supported_facilities"), 2)
        html = portfolio_snapshot_section_html(ps, context="owner")
        self.assertIn("2 qualifying facilities", html)
        self.assertIn("owner-snapshot-sublabel", html)
        self.assertIn("Linked facilities", html)
        self.assertNotIn("4 qualifying", html)
        self.assertIn(
            "Owner-level PBJ staffing metrics use only qualifying facilities",
            html,
        )

    def test_control_only_shows_no_owner_hprd_mean(self) -> None:
        facilities = [
            _fac(
                ccn="000010",
                attribution="uncertain",
                role_category="operational_control",
            ),
            _fac(
                ccn="000011",
                attribution="uncertain",
                role_category="operational_control",
            ),
        ]
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(facilities)
        self.assertEqual(ps.get("n_hprd_supported_facilities"), 0)
        self.assertIsNone(ps.get("wmean_hprd"))
        html = portfolio_snapshot_section_html(ps, context="owner")
        self.assertNotIn("Weighted nurse HPRD", html)
        self.assertNotIn("qualifying facilit", html)

    def test_mitchell_274_reconciles_to_two_supported_hprd(self) -> None:
        """Exact taxonomy + HPRD eligibility reconciliation for PAC 0648429498."""
        from ownership.owner_profile import load_owner_profile_resolved
        from ownership.owner_profile_html import render_owner_profile_body

        profile = load_owner_profile_resolved("0648429498")
        self.assertIsNotNone(profile)
        assert profile is not None
        facs = list(profile.get("facilities") or [])
        self.assertEqual(len(facs), 274)
        tax = Counter(_tax_bucket(f.get("role_category")) for f in facs)
        self.assertEqual(sum(tax.values()), 274)
        self.assertEqual(tax.get("ownership_interest"), 2)
        self.assertEqual(tax.get("managing_control"), 45)
        self.assertEqual(tax.get("governance"), 227)
        self.assertEqual(tax.get("enrollment_admin", 0), 0)
        oi = [f for f in facs if _tax_bucket(f.get("role_category")) == "ownership_interest"]
        hprd = Counter(_hprd_bucket(f) for f in oi)
        self.assertEqual(sum(hprd.values()), 2)
        self.assertEqual(hprd.get("supported"), 2)
        self.assertEqual(hprd.get("uncertain", 0), 0)
        self.assertEqual(hprd.get("exclude", 0), 0)
        self.assertEqual(hprd.get("missing_pbj", 0), 0)
        ps = profile.get("portfolio_summary") or {}
        self.assertEqual(ps.get("n_facilities"), 274)
        self.assertEqual(ps.get("n_hprd_supported_facilities"), 2)
        body, *_ = render_owner_profile_body(profile)
        self.assertIn("2 qualifying facilities", body)
        self.assertIn("owner-snapshot-sublabel", body)
        self.assertIn("Weighted nurse HPRD", body)
        self.assertIn(
            "Owner-level PBJ staffing metrics use only qualifying facilities",
            body,
        )
        self.assertNotIn("274 qualifying", body)

    def test_large_oi_profiles_denominator_matches_calc(self) -> None:
        from ownership.owner_profile import load_owner_profile_resolved
        from ownership.owner_profile_html import render_owner_profile_body

        cases = [
            ("9830337005", "Mark D Hancock"),
            ("0648228304", "Jason H Murray"),
            ("6103289202", "PACS Holdings"),
            ("3476460494", "Ensign Group"),
        ]
        for pac, label in cases:
            with self.subTest(pac=pac, label=label):
                profile = load_owner_profile_resolved(pac)
                self.assertIsNotNone(profile, label)
                assert profile is not None
                ps = profile.get("portfolio_summary") or {}
                supported = int(ps.get("n_hprd_supported_facilities") or 0)
                body, *_ = render_owner_profile_body(profile)
                if supported > 0 and ps.get("wmean_hprd") is not None:
                    noun = "facility" if supported == 1 else "facilities"
                    self.assertIn(f"{supported} qualifying {noun}", body, msg=label)
                    self.assertIn("owner-snapshot-sublabel", body)

    def test_one_supported_facility_wording(self) -> None:
        facilities = [
            _fac(ccn="000001", attribution="supported"),
            _fac(ccn="000002", attribution="uncertain"),
        ]
        with patch(
            "ownership.owner_portfolio_metrics.enrich_facilities",
            side_effect=lambda rows: rows,
        ):
            ps = build_portfolio_summary(facilities)
        html = portfolio_snapshot_section_html(ps, context="owner")
        self.assertEqual(ps.get("n_hprd_supported_facilities"), 1)
        self.assertIn("1 qualifying facility", html)
        self.assertNotIn("1 qualifying facilities", html)

    def test_soon_burnam_control_only_no_hprd_card(self) -> None:
        from ownership.owner_profile import load_owner_profile_resolved
        from ownership.owner_profile_html import render_owner_profile_body

        profile = load_owner_profile_resolved("9739195553")
        self.assertIsNotNone(profile)
        assert profile is not None
        ps = profile.get("portfolio_summary") or {}
        self.assertEqual(int(ps.get("n_hprd_supported_facilities") or 0), 0)
        body, title, *_ = render_owner_profile_body(profile)
        self.assertNotIn("Weighted nurse HPRD", body)
        self.assertNotIn("owner-snapshot-sublabel", body)
        self.assertNotIn("Nursing Home Ownership Interest", title)

    def test_chow_q2_meta_matches_coverage(self) -> None:
        import json

        path = _ROOT / "chow_index.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.get("meta") or {}
        self.assertEqual(meta.get("cms_release"), "Q2 2026")
        self.assertIn("Q2 2026", str(meta.get("source_label") or ""))
        self.assertEqual(meta.get("coverage_date_min"), "2016-01-01")
        self.assertEqual(meta.get("coverage_date_max"), "2026-02-01")
        self.assertEqual(int(meta.get("event_count") or 0), 5227)
        self.assertEqual(len(data.get("records") or []), 5227)
        sha = (meta.get("source_sha256") or {}).get(
            "ownership/Skilled Nursing Facility Change of Ownership.zip"
        )
        self.assertTrue(sha and str(sha).startswith("92e1cd6b"))

    def test_burnam_facility_count_uses_ccn_dedup(self) -> None:
        from ownership.owner_profile import load_owner_profile_resolved

        profile = load_owner_profile_resolved("9739195553")
        self.assertIsNotNone(profile)
        assert profile is not None
        fac_count = int(profile.get("facility_count") or 0)
        self.assertGreaterEqual(fac_count, 350)

    def test_burnam_all_facilities_have_ccns(self) -> None:
        from ownership.owner_profile import load_owner_profile_resolved

        profile = load_owner_profile_resolved("9739195553")
        self.assertIsNotNone(profile)
        assert profile is not None
        for fac in profile.get("facilities") or []:
            ccn = str(fac.get("ccn") or "").strip()
            self.assertEqual(len(ccn), 6, f"Expected 6-digit CCN, got '{ccn}' for {fac.get('facility_name')}")
            self.assertTrue(ccn.isdigit(), f"CCN should be digits: '{ccn}'")

    def test_burnam_roles_consolidated_per_ccn(self) -> None:
        from ownership.owner_profile import load_owner_profile_resolved

        profile = load_owner_profile_resolved("9739195553")
        self.assertIsNotNone(profile)
        assert profile is not None
        ccn_counts: dict[str, int] = {}
        for fac in profile.get("facilities") or []:
            ccn = str(fac.get("ccn") or "").strip()
            if ccn:
                ccn_counts[ccn] = ccn_counts.get(ccn, 0) + 1
        for ccn, count in ccn_counts.items():
            self.assertEqual(count, 1, f"CCN {ccn} appears {count} times; should be deduplicated")

    def test_facility_stake_label_control_role_suppresses_zero_pct(self) -> None:
        from ownership.role_classification import facility_stake_column_label

        short, long = facility_stake_column_label(
            role_raw="Managing Employee",
            role_code="ME",
            pct_raw="0",
        )
        self.assertNotIn("0%", short)
        self.assertNotIn("0%", long)
        self.assertIn("control", short.lower())

        short2, long2 = facility_stake_column_label(
            role_raw="Managing Employee",
            role_code="ME",
            pct_raw="0%",
        )
        self.assertNotIn("0%", short2)
        self.assertNotIn("0%", long2)

    def test_facility_stake_label_ownership_preserves_zero(self) -> None:
        from ownership.role_classification import facility_stake_column_label

        short, long = facility_stake_column_label(
            role_raw="50% owner",
            role_code="01",
            pct_raw="0",
        )
        self.assertEqual(short, "0%")

    def test_associates_summary_excludes_help_button(self) -> None:
        from ownership.owner_profile_html import _associates_summary_html

        html = _associates_summary_html(count_html="")
        self.assertNotIn("<button", html)
        self.assertIn("<summary", html)
        self.assertIn("</summary>", html)

    def test_burnam_role_stake_cells_are_not_zero(self) -> None:
        from ownership.owner_profile import load_owner_profile_resolved
        from ownership.owner_profile_html import render_owner_profile_body

        profile = load_owner_profile_resolved("9739195553")
        self.assertIsNotNone(profile)
        assert profile is not None
        body, *_ = render_owner_profile_body(profile)
        self.assertNotIn("0%</button>", body)
        self.assertIn("control", body.lower())


if __name__ == "__main__":
    unittest.main()
