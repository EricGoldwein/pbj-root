"""SEO/indexability tests for published state ownership index pages (NY, CT, FL)."""
from __future__ import annotations

import json
import re
import unittest

from ownership.name_search import name_search_matches
from ownership.state_owner_index import (
    STATE_INDEX_META,
    format_portfolio_facility_count,
    public_owner_index_sitemap_paths,
    resolve_state_owner_index_slug,
    search_state_owner_index,
    state_index_canonical_path,
    state_index_layout_meta,
    state_index_subtitle,
    state_owner_index_is_draft,
    state_owner_index_search_suggestions,
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
        self.assertEqual(ny["subtitle"], state_index_subtitle("New York"))
        self.assertEqual(ct["subtitle"], state_index_subtitle("Connecticut"))
        self.assertIn("ownership groups", ct["subtitle"])
        self.assertNotIn("affiliated facilities", ct["subtitle"])

    def test_ct_index_matches_ny_template_markers(self):
        body, layout = render_state_owner_index_body("CT", get_canonical_slug=lambda s: "connecticut")
        self.assertIn(layout["subtitle"], body)
        self.assertIn("owners-state-hero-rail", body)
        self.assertIn('owners-state-h1-secondary">Ownership Search</span>', body)
        self.assertIn("owners-state-h1--split", body)
        self.assertIn("Largest CT portfolios", body)
        self.assertIn("About this Connecticut ownership index", body)
        self.assertGreater(body.find("owners-state-method"), body.find("owners-state-panels"))

    def test_canonical_paths(self):
        self.assertEqual(state_index_canonical_path("NY"), "/owners/ny")
        self.assertEqual(state_index_canonical_path("CT"), "/owners/ct")
        self.assertEqual(state_index_canonical_path("FL"), "/owners/fl")

    def test_fl_public_index_not_draft(self):
        self.assertFalse(state_owner_index_is_draft("FL"))
        body, layout = render_state_owner_index_body("FL", get_canonical_slug=lambda s: "florida")
        self.assertNotIn("owners-state-draft-banner", body)
        self.assertIn("Largest FL portfolios", body)
        self.assertIn(layout["subtitle"], body)

    def test_nj_public_index_not_draft(self):
        self.assertFalse(state_owner_index_is_draft("NJ"))
        body, layout = render_state_owner_index_body("NJ", get_canonical_slug=lambda s: "new-jersey")
        self.assertNotIn("owners-state-draft-banner", body)
        self.assertIn("Largest NJ portfolios", body)
        self.assertIn(layout["subtitle"], body)

    def test_sitemap_includes_public_state_pages(self):
        paths = {row[0] for row in public_owner_index_sitemap_paths()}
        self.assertEqual(paths, {"/owners/ny", "/owners/nj", "/owners/ct", "/owners/fl"})
        draft_paths = {f"/owners/{slug}" for slug in ("id",)}
        self.assertFalse(draft_paths & paths)
        for path, _pri, changefreq, lastmod in public_owner_index_sitemap_paths():
            self.assertEqual(changefreq, "weekly")
            self.assertRegex(lastmod, r"^\d{4}-\d{2}-\d{2}$")

    def test_draft_state_indexes_meta_and_slug(self):
        cases = (
            ("id", "ID", "Idaho", "idaho", "Largest ID portfolios"),
        )
        for slug, code, name, state_page_slug, portfolio_short in cases:
            with self.subTest(slug=slug):
                self.assertEqual(resolve_state_owner_index_slug(slug), code)
                self.assertTrue(state_owner_index_is_draft(code))
                layout = state_index_layout_meta(code)
                self.assertEqual(layout["canonical_path"], f"/owners/{slug}")
                self.assertIn(name, layout["page_title"])
                self.assertIn(name, layout["h1"])
                self.assertIn("Ownership Search", layout["h1"])
                self.assertEqual(STATE_INDEX_META[code]["state_page_slug"], state_page_slug)
                body, layout_out = render_state_owner_index_body(
                    code, get_canonical_slug=lambda _s, sp=state_page_slug: sp
                )
                self.assertIn(layout_out["subtitle"], body)
                self.assertIn("owners-state-draft-banner", body)
                self.assertIn(portfolio_short, body)
                self.assertIn(f"This {name} ownership index is not published", body)

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

    def test_portfolio_facility_count_labels(self):
        self.assertEqual(
            format_portfolio_facility_count("NJ", {"facility_count": 53, "facility_count_total": 72}),
            "53 in NJ · 72 total",
        )
        self.assertEqual(
            format_portfolio_facility_count("NJ", {"facility_count": 37, "facility_count_total": 37}),
            "37 in NJ",
        )
        self.assertEqual(
            format_portfolio_facility_count("NY", {"facility_count": 12}),
            "12 in NY",
        )

    def test_chow_feed_dates_include_year(self) -> None:
        from ownership.chow_lookup import format_chow_date_feed_label

        self.assertEqual(format_chow_date_feed_label("2024-05-06"), "5/6/24")
        self.assertEqual(format_chow_date_feed_label("2026-01-15"), "1/15/26")

    def test_chow_feed_details_and_meta_markup(self):
        body, _layout = render_state_owner_index_body("NJ", get_canonical_slug=lambda s: "new-jersey")
        self.assertIn('class="ownership-transfer-row"', body)
        self.assertIn('class="ownership-transfer-title"', body)
        self.assertIn('class="ownership-transfer-location"', body)
        self.assertIn('class="ownership-transfer-buyer"', body)
        self.assertIn('class="ownership-transfer-details chow-view-details"', body)
        self.assertIn(">Details</button>", body)
        self.assertNotIn("Transfer details", body)
        self.assertNotIn("Reported buyer:", body)
        self.assertNotIn("owners-state-chow-head", body)
        self.assertNotIn('ownership-transfer-location">·', body)
        self.assertIn('aria-label="View ownership transfer details for', body)

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

    def test_state_index_search_middle_name_and_prefix(self) -> None:
        """State index autocomplete uses ordered token match (e.g. Ben -> Benjamin)."""
        for code in ("NY", "CT", "FL", "NJ"):
            with self.subTest(state=code):
                rows = search_state_owner_index("Benjamin", code, limit=20)
                self.assertTrue(rows, msg=f"expected Benjamin matches in {code}")
                names = [str(r.get("name") or "") for r in rows]
                self.assertTrue(any("benjamin" in n.lower() for n in names))
                self.assertTrue(
                    name_search_matches("Ben", names[0]),
                    msg=f"prefix Ben should match top hit {names[0]!r}",
                )
                suggestions = state_owner_index_search_suggestions("Benjamin", code, limit=3)
                self.assertLessEqual(len(suggestions), 3)
                for item in suggestions:
                    self.assertIn("associate_id", item)
                    self.assertIn("name", item)
                    self.assertIn("profile_url", item)
                    self.assertIn("facility_count", item)

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
