"""Tests for /owners/{id}/{slug} URL helpers."""
from __future__ import annotations

import unittest

from ownership.owner_profile import (
    associate_profile_url,
    owner_display_slug,
    owner_profile_canonical_path,
)


class OwnerProfileUrlTests(unittest.TestCase):
    def test_slug_from_individual_name(self):
        self.assertEqual(owner_display_slug("Nochum Freund"), "nochum-freund")

    def test_slug_from_org_name(self):
        self.assertEqual(owner_display_slug("Pacs Holdings, LLC"), "pacs-holdings-llc")

    def test_associate_url_with_name(self):
        self.assertEqual(
            associate_profile_url("3870870553", "Nochum Freund"),
            "/owners/3870870553/nochum-freund",
        )

    def test_associate_url_id_only(self):
        self.assertEqual(associate_profile_url("3870870553"), "/owners/3870870553")

    def test_canonical_path_from_profile(self):
        path = owner_profile_canonical_path(
            {"associate_id": "0143110361", "display_name": "Lynn D Watts"}
        )
        self.assertEqual(path, "/owners/0143110361/lynn-d-watts")


if __name__ == "__main__":
    unittest.main()
