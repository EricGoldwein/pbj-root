"""SFF list source links to hosted PBJ320 PDF."""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestSffSourcePdf(unittest.TestCase):
    def test_source_url_points_to_downloads_sff(self):
        from app import get_sff_source_url

        url = get_sff_source_url()
        if url.startswith('/downloads/sff/'):
            self.assertTrue(url.endswith('.pdf'))
            self.assertIn('sff-posting-with-candidate-list', url)
        else:
            self.assertIn('cms.gov', url)


if __name__ == '__main__':
    unittest.main()
