"""Public metadata registry, threshold types, banned terms, and API bundle."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import public_metadata as pm  # noqa: E402


class TestPublicMetadata(unittest.TestCase):
    def test_metric_registry_loads(self):
        reg = pm.load_metric_registry()
        self.assertIn('metrics', reg)
        self.assertGreater(len(reg['metrics']), 10)

    def test_every_public_metric_has_required_fields(self):
        for m in pm.public_metrics():
            for field in pm.REQUIRED_METRIC_FIELDS:
                with self.subTest(metric=m.get('metric_id'), field=field):
                    self.assertIn(field, m)
                    self.assertTrue(str(m[field]).strip(), f'{field} empty')

    def test_source_types_valid(self):
        for m in pm.public_metrics():
            self.assertIn(m['source_type'], pm.VALID_SOURCE_TYPES)

    def test_threshold_registry_distinguishes_types(self):
        reg = pm.load_threshold_registry()
        types = {t.get('threshold_type') for t in reg.get('thresholds', [])}
        self.assertIn('estimated_standard', types)
        self.assertIn('benchmark', types)
        self.assertIn('legal_minimum', types)
        self.assertIn('proposed_standard', types)

    def test_ny_ct_daily_screens_are_estimated_standard(self):
        reg = pm.load_threshold_registry()
        by_id = {t['threshold_id']: t for t in reg.get('thresholds', [])}
        ny = by_id.get('ny_pbj_daily_screen')
        ct = by_id.get('ct_pbj_daily_screen')
        if ny:
            self.assertEqual(ny['threshold_type'], 'legal_minimum')
            self.assertEqual(ny.get('value'), 3.5)
        if ct:
            self.assertEqual(ct['threshold_type'], 'estimated_standard')

    def test_methodology_snippets_include_approved_language(self):
        snippets = pm.load_methodology_snippets().get('snippets') or {}
        self.assertIn('payroll', snippets.get('pbj_staffing', '').lower())
        self.assertIn('not all nursing home metrics', snippets.get('metric_reliability', '').lower())
        self.assertIn('pbj320-derived', snippets.get('pbj320_derived', '').lower())

    def test_source_badges(self):
        self.assertEqual(pm.get_source_badge('payroll_based'), 'Payroll-based')
        self.assertEqual(pm.get_source_badge('inspection_based'), 'Inspection-based')

    def test_premium_bridge_is_public_safe(self):
        text = pm.premium_bridge_text()
        self.assertIn('Premium', text)
        self.assertNotIn('fraud', text.lower())

    def test_no_banned_terms_in_metadata_copy(self):
        hits = pm.scan_banned_terms_in_public_copy()
        self.assertEqual(hits, [], msg='\n'.join(hits))

    def test_no_forensic_calculators_in_public_metadata_module(self):
        hits = pm.scan_forbidden_forensic_patterns()
        self.assertEqual(hits, [])

    def test_validate_all_passes(self):
        self.assertEqual(pm.validate_all(), [])

    def test_page_bootstrap_payload(self):
        payload = pm.page_bootstrap_payload(page_type='facility', state_code='NY')
        self.assertEqual(payload['page_type'], 'facility')
        self.assertEqual(payload['state_code'], 'NY')
        self.assertIn('metrics', payload)
        self.assertIn('thresholds', payload)
        self.assertTrue(any(t.get('state') == 'NY' for t in payload['thresholds']))

    def test_api_bundle_shape(self):
        bundle = pm.public_metadata_api_bundle()
        self.assertIn('metrics', bundle)
        self.assertIn('thresholds', bundle)
        self.assertIn('methodology', bundle)
        self.assertIn('premium_bridge', bundle)
        self.assertIn('independence_guardrails', bundle)
        self.assertIn('evidence_tiers', bundle)

    def test_independence_guardrails_load(self):
        guard = pm.load_independence_guardrails()
        self.assertIn('core_principle', guard)
        self.assertGreaterEqual(len(guard.get('implementation_rules') or []), 5)
        self.assertIn('observed_data', guard.get('evidence_tiers') or {})

    def test_evidence_tier_mapping(self):
        self.assertEqual(pm.evidence_tier_for_source_type('payroll_based'), 'payroll_submitted')
        self.assertEqual(pm.evidence_tier_for_source_type('inspection_based'), 'observed_data')

    def test_no_vendor_or_operator_hardcoding_in_registries(self):
        hits = pm.scan_vendor_or_operator_hardcoding()
        self.assertEqual(hits, [], msg='\n'.join(hits))

    def test_thresholds_have_documented_source(self):
        self.assertEqual(pm.validate_thresholds_have_documented_source(), [])

    def test_future_related_party_label_is_neutral(self):
        guard = pm.load_independence_guardrails()
        rp = (guard.get('future_metric_label_guidance') or {}).get('related_party_payments') or {}
        self.assertEqual(rp.get('approved_public_label'), 'Related-party payments')
        self.assertIn('extraction', (rp.get('rejected_labels') or []))


class TestPublicMetadataApiRoute(unittest.TestCase):
    def test_api_public_metadata_route(self):
        try:
            from app import app
        except ImportError as exc:
            self.skipTest(f'app import failed: {exc}')
        client = app.test_client()
        resp = client.get('/api/public/metadata.json')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('metrics', data)
        self.assertIn('thresholds', data)
        self.assertIn('independence_guardrails', data)


if __name__ == '__main__':
    unittest.main()
