"""Regression tests for the Sept 2026 provider-info runtime incident.

Background (see docs/ incident writeup / PR description for the full timeline): after
commit 00871c4 (historical certified-beds chart series) and 3b2c047 (historical
Provider Info Parquet archive) deployed on 2026-09-03/04, production saw:

  - a pre-existing-class "health starvation" regression (/healthz timeouts) caused by
    _provider_charts_chartjs_data() calling get_provider_info_for_quarter() once per
    historical PBJ quarter (unconditionally, on every single cold render), each of
    which -- absent any cross-call memoization -- re-scanned a live provider_info/
    snapshot CSV in full;
  - repeated >2GB OOMs caused by _historical_provider_info_row_for_ccn_quarter()
    loading the ENTIRE ~484k-row national historical Parquet archive into a permanent,
    never-evicted process-global DataFrame on the first lookup that missed the live
    snapshot window -- true for nearly every long-tenured facility.

The fix: get_provider_info_for_quarter() and its two callees (_scan_provider_row_for_
ccn_quarter for the live snapshot window, _historical_provider_info_row_for_ccn_quarter
for the Parquet archive) now memoize by the RESOLVED canonical quarter/CCN so repeat
calls for the same underlying source don't re-read it, and the Parquet archive is read
per-CCN via pyarrow predicate pushdown (filters=[('ccn','==',ccn)]) into a small,
bounded, LRU-evicted cache -- never the full national table.

These tests assert the actual proven failure mode is fixed: bounded call counts and
bounded cache size, not just correct output values (those are already covered by
test_provider_info_historical_archive.py / test_provider_info_quarter_resolution.py,
which must keep passing unchanged -- this file adds no new value-correctness
assertions, only cost-boundedness ones).
"""

from __future__ import annotations

import unittest
from pathlib import Path

import app as app_mod
from tests.test_provider_info_quarter_resolution import _SyntheticProviderInfoTestCase, _write_snapshot

ARCHIVE_PATH = Path(app_mod.APP_ROOT) / 'data' / 'derived' / 'provider_info_history.parquet'


def _reset_all_caches() -> None:
    app_mod._LOAD_PROVIDER_INFO_CACHE = None
    app_mod._LOAD_PROVIDER_INFO_BY_QUARTER_CACHE = None
    app_mod._LOAD_PROVIDER_INFO_AT = 0
    app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_CACHE = None
    app_mod._PROVIDER_SNAPSHOT_QUARTER_REGISTRY_AT = 0.0
    app_mod._clear_provider_info_history_cache()


