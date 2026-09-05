"""Correctness tests for the malloc_trim(0) proof-of-fix hook.

Two layers:
  - MallocTrimUnitTests: utils/malloc_trim.py in isolation -- fail-open paths,
    threshold/cooldown gating, thread-safety, logging shape. No Flask, no app
    caches, no libc actually invoked (libc.malloc_trim is mocked).
  - MallocTrimWiringTests: app.py call sites -- proves the hook fires exactly
    once per successfully admitted cold provider/entity/owner build, and
    never on a cache hit, an admission rejection, or an exception.
"""

from __future__ import annotations

import json
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import utils.malloc_trim as malloc_trim_mod


class MallocTrimUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # Reset module-level cooldown state so tests don't leak into each other.
        malloc_trim_mod._LAST_TRIM_MONOTONIC = 0.0
        self.stack.enter_context(
            patch.dict(
                "os.environ",
                {
                    "PBJ_MALLOC_TRIM_ENABLED": "1",
                    "PBJ_MALLOC_TRIM_RSS_THRESHOLD_MB": "1000",
                    "PBJ_MALLOC_TRIM_MIN_INTERVAL_S": "60",
                },
            )
        )

    def _fake_libc(self):
        libc = MagicMock()
        libc.malloc_trim = MagicMock(return_value=1)
        return libc

    def _last_log(self, mock_write) -> dict:
        line = mock_write.call_args_list[-1].args[0]
        self.assertTrue(line.startswith("[MALLOC_TRIM] "))
        return json.loads(line[len("[MALLOC_TRIM] "):].strip())

    # -- fail-open paths -----------------------------------------------

    def test_disabled_is_noop_and_silent(self) -> None:
        with patch.dict("os.environ", {"PBJ_MALLOC_TRIM_ENABLED": "0"}), \
             patch.object(malloc_trim_mod, "_LIBC", self._fake_libc()) as libc, \
             patch("sys.stderr.write") as write:
            malloc_trim_mod.maybe_trim("provider")
        libc.malloc_trim.assert_not_called()
        # Disabled is the routine outcome while opted out -- must not log.
        write.assert_not_called()

    def test_default_is_disabled_when_env_var_unset(self) -> None:
        """Merging this module must not silently activate trimming: with no
        PBJ_MALLOC_TRIM_ENABLED set at all, the default is off."""
        import os as _os

        with patch.dict(_os.environ, {}, clear=False):
            _os.environ.pop("PBJ_MALLOC_TRIM_ENABLED", None)
            with patch.object(malloc_trim_mod, "_LIBC", self._fake_libc()) as libc, \
                 patch("sys.stderr.write") as write:
                malloc_trim_mod.maybe_trim("provider")
            libc.malloc_trim.assert_not_called()
            write.assert_not_called()

    def test_libc_unavailable_is_noop(self) -> None:
        with patch.object(malloc_trim_mod, "_LIBC", None), \
             patch("sys.stderr.write") as write:
            malloc_trim_mod.maybe_trim("provider")
        self.assertEqual(self._last_log(write)["skip_reason"], "libc_unavailable")

    def test_rss_unavailable_is_noop(self) -> None:
        with patch.object(malloc_trim_mod, "_LIBC", self._fake_libc()) as libc, \
             patch.object(malloc_trim_mod, "mem_rss_mb", return_value=None), \
             patch("sys.stderr.write") as write:
            malloc_trim_mod.maybe_trim("provider")
        libc.malloc_trim.assert_not_called()
        self.assertEqual(self._last_log(write)["skip_reason"], "rss_unavailable")

    def test_malloc_trim_call_raising_is_caught(self) -> None:
        libc = self._fake_libc()
        libc.malloc_trim.side_effect = OSError("boom")
        with patch.object(malloc_trim_mod, "_LIBC", libc), \
             patch.object(malloc_trim_mod, "mem_rss_mb", return_value=1500.0), \
             patch("sys.stderr.write") as write:
            malloc_trim_mod.maybe_trim("provider")  # must not raise
        self.assertEqual(self._last_log(write)["skip_reason"], "trim_call_failed")

    def test_emit_itself_never_raises(self) -> None:
        with patch("sys.stderr.write", side_effect=OSError("closed")):
            malloc_trim_mod._emit({"event": "malloc_trim"})  # must not raise

    # -- threshold / cooldown gating ------------------------------------

    def test_below_threshold_skips_silently(self) -> None:
        with patch.object(malloc_trim_mod, "_LIBC", self._fake_libc()) as libc, \
             patch.object(malloc_trim_mod, "mem_rss_mb", return_value=999.0), \
             patch("sys.stderr.write") as write:
            malloc_trim_mod.maybe_trim("owner")
        libc.malloc_trim.assert_not_called()
        # Below-threshold is the routine outcome on nearly every admitted
        # cold build -- must not log (that's the noise this hook must avoid).
        write.assert_not_called()

    def test_at_or_above_threshold_runs_once_then_cools_down(self) -> None:
        libc = self._fake_libc()
        with patch.object(malloc_trim_mod, "_LIBC", libc), \
             patch.object(malloc_trim_mod, "mem_rss_mb", side_effect=[1500.0, 1200.0]), \
             patch("sys.stderr.write") as write:
            malloc_trim_mod.maybe_trim("entity")
        libc.malloc_trim.assert_called_once_with(0)
        log = self._last_log(write)
        self.assertTrue(log["ran"])
        self.assertEqual(log["route_family"], "entity")
        self.assertEqual(log["rss_before_mb"], 1500.0)
        self.assertEqual(log["rss_after_mb"], 1200.0)
        self.assertEqual(log["reclaimed_mb"], 300.0)
        self.assertIn("trim_duration_ms", log)

        # Immediately eligible again (RSS still over threshold) but within
        # the cooldown window -- must skip, not trim a second time, and must
        # not log (cooldown skips are routine once trimming is active).
        with patch.object(malloc_trim_mod, "mem_rss_mb", return_value=1500.0), \
             patch("sys.stderr.write") as write2:
            malloc_trim_mod.maybe_trim("entity")
        libc.malloc_trim.assert_called_once()  # still just the one call
        write2.assert_not_called()

    def test_cooldown_expires_and_allows_next_trim(self) -> None:
        libc = self._fake_libc()
        with patch.object(malloc_trim_mod, "_LIBC", libc), \
             patch.dict("os.environ", {"PBJ_MALLOC_TRIM_MIN_INTERVAL_S": "0"}), \
             patch.object(malloc_trim_mod, "mem_rss_mb", return_value=1500.0):
            malloc_trim_mod.maybe_trim("provider")
            malloc_trim_mod.maybe_trim("provider")
        self.assertEqual(libc.malloc_trim.call_count, 2)

    # -- thread safety ----------------------------------------------------

    def test_concurrent_calls_trim_at_most_once(self) -> None:
        """Two threads crossing the threshold at once must not both trim --
        the non-blocking lock makes the loser skip, not queue."""
        libc = self._fake_libc()
        release = threading.Event()

        def slow_trim(_size):
            release.wait(2)
            return 1

        libc.malloc_trim.side_effect = slow_trim
        with patch.object(malloc_trim_mod, "_LIBC", libc), \
             patch.object(malloc_trim_mod, "mem_rss_mb", return_value=1500.0), \
             patch("sys.stderr.write") as write:
            with ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(malloc_trim_mod.maybe_trim, "provider")
                time.sleep(0.05)  # let f1 acquire the lock first
                f2 = pool.submit(malloc_trim_mod.maybe_trim, "owner")
                time.sleep(0.05)
                release.set()
                f1.result(timeout=2)
                f2.result(timeout=2)
        libc.malloc_trim.assert_called_once()
        # The losing thread's contention is unusual/interesting -- unlike
        # routine below-threshold/cooldown skips, it must still be logged.
        logged = [json.loads(c.args[0][len("[MALLOC_TRIM] "):]) for c in write.call_args_list]
        skip_reasons = {entry.get("skip_reason") for entry in logged if not entry.get("ran")}
        self.assertIn("trim_in_progress", skip_reasons)


