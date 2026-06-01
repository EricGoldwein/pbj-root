"""Tests for CMS ownership role classification and sorting."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.role_classification import (  # noqa: E402
    CATEGORY_ADMIN,
    CATEGORY_OPERATIONAL,
    CATEGORY_OWNERSHIP,
    ROLE_CODE_COL,
    ROLE_TEXT_COL,
    PCT_COL,
    ASSOC_DATE_COL,
    build_consolidated_party_from_rows,
    classify_owner_record,
    consolidate_owner_rows,
    enrich_control_party,
    party_sort_key,
    sort_control_parties,
)


def _row(
    *,
    code: str = "",
    text: str = "",
    pct: str = "",
    date: str = "",
    pac: str = "1234567890",
) -> dict:
    return {
        "ASSOCIATE ID - OWNER": pac,
        "ROLE CODE - OWNER": code,
        "ROLE TEXT - OWNER": text,
        "PERCENTAGE OWNERSHIP": pct,
        "ASSOCIATION DATE - OWNER": date,
        "TYPE - OWNER": "I - Individual",
        "FIRST NAME - OWNER": "Jane",
        "LAST NAME - OWNER": "Doe",
    }


class RoleClassificationTests(unittest.TestCase):
    def test_code_43_sorts_above_passive_ownership(self) -> None:
        op = enrich_control_party(
            build_consolidated_party_from_rows("pac:1", [_row(code="43", text="Operational/Managerial Control")])
        )
        own = enrich_control_party(
            build_consolidated_party_from_rows(
                "pac:2",
                [_row(code="01", text="5% OR MORE OWNERSHIP INTEREST", pct="10")],
            )
        )
        self.assertLess(party_sort_key(op), party_sort_key(own))

    def test_high_ownership_plus_managing_control_near_top(self) -> None:
        combined = enrich_control_party(
            build_consolidated_party_from_rows(
                "pac:1",
                [
                    _row(code="01", text="5% OR MORE OWNERSHIP INTEREST", pct="30"),
                    _row(code="43", text="Operational/Managerial Control"),
                ],
            )
        )
        passive = enrich_control_party(
            build_consolidated_party_from_rows(
                "pac:2", [_row(code="72", text="ADP OF THE SNF")]
            )
        )
        self.assertEqual(combined["role_category"], CATEGORY_OPERATIONAL)
        self.assertLess(party_sort_key(combined), party_sort_key(passive))

    def test_adp_does_not_outrank_operational_or_ownership(self) -> None:
        adp = enrich_control_party(
            build_consolidated_party_from_rows("pac:1", [_row(code="72", text="ADP OF THE SNF")])
        )
        own = enrich_control_party(
            build_consolidated_party_from_rows(
                "pac:2", [_row(code="01", text="5% OR MORE OWNERSHIP INTEREST", pct="1")]
            )
        )
        op = enrich_control_party(
            build_consolidated_party_from_rows("pac:3", [_row(code="43", text="Operational/Managerial Control")])
        )
        self.assertEqual(adp["role_category"], CATEGORY_ADMIN)
        self.assertLess(party_sort_key(op), party_sort_key(adp))
        self.assertLess(party_sort_key(own), party_sort_key(adp))

    def test_consolidate_duplicate_rows_preserves_roles(self) -> None:
        rows = [
            _row(code="43", text="Operational/Managerial Control", date="01/01/2020"),
            _row(code="01", text="5% OR MORE OWNERSHIP INTEREST", pct="30", date="06/01/2018"),
        ]
        party = build_consolidated_party_from_rows("pac:1234567890", rows)
        self.assertEqual(len(party["roles"]), 2)
        self.assertIn("Operational/Managerial Control", party["roles"])
        self.assertIn("5% OR MORE OWNERSHIP INTEREST", party["roles"])
        self.assertEqual(party["role_category"], CATEGORY_OPERATIONAL)
        self.assertEqual(party.get("max_ownership_pct"), 30.0)

    def test_classify_flags(self) -> None:
        info = classify_owner_record(_row(code="43", text="Operational/Managerial Control"))
        self.assertTrue(info["is_operational_control"])
        self.assertEqual(info["primary_role_label"], "Operational/managerial control")

    def test_sort_control_parties_order(self) -> None:
        parties = sort_control_parties(
            [
                {"name": "Zed", "roles": ["ADP OF THE SNF"], "role_codes": ["72"], "pcts": []},
                {
                    "name": "Ann",
                    "roles": ["5% OR MORE OWNERSHIP INTEREST"],
                    "role_codes": ["01"],
                    "pcts": ["10%"],
                },
                {
                    "name": "Bob",
                    "roles": ["Operational/Managerial Control"],
                    "role_codes": ["43"],
                    "pcts": [],
                },
            ]
        )
        self.assertEqual(parties[0]["name"], "Bob")
        self.assertEqual(parties[1]["name"], "Ann")
        self.assertEqual(parties[2]["name"], "Zed")


if __name__ == "__main__":
    unittest.main()
