"""Regression tests for Provider Info <-> PBJ quarter vintage resolution.

Background: CCN 075325 (Mary Wade Home) showed 45 certified beds against a Q1
2026 average daily census of ~84 on the public provider page. Root cause:
Provider Info snapshot selection for a PBJ quarter picked whichever snapshot
file happened to be scanned first (directory/newest-first order) among
multiple files self-tagged with the same PBJ quarter, instead of a
deterministic rule. A second, independent bug let a header/export code path
read the static "current" Provider Info snapshot before the quarter-matched
one.

Tie-break methodology: when more than one snapshot self-tags the same PBJ
quarter, the one with the LATEST processing_date is canonical. This was
verified against PBJapp (the sibling per-facility dashboard codebase, the
more complete implementation of this exact problem) --
``pbj_case_mix_cmi.coalesce_provider_quarter_snapshots``: "CMS republishes
the same quarter label across processing_date values ... For each column
this returns the newest non-null, non-sentinel value." An earlier draft of
this resolver picked the EARLIEST same-tagged snapshot (inferred from
release-manifest/ownership-policy pins recorded before the August 2026
snapshot existed); that was superseded once PBJapp's actual running
mechanism was checked directly. Neither repo gives ``certified_beds`` any
sentinel/sanity protection the way PBJapp protects ``nursing_case_mix_index``
-- that remains an open product-policy question, not something encoded here.

These tests cover the deterministic resolver: ``_provider_snapshot_quarter_registry``
/ ``resolve_provider_info_snapshot_path_for_quarter`` / ``get_provider_info_for_quarter``
in app.py.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import app as app_mod


def _write_snapshot(provider_dir: Path, filename: str, *, quarter: str, processing_date: str, rows: list[dict]) -> None:
    cols = ['ccn', 'quarter', 'processing_date', 'certified_beds', 'avg_residents_per_day', 'state']
    out_rows = []
    for r in rows:
        row = {
            'ccn': r['ccn'],
            'quarter': quarter,
            'processing_date': processing_date,
            'certified_beds': r.get('certified_beds'),
            'avg_residents_per_day': r.get('avg_residents_per_day'),
            'state': r.get('state', 'CT'),
        }
        out_rows.append(row)
    pd.DataFrame(out_rows, columns=cols).to_csv(provider_dir / filename, index=False)


class _SyntheticProviderInfoTestCase(unittest.TestCase):
    """Base class: builds an isolated provider_info/ directory and resets all module caches."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix='pbj_provider_info_test_')
        self._provider_dir = Path(self._tmp) / 'provider_info'
        self._provider_dir.mkdir(parents=True, exist_ok=True)
        self._orig_app_root = app_mod.APP_ROOT
        app_mod.APP_ROOT = self._tmp
        self._reset_caches()

    def tearDown(self) -> None:
        app_mod.APP_ROOT = self._orig_app_root
        self._reset_caches()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _reset_caches(self) -> None:
        app_mod._LOAD_PROVIDER_INFO_CACHE = None
        app_mod._LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
        app_mod._LOAD_PROVIDER_INFO_AT = 0
        app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_CACHE = None
        app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_AT = 0.0
        app_mod._clear_provider_info_history_cache()

    def _snapshot(self, filename, *, quarter, processing_date, rows):
        _write_snapshot(self._provider_dir, filename, quarter=quarter, processing_date=processing_date, rows=rows)