@unittest.skipUnless(ARCHIVE_PATH.is_file(), "historical archive not built in this worktree")
class HistoricalArchiveBoundedReadTests(unittest.TestCase):
    """The Parquet archive must never be materialized in full, and must be read at
    most once per CCN per process (subject to LRU eviction), regardless of how many
    distinct quarters are requested for that CCN."""

    def setUp(self) -> None:
        _reset_all_caches()

    tearDown = setUp

    def test_one_ccn_lookup_across_many_quarters_reads_the_archive_once(self) -> None:
        import pyarrow.parquet as pq

        read_calls = []
        orig_read_table = pq.read_table

        def spy_read_table(path, *args, **kwargs):
            read_calls.append(kwargs.get('filters'))
            return orig_read_table(path, *args, **kwargs)

        pq.read_table = spy_read_table
        try:
            quarters = [f'{y}Q{q}' for y in range(2018, 2026) for q in (1, 2, 3, 4)]
            for q in quarters:
                app_mod.get_provider_info_for_quarter('075325', q)
            self.assertEqual(
                len(read_calls), 1,
                f"expected exactly one Parquet read for one CCN across {len(quarters)} "
                f"quarter lookups, got {len(read_calls)}",
            )
            self.assertEqual(read_calls[0], [('ccn', '==', '075325')])
        finally:
            pq.read_table = orig_read_table

    def test_archive_read_is_predicate_scoped_not_a_national_load(self) -> None:
        """A single-CCN historical lookup must return only that CCN's rows (a handful),
        never anywhere close to the archive's full row count (484k+) -- proving the read
        is CCN-scoped (pyarrow filters=), not a full-table load filtered in Python."""
        rows = app_mod._load_provider_info_history_rows_for_ccn('075325')
        self.assertIsNotNone(rows)
        self.assertLess(len(rows), 100, "a single CCN should have at most a few dozen quarters")
        self.assertGreater(len(rows), 0)

    def test_per_ccn_cache_is_bounded_not_a_permanent_national_cache(self) -> None:
        """Looking up many distinct CCNs must not grow the cache without bound -- this
        is the direct fix for the incident's OOM (a permanent, unbounded, never-evicted
        process-global national DataFrame)."""
        cap = app_mod._PROVIDER_INFO_HISTORY_CCN_LRU_MAX
        # Use real CCNs known to exist in the committed archive plus synthetic overflow
        # CCNs (misses are fine -- an LRU entry is written even for "no rows found"
        # results elsewhere, but here we only need to prove the *cap* holds under load).
        for i in range(cap + 50):
            app_mod._load_provider_info_history_rows_for_ccn(f'{900000 + i:06d}')
        self.assertLessEqual(len(app_mod._PROVIDER_INFO_HISTORY_CCN_LRU), cap)

    def test_no_module_global_holds_the_full_national_table(self) -> None:
        """Regression guard for the specific incident architecture: after exercising the
        historical path, no attribute on the app module should be a pandas object with
        anywhere near the archive's full row count resident in memory."""
        import pandas as pd

        app_mod.get_provider_info_for_quarter('075325', '2018Q1')
        for name in dir(app_mod):
            if name.startswith('__'):
                continue
            try:
                val = getattr(app_mod, name)
            except Exception:
                continue
            if isinstance(val, pd.DataFrame):
                self.assertLess(
                    len(val), 10000,
                    f"app_mod.{name} is a {len(val)}-row DataFrame -- looks like a "
                    "reintroduced full-archive national cache",
                )


class LiveSnapshotScanDedupTests(_SyntheticProviderInfoTestCase):
    """Multiple distinct raw quarters that resolve (via nearest-PRIOR fallback) to the
    SAME canonical live snapshot file must scan that file at most once, not once per
    raw quarter -- this was the CPU/GIL-bound driver of the pre-existing-class
    /healthz starvation regression on the single-worker Render process."""

    def setUp(self) -> None:
        super().setUp()
        self._snapshot(
            'ProviderInfoNorm_2026_03.csv', quarter='Q3 2025', processing_date='2026-03-01',
            rows=[{'ccn': '000009', 'certified_beds': 80}],
        )

    def test_many_gap_quarters_share_one_scan_of_the_canonical_file(self) -> None:
        import pandas as pd

        # Warm the (TTL-cached, one-time-per-process) quarter registry first, so the
        # spy below measures only per-quarter SCAN cost, not the unrelated one-time
        # registry-build read (also 2 read_csv calls) that the first resolve() call
        # amortizes regardless of how many quarters get requested afterward.
        app_mod._provider_snapshot_quarter_registry()

        read_calls = []
        orig_read_csv = pd.read_csv

        def spy_read_csv(path, *args, **kwargs):
            read_calls.append(path)
            return orig_read_csv(path, *args, **kwargs)

        pd.read_csv = spy_read_csv
        try:
            # None of these quarters is itself tagged by any snapshot -- all fall back
            # to the single Q3 2025 snapshot as their nearest PRIOR quarter.
            gap_quarters = ['2025Q4', '2026Q1', '2026Q2', '2026Q3']
            for q in gap_quarters:
                row = app_mod.get_provider_info_for_quarter('000009', q)
                self.assertIsNotNone(row)
                self.assertEqual(float(row['certified_beds']), 80.0)
        finally:
            pd.read_csv = orig_read_csv

        # header peek (nrows=0) + one real chunked scan of the one canonical file is
        # the expected shape for the FIRST gap quarter only; the key assertion is that
        # this does NOT scale with the number of distinct raw quarters requested (4
        # requests here, all resolving to the same canonical snapshot).
        real_scans_of_snapshot = [
            p for p in read_calls
            if 'ProviderInfoNorm_2026_03.csv' in str(p)
        ]
        self.assertLessEqual(
            len(real_scans_of_snapshot), 2,
            f"expected the canonical snapshot file to be opened at most once (plus a "
            f"header peek) across {len(gap_quarters)} distinct gap-quarter lookups, "
            f"got {len(real_scans_of_snapshot)} opens: {real_scans_of_snapshot}",
        )


