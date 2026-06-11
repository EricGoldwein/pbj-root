"""Classic NY report URL must not serve stale parallel HTML."""

import unittest
from pathlib import Path

from app import app

ROOT = Path(__file__).resolve().parents[1]
CLASSIC_STUB = ROOT / "insights-ny-minimum-staffing.classic.html"


class NyClassicRedirectTest(unittest.TestCase):
    def test_classic_redirects_to_primary(self):
        client = app.test_client()
        resp = client.get("/insights/ny-minimum-staffing/classic", follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        self.assertIn("/insights/ny-minimum-staffing", resp.headers.get("Location", ""))

    def test_classic_file_is_redirect_stub_not_stale_report(self):
        self.assertTrue(CLASSIC_STUB.is_file(), "classic stub file missing")
        text = CLASSIC_STUB.read_text(encoding="utf-8")
        self.assertIn("/insights/ny-minimum-staffing", text)
        self.assertNotIn("101,779", text)
        self.assertNotIn("47.1%", text)

    def test_press_url_redirects_to_primary_report(self):
        client = app.test_client()
        resp = client.get("/insights/ny-minimum-staffing/press", follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        self.assertIn("/insights/ny-minimum-staffing", resp.headers.get("Location", ""))
        self.assertNotIn("/press", resp.headers.get("Location", "").rstrip("/").split("/")[-1])


if __name__ == "__main__":
    unittest.main()
