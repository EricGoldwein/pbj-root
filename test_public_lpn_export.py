"""Regression checks: LPN HPRD is explicit PBJ only (no total − RN − aide imputation)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import _lpn_hprd_from_facility_quarterly_row  # noqa: E402


class PublicLpnExportTests(unittest.TestCase):
    def test_no_residual_imputation(self):
        row = {
            'Total_Nurse_HPRD': 3.48,
            'RN_HPRD': 0.74,
            'Nurse_Assistant_HPRD': 2.01,
        }
        self.assertIsNone(_lpn_hprd_from_facility_quarterly_row(row))

    def test_reads_explicit_lpn_hprd(self):
        row = {'LPN_HPRD': 0.61, 'Total_Nurse_HPRD': 3.48, 'RN_HPRD': 0.74}
        self.assertEqual(_lpn_hprd_from_facility_quarterly_row(row), 0.61)

    def test_zero_lpn_is_valid(self):
        row = {'LPN_HPRD': 0.0}
        self.assertEqual(_lpn_hprd_from_facility_quarterly_row(row), 0.0)


if __name__ == '__main__':
    unittest.main()
