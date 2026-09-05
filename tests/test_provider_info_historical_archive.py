"""Regression tests for the historical Provider Info archive
(data/derived/provider_info_history.parquet, built by
scripts/build_provider_info_history.py) and the explicit CURRENT vs
PERIOD_MATCHED resolution contract (resolve_provider_info_current /
resolve_provider_info_for_period, app.py).

Background: the live provider_info/ snapshot folder only carries a rolling
recent window (~9 months in this worktree). Before this pass, any PBJ quarter
older than that window resolved to None -- a defensible gap, but one that made
the census chart's historical "Certified beds" line mostly empty. The archive
extends coverage back to 2017Q4 (32 PBJ quarters) using the exact same
canonical-snapshot-selection rule already established and tested in
test_provider_info_quarter_resolution.py (latest processing_date wins among
same-quarter-tagged monthly releases), applied to a wider set of source months.
It is consulted only as a fallback -- after the live snapshot scan finds
nothing -- so it can never override a quarter the live snapshots already cover.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

import app as app_mod
from scripts.build_provider_info_history import build as build_history_artifact

ARTIFACT_PATH = Path(app_mod.APP_ROOT) / 'data' / 'derived' / 'provider_info_history.parquet'
MANIFEST_PATH = Path(app_mod.APP_ROOT) / 'data' / 'derived' / 'provider_info_history_manifest.json'


def _reset_caches() -> None:
    app_mod._LOAD_PROVIDER_INFO_CACHE = None
    app_mod._LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
    app_mod._LOAD_PROVIDER_INFO_AT = 0
    app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_CACHE = None
    app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_AT = 0.0
    app_mod._clear_provider_info_history_cache()


@unittest.skipUnless(ARTIFACT_PATH.is_file(), "historical artifact not built in this worktree")
class HistoricalArchiveRealDataTests(unittest.TestCase):
    """Exercises the real, committed provider_info_history.parquet artifact."""

    def setUp(self) -> None:
        _reset_caches()

    tearDown = setUp

    def test_mary_wade_full_longitudinal_series_no_broadcast(self) -> None:
        # Three genuinely distinct eras for CCN 075325, none of them guessed or
        # broadcast from a neighboring quarter: 93 beds (pre-2022Q3), 94 beds
        # (2022Q3 through 2025Q4), 45 beds (2026Q1, the live-snapshot value).
        beds_2018 = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('075325', '2018Q1')
        )
        beds_2022q2 = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('075325', '2022Q2')
        )
        beds_2022q3 = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('075325', '2022Q3')
        )
        beds_2025q4 = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('075325', '2025Q4')
        )
        beds_2026q1 = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('075325', '2026Q1')
        )
        self.assertEqual(beds_2018, 93)
        self.assertEqual(beds_2022q2, 93)
        self.assertEqual(beds_2022q3, 94)
        self.assertEqual(beds_2025q4, 94)
        self.assertEqual(beds_2026q1, 45)
        self.assertNotEqual(beds_2018, beds_2026q1)

    def test_control_ccn_335513_stable_across_full_archive(self) -> None:
        for q in ('2017Q4', '2019Q4', '2022Q1', '2025Q4', '2026Q1'):
            beds = app_mod._provider_certified_beds(
                app_mod.get_provider_info_for_quarter('335513', q)
            )
            self.assertEqual(beds, 360, f'335513 {q} expected 360, got {beds}')

    def test_additional_real_changing_bed_facility_015100(self) -> None:
        # Real CCN, single clean step-change at 2019Q4 (174 -> 148), stable for
        # years on both sides -- selected from the archive, not fabricated.
        before = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('015100', '2019Q3')
        )
        after = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('015100', '2019Q4')
        )
        later = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('015100', '2025Q4')
        )
        self.assertEqual(before, 174)
        self.assertEqual(after, 148)
        self.assertEqual(later, 148)

    def test_additional_real_changing_bed_facility_015213(self) -> None:
        before = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('015213', '2019Q3')
        )
        after = app_mod._provider_certified_beds(
            app_mod.get_provider_info_for_quarter('015213', '2019Q4')
        )
        self.assertEqual(before, 234)
        self.assertEqual(after, 220)

    def test_pre_archive_period_is_explicit_missing_not_a_guess(self) -> None:
        # 2013Q1 predates the archive's earliest coverage (2017Q4) entirely --
        # must be None, never the archive's oldest available value.
        row = app_mod.get_provider_info_for_quarter('075325', '2013Q1')
        # get_provider_info_for_quarter's established contract on a true miss is an
        # empty dict (falsy), not None -- _enrich_provider_quarter_row_from_combined
        # always returns a dict. What matters is no fields are populated.
        self.assertFalse(row)
        res = app_mod.resolve_provider_info_for_period('075325', '2013Q1')
        self.assertTrue(res.is_gap)
        self.assertIsNone(res.value)
        self.assertIsNone(res.matched_quarter)

    def test_transition_gap_quarter_uses_nearest_prior_not_a_fabricated_value(self) -> None:
        # 2023Q4 does not exist as a distinct tag anywhere in the archive -- CMS's
        # own Provider Info releases jump from "Q3 2023" (processed through June
        # 2024) straight to "Q1 2024" (first PDPM-based case-mix quarter, per the
        # April/July 2024 Five-Star refresh). A request for the PBJ quarter label
        # "2023Q4" must resolve to the nearest PRIOR established quarter (2023Q3),
        # never to 2024Q1 (a later quarter, and a different case-mix methodology).
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        self.assertNotIn('2023Q4', manifest['quarter_coverage']['all'])
        res = app_mod.resolve_provider_info_for_period('075325', '2023Q4')
        self.assertEqual(res.matched_quarter, '2023Q3')
        self.assertNotEqual(res.matched_quarter, '2024Q1')
        self.assertIn('nearest PRIOR', res.selection_reason)

    def test_live_snapshot_window_takes_precedence_over_archive(self) -> None:
        # For a quarter the live provider_info/ snapshots already cover, the
        # historical archive must never be consulted (source_kind stays live,
        # not 'historical_archive') -- it is strictly a coverage-gap fallback.
        res = app_mod.resolve_provider_info_for_period('075325', '2026Q1')
        self.assertNotEqual(res.source_kind, 'historical_archive')

    def test_archive_only_engages_when_live_window_has_no_coverage(self) -> None:
        res = app_mod.resolve_provider_info_for_period('075325', '2018Q1')
        self.assertEqual(res.source_kind, 'historical_archive')


class ExplicitCurrentVsPeriodMatchedContractTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_caches()

    tearDown = setUp

    def test_current_and_period_matched_diverge_on_a_lagging_quarter(self) -> None:
        current = app_mod.resolve_provider_info_current('075325')
        period = app_mod.resolve_provider_info_for_period('075325', '2018Q1')
        self.assertEqual(current.semantic, 'current')
        self.assertEqual(period.semantic, 'period_matched')
        self.assertNotEqual(
            current.value.get('certified_beds'), period.value.get('certified_beds')
        )

    def test_missing_ccn_returns_explicit_gap_not_an_exception(self) -> None:
        res = app_mod.resolve_provider_info_for_period('999999', '2020Q1')
        self.assertTrue(res.is_gap)
        self.assertIsNone(res.value)


@unittest.skipUnless(
    (Path(app_mod.APP_ROOT) / 'provider_info').is_dir(), "no provider_info/ source to build from"
)
class HistoricalArtifactBuildDeterminismTests(unittest.TestCase):
    """Part L: the build is reproducible -- same input, same output, every time."""

    def test_build_is_deterministic_across_two_runs(self) -> None:
        import tempfile

        source_dir = Path(app_mod.APP_ROOT) / 'provider_info'
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            m1 = build_history_artifact(
                source_dir, Path(tmp1) / 'out.parquet', Path(tmp1) / 'out_manifest.json'
            )
            m2 = build_history_artifact(
                source_dir, Path(tmp2) / 'out.parquet', Path(tmp2) / 'out_manifest.json'
            )
            df1 = pd.read_parquet(Path(tmp1) / 'out.parquet')
            df2 = pd.read_parquet(Path(tmp2) / 'out.parquet')
            pd.testing.assert_frame_equal(df1, df2)
            self.assertEqual(m1['row_count'], m2['row_count'])
            self.assertEqual(m1['quarter_coverage'], m2['quarter_coverage'])
            # Source file sha256s are the real reproducibility guarantee -- byte-identical
            # input files (which these are, both runs read the same on-disk source
            # directory) must produce a byte-identical inventory, not just equal counts.
            self.assertEqual(
                [s['sha256'] for s in m1['sources']],
                [s['sha256'] for s in m2['sources']],
            )


if __name__ == '__main__':
    unittest.main()
