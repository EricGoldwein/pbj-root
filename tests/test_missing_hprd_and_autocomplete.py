"""Regression: missing HPRD must not fabricate percentiles or takeaway claims."""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestMissingHprdGuards(unittest.TestCase):
    def test_percentiles_reject_none_total(self):
        import app as app_mod

        pct_t, pct_rn = app_mod._percentiles_for_state_quarter(
            'NY', '2026Q1', None, None, allow_index_build=False
        )
        self.assertIsNone(pct_t)
        self.assertIsNone(pct_rn)

    def test_format_percentile_phrase_empty_on_none(self):
        import app as app_mod

        self.assertEqual(app_mod.format_percentile_phrase(None, 'New York'), '')

    def test_get_facility_state_percentile_none_input(self):
        import app as app_mod

        pct_t, pct_rn = app_mod.get_facility_state_percentile(
            '335513', 'NY', '2026Q1', None, None
        )
        self.assertIsNone(pct_t)
        self.assertIsNone(pct_rn)

    def test_classify_with_missing_reported_not_used_as_zero(self):
        """Document expected caller behavior: do not call _classify with coerced 0."""
        # _classify is nested inside generate_provider_page_html; assert public API instead.
        import app as app_mod

        phrase = app_mod.format_percentile_phrase(0, 'New York')
        # A real 0th percentile is allowed when computed; None input must stay empty.
        self.assertTrue(phrase.startswith('in the bottom'))
        self.assertEqual(app_mod.format_percentile_phrase(None, 'New York'), '')


class TestOwnersAutocompleteSoftFail(unittest.TestCase):
    def test_autocomplete_returns_200_without_donations_db(self):
        # Import donor blueprint app via main Flask app if registered.
        import app as app_mod

        client = app_mod.app.test_client()
        resp = client.get('/owners/api/autocomplete?q=gen')
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True)[:500])
        data = resp.get_json()
        self.assertIn('suggestions', data)
        self.assertIsInstance(data['suggestions'], list)


if __name__ == '__main__':
    unittest.main()
