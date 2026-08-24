import sqlite3
import unittest
from unittest.mock import patch

from ownership import owner_profile


class CanonicalFacilityMatchTests(unittest.TestCase):
    def setUp(self):
        owner_profile._canonical_facility_matches_for_pac.cache_clear()

    def tearDown(self):
        owner_profile._canonical_facility_matches_for_pac.cache_clear()

    def test_uses_pac_indexed_canonical_match(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute(
            "CREATE TABLE current_relationships "
            "(pac TEXT, facility_org_name TEXT, ccn TEXT, ccn_method TEXT)"
        )
        conn.execute(
            "INSERT INTO current_relationships VALUES (?, ?, ?, ?)",
            ("7618113481", "EXAMPLE HEALTH LLC", "12345", "legal_exact"),
        )

        with patch.object(owner_profile, "_sqlite_conn", return_value=conn), patch.object(
            owner_profile,
            "_resolve_ccn_with_method",
            side_effect=AssertionError("national fallback should not run"),
        ):
            self.assertEqual(
                owner_profile._profile_facility_match("7618113481", "Example Health LLC"),
                ("012345", "legal_exact"),
            )

    def test_falls_back_when_canonical_table_is_unavailable(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        with patch.object(owner_profile, "_sqlite_conn", return_value=conn), patch.object(
            owner_profile,
            "_resolve_ccn_with_method",
            return_value=("654321", "name_exact"),
        ):
            self.assertEqual(
                owner_profile._profile_facility_match("7618113481", "Example Health LLC"),
                ("654321", "name_exact"),
            )


if __name__ == "__main__":
    unittest.main()
