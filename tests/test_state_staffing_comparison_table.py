"""State staffing comparison table (state / CMS region / U.S. / rank)."""
from __future__ import annotations

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestStateStaffingComparisonTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        cls.client = app.test_client()

    def test_new_york_comparison_headers(self):
        resp = self.client.get('/state/new-york')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('pbj-staffing-cmp-table', body)
        self.assertIn('New York', body)
        self.assertIn('CMS Region 2', body)
        self.assertNotIn('New York / New Jersey', body)  # not in column header
        self.assertIn('pbj-staffing-cmp-info-wrap', body)
        self.assertIn('CMS Region 2 includes', body)
        self.assertIn('State rank', body)
        self.assertNotIn('<th scope="col">Value</th>', body)
        self.assertNotIn('pbj-staffing-cmp-rank-note', body)
        self.assertIn('pbj-staffing-cmp-caption', body)
        self.assertIn('pbj-staffing-cmp-delta', body)

    def test_new_york_case_mix_and_rural_not_na(self):
        resp = self.client.get('/state/new-york')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        import re
        row = re.search(r'Median Case-Mix HPRD.*?</tr>', body, re.S)
        self.assertIsNotNone(row, 'case-mix row missing')
        row_html = row.group(0)
        # Region and U.S. should not be empty when provider/bundle data exists.
        self.assertNotIn('pbj-staffing-cmp-na', row_html, row_html[:280])
        self.assertRegex(row_html, r'pbj-staffing-cmp-val--cmp[^>]*>.*?pbj-staffing-cmp-primary')
        rural_row = re.search(r'Rural Facilities \(Share\).*?</tr>', body, re.S)
        self.assertIsNotNone(rural_row)
        rural_html = rural_row.group(0)
        # U.S. rural is always known; region may still be em dash only if provider urban missing.
        self.assertIn('27%', rural_html)
        resp = self.client.get('/state/connecticut')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('CMS Region 1', body)
        self.assertIn('vs CT', body)

    def test_comparison_row_structure(self):
        resp = self.client.get('/state/texas')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('Total Nurse Staffing HPRD', body)
        self.assertIn('Rural Facilities (Share)', body)
        self.assertRegex(body, r'pbj-staffing-cmp-val--state[^>]*data-label="Texas"')
        self.assertIn('CMS Region 6', body)
        self.assertIn('pbj-staffing-cmp-na', body)  # may appear if missing; table uses em dash class

    def test_region_metrics_helpers(self):
        from app import (
            format_cms_region_member_list_prose,
            format_cms_region_short_header,
            get_canonical_latest_quarter,
            get_national_quarter_metrics,
            get_region_quarter_metrics,
            get_states_in_cms_region,
            _staffing_cmp_delta_text,
        )

        q = get_canonical_latest_quarter()
        self.assertTrue(q)
        nat = get_national_quarter_metrics(q)
        self.assertIsInstance(nat, dict)
        self.assertIn('Total_Nurse_HPRD', nat)
        ct_states = get_states_in_cms_region(1)
        self.assertIn('CT', ct_states)
        region = get_region_quarter_metrics(1, q)
        self.assertIsInstance(region, dict)
        self.assertIsNotNone(region.get('Total_Nurse_HPRD'))
        self.assertEqual(format_cms_region_short_header(2), 'CMS Region 2')
        members = format_cms_region_member_list_prose(get_states_in_cms_region(2))
        self.assertIn('New York', members)
        self.assertIn('New Jersey', members)
        delta = _staffing_cmp_delta_text(3.59, 3.63, 'hprd', 'NY')
        self.assertEqual(delta, '+0.04 vs NY')
        same = _staffing_cmp_delta_text(3.59, 3.59, 'hprd', 'NY')
        self.assertEqual(same, 'Same as NY')

    def test_render_helper_escapes_html(self):
        from app import render_state_staffing_comparison_table

        html_out = render_state_staffing_comparison_table(
            'Test<script>',
            'TS',
            1,
            'Connecticut, Massachusetts',
            [{
                'metric': 'RN HPRD',
                'state_primary': '1.00',
                'region_primary': '0.90',
                'us_primary': '0.95',
                'region_delta': '+0.10 vs TS',
                'us_delta': '+0.05 vs TS',
                'rank': '#1 of 51',
            }],
        )
        self.assertNotIn('<script>', html_out)
        self.assertIn('Test&lt;script&gt;', html_out)
        self.assertIn('pbj-staffing-cmp-delta', html_out)


if __name__ == '__main__':
    unittest.main()
