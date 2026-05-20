"""Regression checks for the public case-mix export rule (free CSV / AI packets)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pbj_ai_support import (  # noqa: E402
    PUBLIC_CASE_MIX_CSV_FIELDS,
    guard_stale_repeated_quarter_values,
    public_case_mix_quarter_allowlist,
    verify_public_facility_trend_case_mix_export,
)

DEFAULT_FIXTURE_CCN = '075388'


class PublicCaseMixExportRuleTests(unittest.TestCase):
    def test_allowlist_latest_quarter_only(self):
        allow = public_case_mix_quarter_allowlist(['2024Q1', '2024Q4', '2025Q3'])
        self.assertEqual(allow, {'2025Q3'})

    def test_guard_clears_repeated_case_mix(self):
        rows = [
            {'ccn': '123456', 'quarter': 'Q1 2024', 'case_mix_index': '1.40'},
            {'ccn': '123456', 'quarter': 'Q2 2024', 'case_mix_index': '1.40'},
            {'ccn': '123456', 'quarter': 'Q3 2024', 'case_mix_index': '1.40'},
            {'ccn': '123456', 'quarter': 'Q4 2024', 'case_mix_index': '1.40'},
        ]
        out = guard_stale_repeated_quarter_values(
            rows, PUBLIC_CASE_MIX_CSV_FIELDS, min_repeats=4, ccn='123456'
        )
        for row in out:
            self.assertIsNone(row.get('case_mix_index'))

    def test_verify_accepts_latest_only_case_mix(self):
        rows = [
            {'quarter': 'Q1 2024', 'total_nurse_hprd': '3.30', 'state_percentile_total_nurse_hprd': '32'},
            {'quarter': 'Q4 2025', 'total_nurse_hprd': '3.37', 'case_mix_index': '1.40',
             'cms_case_mix_total_nurse_hprd': '3.90', 'state_percentile_total_nurse_hprd': '22'},
        ]
        verify_public_facility_trend_case_mix_export(rows, ccn='123456')

    def test_verify_rejects_historic_case_mix(self):
        rows = [
            {'quarter': 'Q1 2024', 'case_mix_index': '1.40', 'total_nurse_hprd': '3.30'},
            {'quarter': 'Q4 2025', 'total_nurse_hprd': '3.37'},
        ]
        with self.assertRaises(AssertionError):
            verify_public_facility_trend_case_mix_export(rows)


class PublicCaseMixExportIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        (_ROOT / 'facility_quarterly_metrics.csv').is_file()
        or (_ROOT / 'facility_quarterly_metrics_latest.csv').is_file(),
        'facility quarterly metrics CSV not present',
    )
    def test_fixture_ccn_trend_export_shape(self):
        from app import _build_facility_quarterly_trend_csv_rows, load_facility_quarterly_for_provider
        from pbj_format import format_metric_value, format_quarter_display

        ccn = DEFAULT_FIXTURE_CCN
        fq = load_facility_quarterly_for_provider(ccn)
        if fq is None or fq.empty:
            self.skipTest(f'no PBJ rows for CCN {ccn}')
        rows = _build_facility_quarterly_trend_csv_rows(
            ccn,
            fq,
            'Test Facility',
            'CT',
            'Connecticut',
            'https://www.pbj320.com',
            format_metric_value,
            format_quarter_display,
        )
        self.assertGreater(len(rows), 4)
        verify_public_facility_trend_case_mix_export(rows, ccn=ccn)


if __name__ == '__main__':
    unittest.main(verbosity=2)
