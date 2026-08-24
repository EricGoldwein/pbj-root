from __future__ import annotations

import unittest
from unittest.mock import patch

from ownership.owner_profile import (
    OWNER_PAC_COL,
    _build_control_parties,
    _ccn_to_enrollment_ids,
    _fetch_rows_for_pac,
    facility_ownership_rows_for_ccn,
    load_owner_profile_resolved,
    lookup_cms_ownership_for_provider,
    normalize_associate_id,
)
from ownership.page_integrations import render_provider_ownership_chow_block


def _party_pacs(rows: tuple[dict, ...] | list[dict]) -> set[str]:
    return {
        normalize_associate_id(row.get(OWNER_PAC_COL))
        for row in rows
        if normalize_associate_id(row.get(OWNER_PAC_COL))
    }


class ProviderOwnershipScopingTests(unittest.TestCase):
    def test_seagoville_uses_only_its_exact_enrollment(self) -> None:
        eids, rows = facility_ownership_rows_for_ccn("675418")
        self.assertEqual(eids, ("O20150522001759",))
        self.assertEqual(len(rows), 9)
        self.assertEqual({row["ENROLLMENT ID"] for row in rows}, set(eids))

        expected_pacs = {
            "5294242640",
            "6709794472",
            "8325934813",
            "1850312893",
            "0547487696",
            "9739696188",
            "8123180064",
        }
        self.assertEqual(_party_pacs(rows), expected_pacs)

        hit = lookup_cms_ownership_for_provider(ccn="675418")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit["enrollment_ids"], ["O20150522001759"])
        self.assertEqual(hit["raw_owner_row_count"], 9)
        self.assertEqual(
            {party["owner_associate_id"] for party in hit["control_parties"]}, expected_pacs
        )
        self.assertEqual(len(hit["control_parties"]), 7)

        html = render_provider_ownership_chow_block(
            "675418",
            provider_info_row={
                "ccn": "675418",
                "ownership_type": "For profit - Corporation",
            },
            state_code="TX",
            cms=hit,
        )
        self.assertIn("7 parties", html)
        self.assertNotIn("222 parties", html)
        self.assertNotIn("Showing 15 of 222 parties", html)

    def test_other_shared_pac_facilities_are_eid_scoped(self) -> None:
        cases = [
            ("676112", "O20150522002031"),
            ("676128", "O20150521001885"),
            ("676464", "O20250909004460"),
        ]
        for ccn, expected_eid in cases:
            with self.subTest(ccn=ccn):
                eids, rows = facility_ownership_rows_for_ccn(ccn)
                self.assertEqual(eids, (expected_eid,))
                self.assertTrue(rows)
                self.assertEqual({row["ENROLLMENT ID"] for row in rows}, {expected_eid})

                enrollment_pacs = {
                    normalize_associate_id(row.get("ASSOCIATE ID")) for row in rows
                }
                self.assertEqual(enrollment_pacs, {"8325934813"})
                pac_rows, _ = _fetch_rows_for_pac("8325934813")
                self.assertEqual(len({row["ENROLLMENT ID"] for row in pac_rows}), 38)

                hit = lookup_cms_ownership_for_provider(ccn=ccn)
                self.assertIsNotNone(hit)
                assert hit is not None
                self.assertEqual(hit["enrollment_ids"], [expected_eid])
                self.assertEqual(hit["raw_owner_row_count"], len(rows))
                self.assertEqual(
                    {p["owner_associate_id"] for p in hit["control_parties"]},
                    _party_pacs(rows),
                )

    def test_single_enrollment_pac_keeps_existing_party_result(self) -> None:
        ccn = "345500"
        expected_eid = "O20020801000000"
        eids, rows = facility_ownership_rows_for_ccn(ccn)
        self.assertEqual(eids, (expected_eid,))
        self.assertTrue(rows)

        pacs = {normalize_associate_id(row.get("ASSOCIATE ID")) for row in rows}
        self.assertEqual(pacs, {"6103733167"})
        pac_rows, _ = _fetch_rows_for_pac("6103733167")
        self.assertEqual({row["ENROLLMENT ID"] for row in pac_rows}, {expected_eid})

        hit = lookup_cms_ownership_for_provider(ccn=ccn)
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(
            {p["owner_associate_id"] for p in hit["control_parties"]},
            {p["owner_associate_id"] for p in _build_control_parties(pac_rows)},
        )

    def test_active_release_has_no_multi_eid_ccn(self) -> None:
        """Exercise all mapped EIDs if the release gains one; record today's invariant otherwise."""
        multi = {
            ccn: eids
            for ccn, eids in _ccn_to_enrollment_ids().items()
            if len(eids) > 1
        }
        if not multi:
            self.assertEqual(multi, {})
            return

        for ccn, expected_eids in multi.items():
            eids, rows = facility_ownership_rows_for_ccn(ccn)
            self.assertEqual(eids, expected_eids)
            self.assertEqual({row["ENROLLMENT ID"] for row in rows}, set(expected_eids))

    def test_missing_exact_bridge_mapping_fails_closed_without_pac_fallback(self) -> None:
        with (
            patch("ownership.owner_profile._ccn_to_enrollment_ids", return_value={}),
            patch("ownership.owner_profile._fetch_rows_for_pac") as pac_fetch,
        ):
            self.assertEqual(facility_ownership_rows_for_ccn("999999"), ((), ()))
            self.assertIsNone(
                lookup_cms_ownership_for_provider(
                    ccn="999999",
                    provider_name="A name that used to trigger PAC matching",
                )
            )
        pac_fetch.assert_not_called()

    def test_dallas_county_owner_profile_remains_pac_wide(self) -> None:
        profile = load_owner_profile_resolved("8325934813")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertIn(profile["profile_kind"], {"enrollment", "both"})
        self.assertEqual(len(profile["enrollment_ids"]), 38)
        self.assertIn("O20150522001759", profile["enrollment_ids"])
        self.assertEqual(len(profile["control_parties"]), 222)


if __name__ == "__main__":
    unittest.main()
