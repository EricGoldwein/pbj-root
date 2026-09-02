"""Verify search inputs have correct HTML semantics for mobile Safari AutoFill.

iOS Safari uses input type, autocomplete, name/id, and placeholder heuristics to
classify fields and show AutoFill suggestions (password, contact, payment, location).
These tests ensure all user-facing search/discovery inputs declare explicit search
semantics so Safari shows the correct keyboard accessory (Search) instead of
irrelevant AutoFill suggestions.
"""
from __future__ import annotations

import re
import unittest


# -- helpers ------------------------------------------------------------------

def _extract_tag(html: str, pattern: str) -> str | None:
    """Return the first full <input ...> tag matching *pattern* (regex on tag)."""
    m = re.search(pattern, html, re.DOTALL)
    return m.group(0) if m else None


def _attr_value(tag: str, attr: str) -> str | None:
    """Return the value of *attr* from an HTML tag string, or None."""
    m = re.search(rf'{attr}="([^"]*)"', tag)
    return m.group(1) if m else None


def _has_attr(tag: str, attr: str) -> bool:
    """True if *attr* is present (boolean or valued) on the tag."""
    return bool(re.search(rf'\b{attr}(?:=|\s|/|>)', tag))


# -- required semantics -------------------------------------------------------

SEARCH_SEMANTICS_MINIMAL = {
    "type": "search",
    "autocomplete": "off",
    "autocapitalize": "none",
    "autocorrect": "off",
    "spellcheck": "false",
}

# Primary search / combobox inputs also get inputmode and enterkeyhint.
SEARCH_SEMANTICS_PRIMARY = {
    **SEARCH_SEMANTICS_MINIMAL,
    "inputmode": "search",
    "enterkeyhint": "search",
}


def _assert_semantics(test_case, tag: str, expected: dict, label: str) -> None:
    for attr, value in expected.items():
        actual = _attr_value(tag, attr)
        test_case.assertEqual(
            actual, value,
            f"{label}: expected {attr}=\"{value}\", got {attr}={actual!r}",
        )


# ---------------------------------------------------------------------------
class TestHomepageProviderSearch(unittest.TestCase):
    """index.html #homeSearchInput"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (Path(__file__).resolve().parents[1] / "index.html").read_text(
            encoding="utf-8"
        )

    def test_has_search_input(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="homeSearchInput"[^>]*>')
        self.assertIsNotNone(tag, "homeSearchInput not found in index.html")

    def test_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="homeSearchInput"[^>]*>')
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "homeSearchInput")

    def test_role_combobox(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="homeSearchInput"[^>]*>')
        self.assertEqual(_attr_value(tag, "role"), "combobox")

    def test_aria_autocomplete_list(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="homeSearchInput"[^>]*>')
        self.assertEqual(_attr_value(tag, "aria-autocomplete"), "list")

    def test_aria_controls(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="homeSearchInput"[^>]*>')
        self.assertEqual(_attr_value(tag, "aria-controls"), "homeSearchResults")


class TestPublicSearchOverlay(unittest.TestCase):
    """public-search.js dynamically creates #pbj-public-search-input"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.js = (Path(__file__).resolve().parents[1] / "public-search.js").read_text(
            encoding="utf-8"
        )

    def test_input_created_as_type_search(self):
        """The overlay input MUST use type='search', not type='text'."""
        tag = _extract_tag(self.js, r'<input[^>]*id="pbj-public-search-input"[^>]*>')
        self.assertIsNotNone(tag, "pbj-public-search-input not found in public-search.js")
        self.assertEqual(
            _attr_value(tag, "type"), "search",
            "Public search overlay input must use type=\"search\" for iOS Safari semantics",
        )

    def test_search_semantics(self):
        tag = _extract_tag(self.js, r'<input[^>]*id="pbj-public-search-input"[^>]*>')
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "pbj-public-search-input")

    def test_role_combobox(self):
        tag = _extract_tag(self.js, r'<input[^>]*id="pbj-public-search-input"[^>]*>')
        self.assertEqual(_attr_value(tag, "role"), "combobox")


class TestPageHeaderSwitcher(unittest.TestCase):
    """app.py _page_header_switcher_html generates #pbj-page-header-switcher-input-{mode}"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.app_py = (Path(__file__).resolve().parents[1] / "app.py").read_text(
            encoding="utf-8"
        )

    def test_switcher_input_search_semantics(self):
        """The switcher uses f-string templating; verify the template literal."""
        tag = _extract_tag(
            self.app_py,
            r'<input[^>]*id="pbj-page-header-switcher-input-\{mode\}"[^>]*>',
        )
        self.assertIsNotNone(tag, "switcher input template not found in app.py")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "switcher-template")


class TestEntityFacilitiesFilter(unittest.TestCase):
    """app.py entity facilities filter input"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.app_py = (Path(__file__).resolve().parents[1] / "app.py").read_text(
            encoding="utf-8"
        )

    def test_filter_search_semantics(self):
        tag = _extract_tag(
            self.app_py,
            r'<input[^>]*id="entityFacilitiesFilter"[^>]*>',
        )
        self.assertIsNotNone(tag, "entityFacilitiesFilter not found in app.py")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_MINIMAL, "entityFacilitiesFilter")


