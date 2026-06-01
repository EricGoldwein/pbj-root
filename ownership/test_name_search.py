"""Tests for owner name search normalization."""
from __future__ import annotations

import unittest

from ownership.name_search import (
    name_search_matches,
    name_search_rank,
    normalize_search_tokens,
    tokens_match_in_order,
)


class TestNormalizeSearchTokens(unittest.TestCase):
    def test_strips_punctuation(self) -> None:
        self.assertEqual(normalize_search_tokens("Brian J. Foley"), ["brian", "j", "foley"])


class TestNameSearchMatches(unittest.TestCase):
    def test_first_last_matches_middle_initial_record(self) -> None:
        record = "Brian J. Foley"
        self.assertTrue(name_search_matches("Brian Foley", record))
        self.assertTrue(name_search_matches("brian foley", record))
        self.assertTrue(name_search_matches("Brian  Foley", record))

    def test_middle_initial_query_matches_punctuated_record(self) -> None:
        self.assertTrue(name_search_matches("Brian J Foley", "Brian J. Foley"))

    def test_last_name_only(self) -> None:
        self.assertTrue(name_search_matches("Foley", "Brian J. Foley"))

    def test_unrelated_name_does_not_match(self) -> None:
        self.assertFalse(name_search_matches("Brian Foley", "John Smith"))
        self.assertFalse(name_search_matches("Brian Foley", "Brian Smith"))

    def test_org_substring_still_works(self) -> None:
        self.assertTrue(name_search_matches("acme heal", "ACME HEALTH CARE LLC"))

    def test_rank_for_middle_initial_match(self) -> None:
        self.assertIsNotNone(name_search_rank("Brian Foley", "Brian J. Foley"))

    def test_tokens_in_order(self) -> None:
        self.assertTrue(
            tokens_match_in_order(["brian", "foley"], ["brian", "j", "foley"])
        )
        self.assertFalse(
            tokens_match_in_order(["foley", "brian"], ["brian", "j", "foley"])
        )


if __name__ == "__main__":
    unittest.main()