class MallocTrimWiringTests(unittest.TestCase):
    """Confirms the three app.py call sites fire only where intended:
    after a successful admitted cold build, never on a cache hit, an
    admission rejection, or an exception."""

    PAC = "1234567890"

    def setUp(self) -> None:
        import app as app_mod
        import canonical_page_routes
        import ownership.beta_gate as beta_gate
        import ownership.owner_indexability as owner_indexability
        import ownership.owner_profile as owner_profile

        self.app_mod = app_mod
        self.canonical_page_routes = canonical_page_routes
        self.beta_gate = beta_gate
        self.owner_indexability = owner_indexability
        self.owner_profile = owner_profile

        app_mod.clear_provider_page_cache()
        app_mod.clear_entity_page_cache()
        with app_mod._owner_profile_html_cache_lock:
            app_mod._owner_profile_html_cache.clear()

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.trim = self.stack.enter_context(patch.object(app_mod, "_maybe_malloc_trim"))
        self.stack.enter_context(patch.object(app_mod, "_log_mem"))
        self.stack.enter_context(
            patch.object(app_mod, "_ensure_pandas_after_expensive_admission", return_value=True)
        )
        self.stack.enter_context(
            patch.object(owner_indexability, "load_owner_indexability_cache", return_value={})
        )
        self.gate = threading.BoundedSemaphore(1)
        self.stack.enter_context(patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", self.gate))

    def tearDown(self) -> None:
        self.app_mod.clear_provider_page_cache()
        self.app_mod.clear_entity_page_cache()
        with self.app_mod._owner_profile_html_cache_lock:
            self.app_mod._owner_profile_html_cache.clear()

    def _provider(self, ccn: str):
        with self.app_mod.app.test_request_context(
            f"/provider/{ccn}/test-facility", headers={"User-Agent": "Mozilla/5.0"}
        ):
            return self.app_mod._provider_page_impl(ccn)

    def _entity(self, entity_id: int):
        with self.app_mod.app.test_request_context(
            f"/entity/{entity_id}/test-entity", headers={"User-Agent": "Mozilla/5.0"}
        ):
            return self.app_mod._entity_page_impl(entity_id)

    def _owner(self):
        with self.app_mod.app.test_request_context(
            f"/owners/{self.PAC}/test-owner", headers={"User-Agent": "Mozilla/5.0"}
        ):
            return self.app_mod.cms_owner_profile_page(self.PAC, requested_slug="test-owner")

    def _patch_provider(self, *, load_side_effect=None):
        facility_df = SimpleNamespace(empty=False)
        self.stack.enter_context(
            patch.object(
                self.canonical_page_routes, "get_facility_name_from_search_index", return_value="Test Facility"
            )
        )
        self.stack.enter_context(patch.object(self.app_mod, "_provider_page_cache_enabled", return_value=True))
        self.stack.enter_context(patch.object(self.app_mod, "_facility_quarterly_csv_path", return_value="facility.csv"))
        self.stack.enter_context(patch.object(self.app_mod, "_ensure_provider_indexes_hydrated"))
        self.stack.enter_context(
            patch.object(
                self.app_mod,
                "load_facility_quarterly_for_provider",
                side_effect=load_side_effect,
                return_value=None if load_side_effect else facility_df,
            )
        )
        self.stack.enter_context(
            patch.object(
                self.app_mod, "_provider_info_row_for_ccn", return_value={"provider_name": "Test Facility", "state": "NY"}
            )
        )
        self.stack.enter_context(
            patch.object(
                self.app_mod,
                "generate_provider_page_html",
                return_value='<html><div class="pbj-details-ownership"></div>provider</html>',
            )
        )
        self.stack.enter_context(patch.object(self.app_mod, "_enforce_provider_page_html_budget"))
        self.stack.enter_context(
            patch.object(self.app_mod, "_provider_crawler_cold_rate_limit_exceeded", return_value=None)
        )
        self.stack.enter_context(
            patch.object(self.app_mod, "_provider_cold_burst_rate_limit_exceeded", return_value=None)
        )

    def _patch_entity(self, *, load_side_effect=None):
        self.stack.enter_context(
            patch.object(
                self.app_mod,
                "load_entity_facilities",
                side_effect=load_side_effect,
                return_value=("Test Entity", [{"ccn": "100001", "name": "Facility"}]),
            )
        )
        self.stack.enter_context(patch.object(self.app_mod, "get_entity_name_from_search_index", return_value="Test Entity"))
        self.stack.enter_context(patch.object(self.app_mod, "load_chain_performance", return_value={}))
        self.stack.enter_context(
            patch.object(self.app_mod, "generate_entity_page_html", return_value="<html>entity</html>")
        )

    def _patch_owner(self, *, load_side_effect=None):
        self.stack.enter_context(
            patch.object(
                self.owner_indexability,
                "load_owner_indexability_cache",
                return_value={self.PAC: {"classification": "index", "owner_name": "Test Owner"}},
            )
        )
        profile = {
            "associate_id": self.PAC,
            "display_name": "Test Owner",
            "states": ["NY"],
            "facilities": [{"state": "NY"}],
        }
        self.stack.enter_context(
            patch.object(
                self.owner_profile,
                "load_owner_profile_resolved",
                side_effect=load_side_effect,
                return_value=None if load_side_effect else profile,
            )
        )
        self.stack.enter_context(
            patch.object(self.owner_profile, "owner_profile_canonical_path", return_value=f"/owners/{self.PAC}/test-owner")
        )
        self.stack.enter_context(patch.object(self.beta_gate, "profile_is_visible", return_value=True))
        self.stack.enter_context(patch.object(self.beta_gate, "profile_has_public_state", return_value=True))
        self.stack.enter_context(
            patch.object(self.owner_indexability, "classification_for_pac", return_value=("index", "", {}))
        )
        self.stack.enter_context(patch.object(self.owner_indexability, "owner_robots_meta", return_value=None))
        self.stack.enter_context(
            patch.object(self.app_mod, "generate_owner_profile_html", return_value="<html>owner</html>")
        )

    # -- fires exactly once on success -----------------------------------

    def test_fires_once_on_successful_provider_cold_render(self) -> None:
        self._patch_provider()
        result = self._provider("200001")
        self.assertEqual(result[1], 200)
        self.trim.assert_called_once_with("provider")

    def test_fires_once_on_successful_entity_cold_render(self) -> None:
        self._patch_entity()
        result = self._entity(9101)
        self.assertEqual(result[1], 200)
        self.trim.assert_called_once_with("entity")

    def test_fires_once_on_successful_owner_cold_render(self) -> None:
        self._patch_owner()
        result = self._owner()
        self.assertEqual(result.status_code, 200)
        self.trim.assert_called_once_with("owner")

    # -- never fires on a cache hit ---------------------------------------

    def test_does_not_fire_on_provider_cache_hit(self) -> None:
        self._patch_provider()
        self._provider("200002")
        self.trim.assert_called_once()
        self.trim.reset_mock()
        self._provider("200002")  # served from _PROVIDER_PAGE_CACHE
        self.trim.assert_not_called()

    def test_does_not_fire_on_entity_cache_hit(self) -> None:
        self.app_mod._entity_page_cache_put(9102, "<html>cached</html>", time.time())
        result = self._entity(9102)
        self.assertEqual(result[1], 200)
        self.trim.assert_not_called()

    def test_does_not_fire_on_owner_cache_hit(self) -> None:
        self.app_mod._owner_profile_html_cache_put(self.PAC, "<html>cached</html>", "index, follow")
        result = self._owner()
        self.assertEqual(result.status_code, 200)
        self.trim.assert_not_called()

    # -- never fires when admission is rejected ----------------------------

    def test_does_not_fire_when_provider_admission_rejected(self) -> None:
        self._patch_provider()
        self.assertTrue(self.gate.acquire(blocking=False))
        try:
            result = self._provider("200003")
        finally:
            self.gate.release()
        self.assertEqual(result.status_code, 503)
        self.trim.assert_not_called()

    def test_does_not_fire_when_entity_admission_rejected(self) -> None:
        self._patch_entity()
        self.assertTrue(self.gate.acquire(blocking=False))
        try:
            result = self._entity(9103)
        finally:
            self.gate.release()
        self.assertEqual(result.status_code, 503)
        self.trim.assert_not_called()

    def test_does_not_fire_when_owner_admission_rejected(self) -> None:
        self._patch_owner()
        self.assertTrue(self.gate.acquire(blocking=False))
        try:
            result = self._owner()
        finally:
            self.gate.release()
        self.assertEqual(result.status_code, 503)
        self.trim.assert_not_called()

    # -- never fires when the build raises ---------------------------------

    def test_does_not_fire_when_provider_build_raises(self) -> None:
        self._patch_provider(load_side_effect=RuntimeError("boom"))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            self._provider("200004")
        self.trim.assert_not_called()
        self.assertTrue(self.gate.acquire(blocking=False))  # gate was released despite the exception
        self.gate.release()

    def test_does_not_fire_when_entity_build_raises(self) -> None:
        self._patch_entity(load_side_effect=RuntimeError("boom"))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            self._entity(9104)
        self.trim.assert_not_called()

    def test_does_not_fire_when_owner_build_raises(self) -> None:
        self._patch_owner(load_side_effect=RuntimeError("boom"))
        result = self._owner()  # owner route catches load errors and returns 503, does not raise
        self.assertEqual(result[1], 503)
        self.trim.assert_not_called()


if __name__ == "__main__":
    unittest.main()
