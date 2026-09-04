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

    def test_ordinary_exact_rug_iv_quarter_gets_no_note(self) -> None:
        # 2023Q3 is an exact match -- merely being an old/RUG-IV quarter is not itself
        # exceptional. The ordinary case-mix caveat carries the RUG-IV/PDPM wording
        # instead (see CaveatMethodologyAwareTests below); this note stays reserved for
        # a genuine prior-quarter substitution, so it does not double up with the caveat.
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q3')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNone(note)

    def test_modern_pdpm_exact_quarter_has_no_note(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2026Q1')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNone(note)

    def test_methodology_source_cited_when_rug_iv_involved(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        note = app_mod.case_mix_lineage_note(res)
        self.assertEqual(note['source_url'], app_mod.CMS_QSO_24_14_NH_URL)

    def test_data_source_and_methodology_source_evidence_kept_separate(self) -> None:
        # Part 4: the fallback (data-source) claim and the RUG-IV (methodology) claim
        # must not share one piece of "evidence" -- QSO-24-14-NH proves the methodology,
        # not that CMS skipped Q4 2023 (that is proven by pbj-root's own resolver/archive).
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIn('resolver', note['data_source']['label'].lower())
        self.assertNotIn('QSO', note['data_source']['label'])
        self.assertNotIn('qso', note['data_source'].get('basis', '').lower())
        self.assertEqual(note['methodology_source']['label'], 'CMS QSO-24-14-NH')
        self.assertEqual(note['methodology_source']['url'], app_mod.CMS_QSO_24_14_NH_URL)

    def test_data_source_present_even_without_methodology_relevance(self) -> None:
        # A prior-fallback in the PDPM era (hypothetical: e.g. a future gap quarter)
        # still needs data_source evidence even when methodology_source is irrelevant.
        # Simulate via a synthetic resolution object rather than requiring a real future
        # PDPM-era gap to exist in the archive.
        res = app_mod.ProviderInfoResolution(
            semantic='period_matched', ccn='000000', requested_quarter='2025Q4',
            matched_quarter='2025Q3', value={'certified_beds': 100}, source_kind='live_snapshot',
        )
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNotNone(note)
        self.assertIsNotNone(note['data_source'])
        self.assertIsNone(note['methodology_source'])
        self.assertIsNone(note['source_url'])

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


class CaveatMethodologyAwareTests(unittest.TestCase):
    """Part 3: the ordinary case-mix caveat/modal copy names the methodology that
    actually applies to the displayed quarter, instead of hardcoding PDPM and instead
    of a second corrective paragraph underneath a wrong sentence."""

    def _rendered(self, methodology) -> str:
        return app_mod._provider_charts_html(
            {'reportedCaseMix': {'labels': [], 'reported': [], 'caseMix': None,
                                  'caseMixIndex': None, 'caseMixIndexRatio': None}},
            facility_name='Test Facility',
            casemix_title='CMS Case-Mix',
            case_mix_methodology=methodology,
        )

    def test_rug_iv_quarter_caveat_says_rug_iv_not_pdpm(self) -> None:
        html = self._rendered('RUG-IV')
        self.assertIn('based on RUG-IV', html)
        self.assertNotIn('based on PDPM', html)

    def test_pdpm_quarter_caveat_says_pdpm(self) -> None:
        html = self._rendered('PDPM')
        self.assertIn('based on PDPM', html)
        self.assertNotIn('based on RUG-IV', html)

    def test_missing_methodology_defaults_to_pdpm_current_behavior(self) -> None:
        # Callers that don't pass case_mix_methodology (or resolve nothing, e.g. no
        # raw_quarter) keep today's default -- no regression for existing call sites.
        html = self._rendered(None)
        self.assertIn('based on PDPM', html)

    def test_rug_iv_quarter_has_no_redundant_second_paragraph(self) -> None:
        # Part 3: no separate corrective "this value uses RUG-IV" paragraph stacked
        # underneath the (now already-correct) caveat -- the retired legacy_methodology
        # note kind must not appear anywhere in the rendered markup.
        html = self._rendered('RUG-IV')
        self.assertNotIn('This case-mix value uses', html)


class RealPathTransitionWiringTests(unittest.TestCase):
    """Part 6 minimum contract: the transition-range helper is exercised through the
    actual production functions it is wired to (_public_case_mix_quarters_for_facility,
    the same eligibility rule the CSV/trend exports use), not only unit-tested in
    isolation. Confirms both silence under today's real single-quarter export policy
    and correct firing the moment a caller passes include_previous=True."""

    def _facility_df(self, quarters):
        return pd.DataFrame({'CY_Qtr': quarters})

    def test_default_export_eligibility_never_spans_the_boundary(self) -> None:
        # Real call, default args (include_previous=False, what every current
        # production caller uses) -- always exactly one quarter, so the transition
        # helper it feeds correctly stays silent today.
        fac = self._facility_df(['2023Q1', '2023Q2', '2023Q3', '2024Q1', '2024Q2'])
        quarters = app_mod._public_case_mix_quarters_for_facility(fac)
        self.assertEqual(len(quarters), 1)
        note = app_mod.case_mix_methodology_transition_note_for_quarters(quarters)
        self.assertIsNone(note)

    def test_include_previous_eligibility_fires_when_it_spans_the_boundary(self) -> None:
        # Same real eligibility function, include_previous=True (what a future/expanded
        # export caller would pass) -- the latest two quarters straddle 2024Q1, so the
        # composition of the two real production functions correctly produces a note.
        fac = self._facility_df(['2022Q1', '2022Q2', '2023Q3', '2024Q1'])
        quarters = app_mod._public_case_mix_quarters_for_facility(fac, include_previous=True)
        self.assertEqual(quarters, {'2023Q3', '2024Q1'})
        note = app_mod.case_mix_methodology_transition_note_for_quarters(quarters)
        self.assertIsNotNone(note)


class AggregateAndStateReferenceAuditTests(unittest.TestCase):
    """Part 2 follow-up audit: state/national case-mix aggregates (median HPRD, rank,
    CMI reference stats) are PBJ320-derived. None of them perform cross-quarter
    fallback -- they either find data for the exact requested quarter or return
    nothing -- so a 2023Q4 request can never silently masquerade as exact CMS data
    for that quarter (unlike the single-CCN resolver, which explicitly labels its
    fallback). This class proves that "no data" behavior rather than assuming it."""

    def setUp(self) -> None:
        _reset_caches()
        app_mod._STATE_CASE_MIX_MEDIANS = None
        app_mod._STATE_CASE_MIX_MEDIANS_KEY = None
        app_mod._CASE_MIX_VALUES_BY_QUARTER = None
        app_mod._CMI_STATE_REF_STATS_CACHE = {}
        app_mod._CMI_STATE_SORTED_CACHE = {}

    tearDown = setUp

    def test_state_median_case_mix_hprd_2023q4_is_none_not_a_silent_fallback(self) -> None:
        # provider_info/ (the only source _ensure_state_case_mix_medians reads) has no
        # 2023Q4 coverage -- must return None, never quietly substitute 2023Q3 or 2024Q1
        # national/state data as if it were an exact 2023Q4 aggregate.
        val = app_mod.get_state_median_case_mix_hprd('CT', '2023Q4')
        self.assertIsNone(val)

    def test_state_cmi_reference_stats_lineage_present_when_available(self) -> None:
        # get_provider_info_cmi_state_reference_stats is the state-scoped sibling of
        # get_provider_info_cmi_reference_stats -- confirms it independently carries the
        # same lineage block (it is a separate implementation, not a shared code path).
        import tempfile
        from pathlib import Path

        n = 20
        rows = [
            {
                'ccn': str(200000 + i).zfill(6), 'quarter': 'Q3 2023', 'state': 'CT',
                'nursing_case_mix_index': 1.0 + (i % 5) * 0.05,
                'nursing_case_mix_index_ratio': 0.9 + (i % 5) * 0.02,
            }
            for i in range(n)
        ]
        orig = app_mod._cmi_reference_source_paths
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = str(Path(tmp) / 'synthetic_state.csv')
                pd.DataFrame(rows).to_csv(path, index=False)
                app_mod._cmi_reference_source_paths = lambda: [path]
                stats = app_mod.get_provider_info_cmi_state_reference_stats('CT', '2023Q3')
                self.assertIsNotNone(stats)
                lineage = stats.get('lineage')
                self.assertIsNotNone(lineage)
                self.assertEqual(lineage['calculation_origin'], 'pbj320_derived')
                self.assertEqual(lineage['input_quarter_requested'], '2023Q3')
                self.assertEqual(lineage['input_quarter_matched'], '2023Q3')
                self.assertEqual(lineage['case_mix_methodology'], 'RUG-IV')
        finally:
            app_mod._cmi_reference_source_paths = orig


class CaseMixRatioPropagationTests(unittest.TestCase):
    """Part 5 / "ONE MORE THING" #2: the provider page's reported-vs-case-mix ratio bars
    (percent of CMS case-mix HPRD) combine a PBJ-sourced reported value and a Provider-
    Info-sourced case-mix value for the SAME requested quarter -- proves the case-mix
    side's lineage (matched quarter / resolution status / methodology / calculation
    origin) is resolvable from the exact same (ccn, raw_quarter) the ratio bars use, so
    a 2023Q4 ratio can be labeled truthfully rather than silently presented as exact."""

    def setUp(self) -> None:
        _reset_caches()

    tearDown = setUp

    def test_case_mix_side_of_the_ratio_retains_full_lineage_on_a_fallback_quarter(self) -> None:
        ccn, raw_quarter = '075325', '2023Q4'
        # This mirrors the real provider-page call: case-mix HPRD inputs to the ratio
        # bars come from get_provider_info_for_quarter(ccn, raw_quarter) (pi_case_mix).
        pi_case_mix = app_mod.get_provider_info_for_quarter(ccn, raw_quarter)
        case_mix_total = pi_case_mix.get('case_mix_total_nurse_hrs_per_resident_per_day')
        self.assertIsNotNone(case_mix_total, 'fixture must actually exercise a populated case-mix value')
        # The lineage contract is resolvable from the identical (ccn, raw_quarter) pair --
        # nothing about computing the ratio discards the ability to label it.
        res = app_mod.resolve_provider_info_for_period(ccn, raw_quarter)
        self.assertEqual(res.requested_quarter, '2023Q4')
        self.assertEqual(res.matched_quarter, '2023Q3')
        self.assertEqual(res.resolution_status, 'prior_fallback')
        self.assertEqual(res.case_mix_methodology, 'RUG-IV')
        note = app_mod.case_mix_lineage_note(res)
        self.assertIsNotNone(note)

    def test_case_mix_side_of_the_ratio_is_exact_on_an_ordinary_quarter(self) -> None:
        ccn, raw_quarter = '075325', '2026Q1'
        res = app_mod.resolve_provider_info_for_period(ccn, raw_quarter)
        self.assertEqual(res.resolution_status, 'exact')
        self.assertIsNone(app_mod.case_mix_lineage_note(res))


if __name__ == '__main__':
    unittest.main()
