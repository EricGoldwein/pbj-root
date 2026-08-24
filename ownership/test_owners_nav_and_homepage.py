"""Regression: global Owners nav must remain in SITE_NAV_ITEMS (no strip after load)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


class OwnersNavRegressionTests(unittest.TestCase):
    def test_site_nav_items_includes_owners(self) -> None:
        js = (_ROOT / "pbj-site-universal.js").read_text(encoding="utf-8")
        self.assertIn("var SITE_NAV_ITEMS", js)
        self.assertRegex(js, r"\['/owners',\s*'Owners'\]")
        # Live Owners control is a plain /owners link (no chevron dropdown).
        self.assertRegex(
            js,
            r"ownersNavDropdownHtml[\s\S]*?<a href=\"/owners\" class=\"nav-link",
        )
        self.assertNotIn("nav-owners-chevron", js)
        self.assertNotIn("Owners |", js)

    def test_layout_nav_includes_owners_link(self) -> None:
        app = (_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('href="/owners" class="nav-link">Owners</a>', app)
        self.assertIn('data-pbj-nav-version="owners-v2"', app)

    def test_homepage_search_tabs_exclude_owners(self) -> None:
        html = (_ROOT / "index.html").read_text(encoding="utf-8")
        # Homepage search stays Provider / Chain / State; Owners is navbar-only.
        self.assertNotIn('id="searchTabOwners"', html)
        self.assertIn('id="searchTabFacility"', html)
        self.assertIn('id="searchTabChain"', html)
        self.assertIn('id="searchTabState"', html)
        self.assertNotIn("/owners/api/cms-search", html)
        self.assertNotIn("setMode('owners')", html)

    def test_owner_cms_source_is_in_upper_header_row(self) -> None:
        source = (_ROOT / "ownership" / "owner_profile_html.py").read_text(encoding="utf-8")
        header_start = source.index('def _owner_profile_header_html(')
        header_end = source.index('def _associate_shared_facilities_cell', header_start)
        header = source[header_start:header_end]
        top_start = header.index('<div class="owner-profile-header-top">')
        identity_start = header.index('<div class="owner-profile-header-identity">')
        self.assertIn("{cms_html}", header[top_start:identity_start])
        self.assertNotIn("{cms_html}", header[identity_start:])


class FailedAdpStubTests(unittest.TestCase):
    def test_failed_adp_stub_quarantined_not_ingested(self) -> None:
        live = _ROOT / "ownership" / "SNF_Owners_ADP_Association_2026.07.31.csv"
        quarantined = (
            _ROOT
            / "ownership"
            / "_quarantine"
            / "SNF_Owners_ADP_Association_2026.07.31.csv"
        )
        self.assertFalse(live.exists(), "failed ADP stub must not sit in ownership/")
        self.assertTrue(quarantined.exists())
        body = quarantined.read_text(encoding="utf-8", errors="ignore").strip()
        self.assertEqual(body, "Page not found")
        readme = (_ROOT / "ownership" / "_quarantine" / "README.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("never", readme.lower())


if __name__ == "__main__":
    unittest.main()
