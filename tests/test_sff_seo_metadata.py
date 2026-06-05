"""Regression: SFF routes must never inherit PBJ Wrapped OG metadata."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.seo_utils import get_seo_metadata  # noqa: E402


class TestSffSeoMetadata(unittest.TestCase):
    def test_sff_usa_lowercase(self):
        meta = get_seo_metadata('/sff/usa')
        self.assertIn('Special Focus Facilities', meta['og_title'])
        self.assertNotIn('PBJ Wrapped', meta['og_title'])

    def test_sff_usa_mixed_case_does_not_fall_through_to_wrapped(self):
        meta = get_seo_metadata('/sff/USA')
        self.assertIn('Special Focus Facilities', meta['og_title'])
        self.assertNotIn('PBJ Wrapped', meta['og_title'])

    def test_sff_state_page(self):
        meta = get_seo_metadata('/sff/ny')
        self.assertEqual(meta['og_title'], 'New York Special Focus Facilities')

    def test_sff_state_page_mixed_case(self):
        meta = get_seo_metadata('/sff/NY')
        self.assertEqual(meta['og_title'], 'New York Special Focus Facilities')
        self.assertNotIn('PBJ Wrapped', meta['og_title'])

    def test_sff_region_page(self):
        meta = get_seo_metadata('/sff/region3')
        self.assertEqual(meta['og_title'], 'SFF Program: CMS Region 3')

    def test_wrapped_still_uses_wrapped_title(self):
        meta = get_seo_metadata('/wrapped/usa')
        self.assertIn('PBJ Wrapped', meta['og_title'])


if __name__ == '__main__':
    unittest.main()
