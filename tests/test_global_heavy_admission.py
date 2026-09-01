from __future__ import annotations

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import app as app_mod
import canonical_page_routes
import ownership.beta_gate as beta_gate
import ownership.owner_indexability as owner_indexability
import ownership.owner_profile as owner_profile


def _status(result) -> int:
    return int(result.status_code if hasattr(result, "status_code") else result[1])


class GlobalHeavyAdmissionTests(unittest.TestCase):
    PAC = "1234567890"

    def setUp(self) -> None:
        app_mod.clear_provider_page_cache()
        app_mod.clear_entity_page_cache()
        with app_mod._owner_profile_html_cache_lock:
            app_mod._owner_profile_html_cache.clear()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(app_mod, "_log_mem"))
        self.stack.enter_context(
            patch.object(app_mod, "_ensure_pandas_after_expensive_admission", return_value=True)
        )
        self.stack.enter_context(
            patch.object(owner_indexability, "load_owner_indexability_cache", return_value={})
        )

    def tearDown(self) -> None:
        app_mod.clear_provider_page_cache()
        app_mod.clear_entity_page_cache()
        with app_mod._owner_profile_html_cache_lock:
            app_mod._owner_profile_html_cache.clear()

    def _provider(self, ccn: str):
        with app_mod.app.test_request_context(
            f"/provider/{ccn}/test-facility", headers={"User-Agent": "Mozilla/5.0"}
        ):
            return app_mod._provider_page_impl(ccn)

    def _entity(self, entity_id: int, user_agent: str = "Mozilla/5.0"):
        with app_mod.app.test_request_context(
            f"/entity/{entity_id}/test-entity", headers={"User-Agent": user_agent}
        ):
            return app_mod._entity_page_impl(entity_id)

    def _owner(self, user_agent: str = "Mozilla/5.0"):
        with app_mod.app.test_request_context(
            f"/owners/{self.PAC}/test-owner", headers={"User-Agent": user_agent}
        ):
            return app_mod.cms_owner_profile_page(self.PAC, requested_slug="test-owner")

    def _patch_provider(self, *, load_side_effect=None):
        facility_df = SimpleNamespace(empty=False)
        self.stack.enter_context(
            patch.object(
                canonical_page_routes,
                "get_facility_name_from_search_index",
                return_value="Test Facility",
            )
        )
        self.stack.enter_context(patch.object(app_mod, "_provider_page_cache_enabled", return_value=True))
        self.stack.enter_context(patch.object(app_mod, "_facility_quarterly_csv_path", return_value="facility.csv"))
        self.stack.enter_context(patch.object(app_mod, "_ensure_provider_indexes_hydrated"))
        load = self.stack.enter_context(
            patch.object(
                app_mod,
                "load_facility_quarterly_for_provider",
                side_effect=load_side_effect,
                return_value=None if load_side_effect else facility_df,
            )
        )
        self.stack.enter_context(
            patch.object(
                app_mod,
                "_provider_info_row_for_ccn",
                return_value={"provider_name": "Test Facility", "state": "NY"},
            )
        )
        render = self.stack.enter_context(
            patch.object(app_mod, "generate_provider_page_html", return_value="<html>provider</html>")
        )
        self.stack.enter_context(patch.object(app_mod, "_enforce_provider_page_html_budget"))
        self.stack.enter_context(
            patch.object(app_mod, "_provider_crawler_cold_rate_limit_exceeded", return_value=None)
        )
        self.stack.enter_context(
            patch.object(app_mod, "_provider_cold_burst_rate_limit_exceeded", return_value=None)
        )
        return load, render

    def _patch_entity(self, *, load_side_effect=None):
        load = self.stack.enter_context(
            patch.object(
                app_mod,
                "load_entity_facilities",
                side_effect=load_side_effect,
                return_value=("Test Entity", [{"ccn": "100001", "name": "Facility"}]),
            )
        )
        self.stack.enter_context(patch.object(app_mod, "get_entity_name_from_search_index", return_value="Test Entity"))
        self.stack.enter_context(patch.object(app_mod, "load_chain_performance", return_value={}))
        render = self.stack.enter_context(
            patch.object(app_mod, "generate_entity_page_html", return_value="<html>entity</html>")
        )
        return load, render

    def _patch_owner(self, *, load_side_effect=None):
        self.stack.enter_context(
            patch.object(
                owner_indexability,
                "load_owner_indexability_cache",
                return_value={
                    self.PAC: {"classification": "index", "owner_name": "Test Owner"}
                },
            )
        )
        profile = {
            "associate_id": self.PAC,
            "display_name": "Test Owner",
            "states": ["NY"],
            "facilities": [{"state": "NY"}],
        }
        load = self.stack.enter_context(
            patch.object(
                owner_profile,
                "load_owner_profile_resolved",
                side_effect=load_side_effect,
                return_value=None if load_side_effect else profile,
            )
        )
        self.stack.enter_context(
            patch.object(
                owner_profile,
                "owner_profile_canonical_path",
                return_value=f"/owners/{self.PAC}/test-owner",
            )
        )
        self.stack.enter_context(patch.object(beta_gate, "profile_is_visible", return_value=True))
        self.stack.enter_context(patch.object(beta_gate, "profile_has_public_state", return_value=True))
        self.stack.enter_context(
            patch.object(owner_indexability, "classification_for_pac", return_value=("index", "", {}))
        )
        self.stack.enter_context(patch.object(owner_indexability, "owner_robots_meta", return_value=None))
        render = self.stack.enter_context(
            patch.object(app_mod, "generate_owner_profile_html", return_value="<html>owner</html>")
        )
        return load, render

    def test_mixed_routes_share_one_budget_and_overflow_is_cheap(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocking_provider(_ccn):
            entered.set()
            if not release.wait(5):
                raise AssertionError("provider release not signaled")
            return SimpleNamespace(empty=False)

        self._patch_provider(load_side_effect=blocking_provider)
        entity_load, entity_render = self._patch_entity()
        owner_load, owner_render = self._patch_owner()
        gate = threading.BoundedSemaphore(1)
        with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", gate):
            with ThreadPoolExecutor(max_workers=1) as pool:
                provider_future = pool.submit(self._provider, "200001")
                self.assertTrue(entered.wait(5))
                started = time.perf_counter()
                entity_result = self._entity(9001)
                owner_result = self._owner()
                rejected_ms = (time.perf_counter() - started) * 1000
                release.set()
                provider_result = provider_future.result(timeout=5)

        self.assertEqual(_status(provider_result), 200)
        self.assertEqual(_status(entity_result), 503)
        self.assertEqual(_status(owner_result), 503)
        self.assertLess(rejected_ms, 100)
        entity_load.assert_not_called()
        entity_render.assert_not_called()
        owner_load.assert_not_called()
        owner_render.assert_not_called()

    def test_provider_entity_owner_never_exceed_configured_budget(self) -> None:
        capacity = 2
        start = threading.Barrier(3)
        filled = threading.Event()
        release = threading.Event()
        active_lock = threading.Lock()
        active = 0
        max_active = 0
        all_attempted = threading.Event()

        class CountingGate:
            def __init__(self):
                self._gate = threading.BoundedSemaphore(capacity)
                self._lock = threading.Lock()
                self._attempts = 0

            def acquire(self, blocking=False):
                with self._lock:
                    self._attempts += 1
                    if self._attempts == 3:
                        all_attempted.set()
                return self._gate.acquire(blocking=blocking)

            def release(self):
                self._gate.release()

        def blocking_loader(value):
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
                if active == capacity:
                    filled.set()
            try:
                if not release.wait(5):
                    raise AssertionError("mixed loaders were not released")
            finally:
                with active_lock:
                    active -= 1
            if isinstance(value, int):
                return "Test Entity", [{"ccn": "100001", "name": "Facility"}]
            if str(value).isdigit() and len(str(value)) == 10:
                return {
                    "associate_id": self.PAC,
                    "display_name": "Test Owner",
                    "states": ["NY"],
                    "facilities": [{"state": "NY"}],
                }
            return SimpleNamespace(empty=False)

        self._patch_provider(load_side_effect=blocking_loader)
        self._patch_entity(load_side_effect=blocking_loader)
        self._patch_owner(load_side_effect=blocking_loader)

        def invoke(kind):
            start.wait(timeout=5)
            if kind == "provider":
                return _status(self._provider("200002"))
            if kind == "entity":
                return _status(self._entity(9002))
            return _status(self._owner())

        with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", CountingGate()):
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = [pool.submit(invoke, kind) for kind in ("provider", "entity", "owner")]
                self.assertTrue(filled.wait(5))
                self.assertTrue(all_attempted.wait(5))
                release.set()
                statuses = [future.result(timeout=5) for future in futures]

        self.assertEqual(max_active, capacity)
        self.assertEqual(statuses.count(200), capacity)
        self.assertEqual(statuses.count(503), 1)

    def test_cached_entity_and_owner_bypass_occupied_gate(self) -> None:
        app_mod._entity_page_cache_put(9003, "<html>cached entity</html>", time.time())
        app_mod._owner_profile_html_cache_put(self.PAC, "<html>cached owner</html>", "noindex, follow")
        self._patch_owner()
        gate = threading.BoundedSemaphore(1)
        self.assertTrue(gate.acquire(blocking=False))
        try:
            with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", gate):
                entity_result = self._entity(9003)
                owner_result = self._owner()
        finally:
            gate.release()
        self.assertEqual(_status(entity_result), 200)
        self.assertEqual(entity_result[2]["X-PBJ-Entity-Cache"], "HIT")
        self.assertEqual(_status(owner_result), 200)
        self.assertEqual(owner_result.headers["X-Robots-Tag"], "noindex, follow")

    def test_entity_and_owner_recheck_cache_after_admission(self) -> None:
        entity_cached = ("<html>race entity</html>", 200, {"X-PBJ-Entity-Cache": "HIT"})
        owner_cached = ("<html>race owner</html>", None)
        with patch.object(
            app_mod, "_entity_page_cached_response", side_effect=(None, entity_cached)
        ) as entity_get:
            entity_result = self._entity(9004)
        with patch.object(
            app_mod, "_owner_profile_html_cache_get", side_effect=(None, owner_cached)
        ) as owner_get:
            owner_result = self._owner()
        self.assertEqual(entity_result, entity_cached)
        self.assertEqual(entity_get.call_count, 2)
        self.assertEqual(_status(owner_result), 200)
        self.assertEqual(owner_get.call_count, 2)

    def test_slot_released_after_entity_and_owner_exceptions(self) -> None:
        entity_load, _ = self._patch_entity()
        entity_load.side_effect = RuntimeError("entity failure")
        with self.assertRaisesRegex(RuntimeError, "entity failure"):
            self._entity(9005)
        entity_load.side_effect = None
        self.assertEqual(_status(self._entity(9006)), 200)

        owner_load, _ = self._patch_owner()
        owner_load.side_effect = KeyboardInterrupt("owner failure")
        with self.assertRaisesRegex(KeyboardInterrupt, "owner failure"):
            self._owner()
        owner_load.side_effect = None
        self.assertEqual(_status(self._owner()), 200)

    def test_slow_provider_with_entity_owner_overflow_keeps_health_immediate(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocking_provider(_ccn):
            entered.set()
            if not release.wait(5):
                raise AssertionError("provider release not signaled")
            return SimpleNamespace(empty=False)

        self._patch_provider(load_side_effect=blocking_provider)
        self._patch_entity()
        self._patch_owner()
        latencies = []
        with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", threading.BoundedSemaphore(1)):
            with ThreadPoolExecutor(max_workers=3) as pool:
                provider_future = pool.submit(self._provider, "200003")
                self.assertTrue(entered.wait(5))
                entity_future = pool.submit(self._entity, 9007)
                owner_future = pool.submit(self._owner)
                client = app_mod.app.test_client()
                for _ in range(50):
                    started = time.perf_counter()
                    response = client.get("/healthz")
                    latencies.append((time.perf_counter() - started) * 1000)
                    self.assertEqual(response.status_code, 200)
                release.set()
                self.assertEqual(_status(provider_future.result(timeout=5)), 200)
                self.assertEqual(_status(entity_future.result(timeout=5)), 503)
                self.assertEqual(_status(owner_future.result(timeout=5)), 503)
        ordered = sorted(latencies)
        p95 = ordered[int(0.95 * (len(ordered) - 1))]
        self.assertLess(p95, 250)
        self.assertLess(max(latencies), 1000)

    def test_rejection_does_not_initialize_pandas_or_enter_loaders(self) -> None:
        entity_load, _ = self._patch_entity()
        owner_load, _ = self._patch_owner()
        pandas_init = self.stack.enter_context(
            patch.object(app_mod, "_ensure_pandas_after_expensive_admission")
        )
        gate = threading.BoundedSemaphore(1)
        self.assertTrue(gate.acquire(blocking=False))
        try:
            with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", gate):
                entity_bot = self._entity(9008, "Applebot/0.3")
                owner_human = self._owner()
        finally:
            gate.release()
        self.assertEqual(_status(entity_bot), 429)
        self.assertEqual(_status(owner_human), 503)
        pandas_init.assert_not_called()
        entity_load.assert_not_called()
        owner_load.assert_not_called()

    def test_provider_canonical_fallback_is_also_admission_protected(self) -> None:
        pandas_init = self.stack.enter_context(
            patch.object(app_mod, "_ensure_pandas_after_expensive_admission")
        )
        provider_info = self.stack.enter_context(
            patch.object(app_mod, "_provider_info_row_for_ccn")
        )
        self.stack.enter_context(
            patch.object(canonical_page_routes, "get_facility_name_from_search_index", return_value="")
        )
        gate = threading.BoundedSemaphore(1)
        self.assertTrue(gate.acquire(blocking=False))
        try:
            with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", gate):
                response = app_mod.app.test_client().get(
                    "/provider/999999/unknown-facility",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
        finally:
            gate.release()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        pandas_init.assert_not_called()
        provider_info.assert_not_called()

    def test_before_request_defers_pandas_for_all_admitted_page_paths(self) -> None:
        get_pd = self.stack.enter_context(patch.object(app_mod, "get_pd"))
        for path in (
            "/provider/100001/test-facility",
            "/entity/9009/test-entity",
            f"/owners/{self.PAC}/test-owner",
        ):
            with self.subTest(path=path), app_mod.app.test_request_context(path):
                self.assertIsNone(app_mod._ensure_pandas())
        get_pd.assert_not_called()

    def test_light_owner_identity_and_canonical_helpers_match_existing_behavior(self) -> None:
        for raw in (self.PAC, "234567890", "O1234567890", "x12345678901"):
            self.assertEqual(
                app_mod._normalize_owner_associate_id_light(raw),
                owner_profile.normalize_associate_id(raw),
            )
        for name in ("Test Owner", "ACME, L.L.C.", "Élite Health"):
            self.assertEqual(
                app_mod._owner_profile_url_from_index(self.PAC, name),
                owner_profile.associate_profile_url(self.PAC, name),
            )


class EntityPageCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        app_mod.clear_entity_page_cache()

    def tearDown(self) -> None:
        app_mod.clear_entity_page_cache()

    def test_ttl_headers_output_and_byte_budget(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "PBJ_ENTITY_PAGE_CACHE_TTL": "10",
                "PBJ_ENTITY_PAGE_CACHE_MAX": "2",
                "PBJ_ENTITY_PAGE_HTML_BUDGET_MB": "0.00002",
            },
        ):
            self.assertTrue(app_mod._entity_page_cache_put(1, "one", 100.0))
            self.assertTrue(app_mod._entity_page_cache_put(2, "two", 101.0))
            hit = app_mod._entity_page_cached_response(1, 105.0)
            self.assertEqual(hit[0], "one")
            self.assertEqual(hit[2]["X-PBJ-Entity-Cache"], "HIT")
            self.assertIn("public", hit[2]["Cache-Control"])
            self.assertIsNone(app_mod._entity_page_cached_response(1, 111.0))
            self.assertFalse(app_mod._entity_page_cache_put(3, "x" * 100, 112.0))
            self.assertLessEqual(
                app_mod._ENTITY_PAGE_HTML_CACHE_BYTES,
                app_mod._entity_page_cache_byte_budget(),
            )

    def test_entry_bound_evicts_lru(self) -> None:
        with patch.dict("os.environ", {"PBJ_ENTITY_PAGE_CACHE_MAX": "2"}):
            app_mod._entity_page_cache_put(1, "one", 1.0)
            app_mod._entity_page_cache_put(2, "two", 2.0)
            self.assertIsNotNone(app_mod._entity_page_cached_response(1, 2.5))
            app_mod._entity_page_cache_put(3, "three", 3.0)
            self.assertIsNone(app_mod._entity_page_cached_response(2, 3.5))
            self.assertLessEqual(len(app_mod._ENTITY_PAGE_HTML_CACHE), 2)


if __name__ == "__main__":
    unittest.main()
