from __future__ import annotations

import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app as app_mod
import canonical_page_routes


ROOT = Path(__file__).resolve().parents[1]


def _status(result) -> int:
    if hasattr(result, "status_code"):
        return int(result.status_code)
    return int(result[1])


class ProviderColdAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        app_mod.clear_provider_page_cache()
        self.gate_patch = patch.object(
            app_mod,
            "_EXPENSIVE_BUILD_GATE",
            threading.BoundedSemaphore(1),
        )
        self.gate_patch.start()

    def tearDown(self) -> None:
        self.gate_patch.stop()
        app_mod.clear_provider_page_cache()

    @contextmanager
    def cold_path(self, *, load_side_effect=None, render_side_effect=None):
        facility_df = SimpleNamespace(empty=False)
        with ExitStack() as stack:
            stack.enter_context(patch.object(app_mod, "_log_mem"))
            stack.enter_context(patch.object(app_mod, "_provider_page_cache_enabled", return_value=True))
            stack.enter_context(
                patch.object(
                    canonical_page_routes,
                    "get_facility_name_from_search_index",
                    return_value="Test Facility",
                )
            )
            stack.enter_context(patch.object(app_mod, "_facility_quarterly_csv_path", return_value="facility.csv"))
            ensure_indexes = stack.enter_context(patch.object(app_mod, "_ensure_provider_indexes_hydrated"))
            load_provider = stack.enter_context(
                patch.object(
                    app_mod,
                    "load_facility_quarterly_for_provider",
                    side_effect=load_side_effect,
                    return_value=None if load_side_effect else facility_df,
                )
            )
            provider_info = stack.enter_context(
                patch.object(
                    app_mod,
                    "_provider_info_row_for_ccn",
                    return_value={"provider_name": "Test Facility", "state": "NY"},
                )
            )
            render = stack.enter_context(
                patch.object(
                    app_mod,
                    "generate_provider_page_html",
                    side_effect=render_side_effect,
                    return_value="<html>provider</html>" if render_side_effect is None else None,
                )
            )
            stack.enter_context(patch.object(app_mod, "_enforce_provider_page_html_budget"))
            stack.enter_context(patch.object(app_mod, "_provider_crawler_cold_rate_limit_exceeded", return_value=None))
            stack.enter_context(patch.object(app_mod, "_provider_cold_burst_rate_limit_exceeded", return_value=None))
            yield {
                "ensure_indexes": ensure_indexes,
                "load_provider": load_provider,
                "provider_info": provider_info,
                "render": render,
            }

    def request(self, ccn: str, user_agent: str = "Mozilla/5.0"):
        with app_mod.app.test_request_context(
            f"/provider/{ccn}/test-facility",
            headers={"User-Agent": user_agent},
        ):
            return app_mod._provider_page_impl(ccn)

    def test_render_default_is_one_slot_and_env_can_override(self) -> None:
        with patch.dict(os.environ, {"RENDER": "1", "PBJ_GLOBAL_HEAVY_SLOTS": "", "PBJ_PROVIDER_COLD_SLOTS": ""}):
            self.assertEqual(app_mod._expensive_build_slot_count(), 1)
        with patch.dict(os.environ, {"RENDER": "1", "PBJ_PROVIDER_COLD_SLOTS": "3"}):
            self.assertEqual(app_mod._expensive_build_slot_count(), 3)
        with patch.dict(os.environ, {"RENDER": "1", "PBJ_GLOBAL_HEAVY_SLOTS": "4", "PBJ_PROVIDER_COLD_SLOTS": "3"}):
            self.assertEqual(app_mod._expensive_build_slot_count(), 4)

    def test_other_bots_miss_without_starting_provider_work(self) -> None:
        user_agents = (
            "Mozilla/5.0 (compatible; Applebot/0.3; +http://www.apple.com/go/applebot)",
            "Mozilla/5.0 (compatible; ReflectionBot/1.0)",
            "Mozilla/5.0 (compatible; ShapBot/1.0)",
        )
        with self.cold_path() as calls:
            for i, user_agent in enumerate(user_agents, start=1):
                with self.subTest(user_agent=user_agent):
                    response = self.request(f"10{i:04d}", user_agent)
                    self.assertEqual(response.status_code, 429)
                    self.assertEqual(response.headers["Retry-After"], "3600")
                    self.assertEqual(response.headers["X-PBJ-Provider-Cache"], "MISS")
            calls["ensure_indexes"].assert_not_called()
            calls["load_provider"].assert_not_called()
            calls["provider_info"].assert_not_called()
            calls["render"].assert_not_called()

    def test_cached_bot_page_remains_200(self) -> None:
        ccn = "100010"
        app_mod._PROVIDER_PAGE_CACHE[ccn] = (time.time(), "<html>cached</html>")
        with self.cold_path() as calls, patch.object(app_mod, "_provider_page_cache_hit_ok", return_value=True):
            result = self.request(ccn, "Applebot/0.3")
        self.assertEqual(_status(result), 200)
        self.assertEqual(result[2]["X-PBJ-Provider-Cache"], "HIT")
        calls["ensure_indexes"].assert_not_called()
        calls["load_provider"].assert_not_called()
        calls["render"].assert_not_called()

    def test_human_cold_request_still_renders(self) -> None:
        with self.cold_path() as calls:
            result = self.request("100020")
        self.assertEqual(_status(result), 200)
        self.assertEqual(result[2]["X-PBJ-Provider-Cache"], "MISS")
        calls["ensure_indexes"].assert_called_once()
        calls["load_provider"].assert_called_once_with("100020")
        calls["render"].assert_called_once()

    def test_cache_is_rechecked_after_cold_slot_admission(self) -> None:
        cached = ("<html>won race</html>", 200, {"X-PBJ-Provider-Cache": "HIT"})
        with self.cold_path() as calls, patch.object(
            app_mod,
            "_provider_page_cached_response",
            side_effect=(None, cached),
        ) as cache_lookup:
            result = self.request("100021")
        self.assertEqual(result, cached)
        self.assertEqual(cache_lookup.call_count, 2)
        calls["ensure_indexes"].assert_not_called()
        calls["load_provider"].assert_not_called()
        calls["render"].assert_not_called()

    def test_unique_cold_requests_never_exceed_configured_slots(self) -> None:
        slots = 2
        start = threading.Barrier(8)
        release = threading.Event()
        both_entered = threading.Event()
        active_lock = threading.Lock()
        active = 0
        max_active = 0

        def blocking_load(_ccn):
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
                if active == slots:
                    both_entered.set()
            try:
                if not release.wait(5):
                    raise AssertionError("test did not release blocked cold renders")
                return SimpleNamespace(empty=False)
            finally:
                with active_lock:
                    active -= 1

        def invoke(i: int):
            start.wait(timeout=5)
            result = self.request(f"20{i:04d}")
            retry_after = result.headers.get("Retry-After") if hasattr(result, "headers") else None
            return _status(result), retry_after

        with patch.object(app_mod, "_EXPENSIVE_BUILD_GATE", threading.BoundedSemaphore(slots)):
            with self.cold_path(load_side_effect=blocking_load):
                with ThreadPoolExecutor(max_workers=8) as pool:
                    futures = [pool.submit(invoke, i) for i in range(8)]
                    self.assertTrue(both_entered.wait(5), "configured cold-render slots did not fill")
                    time.sleep(0.1)
                    release.set()
                    results = [future.result(timeout=5) for future in futures]

        self.assertEqual(max_active, slots)
        self.assertEqual(sum(status == 200 for status, _ in results), slots)
        self.assertEqual(sum(status == 503 for status, _ in results), 8 - slots)
        self.assertTrue(all(retry == "3" for status, retry in results if status == 503))

    def test_slot_released_after_error(self) -> None:
        with self.cold_path() as calls:
            calls["ensure_indexes"].side_effect = RuntimeError("index failure")
            with self.assertRaisesRegex(RuntimeError, "index failure"):
                self.request("300001")
            calls["ensure_indexes"].side_effect = None
            result = self.request("300002")
        self.assertEqual(_status(result), 200)

    def test_healthz_is_immediate_while_cold_slot_is_occupied(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def blocking_load(_ccn):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test did not release blocked cold render")
            return SimpleNamespace(empty=False)

        with self.cold_path(load_side_effect=blocking_load):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.request, "400001")
                self.assertTrue(entered.wait(5), "cold render never occupied the gate")
                t0 = time.perf_counter()
                response = app_mod.app.test_client().get("/healthz")
                elapsed = time.perf_counter() - t0
                release.set()
                provider_result = future.result(timeout=5)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True), "ok")
        self.assertLess(elapsed, 1.0)
        self.assertEqual(_status(provider_result), 200)


class DeployIndexGateTests(unittest.TestCase):
    def test_always_run_deploy_gate_ensures_ownership_runtime_index(self) -> None:
        source = (ROOT / "scripts" / "ensure_deploy_csvs.py").read_text(encoding="utf-8")
        self.assertIn("snf_owners_lookup.sqlite", source)
        self.assertIn("build_snf_owners_index.py", source)
        self.assertIn("idx_enrollment_pac", source)
        self.assertIn("idx_owner_pac", source)


if __name__ == "__main__":
    unittest.main()
