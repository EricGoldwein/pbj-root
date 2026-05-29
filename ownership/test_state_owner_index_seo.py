"""SEO/indexability tests for /owners/ny and /owners/ct state ownership index pages."""
from __future__ import annotations

import json
import re
import unittest

from ownership.state_owner_index import (
    STATE_INDEX_META,
    public_owner_index_sitemap_paths,
    state_index_canonical_path,
    state_index_layout_meta,
)
from ownership.state_owner_index_html import render_state_owner_index_body
from ownership.state_owner_index_seo import build_state_owner_index_json_ld


class StateOwnerIndexSeoTests(unittest.TestCase):
    def test_ny_ct_unique_titles_and_descriptions(self):
        ny = state_index_layout_meta("NY")
        ct = state_index_layout_meta("CT")
        self.assertNotEqual(ny["page_title"], ct["page_title"])
        self.assertNotEqual(ny["meta_description"], ct["meta_description"])
        self.assertIn("New York", ny["page_title"])
        self.assertIn("Connecticut", ct["page_title"])
        self.assertIn("PBJ320", ny["page_title"])
        self.assertIn("PAC IDs", ny["meta_description"])

    def test_canonical_paths(self):
        self.assertEqual(state_index_canonical_path("NY"), "/owners/ny")
        self.assertEqual(state_index_canonical_path("CT"), "/owners/ct")

    def test_sitemap_includes_public_state_pages(self):
        paths = {row[0] for row in public_owner_index_sitemap_paths()}
        self.assertEqual(paths, {"/owners/ny", "/owners/ct"})
        for path, _pri, changefreq, lastmod in public_owner_index_sitemap_paths():
            self.assertEqual(changefreq, "weekly")
            self.assertRegex(lastmod, r"^\d{4}-\d{2}-\d{2}$")

    def test_render_has_one_h1_and_crawlable_intro(self):
        body, layout = render_state_owner_index_body("NY", get_canonical_slug=lambda s: "new-york")
        self.assertEqual(body.lower().count("<h1"), 1)
        self.assertIn("owners-state-subtitle", body)
        self.assertIn(layout["subtitle"], body)
        self.assertNotIn("owners-state-page-meta", body)
        self.assertNotIn("owners indexed", body)
        self.assertIn("owners-state-index-stats", body)
        self.assertNotIn("PAC IDs", layout["subtitle"])
        self.assertIn("ownership groups", layout["subtitle"])
        self.assertIn("staffing patterns", layout["subtitle"])
        self.assertGreater(body.find("owners-state-index-stats"), body.find("owners-state-crumb"))
        self.assertLess(body.find("owners-state-index-stats"), body.find("owners-state-h1"))
        self.assertNotIn("owners-state-below-search", body)
        self.assertNotIn("owners-state-search-foot", body)
        self.assertIn("owners-state-desktop-sources", body)
        self.assertGreater(body.find("owners-state-method"), body.find("owners-state-panels"))
        self.assertGreater(body.find("owners-state-desktop-sources"), body.find("</details>"))
        self.assertIn("owners-state-panel-tabs", body)
        self.assertIn("data-owners-state-tab=\"portfolios\"", body)
        self.assertIn("owners-state-sources-trigger", body)
        self.assertIn("ownersStateSourcesModal", body)
        self.assertIn("owners-state-search-sources", body)
        self.assertIn(">Sources:</span>", body)
        self.assertNotIn("owners-state-sources-site", body)
        self.assertNotIn("owners-state-method-links", body)
        self.assertIn("owners-state-src-link", body)
        self.assertNotIn("owners-state-meta-badge", body)
        self.assertNotIn("owners-state-stat-badge", body)
        self.assertIn("owners-state-meta-dot", body)
        self.assertIn("CMS Ownership</a>", body)
        self.assertIn(">CHOW</a>", body)
        self.assertIn(">PBJ</a>", body)
        self.assertIn("skilled-nursing-facility-all-owners", body)
        self.assertIn("skilled-nursing-facility-change-of-ownership", body)
        self.assertIn("payroll-based-journal-daily-nurse-staffing", body)
        self.assertIn('href="https://fec.gov/"', body)
        self.assertNotIn("owners-state-panel-footer", body)
        self.assertIn("Largest NY portfolios", body)
        self.assertIn("Largest New York portfolios", body)
        self.assertIn("Recent ownership changes", body)
        self.assertIn('owners-state-h1-secondary">Ownership Search</span>', body)
        self.assertIn("About this New York ownership index", body)
        self.assertIn("owners-state-method-trigger", body)
        self.assertIn("PBJ320 maps CMS nursing home ownership records", body)

    def test_try_chips_link_to_owner_profiles(self):
        body, _layout = render_state_owner_index_body("NY", get_canonical_slug=lambda s: "new-york")
        self.assertIn('class="owners-state-try-chip"', body)
        self.assertIn('href="/owners/', body)
        self.assertRegex(body, r'aria-label="View .+ ownership profile"')

    def test_try_chips_skew_top_five_within_top_ten(self):
        from ownership import state_owner_index_html as html_mod

        pool = [
            {
                "display_name": f"Owner {i}",
                "associate_id": f"{i:010d}",
                "href": f"/owners/{i:010d}",
                "query": f"Owner {i}",
            }
            for i in range(10)
        ]
        for _ in range(40):
            picked = html_mod._pick_try_chips(pool, 3)
            self.assertEqual(len(picked), 3)
            names = {c["display_name"] for c in picked}
            self.assertEqual(len(names), 3)
            self.assertTrue(any(c["display_name"].startswith("Owner ") and int(c["display_name"][6:]) < 5 for c in picked))
            self.assertTrue(all(int(c["display_name"][6:]) < 10 for c in picked))

    def test_json_ld_breadcrumb_uses_state_name(self):
        web_page, crumbs = build_state_owner_index_json_ld(
            "NY",
            site_origin="https://www.pbj320.com",
            page_title=STATE_INDEX_META["NY"]["title"],
            meta_description=STATE_INDEX_META["NY"]["meta_description"],
            canonical_url="https://www.pbj320.com/owners/ny",
        )
        self.assertEqual(web_page["@type"], "CollectionPage")
        self.assertEqual(web_page["publisher"]["name"], "320 Consulting")
        self.assertEqual(crumbs[-1][0], "New York")
        about = web_page.get("about") or []
        self.assertTrue(any(item.get("name") == "New York" for item in about if isinstance(item, dict)))

    def test_json_ld_script_serializes(self):
        from ownership.state_owner_index_seo import render_state_owner_index_json_ld_scripts

        scripts = render_state_owner_index_json_ld_scripts(
            "CT",
            site_origin="https://www.pbj320.com",
            page_title=STATE_INDEX_META["CT"]["title"],
            meta_description=STATE_INDEX_META["CT"]["meta_description"],
            canonical_url="https://www.pbj320.com/owners/ct",
        )
        blocks = re.findall(r"<script type=\"application/ld\+json\">(.*?)</script>", scripts, re.S)
        self.assertEqual(len(blocks), 2)
        for raw in blocks:
            json.loads(raw)


if __name__ == "__main__":
    unittest.main()
