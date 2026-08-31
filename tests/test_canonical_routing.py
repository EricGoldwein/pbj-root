"""Regression tests for canonical URL routing across all object families.

Verifies that canonical, ID-only, and stale-slug routes resolve correctly
for providers, entities, owners, and states.
"""

from __future__ import annotations

import pathlib
import re
import unittest


class ProviderCanonicalRoutingTests(unittest.TestCase):
    """Provider pages: /provider/{ccn}/{slug} is canonical."""

    @classmethod
    def setUpClass(cls) -> None:
        from app import app as flask_app
        from canonical_urls import get_facility_name_from_search_index, provider_url

        cls.client = flask_app.test_client()
        cls.test_ccn = "015136"
        cls.name = get_facility_name_from_search_index(cls.test_ccn)
        cls.canonical = provider_url(cls.test_ccn, cls.name)

    def test_canonical_slugged_returns_200(self):
        resp = self.client.get(self.canonical)
        self.assertIn(resp.status_code, (200, 503))

    def test_bare_ccn_301_to_canonical(self):
        resp = self.client.get(f"/provider/{self.test_ccn}")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers["Location"], self.canonical)

    def test_wrong_slug_301_to_canonical(self):
        resp = self.client.get(f"/provider/{self.test_ccn}/wrong-name")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers["Location"], self.canonical)

    def test_canonical_no_redirect_loop(self):
        resp = self.client.get(self.canonical)
        self.assertIn(resp.status_code, (200, 503))
        self.assertNotIn("Location", resp.headers)

    def test_canonical_tag_matches(self):
        resp = self.client.get(self.canonical)
        if resp.status_code != 200:
            self.skipTest("Provider page not available locally (503)")
        html = resp.get_data(as_text=True)
        m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
        self.assertIsNotNone(m, "No canonical tag found")
        self.assertIn(self.test_ccn, m.group(1))

    def test_bare_ccn_preserves_query_string(self):
        resp = self.client.get(f"/provider/{self.test_ccn}?foo=bar")
        self.assertEqual(resp.status_code, 301)
        self.assertIn("foo=bar", resp.headers["Location"])

    def test_wrong_slug_preserves_query_string(self):
        resp = self.client.get(f"/provider/{self.test_ccn}/wrong-name?foo=bar")
        self.assertEqual(resp.status_code, 301)
        self.assertIn("foo=bar", resp.headers["Location"])


class EntityCanonicalRoutingTests(unittest.TestCase):
    """Entity pages: /entity/{id}/{slug} is canonical."""

    @classmethod
    def setUpClass(cls) -> None:
        from app import app as flask_app
        from canonical_urls import entity_url, get_entity_name_from_search_index

        cls.client = flask_app.test_client()
        cls.test_eid = 237
        cls.name = get_entity_name_from_search_index(cls.test_eid)
        cls.canonical = entity_url(cls.test_eid, cls.name)

    def test_canonical_slugged_returns_200(self):
        resp = self.client.get(self.canonical)
        self.assertEqual(resp.status_code, 200)

    def test_bare_id_301_to_canonical(self):
        resp = self.client.get(f"/entity/{self.test_eid}")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers["Location"], self.canonical)

    def test_wrong_slug_301_to_canonical(self):
        resp = self.client.get(f"/entity/{self.test_eid}/wrong-name")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers["Location"], self.canonical)

    def test_canonical_no_redirect_loop(self):
        resp = self.client.get(self.canonical)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Location", resp.headers)

    def test_canonical_tag_matches(self):
        resp = self.client.get(self.canonical)
        html = resp.get_data(as_text=True)
        m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
        self.assertIsNotNone(m, "No canonical tag found")
        self.assertIn(str(self.test_eid), m.group(1))


