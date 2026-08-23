"""Regression tests for canonical owner/provider/entity URL system."""
from __future__ import annotations

import re
import unittest

from canonical_urls import (
    absolute_canonical_url,
    entity_url,
    get_entity_name_from_search_index,
    get_facility_name_from_search_index,
    owner_url,
    provider_url,
    slugify_name,
)


class CanonicalUrlHelperTests(unittest.TestCase):
    def test_slugify_name(self):
        self.assertEqual(slugify_name("Example Nursing Home"), "example-nursing-home")
        self.assertEqual(slugify_name(""), "page")
        self.assertEqual(slugify_name("", fallback="facility"), "facility")

    def test_provider_url(self):
        self.assertEqual(
            provider_url("366395", "Example Nursing Home"),
            "/provider/366395/example-nursing-home",
        )
        self.assertEqual(provider_url("366395"), "/provider/366395/facility")

    def test_entity_url(self):
        self.assertEqual(
            entity_url(12345, "Genesis Healthcare"),
            "/entity/12345/genesis-healthcare",
        )
        self.assertEqual(entity_url(12345), "/entity/12345/entity")

    def test_owner_url_wraps_associate_profile(self):
        self.assertEqual(
            owner_url("7113172370", "Yecheskel Webster"),
            "/owners/7113172370/yecheskel-webster",
        )

    def test_absolute_canonical_url(self):
        self.assertEqual(
            absolute_canonical_url("/provider/366395/example-nursing-home"),
            "https://www.pbj320.com/provider/366395/example-nursing-home",
        )


class CanonicalRouteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import app as flask_app

        cls.client = flask_app.test_client()
        cls.test_ccn = "335513"
        cls.facility_name = get_facility_name_from_search_index(cls.test_ccn)
        cls.canonical_provider_path = provider_url(cls.test_ccn, cls.facility_name)
        cls.test_entity_id = 237
        cls.entity_name = get_entity_name_from_search_index(cls.test_entity_id)
        cls.canonical_entity_path = entity_url(cls.test_entity_id, cls.entity_name)

    def _canonical_tag(self, html: str) -> str | None:
        m = re.search(
            r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
            html,
            re.I,
        )
        return m.group(1).strip() if m else None

    def test_canonical_provider_url_200(self):
        if not self.facility_name:
            self.skipTest("search index missing facility name for test CCN")
        resp = self.client.get(self.canonical_provider_path)
        self.assertEqual(resp.status_code, 200, resp.data[:300])

    def test_provider_id_only_301(self):
        if not self.facility_name:
            self.skipTest("search index missing facility name for test CCN")
        resp = self.client.get(f"/provider/{self.test_ccn}", follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        loc = resp.headers.get("Location") or ""
        self.assertIn(self.canonical_provider_path, loc)

    def test_provider_stale_slug_301(self):
        if not self.facility_name:
            self.skipTest("search index missing facility name for test CCN")
        stale = f"/provider/{self.test_ccn}/old-facility-name"
        resp = self.client.get(stale, follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        loc = resp.headers.get("Location") or ""
        self.assertIn(self.canonical_provider_path, loc)

    def test_canonical_entity_url_200(self):
        if not self.entity_name:
            self.skipTest("search index missing entity name for test entity")
        resp = self.client.get(self.canonical_entity_path)
        self.assertEqual(resp.status_code, 200, resp.data[:300])

    def test_entity_id_only_301(self):
        if not self.entity_name:
            self.skipTest("search index missing entity name for test entity")
        resp = self.client.get(
            f"/entity/{self.test_entity_id}", follow_redirects=False
        )
        self.assertEqual(resp.status_code, 301)
        loc = resp.headers.get("Location") or ""
        self.assertIn(self.canonical_entity_path, loc)

    def test_entity_stale_slug_301(self):
        if not self.entity_name:
            self.skipTest("search index missing entity name for test entity")
        stale = f"/entity/{self.test_entity_id}/old-chain-name"
        resp = self.client.get(stale, follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        loc = resp.headers.get("Location") or ""
        self.assertIn(self.canonical_entity_path, loc)

    def test_provider_canonical_tag(self):
        if not self.facility_name:
            self.skipTest("search index missing facility name for test CCN")
        html = self.client.get(self.canonical_provider_path).get_data(as_text=True)
        canon = self._canonical_tag(html)
        self.assertIsNotNone(canon)
        expected = absolute_canonical_url(self.canonical_provider_path)
        self.assertEqual(canon, expected)
        self.assertEqual(len(re.findall(r'rel=["\']canonical["\']', html, re.I)), 1)

    def test_unknown_provider_404(self):
        resp = self.client.get("/provider/999999/unknown-facility")
        self.assertEqual(resp.status_code, 404)

    def test_no_redirect_chain_provider(self):
        if not self.facility_name:
            self.skipTest("search index missing facility name for test CCN")
        resp = self.client.get(f"/provider/{self.test_ccn}", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        final_path = (resp.request.path or "").rstrip("/")
        self.assertEqual(final_path, self.canonical_provider_path.rstrip("/"))

    def test_sitemap_uses_slugged_provider_urls(self):
        from app import _build_sitemap_xml

        xml = _build_sitemap_xml()
        self.assertIn("/provider/", xml)
        self.assertNotRegex(xml, r"<loc>https?://[^<]+/provider/\d{6}</loc>")
        if self.facility_name and self.canonical_provider_path:
            self.assertIn(self.canonical_provider_path, xml)

    def test_sitemap_excludes_id_only_owner_when_slug_known(self):
        from app import _build_sitemap_xml

        xml = _build_sitemap_xml()
        if re.search(r"/owners/\d{10}/", xml):
            self.assertNotRegex(xml, r"<loc>https?://[^<]+/owners/\d{10}</loc>")

    def test_owner_id_only_301(self):
        from ownership.owner_indexability import load_owner_indexability_cache

        cache = load_owner_indexability_cache() or {}
        if not cache:
            self.skipTest("owner indexability cache missing")
        pac = next(iter(cache.keys()), None)
        if not pac:
            self.skipTest("no owner PAC in cache")
        name = str((cache.get(pac) or {}).get("owner_name") or "").strip()
        canon = owner_url(pac, name)
        if "/" not in canon.strip("/") or canon.count("/") < 3:
            self.skipTest("owner has no slug canonical")
        resp = self.client.get(f"/owners/{pac}", follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        self.assertIn(canon, resp.headers.get("Location") or "")


if __name__ == "__main__":
    unittest.main()
