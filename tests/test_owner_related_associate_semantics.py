from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ownership.owner_profile as owner_profile
import ownership.owner_profile_html as owner_html
import scripts.build_snf_owners_index as index_builder


class OwnerRelatedAssociateSemanticsTests(unittest.TestCase):
    WENDY = "6800193137"
    AMY = "2222222222"
    AARON = "9739542788"
    BETH = "3333333333"
    SELLER = "4444444444"
    ENTITY = "1111111111"

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            '''
            CREATE TABLE snf_owners (
              "ASSOCIATE ID" TEXT,
              "ASSOCIATE ID - OWNER" TEXT,
              "ENROLLMENT ID" TEXT,
              "ORGANIZATION NAME" TEXT,
              "ORGANIZATION NAME - OWNER" TEXT,
              "FIRST NAME - OWNER" TEXT,
              "MIDDLE NAME - OWNER" TEXT,
              "LAST NAME - OWNER" TEXT,
              "TYPE - OWNER" TEXT,
              "ROLE CODE - OWNER" TEXT,
              "ROLE TEXT - OWNER" TEXT,
              "PERCENTAGE OWNERSHIP" TEXT
            )
            '''
        )
        rows = [
            (self.ENTITY, self.WENDY, "E1", "TODD-DICKEY", "WENDY BROUGHTON"),
            (self.ENTITY, self.AMY, "E1", "TODD-DICKEY", "AMY GARY"),
            (self.ENTITY, self.AARON, "E2", "HERITAGE PARK", "AARON SCHMID"),
            (self.ENTITY, self.BETH, "E4", "TODD-DICKEY", "BETH EXAMPLE"),
        ]
        self.conn.executemany(
            '''
            INSERT INTO snf_owners (
              "ASSOCIATE ID", "ASSOCIATE ID - OWNER", "ENROLLMENT ID",
              "ORGANIZATION NAME", "ORGANIZATION NAME - OWNER", "TYPE - OWNER"
            ) VALUES (?, ?, ?, ?, ?, 'O')
            ''',
            rows,
        )
        self.conn.execute(
            'CREATE INDEX idx_enrollment_pac ON snf_owners ("ASSOCIATE ID")'
        )
        self.conn.execute(
            'CREATE INDEX idx_enrollment_id ON snf_owners ("ENROLLMENT ID")'
        )
        self.profile = {
            "associate_id": self.WENDY,
            "profile_kind": "owner_control",
            "display_name": "Wendy Broughton",
            "facilities": [
                {
                    "facility_name": "Todd-Dickey Nursing and Rehabilitation",
                    "enrollment_id": "E1",
                    "enrollment_pac": self.ENTITY,
                    "ccn": "123456",
                }
            ],
            "portfolio_summary": {"n_facilities": 1},
            "chow_transactions": [
                {
                    "chow_role": "buyer",
                    "seller_associate_id": self.SELLER,
                    "seller_org_name": "Seller Organization",
                }
            ],
        }

    def tearDown(self) -> None:
        self.conn.close()

    def _related(self) -> list[dict]:
        with patch.object(owner_profile, "_sqlite_conn", return_value=self.conn), patch.object(
            owner_profile,
            "_enrollment_to_ccn_bridge",
            return_value={"E1": "123456", "E2": "654321", "E4": "123456"},
        ):
            with patch.object(
                owner_profile,
                "_ccn_to_enrollment_ids",
                return_value={"123456": ("E1", "E4"), "654321": ("E2",)},
            ):
                return owner_profile.build_related_associates(self.profile, limit=20)

    def test_exact_enrollment_and_pac_only_relationships_are_distinct(self) -> None:
        rows = self._related()
        by_id = {r["associate_id"]: r for r in rows}

        amy = by_id[self.AMY]
        self.assertEqual(amy["shared_facilities"], 1)
        self.assertEqual(amy["shared_enrollments"], 1)
        self.assertEqual(amy["shared_entities"], 1)

        aaron = by_id[self.AARON]
        self.assertEqual(aaron["shared_facilities"], 0)
        self.assertEqual(aaron["shared_enrollments"], 0)
        self.assertEqual(aaron["shared_entities"], 1)

        beth = by_id[self.BETH]
        self.assertEqual(beth["shared_facilities"], 1)
        self.assertEqual(beth["shared_enrollments"], 0)
        self.assertEqual(beth["shared_entities"], 1)
        self.assertEqual(owner_html._associate_source_label(beth), "Same facility")

        self.assertLess(
            next(i for i, r in enumerate(rows) if r["associate_id"] == self.AMY),
            next(i for i, r in enumerate(rows) if r["associate_id"] == self.AARON),
        )

    def test_high_fanout_entity_does_not_create_false_coenrollees(self) -> None:
        rows = self._related()
        profile = {
            "related_associates": rows,
            "portfolio_summary": {"n_facilities": 1},
        }
        fragment = owner_html.render_related_associates_fragment(profile)
        self.assertIn("Same facility", fragment)
        self.assertIn("Same CMS entity", fragment)
        self.assertIn("CMS ownership change", fragment)
        self.assertNotIn("Co-enrollee", fragment)

        aaron = next(r for r in rows if r["associate_id"] == self.AARON)
        self.assertEqual(
            owner_html._associate_shared_facilities_cell(aaron, n_facilities=1), "—"
        )
        self.assertEqual(owner_html._associate_source_label(aaron), "Same CMS entity")

    def test_relationship_strength_ranking_is_direct_then_chow_then_entity(self) -> None:
        rows = self._related()
        positions = {r["associate_id"]: i for i, r in enumerate(rows)}
        self.assertLess(positions[self.AMY], positions[self.SELLER])
        self.assertLess(positions[self.SELLER], positions[self.AARON])

    def test_exact_relationship_fails_closed_without_sqlite(self) -> None:
        with patch.object(owner_profile, "_sqlite_conn", return_value=None), patch.object(
            owner_profile, "_read_owners_csv_chunks", side_effect=AssertionError("CSV fallback used")
        ):
            rows = owner_profile._snf_associates_on_exact_enrollments(
                {"E1"}, eid_to_ccn={"E1": "123456"}, exclude_pac=self.WENDY
            )
        self.assertEqual(rows, [])


