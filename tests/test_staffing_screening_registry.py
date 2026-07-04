"""Tests for staffing metric + state rule registry (daily PBJ screens)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import staffing_screening_registry as ssr  # noqa: E402
from site_public_config import inject_public_html_cms_urls  # noqa: E402


class TestStaffingScreeningRegistry(unittest.TestCase):
    def test_ny_rule_uses_direct_care_350(self):
        rule = ssr.get_daily_screen_rule('NY')
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule['metric_id'], 'direct_care_hprd')
        self.assertAlmostEqual(float(rule['threshold']), 3.5)
        self.assertEqual(rule['rule_type'], 'statutory_minimum')

    def test_ct_rule_uses_total_nursing_306(self):
        rule = ssr.get_daily_screen_rule('CT')
        self.assertIsNotNone(rule)
        assert rule is not None
        self.assertEqual(rule['metric_id'], 'total_nurse_hprd')
        self.assertAlmostEqual(float(rule['threshold']), 3.06)

    def test_every_rule_has_defined_metric(self):
        for rule in ssr.daily_screen_rules():
            metric = ssr.get_staffing_metric(rule['metric_id'])
            self.assertIsNotNone(metric, msg=rule.get('id'))

    def test_validate_daily_screen_rules_passes(self):
        self.assertEqual(ssr.validate_daily_screen_rules(), [])

    def test_data_sources_methodology_mentions_ny_direct_care_not_356_screen(self):
        html = ssr.compose_data_sources_pbj_daily_staffing_html()
        self.assertIn('3.50', html)
        self.assertIn('direct-care', html.lower())
        self.assertNotIn('3.56</strong> total nursing HPRD', html)
        self.assertNotIn('New York screens use <strong>3.56</strong>', html)

    def test_data_sources_page_injection(self):
        raw = '<li id="pbj-daily-staffing">__PBJ_DAILY_STAFFING_METHODOLOGY__</li>'
        out = inject_public_html_cms_urls(raw)
        self.assertNotIn('__PBJ_DAILY_STAFFING_METHODOLOGY__', out)
        self.assertIn('3.50', out)
        self.assertNotIn('3.56</strong> total nursing HPRD', out)


if __name__ == '__main__':
    unittest.main()
