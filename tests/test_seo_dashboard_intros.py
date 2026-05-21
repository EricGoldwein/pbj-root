"""Regression: dashboard shells must not inject visible SEO intro paragraphs."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.seo_utils import (  # noqa: E402
    dashboard_intro_must_be_empty,
    entity_page_intro_html,
    owner_page_intro_html,
    provider_page_intro_html,
)


class TestDashboardIntroEmpty(unittest.TestCase):
    def test_provider_intro_empty(self):
        intro = provider_page_intro_html('Seagate Rehabilitation and Nursing Center', ccn='335513')
        dashboard_intro_must_be_empty(intro, context='provider')

    def test_entity_intro_empty(self):
        intro = entity_page_intro_html('Genesis Healthcare')
        dashboard_intro_must_be_empty(intro, context='entity')

    def test_owner_intro_empty(self):
        intro = owner_page_intro_html('Example Owner LLC', state_names=['New York'])
        dashboard_intro_must_be_empty(intro, context='owner')


if __name__ == '__main__':
    unittest.main()
