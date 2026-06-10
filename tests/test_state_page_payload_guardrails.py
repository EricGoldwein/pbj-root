"""Guardrails: state page payload size, CHOW lazy details, aggregate source."""
from __future__ import annotations

import re
import unittest
from unittest.mock import patch

# Targets after CHOW lazy-detail SSR (initial_visible rows only embed panels).
NY_MAX_HTML_BYTES = 480_000
TX_MAX_HTML_BYTES = 260_000
MAX_CHOW_DETAIL_STORES_NY = 12
MAX_DOM_NODES_APPROX = 4_500


class TestStatePagePayloadGuardrails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import app

        cls.client = app.test_client()

    def _get(self, path: str):
        return self.client.get(path)

    def test_warmup_aggregates_hydrated_or_fallback(self):
        resp = self._get('/warmup')
        self.assertEqual(resp.status_code, 200)
        agg = resp.get_json().get('checks', {}).get('state_page_aggregates', {})
        self.assertTrue(agg.get('bundle_exists') or agg.get('live_fallback'))
        self.assertIn('validation_reason', agg)

    def test_texas_html_size_and_chow_lazy(self):
        resp = self._get('/state/texas')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data()
        self.assertLess(len(body), TX_MAX_HTML_BYTES, f'TX HTML {len(body):,} bytes')
        text = body.decode('utf-8', 'replace')
        hdr = resp.headers.get('X-PBJ-State-Aggregates') or resp.headers.get('x-pbj-state-aggregates')
        self.assertIn(hdr, ('hydrated', 'live_fallback'))
        self.assertEqual(len(re.findall(r'class="state-hr-facility-name"', text)), 0)
        self.assertIn('data-state-high-risk="1"', text)

    def test_ny_html_size_chow_stores_capped(self):
        from ownership.beta_gate import ownership_beta_enabled_for_state

        if not ownership_beta_enabled_for_state('NY'):
            self.skipTest('NY ownership not enabled')
        resp = self._get('/state/new-york')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data()
        text = body.decode('utf-8', 'replace')
        stores = len(re.findall(r'class="chow-detail-store"', text))
        lazy = len(re.findall(r'data-chow-lazy-id=', text))
        self.assertLess(len(body), NY_MAX_HTML_BYTES, f'NY HTML {len(body):,} bytes')
        self.assertLessEqual(stores, MAX_CHOW_DETAIL_STORES_NY, f'{stores} chow-detail-store embeds')
        self.assertGreater(lazy, 0, 'expected lazy CHOW detail buttons beyond first page')

    def test_high_risk_api_aggregate_cache_when_hydrated(self):
        from app import _STATE_PAGE_AGGREGATES_HYDRATE_OK

        resp = self._get('/api/state/TX/high-risk-table?category=sff')
        self.assertEqual(resp.status_code, 200)
        src = resp.headers.get('X-Pbj-High-Risk-Source') or resp.headers.get('x-pbj-high-risk-source')
        if _STATE_PAGE_AGGREGATES_HYDRATE_OK:
            self.assertEqual(src, 'aggregate_cache')
        else:
            self.assertIn(src, ('aggregate_cache', 'live_fallback'))

    def test_chow_transfer_detail_api(self):
        from ownership.chow_lookup import chow_records_for_state

        rows = chow_records_for_state('NY', limit=1)
        if not rows:
            self.skipTest('no NY CHOW rows in index')
        cid = rows[0].get('chow_id')
        self.assertTrue(cid)
        resp = self.client.get(f'/api/chow/transfer-detail/{cid}?state=NY')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('html', data)
        self.assertIn('chow-detail', data['html'])

    def test_chow_cap_still_truncates_with_link(self):
        from ownership.page_integrations import _render_state_chow_recent_table

        fake_rows = [
            {
                'chow_id': f'r{i}',
                'effective_date': '2025-01-01',
                'buyer_org_name': f'Buyer {i}',
                'seller_org_name': f'Seller {i}',
                'ccn': f'{i:06d}',
                'state': 'TX',
                'buyer_owner_url': '/owners/buyer',
                'seller_owner_url': '/owners/seller',
            }
            for i in range(120)
        ]
        with patch('ownership.page_integrations.chow_records_for_state', return_value=fake_rows):
            html = _render_state_chow_recent_table('TX')
        self.assertIn('chow-state-truncate-note', html)
        panel_divs = len(re.findall(r'class="chow-detail-store" hidden', html))
        self.assertLessEqual(panel_divs, 12)
        self.assertGreater(html.count('data-chow-lazy-id='), 0)


if __name__ == '__main__':
    unittest.main()
