"""State page aggregate bundle validation (deploy fast path)."""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import state_page_aggregates as spa  # noqa: E402


class StatePageAggregatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.data_dir = os.path.join(self.root, 'data')
        os.makedirs(self.data_dir, exist_ok=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_csv(self, rel: str, body: str) -> str:
        path = os.path.join(self.root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        return path

    def test_v2_signature_survives_mtime_touch(self) -> None:
        fq_rel = 'facility_quarterly_metrics.csv'
        prov_rel = 'provider_info_combined_latest.csv'
        self._write_csv(fq_rel, 'STATE,CY_Qtr\nNY,2025Q4\n')
        self._write_csv(prov_rel, 'ccn,state\n015009,NY\n')

        bundle = {
            'version': spa.BUNDLE_VERSION,
            'built_at': '2026-06-09T00:00:00Z',
            'canonical_quarter': '2025Q4',
            'sources': {
                'facility_quarterly': spa.source_meta(
                    os.path.join(self.root, fq_rel), self.root
                ),
                'provider_primary': spa.source_meta(
                    os.path.join(self.root, prov_rel), self.root
                ),
            },
            'facility_counts_by_quarter': {'2025Q4': {'NY': 1}},
        }
        out_path = spa.write_bundle(self.root, bundle)
        self.assertTrue(os.path.isfile(out_path))

        fq_abs = os.path.join(self.root, fq_rel)
        os.utime(fq_abs, (1_700_000_000, 1_700_000_001))

        status = spa.inspect_bundle_status(self.root)
        self.assertTrue(status['bundle_exists'])
        self.assertTrue(status['validation_ok'], status)
        loaded = spa.load_bundle(self.root)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.get('canonical_quarter'), '2025Q4')

    def test_inspect_reports_missing_bundle(self) -> None:
        status = spa.inspect_bundle_status(self.root)
        self.assertFalse(status['bundle_exists'])
        self.assertEqual(status['validation_reason'], 'bundle_missing')
        self.assertTrue(status['live_fallback'])

    def test_v1_mtime_rejected_after_touch(self) -> None:
        fq_rel = 'facility_quarterly_metrics.csv'
        path = self._write_csv(fq_rel, 'a\n1\n')
        meta = spa.source_meta(path, self.root)
        bundle = {
            'version': 1,
            'sources': {'facility_quarterly': meta},
        }
        spa.write_bundle(self.root, bundle)
        os.utime(path, (1_700_000_000, 1_700_000_002))
        ok, reason, _details = spa.validate_bundle_sources(self.root, bundle)
        self.assertFalse(ok)
        self.assertIn('mtime', reason)


if __name__ == '__main__':
    unittest.main()
