"""USA national page at /state/usa."""
from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestUsaStatePage(unittest.TestCase):
    def test_is_usa_page_slug(self):
        from app import is_usa_page_slug

        self.assertTrue(is_usa_page_slug('usa'))
        self.assertTrue(is_usa_page_slug('US'))
        self.assertTrue(is_usa_page_slug('united-states'))
        self.assertFalse(is_usa_page_slug('fl'))
        self.assertFalse(is_usa_page_slug('florida'))

    def test_national_chart_data_has_lpn(self):
        from app import get_national_historical_chart_data, get_pd

        self.assertIsNotNone(get_pd())
        data = get_national_historical_chart_data()
        self.assertIsNotNone(data)
        self.assertTrue(data.get('lpn'))
        self.assertTrue(any(v is not None for v in data['lpn']))
        self.assertTrue(data.get('lpn_care'))

    def test_usa_page_route(self):
        from app import app

        client = app.test_client()
        resp = client.get('/state/usa')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('United States PBJ', body)
        self.assertIn('data-state-code="usa"', body)
        self.assertNotIn('National Rank', body)

    def test_usa_chart_api(self):
        from app import app

        client = app.test_client()
        resp = client.get('/api/state/usa/chart-data')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('raw_quarters', data)
        self.assertIn('lpn', data)


if __name__ == '__main__':
    unittest.main()