class RegistryCanonicalSnapshotTests(_SyntheticProviderInfoTestCase):
    """1 & 2: multiple snapshots share a quarter tag; the collection/processing-date
    interval decides which one is canonical -- the LATEST processing_date among
    same-tagged snapshots (matches PBJapp's coalesce_provider_quarter_snapshots)."""

    def test_latest_processing_date_wins_for_shared_quarter_tag(self) -> None:
        self._snapshot(
            'ProviderInfoNorm_2026_06.csv', quarter='Q4 2025', processing_date='2026-06-01',
            rows=[{'ccn': '000001', 'certified_beds': 100}],
        )
        # Two snapshots both self-tag Q1 2026 -- July (first) and August (later republish).
        self._snapshot(
            'ProviderInfoNorm_2026_07.csv', quarter='Q1 2026', processing_date='2026-07-01',
            rows=[{'ccn': '000001', 'certified_beds': 94, 'avg_residents_per_day': 84}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_08.csv', quarter='Q1 2026', processing_date='2026-08-01',
            rows=[{'ccn': '000001', 'certified_beds': 45, 'avg_residents_per_day': 84}],
        )
        registry = app_mod._provider_snapshot_quarter_registry()
        self.assertIn('2026Q1', registry)
        self.assertTrue(registry['2026Q1']['path'].endswith('ProviderInfoNorm_2026_08.csv'))
        path, matched = app_mod.resolve_provider_info_snapshot_path_for_quarter('2026Q1')
        self.assertEqual(matched, '2026Q1')
        self.assertTrue(path.endswith('ProviderInfoNorm_2026_08.csv'))

    def test_exact_match_resolves_certified_beds_from_canonical_snapshot(self) -> None:
        self._snapshot(
            'ProviderInfoNorm_2026_07.csv', quarter='Q1 2026', processing_date='2026-07-01',
            rows=[{'ccn': '000001', 'certified_beds': 94, 'avg_residents_per_day': 84}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_08.csv', quarter='Q1 2026', processing_date='2026-08-01',
            rows=[{'ccn': '000001', 'certified_beds': 45, 'avg_residents_per_day': 84}],
        )
        row = app_mod.get_provider_info_for_quarter('000001', '2026Q1')
        self.assertIsNotNone(row)
        self.assertEqual(float(row['certified_beds']), 45.0)


class PriorValueFallbackTests(_SyntheticProviderInfoTestCase):
    """4 & 5: missing exact vintage falls back to the most recent PRIOR eligible
    value; a future vintage is never used to describe an earlier quarter --
    including when that future quarter itself has multiple same-tagged
    snapshots (the "latest wins" tie-break must stay scoped to its own quarter
    and never leak into an earlier quarter's resolution)."""

    def setUp(self) -> None:
        super().setUp()
        self._snapshot(
            'ProviderInfoNorm_2026_03.csv', quarter='Q3 2025', processing_date='2026-03-01',
            rows=[{'ccn': '000002', 'certified_beds': 80}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_07.csv', quarter='Q1 2026', processing_date='2026-07-01',
            rows=[{'ccn': '000002', 'certified_beds': 94}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_08.csv', quarter='Q1 2026', processing_date='2026-08-01',
            rows=[{'ccn': '000002', 'certified_beds': 45}],
        )

    def test_missing_exact_quarter_uses_most_recent_prior(self) -> None:
        # No snapshot tags Q4 2025 at all; nearest PRIOR quarter present is Q3 2025.
        path, matched = app_mod.resolve_provider_info_snapshot_path_for_quarter('2025Q4')
        self.assertEqual(matched, '2025Q3')
        self.assertTrue(path.endswith('ProviderInfoNorm_2026_03.csv'))

    def test_never_selects_a_future_quarter_snapshot(self) -> None:
        # Only Q3 2025 is available as a prior candidate for a Q4 2025 request even
        # though later (Q1 2026) snapshots exist -- they must never be selected for
        # an earlier PBJ quarter, regardless of which one wins the Q1 2026 tie-break.
        path, matched = app_mod.resolve_provider_info_snapshot_path_for_quarter('2025Q4')
        self.assertNotEqual(matched, '2026Q1')
        self.assertNotIn('ProviderInfoNorm_2026_07.csv', path)
        self.assertNotIn('ProviderInfoNorm_2026_08.csv', path)

    def test_quarter_before_any_known_snapshot_returns_none(self) -> None:
        path, matched = app_mod.resolve_provider_info_snapshot_path_for_quarter('2020Q1')
        self.assertIsNone(path)
        self.assertIsNone(matched)


class ColdWarmConsistencyTests(_SyntheticProviderInfoTestCase):
    """6: a cold single-CCN lookup and a warmed national scan must agree."""

    def setUp(self) -> None:
        super().setUp()
        self._snapshot(
            'ProviderInfoNorm_2026_07.csv', quarter='Q1 2026', processing_date='2026-07-01',
            rows=[{'ccn': '000003', 'certified_beds': 94}, {'ccn': '000004', 'certified_beds': 360}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_08.csv', quarter='Q1 2026', processing_date='2026-08-01',
            rows=[{'ccn': '000003', 'certified_beds': 45}, {'ccn': '000004', 'certified_beds': 360}],
        )

    def test_cold_and_warm_scans_agree(self) -> None:
        # Cold: single-CCN lookup, nothing cached yet.
        self._reset_caches()
        cold = app_mod.get_provider_info_for_quarter('000003', '2026Q1')

        # Warm: full national scan populates the by-quarter cache first.
        self._reset_caches()
        app_mod.load_provider_info()
        warm = app_mod.get_provider_info_for_quarter('000003', '2026Q1')

        self.assertEqual(float(cold['certified_beds']), 45.0)
        self.assertEqual(float(warm['certified_beds']), 45.0)


class NeverFutureAcrossQuartersTests(_SyntheticProviderInfoTestCase):
    """5 (extended): the "latest wins" tie-break resolves WITHIN a quarter tag
    only. A facility whose displayed PBJ quarter lags the site's current
    quarter must still get that earlier quarter's own snapshot, never a later
    quarter's -- i.e. this is not equivalent to "always use whatever is
    globally newest"."""

    def setUp(self) -> None:
        super().setUp()
        # Q4 2025 has one snapshot (June). Q1 2026 has two (July, August) -- August
        # is both the globally-newest file AND tagged with a LATER PBJ quarter than
        # Q4 2025.
        self._snapshot(
            'ProviderInfoNorm_2026_06.csv', quarter='Q4 2025', processing_date='2026-06-01',
            rows=[{'ccn': '000005', 'certified_beds': 200}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_07.csv', quarter='Q1 2026', processing_date='2026-07-01',
            rows=[{'ccn': '000005', 'certified_beds': 94}],
        )
        self._snapshot(
            'ProviderInfoNorm_2026_08.csv', quarter='Q1 2026', processing_date='2026-08-01',
            rows=[{'ccn': '000005', 'certified_beds': 45}],
        )

    def test_lagging_quarter_page_never_shows_a_later_quarters_vintage(self) -> None:
        row = app_mod.get_provider_info_for_quarter('000005', '2025Q4')
        self.assertIsNotNone(row)
        self.assertEqual(float(row['certified_beds']), 200.0)


class RealRepoDataTests(unittest.TestCase):
    """7, 8, 9: exercise the real, committed provider_info/ snapshots (no synthetic
    fixtures) for the Mary Wade Home case and its control."""

    def setUp(self) -> None:
        app_mod._LOAD_PROVIDER_INFO_CACHE = None
        app_mod._LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
        app_mod._LOAD_PROVIDER_INFO_AT = 0
        app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_CACHE = None
        app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_AT = 0.0

    tearDown = setUp

    def test_mary_wade_q1_2026_resolves_to_canonical_august_vintage(self) -> None:
        # July and August 2026 both self-tag Q1 2026; August has the later
        # processing_date, so it is canonical (see module docstring for the
        # PBJapp cross-check). This intentionally now equals the "current"
        # value for this CCN today -- that is a fact about this specific
        # facility this month, not a merged code path (see the next test).
        row = app_mod.get_provider_info_for_quarter('075325', '2026Q1')
        self.assertIsNotNone(row)
        self.assertEqual(float(row['certified_beds']), 45.0)

    def test_control_ccn_335513_unchanged(self) -> None:
        row = app_mod.get_provider_info_for_quarter('335513', '2026Q1')
        self.assertIsNotNone(row)
        self.assertEqual(float(row['certified_beds']), 360.0)

    def test_current_latest_provider_info_still_reflects_cms_current_value(self) -> None:
        # The static "current" snapshot path is intentionally independent of PBJ-quarter
        # matching (facility identity/current-attribute semantics) and must keep returning
        # whatever CMS's newest Provider Info release reports. For Mary Wade this happens
        # to numerically match the quarter-matched result above today, but the two are
        # still architecturally independent code paths -- see the lagging-quarter test in
        # NeverFutureAcrossQuartersTests, which proves they diverge correctly when a page's
        # displayed PBJ quarter is not the newest available one.
        current_row = app_mod._provider_info_row_for_ccn('075325')
        self.assertEqual(float(current_row['certified_beds']), 45.0)


class OwnershipPortfolioCurrentSnapshotUnaffectedTests(unittest.TestCase):
    """10: the ownership/Premium-shared "current" provider-info resolver
    (owner_portfolio_metrics.entity_facility_for_portfolio) is a separate,
    module-local hot path and must not regress -- it intentionally shows the
    facility's current roster attributes, not a PBJ-quarter-matched value."""

    def test_entity_portfolio_row_uses_current_snapshot(self) -> None:
        from ownership.owner_portfolio_metrics import _ccn_provider_lookup

        lookup = _ccn_provider_lookup()
        row = lookup.get('075325')
        self.assertIsNotNone(row)
        self.assertEqual(str(row.get('beds')), '45')


def _facility_df(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """facility_quarterly-shaped DataFrame with every column
    _provider_charts_chartjs_data touches, so a missing optional column doesn't
    silently truncate a series to length 0 (real facility_quarterly_metrics rows
    always carry these columns; only this synthetic fixture needs them spelled out)."""
    return pd.DataFrame(
        [
            {
                'CY_Qtr': q,
                'Total_Nurse_HPRD': 4.0,
                'Nurse_Care_HPRD': 3.5,
                'RN_HPRD': 0.6,
                'RN_Care_HPRD': 0.5,
                'LPN_HPRD': 1.0,
                'LPN_Care_HPRD': 0.9,
                'Nurse_Assistant_HPRD': 2.4,
                'Contract_Percentage': 0.0,
                'avg_daily_census': census,
            }
            for q, census in rows
        ]
    )


class HistoricalCertifiedBedsChartSeriesTests(unittest.TestCase):
    """Live-site follow-up: the census chart's "Certified beds" line was broadcasting one
    scalar (the current-quarter value) across every historical quarter instead of resolving
    each quarter independently. _provider_charts_chartjs_data must build that series by
    calling get_provider_info_for_quarter() once per quarter -- the same deterministic,
    prior-only/never-future resolver used for the current-quarter display -- not repeat a
    single value backward across history."""

    def setUp(self) -> None:
        app_mod._LOAD_PROVIDER_INFO_CACHE = None
        app_mod._LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
        app_mod._LOAD_PROVIDER_INFO_AT = 0
        app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_CACHE = None
        app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_AT = 0.0
        app_mod._clear_provider_info_history_cache()
        app_mod.get_pd()

    tearDown = setUp

    def test_mary_wade_historical_beds_series_is_not_flat_45(self) -> None:
        # Real repo data: 075325 across every available PBJ quarter.
        fac = _facility_df(
            [
                ('2025Q3', 89.2),
                ('2025Q4', 86.1),
                ('2026Q1', 84.0),
            ]
        )
        out = app_mod._provider_charts_chartjs_data(
            fac, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='075325',
        )
        beds = out['census']['beds']
        self.assertIsNotNone(beds)
        # Each quarter resolves through its own vintage -- not a single repeated scalar.
        self.assertEqual(beds, [94, 94, 45])
        self.assertFalse(all(b == beds[0] for b in beds), 'beds series must not be flat')

    def test_bed_count_change_does_not_broadcast_backward(self) -> None:
        # A facility whose bed count changes in the newest quarter must not have that
        # newest value silently applied to older quarters that had a different value.
        fac = _facility_df([('2025Q3', 89.2), ('2025Q4', 86.1), ('2026Q1', 84.0)])
        out = app_mod._provider_charts_chartjs_data(
            fac, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='075325',
        )
        beds = out['census']['beds']
        self.assertEqual(beds[0], 94)   # 2025Q3: pre-change value preserved
        self.assertEqual(beds[1], 94)   # 2025Q4: pre-change value preserved
        self.assertEqual(beds[2], 45)   # 2026Q1: new value only on its own quarter
        self.assertNotEqual(beds[0], beds[2])

    def test_control_ccn_335513_historical_series_constant_where_source_is_constant(self) -> None:
        fac = _facility_df([('2025Q3', 350.7), ('2025Q4', 347.4), ('2026Q1', 350.2)])
        out = app_mod._provider_charts_chartjs_data(
            fac, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='335513',
        )
        beds = out['census']['beds']
        self.assertEqual(beds, [360, 360, 360])

    def test_quarter_with_no_eligible_vintage_is_a_null_gap_not_a_guess(self) -> None:
        # 2017Q1 predates every available Provider Info snapshot in this worktree (no
        # provider_info_combined.csv deep archive present locally) -- must be null, never
        # backfilled from a later quarter's value.
        fac = _facility_df([('2017Q1', 92.7), ('2026Q1', 84.0)])
        out = app_mod._provider_charts_chartjs_data(
            fac, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='075325',
        )
        beds = out['census']['beds']
        self.assertIsNone(beds[0])
        self.assertEqual(beds[1], 45)


if __name__ == '__main__':
    unittest.main()