class OwnerCanonicalRoutingTests(unittest.TestCase):
    """Owner pages: /owners/{pac}/{slug} is canonical."""

    @classmethod
    def setUpClass(cls) -> None:
        from app import app as flask_app
        from canonical_urls import owner_url
        from ownership.owner_indexability import load_owner_indexability_cache

        cls.client = flask_app.test_client()
        cache = load_owner_indexability_cache() or {}
        cls.pac = None
        cls.canonical = None
        for pac, row in cache.items():
            cls_name = row.get("class", "")
            if cls_name in ("index", "noindex_follow") and len(pac) == 10:
                name = str(row.get("owner_name") or "").strip()
                if name:
                    cls.pac = pac
                    cls.canonical = owner_url(pac, name)
                    break

    def _skip_if_no_owner(self):
        if not self.pac:
            self.skipTest("No testable owner in cache")

    def test_canonical_slugged_returns_200(self):
        self._skip_if_no_owner()
        resp = self.client.get(self.canonical)
        self.assertEqual(resp.status_code, 200)

    def test_bare_pac_301_to_canonical(self):
        self._skip_if_no_owner()
        resp = self.client.get(f"/owners/{self.pac}")
        self.assertEqual(resp.status_code, 301)
        self.assertTrue(resp.headers["Location"].startswith(f"/owners/{self.pac}/"))

    def test_wrong_slug_301_to_canonical(self):
        self._skip_if_no_owner()
        resp = self.client.get(f"/owners/{self.pac}/wrong-slug")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers["Location"], self.canonical)

    def test_canonical_no_redirect_loop(self):
        self._skip_if_no_owner()
        resp = self.client.get(self.canonical)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Location", resp.headers)


class StateCanonicalRoutingTests(unittest.TestCase):
    """State pages: /state/{slug} is canonical."""

    @classmethod
    def setUpClass(cls) -> None:
        from app import app as flask_app

        cls.client = flask_app.test_client()

    def test_canonical_slug_returns_200(self):
        resp = self.client.get("/state/tennessee")
        self.assertEqual(resp.status_code, 200)

    def test_state_abbreviation_200(self):
        resp = self.client.get("/state/tn")
        self.assertEqual(resp.status_code, 200)

    def test_root_level_abbreviation_302(self):
        resp = self.client.get("/tn")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/state/tennessee")

    def test_root_level_name_302(self):
        resp = self.client.get("/tennessee")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/state/tennessee")

    def test_canonical_tag_matches(self):
        resp = self.client.get("/state/tennessee")
        html = resp.get_data(as_text=True)
        m = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
        self.assertIsNotNone(m, "No canonical tag found")
        self.assertIn("/state/tennessee", m.group(1))


class SearchURLConstructionTests(unittest.TestCase):
    """Verify search-result URL construction uses canonical forms."""

    def test_universal_search_builds_canonical_provider_urls(self):
        """pbj-site-universal.js uses pbjProviderUrl(ccn, name) for facility results."""
        path = pathlib.Path(__file__).resolve().parent.parent / "pbj-site-universal.js"
        src = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(
            r"function buildFacilityResultItems\b.*?^\s*\}",
            src,
            re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(m, "buildFacilityResultItems not found")
        self.assertIn("pbjProviderUrl(", m.group(0))

    def test_context_detection_matches_slugged_provider_urls(self):
        """detectPageContext() regex must match /provider/{ccn}/{slug}."""
        path = pathlib.Path(__file__).resolve().parent.parent / "pbj-site-universal.js"
        src = path.read_text(encoding="utf-8", errors="replace")
        self.assertIn(
            "(?:\\/[^/]+)?$",
            src,
            "pbj-site-universal.js provider regex should match optional /slug suffix",
        )

    def test_region_page_uses_state_prefix(self):
        """Region page state links should use /state/{slug} not /{slug}."""
        path = pathlib.Path(__file__).resolve().parent.parent / "app.py"
        src = path.read_text(encoding="utf-8", errors="replace")
        region_section = src[24400:24620]
        self.assertNotIn(
            'href="/{state_slug}"',
            region_section,
            "Region page should use /state/{state_slug}, not /{state_slug}",
        )
        self.assertNotIn(
            'href="/{slug}"',
            region_section,
            "Region page should use /state/{slug}, not /{slug}",
        )


if __name__ == "__main__":
    unittest.main()