class OwnerEnrollmentIndexBuildTests(unittest.TestCase):
    def test_build_creates_exact_enrollment_id_index_used_by_query_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "SNF_All_Owners_July_2026.csv"
            db = root / "owners.sqlite"
            with source.open("w", newline="", encoding="latin-1") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ASSOCIATE ID",
                        "ASSOCIATE ID - OWNER",
                        "ENROLLMENT ID",
                        "ORGANIZATION NAME",
                        "ORGANIZATION NAME - OWNER",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "ASSOCIATE ID": "1111111111",
                        "ASSOCIATE ID - OWNER": "2222222222",
                        "ENROLLMENT ID": "E1",
                        "ORGANIZATION NAME": "Example SNF",
                        "ORGANIZATION NAME - OWNER": "Example Owner",
                    }
                )

            with patch.object(index_builder, "snf_owners_csv_path", return_value=source), patch.object(
                index_builder, "ORG_INDEX_PATH", root / "org.json.gz"
            ), patch.object(index_builder, "CCN_INDEX_PATH", root / "ccn.json.gz"), patch.object(
                index_builder, "_write_ccn_key", return_value=None
            ):
                index_builder.build_sqlite_from_csv(out_path=db)

            conn = sqlite3.connect(db)
            try:
                indexes = {row[1] for row in conn.execute("PRAGMA index_list(snf_owners)")}
                self.assertIn("idx_enrollment_id", indexes)
                plan = conn.execute(
                    'EXPLAIN QUERY PLAN SELECT * FROM snf_owners WHERE "ENROLLMENT ID" = ?',
                    ("E1",),
                ).fetchall()
                self.assertTrue(
                    any("idx_enrollment_id" in str(row[3]) for row in plan),
                    plan,
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
