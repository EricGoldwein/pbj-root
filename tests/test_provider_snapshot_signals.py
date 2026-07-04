"""Tests for provider_snapshot_signals scaffolding (not production-wired)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_snapshot_signals as pss  # noqa: E402


class TestProviderSnapshotSignals(unittest.TestCase):
    def test_hprd_vs_state_signal_shape(self):
        sig = pss.build_hprd_vs_state_average_signal(
            ccn='335513',
            period='CY2025Q4',
            period_display='Q4 2025',
            reported_total_hprd=3.42,
            state_average_hprd=3.38,
            state_name='New York',
            observed_display='3.42',
            state_average_display='3.38',
        )
        self.assertIsNotNone(sig)
        assert sig is not None
        self.assertEqual(sig['metric_id'], 'total_nurse_hprd')
        self.assertEqual(sig['direction'], 'near')
        self.assertIn('patterns_anchor', sig['depth_links'])
        self.assertIn('payroll', sig['explanation'].lower())

    def test_compliance_signal_uses_bundle_labels(self):
        sig = pss.build_compliance_shortfall_signal(
            ccn='335513',
            period='CY2025Q4',
            period_display='Q4 2025',
            state_code='NY',
            compliance_summary={
                'total_days_reported': 92,
                'below_state_min_days_count': 18,
                'state_min_threshold_used': 3.5,
                'state_min_metric_used': 'direct_care_hprd',
                'state_min_label': 'NY direct care minimum (3.50 HPRD)',
            },
        )
        self.assertIsNotNone(sig)
        assert sig is not None
        self.assertEqual(sig['metric_id'], 'threshold_shortfall_rate')
        self.assertEqual(sig['comparator']['threshold_type'], 'legal_minimum')
        self.assertIn('not a legal finding', sig['explanation'].lower())
        self.assertNotIn('NY NY', sig['explanation'])

    def test_build_facility_snapshot_signals_caps_count(self):
        signals = pss.build_facility_snapshot_signals(
            ccn='335513',
            period='CY2025Q4',
            period_display='Q4 2025',
            state_code='NY',
            state_name='New York',
            reported_total_hprd=3.1,
            state_average_hprd=3.38,
            observed_display='3.10',
            state_average_display='3.38',
            compliance_summary={
                'total_days_reported': 90,
                'below_state_min_days_count': 40,
                'state_min_threshold_used': 3.5,
                'state_min_metric_used': 'direct_care_hprd',
                'state_min_label': 'NY direct care minimum (3.50 HPRD)',
            },
            max_signals=4,
        )
        self.assertGreaterEqual(len(signals), 2)
        self.assertLessEqual(len(signals), 4)
        ids = {s['metric_id'] for s in signals}
        self.assertIn('total_nurse_hprd', ids)
        self.assertIn('threshold_shortfall_rate', ids)


if __name__ == '__main__':
    unittest.main()