class TestAISupportFacilitySearch(unittest.TestCase):
    """pbj-ai-support.html #ai-facility-search"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (
            Path(__file__).resolve().parents[1] / "pbj-ai-support.html"
        ).read_text(encoding="utf-8")

    def test_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="ai-facility-search"[^>]*>')
        self.assertIsNotNone(tag, "ai-facility-search not found")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "ai-facility-search")


class TestRankingsFilter(unittest.TestCase):
    """insights_posts rankings table filter #irt-filter"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        fragment = (
            Path(__file__).resolve().parents[1]
            / "insights_posts"
            / "_rankings_table_q1_2026.fragment.html"
        )
        if fragment.exists():
            cls.html = fragment.read_text(encoding="utf-8")
        else:
            cls.html = ""

    def test_search_semantics(self):
        if not self.html:
            self.skipTest("rankings fragment not present")
        tag = _extract_tag(self.html, r'<input[^>]*id="irt-filter"[^>]*>')
        self.assertIsNotNone(tag, "irt-filter not found")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_MINIMAL, "irt-filter")


class TestNYStaffingFilter(unittest.TestCase):
    """insights-ny-minimum-staffing.html #fac-filter-search"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (
            Path(__file__).resolve().parents[1] / "insights-ny-minimum-staffing.html"
        ).read_text(encoding="utf-8")

    def test_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="fac-filter-search"[^>]*>')
        self.assertIsNotNone(tag, "fac-filter-search not found")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_MINIMAL, "fac-filter-search")


class TestCHOWSearch(unittest.TestCase):
    """templates/chow_body.html #chowSearch"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (
            Path(__file__).resolve().parents[1] / "templates" / "chow_body.html"
        ).read_text(encoding="utf-8")

    def test_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="chowSearch"[^>]*>')
        self.assertIsNotNone(tag, "chowSearch not found")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_MINIMAL, "chowSearch")


class TestOwnersHubSearch(unittest.TestCase):
    """ownership/state_owner_index_html.py #ownersHubSearchInput"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.py = (
            Path(__file__).resolve().parents[1]
            / "ownership"
            / "state_owner_index_html.py"
        ).read_text(encoding="utf-8")

    def test_search_semantics(self):
        tag = _extract_tag(self.py, r'<input[^>]*id="ownersHubSearchInput"[^>]*>')
        self.assertIsNotNone(tag, "ownersHubSearchInput not found")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "ownersHubSearchInput")


class TestOwnerProfileFilters(unittest.TestCase):
    """ownership/owner_profile_html.py #ownerFacilitiesFilter[Mobile]"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.py = (
            Path(__file__).resolve().parents[1]
            / "ownership"
            / "owner_profile_html.py"
        ).read_text(encoding="utf-8")

    def test_desktop_filter_semantics(self):
        tag = _extract_tag(self.py, r'<input[^>]*id="ownerFacilitiesFilter"[^>]*>')
        self.assertIsNotNone(tag, "ownerFacilitiesFilter not found")
        _assert_semantics(self, tag, SEARCH_SEMANTICS_MINIMAL, "ownerFacilitiesFilter")

    def test_mobile_filter_semantics(self):
        tag = _extract_tag(self.py, r'<input[^>]*id="ownerFacilitiesFilterMobile"[^>]*>')
        self.assertIsNotNone(tag, "ownerFacilitiesFilterMobile not found")
        _assert_semantics(
            self, tag, SEARCH_SEMANTICS_MINIMAL, "ownerFacilitiesFilterMobile"
        )


class TestDonorDashboardSearch(unittest.TestCase):
    """donor/templates/owner_donor_dashboard.html #searchInput"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (
            Path(__file__).resolve().parents[1]
            / "donor"
            / "templates"
            / "owner_donor_dashboard.html"
        ).read_text(encoding="utf-8")

    def test_main_search_uses_type_search(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="searchInput"[^>]*>')
        self.assertIsNotNone(tag, "searchInput not found")
        self.assertEqual(
            _attr_value(tag, "type"), "search",
            "Donor dashboard searchInput must use type=\"search\"",
        )

    def test_main_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="searchInput"[^>]*>')
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "donor-searchInput")

    def test_recipient_filter_uses_type_search(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="recipientFilter"[^>]*>')
        self.assertIsNotNone(tag, "recipientFilter not found")
        self.assertEqual(
            _attr_value(tag, "type"), "search",
            "Donor dashboard recipientFilter must use type=\"search\"",
        )

    def test_recipient_filter_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="recipientFilter"[^>]*>')
        _assert_semantics(
            self, tag, SEARCH_SEMANTICS_MINIMAL, "donor-recipientFilter"
        )


class TestDonorDashboardTopSearch(unittest.TestCase):
    """donor/templates/owner_donor_dashboard_top.html #topSearch"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (
            Path(__file__).resolve().parents[1]
            / "donor"
            / "templates"
            / "owner_donor_dashboard_top.html"
        ).read_text(encoding="utf-8")

    def test_top_search_uses_type_search(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="topSearch"[^>]*>')
        self.assertIsNotNone(tag, "topSearch not found")
        self.assertEqual(
            _attr_value(tag, "type"), "search",
            "Donor top contributors topSearch must use type=\"search\"",
        )

    def test_top_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="topSearch"[^>]*>')
        _assert_semantics(self, tag, SEARCH_SEMANTICS_MINIMAL, "donor-topSearch")


class TestDonorDashboardTestSearch(unittest.TestCase):
    """donor/templates/owner_donor_dashboard_test.html #searchInput"""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.html = (
            Path(__file__).resolve().parents[1]
            / "donor"
            / "templates"
            / "owner_donor_dashboard_test.html"
        ).read_text(encoding="utf-8")

    def test_main_search_uses_type_search(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="searchInput"[^>]*>')
        self.assertIsNotNone(tag, "searchInput not found in test dashboard")
        self.assertEqual(_attr_value(tag, "type"), "search")

    def test_main_search_semantics(self):
        tag = _extract_tag(self.html, r'<input[^>]*id="searchInput"[^>]*>')
        _assert_semantics(self, tag, SEARCH_SEMANTICS_PRIMARY, "donor-test-searchInput")


if __name__ == "__main__":
    unittest.main()
