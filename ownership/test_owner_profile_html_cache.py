import unittest

import app


class OwnerProfileHtmlCacheTests(unittest.TestCase):
    def setUp(self):
        with app._owner_profile_html_cache_lock:
            app._owner_profile_html_cache.clear()

    def tearDown(self):
        with app._owner_profile_html_cache_lock:
            app._owner_profile_html_cache.clear()

    def test_cache_is_bounded_and_recently_used_entry_survives(self):
        original_max = app._OWNER_PROFILE_HTML_CACHE_MAX
        app._OWNER_PROFILE_HTML_CACHE_MAX = 2
        self.addCleanup(setattr, app, "_OWNER_PROFILE_HTML_CACHE_MAX", original_max)

        app._owner_profile_html_cache_put("1", "one", "index")
        app._owner_profile_html_cache_put("2", "two", "noindex, follow")
        self.assertEqual(app._owner_profile_html_cache_get("1"), ("one", "index"))
        app._owner_profile_html_cache_put("3", "three", None)

        self.assertIsNone(app._owner_profile_html_cache_get("2"))
        self.assertEqual(app._owner_profile_html_cache_get("1"), ("one", "index"))

    def test_owner_response_allows_safe_edge_reuse(self):
        with app.app.test_request_context("/owners/1/test"):
            response = app._owner_profile_response("<html>ok</html>", "noindex, follow")

        self.assertEqual(response.status_code, 200)
        self.assertIn("s-maxage=3600", response.headers["Cache-Control"])
        self.assertIn("stale-while-revalidate=86400", response.headers["Cache-Control"])
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, follow")


if __name__ == "__main__":
    unittest.main()
