"""Targeted tests for the case-mix Metric Lineage layer (ProviderInfoResolution's
resolution_status / case_mix_methodology, case_mix_lineage_note,
case_mix_methodology_transition_note_for_quarters, and derived-metric lineage on
get_provider_info_cmi_reference_stats).

Background: CMS switched the staffing case-mix adjustment methodology from RUG-IV
to PDPM starting with PBJ 2024Q1 (staffing measures frozen April-June 2024;
first publicly posted at the July 31, 2024 Care Compare refresh -- QSO-23-21-NH /
QSO-24-14-NH). No PBJ quarter tag "2023Q4" exists in this repo's historical
Provider Info archive -- CMS's monthly releases jump from "Q3 2023" straight to
"Q1 2024". A request for 2023Q4 must resolve to 2023Q3 via the existing
nearest-prior fallback (established in test_provider_info_historical_archive.py)
and MUST NOT be described as if CMS published a distinct Q4 2023 case-mix
observation, and must never borrow the (differently-methodologied) Q1 2024 value.

Does not re-verify the archive/resolver itself -- see
test_provider_info_quarter_resolution.py and test_provider_info_historical_archive.py.
"""

from __future__ import annotations

import unittest

import pandas as pd

import app as app_mod


def _reset_caches() -> None:
    app_mod._LOAD_PROVIDER_INFO_CACHE = None
    app_mod._LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
    app_mod._LOAD_PROVIDER_INFO_AT = 0
    app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_CACHE = None
    app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_AT = 0.0
    app_mod._PROVIDER_INFO_HISTORY_CACHE = None
    app_mod._PROVIDER_INFO_HISTORY_QUARTERS_CACHE = None


