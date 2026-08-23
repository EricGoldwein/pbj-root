"""Fast release smoke invariants for critical public routes and owners APIs."""
from __future__ import annotations

import re
import unittest

from site_public_config import PBJ_SITE_UNIVERSAL_JS_VERSION


class ReleaseSmokeInvariantsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import app as flask_app

        cls.client = flask_app.test_client()

    def test_owners_index_returns_200(self) -> None:
        resp = self.client.get("/owners/")
        self.assertEqual(resp.status_code, 200, resp.data[:500])

    def test_owners_index_national_hub_marker(self) -> None:
        html = self.client.get("/owners/").get_data(as_text=True)
        self.assertIn('data-owners-hub="national"', html)

    def test_owners_index_not_legacy_state_cards(self) -> None:
        html = self.client.get("/owners/").get_data(as_text=True)
        self.assertNotIn("owners-hub-state-cards", html)

    def test_owners_index_includes_hub_search(self) -> None:
        html = self.client.get("/owners/").get_data(as_text=True)
        self.assertIn("owners-hub-search", html)

    def test_provider_page_canonical_redirect(self) -> None:
        resp = self.client.get("/provider/335513", follow_redirects=False)
        self.assertEqual(resp.status_code, 301, resp.data[:500])
        loc = resp.headers.get("Location") or ""
        self.assertTrue(loc.startswith("/provider/335513/"), loc)

    def test_provider_canonical_page_returns_200(self) -> None:
        legacy = self.client.get("/provider/335513", follow_redirects=True)
        self.assertEqual(legacy.status_code, 200, legacy.data[:500])
        self.assertIn('rel="canonical"', legacy.get_data(as_text=True))

    def test_provider_page_includes_site_shell_js(self) -> None:
        html = self.client.get("/provider/335513", follow_redirects=True).get_data(as_text=True)
        self.assertRegex(
            html,
            rf'pbj-site-universal\.js\?v={re.escape(PBJ_SITE_UNIVERSAL_JS_VERSION)}',
        )
        self.assertIn('id="navMenu"', html)
        self.assertIn('id="navToggle"', html)

    def test_about_page_returns_200(self) -> None:
        resp = self.client.get("/about")
        self.assertEqual(resp.status_code, 200, resp.data[:500])

    def test_about_page_includes_site_shell_js(self) -> None:
        html = self.client.get("/about").get_data(as_text=True)
        self.assertIn("pbj-site-universal.js", html)

    def test_owners_cms_search_api_resolves(self) -> None:
        resp = self.client.get("/owners/api/cms-search?q=mit")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("suggestions", data)


if __name__ == "__main__":
    unittest.main()