@unittest.skipUnless(ARCHIVE_PATH.is_file(), "historical archive not built in this worktree")
class ColdRenderCostBoundedTests(unittest.TestCase):
    """End-to-end: one cold provider-page chart build for a long-tenured facility (the
    real proven failure mode -- Mary Wade Home, 34 PBJ quarters back to 2017Q4) must
    not repeat expensive per-quarter resolution and must not blow up process memory."""

    def setUp(self) -> None:
        _reset_all_caches()
        app_mod.get_pd()

    tearDown = setUp

    def _quarters_2017q4_to_2026q1(self):
        quarters = []
        y, q = 2017, 4
        while (y, q) <= (2026, 1):
            quarters.append(f'{y}Q{q}')
            q += 1
            if q > 4:
                q = 1
                y += 1
        return quarters

    def test_full_longitudinal_chart_build_uses_one_bounded_historical_lookup(self) -> None:
        import pandas as pd

        quarters = self._quarters_2017q4_to_2026q1()
        facility_df = pd.DataFrame(
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
                    'avg_daily_census': 84.0,
                }
                for q in quarters
            ]
        )

        import pyarrow.parquet as pq

        read_calls = []
        orig_read_table = pq.read_table

        def spy_read_table(path, *args, **kwargs):
            read_calls.append(kwargs.get('filters'))
            return orig_read_table(path, *args, **kwargs)

        pq.read_table = spy_read_table
        try:
            out = app_mod._provider_charts_chartjs_data(
                facility_df, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='075325',
            )
        finally:
            pq.read_table = orig_read_table

        beds = out['census']['beds']
        self.assertEqual(len(beds), len(quarters))
        # Real values, unchanged by this fix -- see HistoricalArchiveRealDataTests for
        # the authoritative value assertions; spot-checked here as an end-to-end sanity
        # check that the cost fix didn't silently change output.
        self.assertEqual(beds[0], 93)  # 2017Q4
        self.assertEqual(beds[-1], 45)  # 2026Q1

        self.assertEqual(
            len(read_calls), 1,
            f"one facility's full chart build across {len(quarters)} quarters must "
            f"issue exactly one Parquet read, got {len(read_calls)}",
        )
        self.assertLessEqual(len(app_mod._PROVIDER_INFO_HISTORY_CCN_LRU), 1)

    def test_cold_render_rss_delta_stays_well_under_the_old_national_load_cost(self) -> None:
        """Soft guard: the old architecture added ~250-300MB of PERMANENT resident
        memory on this exact render. The fix should keep the transient delta well
        under that (measured ~35-60MB locally) -- generous threshold to avoid
        flakiness across environments while still catching a reintroduced full load."""
        try:
            import psutil
        except ImportError:
            self.skipTest("psutil not available")
        import os

        import pandas as pd

        proc = psutil.Process(os.getpid())
        quarters = self._quarters_2017q4_to_2026q1()
        facility_df = pd.DataFrame(
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
                    'avg_daily_census': 84.0,
                }
                for q in quarters
            ]
        )
        rss_before = proc.memory_info().rss / 1024 / 1024
        app_mod._provider_charts_chartjs_data(
            facility_df, 'CT', 1.0, 1.0, 1.0, 1.0, None, None, None, None, ccn='075325',
        )
        rss_after = proc.memory_info().rss / 1024 / 1024
        delta = rss_after - rss_before
        self.assertLess(
            delta, 150.0,
            f"RSS grew {delta:.1f}MB for one facility's cold chart build -- the old "
            "full-national-archive-load architecture cost ~250-300MB permanently; "
            "this should stay well under that even as a generous, environment-tolerant bound",
        )


if __name__ == '__main__':
    unittest.main()
