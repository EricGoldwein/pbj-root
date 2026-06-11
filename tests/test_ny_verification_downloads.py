"""NY verification workbook download routes: HTTPS-safe attachment serving."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

XLSX_PATH = "/downloads/PBJ320_NY_2025_daily_staffing_verification_file.xlsx"
ZIP_PATH = "/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs.zip"


class NyVerificationDownloadsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        cls.app = app
        cls.client = app.test_client()

    def _get(self, path: str, *, follow_redirects: bool = False):
        return self.client.get(
            path,
            follow_redirects=follow_redirects,
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "www.pbj320.com",
            },
        )

    def test_workbook_route_200_attachment(self):
        r = self._get(XLSX_PATH)
        self.assertEqual(r.status_code, 200, r.data[:200])
        self.assertGreater(len(r.data), 1_000_000)
        ct = r.headers.get("Content-Type", "")
        self.assertIn("spreadsheetml.sheet", ct)
        cd = r.headers.get("Content-Disposition", "")
        self.assertIn("attachment", cd.lower())
        self.assertIn("PBJ320_NY_2025_daily_staffing_verification_file.xlsx", cd)

    def test_zip_route_200_attachment(self):
        r = self._get(ZIP_PATH)
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.data), 100_000)
        self.assertIn("zip", r.headers.get("Content-Type", "").lower())
        cd = r.headers.get("Content-Disposition", "")
        self.assertIn("attachment", cd.lower())
        self.assertIn("PBJ320_NY_2025_daily_staffing_verification_csvs.zip", cd)

    def test_public_alias_redirects_to_canonical_https_safe(self):
        r = self._get("/public/downloads/PBJ320_NY_2025_daily_staffing_verification_file.xlsx")
        self.assertEqual(r.status_code, 301)
        loc = r.headers.get("Location", "")
        self.assertTrue(loc.endswith(XLSX_PATH) or loc == XLSX_PATH)
        self.assertFalse(loc.lower().startswith("http://"))

    def test_no_http_redirect_in_download_chain(self):
        r = self._get(
            "/public/downloads/PBJ320_NY_2025_daily_staffing_verification_csvs.zip",
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)
        loc_chain = r.headers.get("Location", "")
        self.assertFalse(str(loc_chain).lower().startswith("http://"))

    def test_html_uses_relative_download_paths_only(self):
        html = (ROOT / "insights-ny-minimum-staffing.html").read_text(encoding="utf-8")
        self.assertIn(f'href="{XLSX_PATH}"', html)
        self.assertIn(f'href="{ZIP_PATH}"', html)
        self.assertNotRegex(html, r'href="http://[^"]*PBJ320_NY_2025_daily_staffing_verification')
        self.assertNotRegex(html, r'href="/public/downloads/PBJ320_NY_2025')

    def test_og_image_route_200_inline_png(self):
        og_path = "/downloads/ny_350_min_report.png"
        r = self._get(og_path)
        self.assertEqual(r.status_code, 200, r.data[:200])
        self.assertGreater(len(r.data), 100_000)
        self.assertIn("image/png", r.headers.get("Content-Type", "").lower())
        cd = r.headers.get("Content-Disposition", "")
        self.assertNotIn("attachment", cd.lower())
        self.assertNotRegex(
            (ROOT / "insights-ny-minimum-staffing.html").read_text(encoding="utf-8"),
            r'og:image" content="https://www\.pbj320\.com/og-image-1200x630\.png"',
        )


if __name__ == "__main__":
    unittest.main()
