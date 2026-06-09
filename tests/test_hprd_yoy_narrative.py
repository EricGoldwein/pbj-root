"""YoY staffing-ratio takeaway narrative tiers."""
from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _fmt(v, _k, d='N/A'):
    return f'{float(v):.2f}'


_SUBJECT = "Florida's statewide staffing ratio"


class TestHprdYoyNarrative(unittest.TestCase):
    def test_unchanged_within_one_cent(self):
        from app import _staffing_ratio_yoy_sentence

        s = _staffing_ratio_yoy_sentence(0.004, 3.79, '2025Q4', _fmt, _SUBJECT)
        self.assertIn("Florida's statewide staffing ratio remains in line with Q4 2024", s)
        self.assertIn('3.79', s)
        self.assertNotIn('up 0.00', s)

    def test_slightly_up(self):
        from app import _staffing_ratio_yoy_sentence

        s = _staffing_ratio_yoy_sentence(0.03, 3.76, '2025Q4', _fmt, _SUBJECT)
        self.assertIn("is up slightly (+0.03) since Q4 2024", s)

    def test_clearly_down(self):
        from app import _staffing_ratio_yoy_sentence

        s = _staffing_ratio_yoy_sentence(-0.12, 3.88, '2025Q4', _fmt, _SUBJECT)
        self.assertIn('is down (−0.12) since Q4 2024', s)
        self.assertNotIn('slightly', s)

    def test_nationwide_subject(self):
        from app import _staffing_ratio_yoy_sentence

        s = _staffing_ratio_yoy_sentence(
            0.02, 3.73, '2025Q4', _fmt, 'The nationwide staffing ratio',
        )
        self.assertTrue(s.startswith('The nationwide staffing ratio is up slightly (+0.02)'))


if __name__ == '__main__':
    unittest.main()