class ExactAndFallbackLineageTests(unittest.TestCase):
    """Part 8 minimum contract #1."""

    def setUp(self) -> None:
        _reset_caches()

    tearDown = setUp

    def test_exact_2023q3_is_exact_rug_iv(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q3')
        self.assertEqual(res.matched_quarter, '2023Q3')
        self.assertEqual(res.resolution_status, 'exact')
        self.assertEqual(res.case_mix_methodology, 'RUG-IV')

    def test_requested_2023q4_matches_2023q3_as_prior_fallback_rug_iv(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        self.assertEqual(res.requested_quarter, '2023Q4')
        self.assertEqual(res.matched_quarter, '2023Q3')
        self.assertEqual(res.resolution_status, 'prior_fallback')
        self.assertEqual(res.case_mix_methodology, 'RUG-IV')

    def test_requested_2023q4_never_takes_2024q1(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        self.assertNotEqual(res.matched_quarter, '2024Q1')

    def test_2024q1_is_exact_pdpm(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2024Q1')
        self.assertEqual(res.matched_quarter, '2024Q1')
        self.assertEqual(res.resolution_status, 'exact')
        self.assertEqual(res.case_mix_methodology, 'PDPM')

    def test_missing_period_resolution_status_is_missing(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2013Q1')
        self.assertEqual(res.resolution_status, 'missing')
        self.assertIsNone(res.case_mix_methodology)

    def test_current_semantic_is_always_exact(self) -> None:
        res = app_mod.resolve_provider_info_current('075325')
        self.assertEqual(res.resolution_status, 'exact')


class AnnotationBehaviorTests(unittest.TestCase):
    """Part 8 minimum contract #3: fallback/methodology notes fire exactly when warranted."""

    def setUp(self) -> None:
        _reset_caches()

    tearDown = setUp

    def test_2023q4_fallback_triggers_note_naming_both_quarters(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNotNone(note)
        self.assertIn('Q4 2023', note['text'])
        self.assertIn('Q3 2023', note['text'])
        self.assertIn('RUG-IV', note['text'])
        # Never phrased as if CMS published a distinct Q4 2023 observation.
        self.assertNotIn('CMS published', note['text'])

    def test_2023q4_fallback_note_never_cites_q1_2024_as_a_source_quarter(self) -> None:
        # "pre-2024" is fine as a methodology-boundary descriptor; the note must not
        # name Q1 2024 as if it were a quarter this value came from.
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        note = app_mod.case_mix_lineage_note(res)
        self.assertNotIn('Q1 2024', note['text'])

    def test_ordinary_exact_rug_iv_quarter_gets_methodology_note_not_silence(self) -> None:
        # 2023Q3 is an exact match but still pre-PDPM -- the site's default "based on
        # PDPM" case-mix caveat does not apply to it, so it still needs a (different,
        # non-fallback) methodology note.
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q3')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNotNone(note)
        self.assertEqual(note['kind'], 'legacy_methodology')

    def test_modern_pdpm_exact_quarter_has_no_note(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2026Q1')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNone(note)

    def test_methodology_source_cited_when_rug_iv_involved(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        note = app_mod.case_mix_lineage_note(res)
        self.assertEqual(note['source_url'], app_mod.CMS_QSO_24_14_NH_URL)

    def test_historical_range_crossing_boundary_exposes_transition_note(self) -> None:
        note = app_mod.case_mix_methodology_transition_note_for_quarters(
            ['2023Q1', '2023Q2', '2023Q3', '2024Q1', '2024Q2']
        )
        self.assertIsNotNone(note)
        self.assertIn('RUG-IV', note)
        self.assertIn('PDPM', note)

    def test_modern_pdpm_only_range_has_no_transition_marker(self) -> None:
        note = app_mod.case_mix_methodology_transition_note_for_quarters(
            ['2024Q2', '2025Q1', '2025Q2', '2026Q1']
        )
        self.assertIsNone(note)

    def test_legacy_only_range_has_no_transition_marker(self) -> None:
        note = app_mod.case_mix_methodology_transition_note_for_quarters(
            ['2018Q1', '2019Q1', '2023Q3']
        )
        self.assertIsNone(note)

    def test_unrelated_staffing_hprd_chart_data_carries_no_case_mix_note(self) -> None:
        # Regression guard for "unrelated staffing metrics do not acquire a case-mix
        # asterisk": _provider_charts_chartjs_data's non-case-mix sections must never
        # gain a cmiSourceNote-shaped key.
        fac = pd.DataFrame(
            [
                {
                    'CY_Qtr': q, 'Total_Nurse_HPRD': 4.0, 'Nurse_Care_HPRD': 3.5,
                    'RN_HPRD': 0.6, 'RN_Care_HPRD': 0.5, 'LPN_HPRD': 1.0,
                    'LPN_Care_HPRD': 0.9, 'Nurse_Assistant_HPRD': 2.4,
                    'Contract_Percentage': 0.0, 'avg_daily_census': 84.0,
                }
                for q in ('2023Q3', '2023Q4', '2024Q1')
            ]
        )
        out = app_mod._provider_charts_chartjs_data(
            fac, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='075325',
        )
        for key in ('totalHprd', 'rnHprd', 'staffingRole', 'contract', 'census'):
            self.assertNotIn('cmiSourceNote', out.get(key) or {})


class DerivedMetricLineageTests(unittest.TestCase):
    """Part 8 minimum contract #2: at least one real PBJ320-derived case-mix metric
    preserves input source period, fallback state, methodology, and calculation
    origin. get_provider_info_cmi_reference_stats (national CMI percentile/quantile
    reference used on the provider page's case-mix strip) is PBJ320-derived -- CMS
    does not publish this distribution itself."""

    def setUp(self) -> None:
        app_mod._CMI_REF_STATS_CACHE = {}
        app_mod._CMI_NATIONAL_SORTED_CACHE = {}
        app_mod._collect_cmi_series_from_provider_csv.cache_clear()
        self._orig_paths_fn = app_mod._cmi_reference_source_paths

    def tearDown(self) -> None:
        app_mod._cmi_reference_source_paths = self._orig_paths_fn
        app_mod._CMI_REF_STATS_CACHE = {}
        app_mod._CMI_NATIONAL_SORTED_CACHE = {}
        app_mod._collect_cmi_series_from_provider_csv.cache_clear()

    def _write_synthetic_snapshot(self, tmp_path, *, quarter: str, n: int = 40) -> str:
        rows = [
            {
                'ccn': str(100000 + i).zfill(6),
                'quarter': quarter,
                'nursing_case_mix_index': 1.0 + (i % 5) * 0.05,
                'nursing_case_mix_index_ratio': 0.9 + (i % 5) * 0.02,
            }
            for i in range(n)
        ]
        path = str(tmp_path / 'synthetic_provider_info.csv')
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def test_derived_cmi_reference_stats_carry_full_lineage(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_synthetic_snapshot(Path(tmp), quarter='Q3 2023')
            app_mod._cmi_reference_source_paths = lambda: [path]
            stats = app_mod.get_provider_info_cmi_reference_stats('2023Q3')
            self.assertIsNotNone(stats)
            lineage = stats.get('lineage')
            self.assertIsNotNone(lineage)
            self.assertEqual(lineage['calculation_origin'], 'pbj320_derived')
            self.assertEqual(lineage['input_quarter_requested'], '2023Q3')
            self.assertEqual(lineage['input_quarter_matched'], '2023Q3')
            self.assertEqual(lineage['case_mix_methodology'], 'RUG-IV')
            self.assertTrue(lineage['input_source_filename'])

    def test_derived_cmi_reference_stats_pdpm_era(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_synthetic_snapshot(Path(tmp), quarter='Q1 2024')
            app_mod._cmi_reference_source_paths = lambda: [path]
            stats = app_mod.get_provider_info_cmi_reference_stats('2024Q1')
            self.assertIsNotNone(stats)
            self.assertEqual(stats['lineage']['case_mix_methodology'], 'PDPM')


if __name__ == '__main__':
    unittest.main()
