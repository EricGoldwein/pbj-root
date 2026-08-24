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

    def test_current_provider_markup_is_cacheable(self) -> None:
        app = (_ROOT / "app.py").read_text(encoding="utf-8")
        for marker in (
            "pbj-cmi-modal-related",
            "pbj-casemix-cmi-strip--intoprow",
            "pbj-takeaway-compliance-note",
        ):
            self.assertNotIn(f"if '{marker}' in body:", app)

    def test_related_associates_has_cache_and_accessible_retry(self) -> None:
        app = (_ROOT / "app.py").read_text(encoding="utf-8")
        js = (_ROOT / "ownership" / "owner-profile.js").read_text(encoding="utf-8")
        html = (_ROOT / "ownership" / "owner_profile_html.py").read_text(encoding="utf-8")
        self.assertIn("_RELATED_ASSOCIATES_CACHE", app)
        self.assertIn("X-PBJ-Related-Cache", app)
        self.assertIn("aria-busy", js)
        self.assertIn("owner-associates-retry", js)
        self.assertIn('role="status"', html)

    def test_mobile_ccn_hint_and_home_signup_remain_visible(self) -> None:
        html = (_ROOT / "index.html").read_text(encoding="utf-8")
        audience_js = (_ROOT / "pbj-audience.js").read_text(encoding="utf-8")
        self.assertIn("? 'Name or 6-digit CCN'", html)
        self.assertIn("homeMount.closest('.home-subscribe-band')", audience_js)
        self.assertIn("homeBand.hidden = true", audience_js)

    def test_provider_cold_admission_protects_health_thread(self) -> None:
        app = (_ROOT / "app.py").read_text(encoding="utf-8")
        perf = (_ROOT / "pbj_provider_perf.py").read_text(encoding="utf-8")
        route_start = app.index("def _provider_page_impl(")
        route_end = app.index("def _state_page_impl(", route_start)
        route = app[route_start:route_end]
        self.assertLess(
            route.index("acquired = sem.acquire"),
            route.index("_ensure_provider_indexes_hydrated()"),
        )
        self.assertIn("default = '0' if (os.environ.get('RENDER')", app)
        self.assertIn("'googleother'", perf)

    def test_pandas_warmup_does_not_block_home_search_or_all_threads(self) -> None:
        app = (_ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("_PANDAS_INIT_LOCK = threading.Lock()", app)
        self.assertIn("'/search_index.json'", app)
        self.assertIn("'/public-search.js'", app)
        self.assertIn("_PANDAS_INIT_LOCK.acquire(blocking=False)", app)
        self.assertIn("'Service is warming up; retry shortly.'", app)

    def test_provider_cold_path_avoids_national_entity_rebuild_and_dead_end(self) -> None:
        app = (_ROOT / "app.py").read_text(encoding="utf-8")
        integrations = (_ROOT / "ownership" / "page_integrations.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("load_entity_facilities(eid, attach_quarterly_metrics=False)", app)
        self.assertIn("entity_id, entity_name, raw_quarter, attach_metrics=False", app)
        self.assertIn("@lru_cache(maxsize=32)\ndef _collect_cmi_series", app)
        self.assertIn('cms_lookup_complete=True', app)
        self.assertIn('if cms is None and not cms_lookup_complete:', integrations)
        self.assertIn('This page will retry automatically in {ra} seconds.', app)
        self.assertIn("return _provider_busy_response('3')", app)


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
